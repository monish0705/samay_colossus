"""Regression coverage for fabricated data, invalid inputs and service divergence."""
import hashlib
import json
import shutil
import sqlite3
from datetime import UTC, datetime

from app.api_routes import get_clock
from app.config import get_settings
from app.ingestion import SourceManifest, import_csv, normalize
from app.main import app
from app.provenance_repair import repair
from sqlalchemy.orm import Session
from test_api_integration import recommendation
from test_backend import ROOT

pytest_plugins = ["test_api_integration"]


def test_prepared_bundle_never_exposes_generated_prices_as_official(tmp_path):
    target = tmp_path / "prepared.db"
    shutil.copyfile(ROOT / "data/prepared/samay.db", target)
    result = repair(target)
    assert result["corrected_observations"] == 0  # Already repaired; repeat is harmless.
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT count(*) FROM mandi_observations WHERE data_kind='official'").fetchone()[0] == 1943
        assert connection.execute("SELECT count(*) FROM mandi_observations WHERE data_kind='official' AND latest_batch_id IN (SELECT id FROM import_batches WHERE filename='karnataka_mandis_multi_crop_2026.csv')").fetchone()[0] == 0
    manifest = json.loads((ROOT / "data/prepared/manifest.json").read_text())
    assert hashlib.sha256(target.read_bytes()).hexdigest() == manifest["database_sha256"]


def test_unsafe_preview_endpoints_are_retired_and_reject_negative_days(api):
    client, _ = api
    assert client.get("/api/v1/storage/nearby?days=-3").status_code == 422
    assert client.get("/api/v1/storage/nearby?days=3").status_code == 410
    assert client.get("/api/v1/predict/multi-factor").status_code == 410
    response = client.post("/api/v1/predict", json={"variety":"nonexistent","grade":"faq","horizon":3})
    assert response.status_code == 503
    assert "prediction_inr_per_quintal" not in response.json()


def test_repair_reclassifies_legacy_batch_without_deleting_authentic_rows(tmp_path):
    target = tmp_path / "legacy.db"
    shutil.copyfile(ROOT / "data/prepared/samay.db", target)
    with sqlite3.connect(target) as connection:
        batch_id, manifest = connection.execute("SELECT id,manifest FROM import_batches WHERE filename='karnataka_mandis_multi_crop_2026.csv'").fetchone()
        original = json.loads(manifest)["original_claims_for_audit_only"]
        connection.execute("UPDATE import_batches SET data_kind='official',manifest=? WHERE id=?",(json.dumps(original),batch_id))
        connection.execute("UPDATE mandi_observations SET data_kind='official' WHERE latest_batch_id=?",(batch_id,))
        before = connection.execute("SELECT count(*) FROM mandi_observations").fetchone()[0]
    assert repair(target)["corrected_observations"] == 7304
    assert repair(target)["corrected_observations"] == 0
    with sqlite3.connect(target) as connection:
        assert connection.execute("SELECT count(*) FROM mandi_observations").fetchone()[0] == before
        assert connection.execute("SELECT count(*) FROM mandi_observations WHERE data_kind='official'").fetchone()[0] == 1943


def test_long_duration_explicit_scenario_obeys_cash_without_promoting_to_advice(api):
    client, _ = api
    body = recommendation()
    body.update(market="Shivamogga Mandi", commodity="Arecanut", variety="rashi edi", grade="faq", today_price_inr_per_quintal="48000", maximum_horizon_days=730, risk_tolerance="balanced")
    body["crop_storage_profile"].update(commodity="Arecanut", maximum_holding_days=730)
    option = body["holding_options"][0]
    option.update(days=60, daily_loss_fractions=["0"]*60, daily_storage_inr_per_quintal=["1"]*60,
        scenario_price_inr_per_quintal="80000", adverse_inr_per_quintal="50000")
    result = client.post("/api/v1/recommend",json=body)
    assert result.status_code == 200, result.text
    output = result.json()["optimization"]
    assert output["recommended_plan"]["holding_days"] == 0
    assert output["best_scenario_only_or_validated_plan"]["holding_days"] == 60
    assert output["best_scenario_only_or_validated_plan"]["recommendation_eligible"] is False
    assert float(output["best_scenario_only_or_validated_plan"]["cash_today_inr"]) >= float(body["required_net_cash_inr"])
    option["adverse_inr_per_quintal"] = "90000"
    assert client.post("/api/v1/recommend",json=body).status_code == 422


def test_real_archived_tomato_saved_research_artifact_and_recommendation_share_service(api,tmp_path,monkeypatch):
    client, engine = api
    # Actual archived government CSVs; never generated training records.
    for year in (2025,2026):
        base = ROOT / f"data/raw/official-history/kolar-tomato-{year}"
        manifest = SourceManifest.model_validate_json(base.with_suffix(".manifest.json").read_text())
        with Session(engine) as session, session.begin():
            import_csv(session,base.with_suffix(".csv"),manifest,tmp_path/"imports")
    monkeypatch.setenv("SAMAY_ENABLE_RESEARCH_FORECASTS","true")
    monkeypatch.setenv("SAMAY_RESEARCH_SERVING_REGISTRY_PATH",str(ROOT/"research-serving-registry.json"))
    get_settings.cache_clear()
    now = datetime(2026,11,5,12,tzinfo=UTC)
    app.dependency_overrides[get_clock] = lambda: now
    predicted = client.post("/api/v1/predict",json={"variety":"tomato","grade":"local","horizon":3})
    assert predicted.status_code == 200,predicted.text
    value = predicted.json()
    assert value["reliability_status"] == "limited evidence"
    assert "retrospective_research_only" in value["flags"]
    for band in value["intervals"]:
        assert float(band["lower_inr_per_quintal"]) <= float(value["prediction_inr_per_quintal"]) <= float(band["upper_inr_per_quintal"])
    status = client.get("/api/v1/models/status").json()
    assert status["models"] == [] and len(status["research_models"]) == len(json.loads((ROOT/"research-serving-registry.json").read_text()))
    body = recommendation()
    body.update(variety="tomato",grade="local",decision_at=now.isoformat())
    response = client.post("/api/v1/recommend",json=body)
    assert response.status_code == 200,response.text
    assert response.json()["predictions"][0]["model_version"] == value["model_version"]
    assert datetime.fromisoformat(response.json()["predictions"][0]["timestamp"]) == now
    assert response.json()["optimization"]["recommended_plan"]["holding_days"] == 0
    assert client.post("/api/v1/predict",json={"variety":"nonexistent","grade":"local","horizon":3}).status_code == 503


def test_non_kolar_scope_has_consistent_district_and_accepts_official_names():
    manifest = SourceManifest(source_label="TEST_ONLY",source_url="https://agmarknet.gov.in/",data_kind="fixture",fetched_at=datetime.now(UTC),price_unit="INR/quintal",unit_evidence="TEST_ONLY")
    row={"state":"Karnataka","district":"Shimoga","market":"Shimoga APMC","commodity":"Arecanut(Betelnut/Supari)","variety":"Rashi","grade":"FAQ","report_date":"01/01/2021","min":"100","modal":"200","max":"300"}
    assert normalize(row,manifest)["district"] == "Shivamogga"
    row["district"] = "Kolar"
    import pytest
    with pytest.raises(ValueError,match="mismatch"):
        normalize(row,manifest)
