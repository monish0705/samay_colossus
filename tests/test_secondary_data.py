"""Real mirror archive integrity and isolated TEST_ONLY wiring/causality checks."""
import hashlib
import json
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest
from app.api_routes import get_clock
from app.config import get_settings
from app.features import features_at
from app.forecasting import examples, fit, predict_rows, relative_inputs
from app.ingestion import SourceManifest, import_csv
from app.main import app
from sqlalchemy.orm import Session
from test_backend import ROOT
from test_forecasting import case

pytest_plugins = ["test_api_integration"]


def archive():
    return sorted((ROOT/"data/raw/idp-history").glob("*/catalog.json"))[-1].parent


def test_real_secondary_archives_have_complete_pages_and_noninvented_grades():
    catalog=json.loads((archive()/"catalog.json").read_text())
    assert sum(x["n"] for x in catalog["series"]) == 5837
    for item in catalog["series"]:
        folder=ROOT/item["folder"]
        retrieval=json.loads((folder/"retrieval.json").read_text())
        manifest=SourceManifest.model_validate_json((folder/"manifest.json").read_text())
        assert manifest.data_kind == "secondary"
        assert hashlib.sha256((folder/"observations.csv").read_bytes()).hexdigest()==manifest.sha256
        rows=[]
        for page in retrieval["pages"]:
            raw=(folder/page["file"]).read_bytes()
            assert hashlib.sha256(raw).hexdigest()==page["sha256"]
            payload=json.loads(raw)
            assert payload["success"] is True
            rows.extend(payload["result"]["records"])
        assert len(rows)==retrieval["records"]==item["n"]
        assert len({r["_id"] for r in rows})==len(rows)
        if item["source"]=="old":
            assert all("grade" not in r for r in rows)
        bad=manifest.model_dump()
        bad["source_url"]="https://example.com/fake.csv"
        with pytest.raises(ValueError,match="Secondary source"):
            SourceManifest.model_validate(bad)
        bad=manifest.model_dump()
        bad["upstream_source_url"]=None
        with pytest.raises(ValueError,match="requires upstream"):
            SourceManifest.model_validate(bad)


def test_secondary_import_is_visible_as_secondary_and_stale_not_invented(api,tmp_path,monkeypatch):
    client,engine=api
    folder=archive()/"copra-old"
    manifest=SourceManifest.model_validate_json((folder/"manifest.json").read_text())
    with Session(engine) as session,session.begin():
        report=import_csv(session,folder/"observations.csv",manifest,tmp_path/"imports",market="Tiptur APMC",commodity="Copra")
    assert report["counts"]["inserted"]==1259
    assert client.get("/api/v1/markets").json()[0]["name"]=="Tiptur APMC"
    scope="market=Tiptur%20APMC&commodity=Copra&variety=copra&grade=unspecified"
    history=client.get("/api/v1/prices/history?"+scope).json()
    assert history["items"][0]["data_kind"]=="secondary"
    assert "India Data Portal" in history["items"][0]["source"]
    status=client.get("/api/v1/data/status").json()
    assert status["official_observations"]==0 and status["secondary_observations"]==1259
    assert status["status"]=="stale"
    monkeypatch.setenv("SAMAY_ENABLE_RESEARCH_FORECASTS","true")
    monkeypatch.setenv("SAMAY_RESEARCH_SERVING_REGISTRY_PATH",str(ROOT/"research-serving-registry.json"))
    get_settings.cache_clear()
    app.dependency_overrides[get_clock]=lambda:datetime(2026,11,5,12,tzinfo=UTC)
    response=client.post("/api/v1/predict",json={"market":"Tiptur APMC","commodity":"Copra","variety":"copra","grade":"unspecified","horizon":3})
    assert response.status_code==503
    assert response.json()["error"]["code"]=="stale_market_data"


def test_real_dated_evaluation_endpoint_and_small_final_set(api,monkeypatch):
    client,_=api
    monkeypatch.setenv("SAMAY_RESEARCH_REGISTRY_PATH",str(ROOT/"research-registry.json"))
    get_settings.cache_clear()
    response=client.get("/api/v1/models/evaluation",params={"market":"Tiptur APMC","commodity":"Copra","variety":"copra","grade":"unspecified","horizon":1})
    assert response.status_code==200,response.text
    output=response.json()
    assert output["research_only"] is True and output["source_kind"]=="secondary"
    assert len(output["points"])==output["final_n"]==39
    assert all(p["origin_date"]>output["validation_end"] and p["target_date"]<=output["test_end"] for p in output["points"])
    assert np.mean([float(p["absolute_error_inr_per_quintal"]) for p in output["points"]])==pytest.approx(output["metrics"]["mae_inr_per_quintal"],abs=.01)
    small=client.get("/api/v1/models/evaluation",params={"market":"Bengaluru APMC","commodity":"Potato","variety":"local","grade":"unspecified","horizon":7}).json()
    assert small["status"]=="insufficient_final_samples" and small["metrics"] is None and small["final_n"]==26


def test_historical_evaluation_rejects_tampered_csv(api,tmp_path,monkeypatch):
    client,_=api
    entries=json.loads((ROOT/"research-registry.json").read_text())
    entry=entries[2].copy()
    source=ROOT/entry["directory"]
    target=tmp_path/"tampered"
    shutil.copytree(source,target)
    (target/"final-predictions-1d.csv").write_text("TEST_ONLY_TAMPERED")
    entry["directory"]=str(target)
    registry=tmp_path/"registry.json"
    registry.write_text(json.dumps([entry]))
    monkeypatch.setenv("SAMAY_RESEARCH_REGISTRY_PATH",str(registry))
    get_settings.cache_clear()
    response=client.get("/api/v1/models/evaluation",params={"market":"Tiptur APMC","commodity":"Copra","variety":"copra","grade":"unspecified","horizon":1})
    assert response.status_code==503


def test_relative_return_features_ignore_targets_and_preserve_units():
    rows,plan=case()
    plan=replace(plan,candidate_suite="relative_v2")
    frame=examples(rows,plan.start,plan.train_end,3,plan.train_end+timedelta(days=1))
    changed=frame.copy()
    changed["target_modal_price_inr_per_quintal"]*=100
    assert relative_inputs(frame).equals(relative_inputs(changed))
    model=fit("ridge_return_10",frame)
    assert np.allclose(predict_rows("ridge_return_10",model,frame),1000)
    assert np.allclose(predict_rows("blend_naive_mean14_25",None,frame),1000)


def test_intraday_research_inputs_never_use_a_later_download():
    from datetime import date

    import pandas as pd
    origin=date(2026,11,5)
    rows=pd.DataFrame([
        {"report_date":date(2026,11,3),"available_at":pd.Timestamp("2026-11-05T01:00:00+05:30"),"price":100.,"batch_id":1,"row_id":1,"file_sha256":"TEST_ONLY"},
        {"report_date":date(2026,11,4),"available_at":pd.Timestamp("2026-11-05T03:00:00+05:30"),"price":200.,"batch_id":2,"row_id":2,"file_sha256":"TEST_ONLY"},
    ])
    early,audit=features_at(rows,origin,1,decision_at=pd.Timestamp("2026-11-05T02:00:00+05:30"))
    late,_=features_at(rows,origin,1,decision_at=pd.Timestamp("2026-11-05T03:00:00+05:30"))
    assert early["lag_1_obs_inr_per_quintal"]==100
    assert late["lag_1_obs_inr_per_quintal"]==200
    assert pd.Timestamp(audit["max_feature_available_at"])<=pd.Timestamp(audit["decision_at"])
