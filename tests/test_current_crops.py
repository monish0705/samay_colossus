"""Acquisition guards, chronological folds and real archived-crop inference."""
import hashlib
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pandas as pd
import pytest
from app.api_schemas import PredictRequest
from app.api_services import predict
from app.config import get_settings
from app.forecasting import rolling_folds, select_horizon
from app.models import Commodity, ImportBatch, MandiObservation, Market
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from test_backend import ROOT
from test_forecasting import case

from scripts.collect_ogd_history import discover, validate_page

pytest_plugins = ["test_api_integration"]


def test_ogd_discovers_only_publisher_linked_endpoint(monkeypatch):
    monkeypatch.delenv("SAMAY_OGD_API_KEY", raising=False)
    page = b'field_datafile_url:"https:\\u002F\\u002Fapi.data.gov.in\\u002Fresource\\u002F35985678-0d79-46b4-9ed6-6f13308a1d24?api-key=TEST_ONLY&amp;format=csv"'
    endpoint, key = discover(page)
    assert endpoint.endswith("/35985678-0d79-46b4-9ed6-6f13308a1d24") and key == "TEST_ONLY"
    assert "TEST_ONLY" not in endpoint
    with pytest.raises(ValueError, match="Unexpected"):
        discover(page.replace(b"api.data.gov.in", b"example.com"))


def test_ogd_rejects_incomplete_pages_and_ignored_filters():
    payload = {"status": "ok", "records": [], "total": 4, "offset": "0", "count": 0}
    with pytest.raises(ValueError, match="incomplete"):
        validate_page(payload, "Onion", "APMC Hubballi", 0)
    payload.update(records=[dict.fromkeys(("State", "District", "Market", "Commodity", "Variety", "Grade", "Arrival_Date", "Min_Price", "Max_Price", "Modal_Price"), "TEST_ONLY")], count=1)
    with pytest.raises(ValueError, match="ignored"):
        validate_page(payload, "Onion", "APMC Hubballi", 0)
    with pytest.raises(ValueError, match="changed during"):
        validate_page(payload, "Onion", "APMC Hubballi", 0, expected_total=5)


def test_recent_cv_uses_only_past_training_labels_and_disjoint_validation_targets():
    rows, plan = case()
    plan = replace(plan, candidate_suite="recent_v3")
    for horizon in (1, 3, 7):
        folds = rolling_folds(rows, plan, horizon)
        assert len(folds) == 3
        targets = []
        for train, valid in folds:
            assert len(train) >= 60 and len(valid) >= 14
            assert train.target_date.max() < valid.origin_date.min()
            assert pd.to_datetime(train.label_available_at, utc=True).max() < pd.Timestamp(valid.origin_date.min(), tz="Asia/Kolkata").tz_convert("UTC")
            assert valid.target_date.max() <= plan.train_end.isoformat()
            targets.extend(valid.target_date)
        assert len(set(targets)) == len(targets)
        changed = rows.copy()
        changed.loc[changed.report_date > plan.train_end, "price"] *= 1000
        for (train, valid), (other_train, other_valid) in zip(folds, rolling_folds(changed, plan, horizon), strict=True):
            pd.testing.assert_frame_equal(train, other_train)
            pd.testing.assert_frame_equal(valid, other_valid)


def test_recent_short_span_allows_baselines_and_blocks_learned_models():
    rows, plan = case()
    # A policy below the full learned-model span is sufficient for stateless
    # comparisons, never for claiming a learned estimator was justified.
    plan = replace(plan, candidate_suite="recent_v3", start=plan.train_end-timedelta(days=160), min_train=90, min_train_span_days=90)
    result, _, _ = select_horizon(rows, plan, 1)
    assert result["champion"] is not None
    assert result["learned_model_eligible"] is False
    assert not any(x["candidate"].startswith(("ridge", "hist_gradient", "lightgbm")) for x in result["comparisons"])


def test_verified_history_deduplicates_sources_before_pagination(api):
    client, engine = api
    with Session(engine) as session, session.begin():
        market = Market(name="Tiptur APMC", district="Tumakuru", state="Karnataka", data_source="TEST_ONLY")
        crop = Commodity(name="Copra", data_source="TEST_ONLY")
        session.add_all([market, crop])
        session.flush()
        for kind, day, price in (("secondary", 1, 100), ("official", 2, 110)):
            batch = ImportBatch(filename="TEST_ONLY.csv", archive_path="TEST_ONLY", file_sha256="0"*64,
                source_url="https://www.data.gov.in/", source_label="TEST_ONLY", data_kind=kind,
                fetched_at=datetime(2026, 11, day, tzinfo=UTC), manifest={}, report={})
            session.add(batch)
            session.flush()
            session.add(MandiObservation(market_id=market.id, commodity_id=crop.id, observed_on=datetime(2026, 10, 31).date(),
                variety="other", grade="local", data_kind=kind, latest_batch_id=batch.id,
                min_price_inr_per_quintal=Decimal(price), modal_price_inr_per_quintal=Decimal(price),
                max_price_inr_per_quintal=Decimal(price), data_source="TEST_ONLY"))
    params={"market":"Tiptur APMC", "commodity":"Copra", "variety":"other", "grade":"local", "limit":1}
    response=client.get("/api/v1/prices/history",params=params)
    assert response.status_code == 200, response.text
    result=response.json()
    assert len(result["items"]) == 1 and result["next_offset"] is None
    assert result["items"][0]["data_kind"] == "official"
    assert Decimal(result["items"][0]["modal_price_inr_per_quintal"]) == Decimal(110)
    assert client.get("/api/v1/prices/history",params={**params,"data_kind":"secondary"}).json()["items"][0]["data_kind"] == "secondary"


def test_all_four_current_crops_have_hash_pinned_real_forecasts_and_stale_fallbacks(monkeypatch):
    monkeypatch.setenv("SAMAY_ENABLE_RESEARCH_FORECASTS", "true")
    monkeypatch.setenv("SAMAY_RESEARCH_SERVING_REGISTRY_PATH", str(ROOT/"research-serving-registry.json"))
    monkeypatch.delenv("SAMAY_SERVICE_REGISTRY_PATH", raising=False)
    get_settings.cache_clear()
    from app.research_service import bundles
    current=[(folder,meta) for folder,meta in bundles() if meta["plan"].get("candidate_suite")=="recent_v3" and not meta.get('horizon_evidence_status')]
    assert len(current) == 12
    when=max(datetime.fromisoformat(meta["trained_before"]) for _,meta in current)+timedelta(minutes=1)
    origin=when.astimezone(ZoneInfo("Asia/Kolkata")).date()
    database=ROOT/"data/prepared/samay.db"
    engine=create_engine("sqlite://",creator=lambda:sqlite3.connect(f"file:{database.as_posix()}?mode=ro",uri=True))
    try:
        with Session(engine) as session:
            for folder,meta in current:
                assert hashlib.sha256((folder/"model.pkl").read_bytes()).hexdigest()==meta["model_sha256"]
                request=PredictRequest(**{k:meta[k] for k in ("market","commodity","variety","grade","horizon")})
                result,response=predict(session,request,origin,"TEST_ONLY",when)
                assert response.prediction_inr_per_quintal > 0
                assert result.reliability_status == "limited evidence"
                assert 0 <= result.observation_age_calendar_days <= 7
                assert any("data.gov.in" in s["source_url"] for s in result.data_source["sources"])
                assert all(i.lower_inr_per_quintal <= result.prediction_inr_per_quintal <= i.upper_inr_per_quintal for i in result.intervals)
                from app.api_services import ServiceProblem
                with pytest.raises(ServiceProblem) as stale:
                    predict(session,request,origin+timedelta(days=10),"TEST_ONLY",when+timedelta(days=10))
                assert stale.value.code == "stale_market_data"
    finally:
        engine.dispose()
        get_settings.cache_clear()
