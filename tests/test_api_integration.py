"""Isolated deterministic test data simulates an official schema, never production/live observations."""
import json
from datetime import UTC, date, datetime, timedelta

import pytest
from alembic import command
from alembic.config import Config
from app.api_routes import get_clock
from app.config import get_settings
from app.db import make_engine
from app.features import Plan, load_vintages
from app.forecasting import examples, fit, save_champion
from app.ingestion import SourceManifest, import_csv
from app.main import app
from app.models import RecommendationHistory
from app.prices import get_session
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from test_backend import ROOT


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMAY_DATABASE_URL", f"sqlite:///{(tmp_path / 'api.db').as_posix()}")
    monkeypatch.setenv("SAMAY_ENVIRONMENT", "test")
    monkeypatch.delenv("SAMAY_SERVICE_REGISTRY_PATH", raising=False)
    empty_research = tmp_path / "research-registry.json"
    empty_research.write_text("[]")
    monkeypatch.setenv("SAMAY_RESEARCH_REGISTRY_PATH", str(empty_research))
    get_settings.cache_clear()
    command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
    engine = make_engine(get_settings().database_url)
    def session_dependency():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = session_dependency
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 11, 4, 12, tzinfo=UTC)
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client, engine
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def recommendation():
    payload = json.loads((ROOT / "docs/examples/selling-example.json").read_text())
    option = payload["holding_options"][0]
    option.pop("scenarios")
    option.update(realization_multiplier="1", price_basis_assumption="TEST_ONLY farmer mapping", adverse_inr_per_quintal="100", adverse_assumption="TEST_ONLY adverse stress")
    return payload


def test_empty_real_data_never_uses_demo_and_fallback_is_persisted(api):
    client, engine = api
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/v1/markets").json() == []
    assert client.get("/api/v1/commodities").json() == []
    assert client.get("/api/v1/data/status").json()["status"] == "unavailable"
    assert client.get("/api/v1/models/status").json()["status"] == "no_models_deployed"
    latest = client.get("/api/v1/prices/latest?variety=local&grade=faq")
    assert latest.status_code == 404
    forecast = client.post("/api/v1/predict", json={"variety": "local", "grade": "faq", "horizon": 3})
    assert forecast.status_code == 503
    assert forecast.json()["error"]["code"] == "missing_model"
    response = client.post("/api/v1/recommend", json=recommendation())
    assert response.status_code == 200, response.text
    output = response.json()
    assert output["optimization"]["recommendation_basis"] == "today_only_safe_fallback"
    assert output["optimization"]["recommended_plan"]["cash_today_inr"] == "18700.00"
    assert output["market_data"]["report_date"] is None
    assert output["predictions"] == []
    assert "3d:missing_model" in output["reliability_warnings"]
    assert response.headers["X-Request-ID"] == output["request_id"]
    with Session(engine) as session:
        stored = session.get(RecommendationHistory, output["history_id"])
        assert "assumption" not in json.dumps(stored.outcome)
        assert stored.decision_at.utcoffset() is not None
        assert stored.outcome["cash_today_inr"] == "18700.00"


def deploy_test_model(engine, tmp_path, monkeypatch):
    # Two captured CSV snapshots permit genuine causal example construction:
    # Oct 2–8 predictors see only Oct 1 snapshot; their labels arrive Nov 1.
    # Every file/label is synthetic TEST_ONLY in an isolated temporary database.
    for first, last, captured in [(date(2026, 7, 1), date(2026, 10, 1), "2026-10-01T18:00:00Z"),
                                  (date(2026, 10, 2), date(2026, 11, 1), "2026-11-01T18:00:00Z")]:
        path = tmp_path / f"test-only-{last}.csv"
        lines = ["State,District,Market,Commodity,Variety,Grade,Arrival_Date,Min_Price,Max_Price,Modal_Price"]
        for i in range((last - first).days + 1):
            day = first + timedelta(days=i)
            lines.append(f"Karnataka,Kolar,Kolar,Tomato,Local,FAQ,{day:%d/%m/%Y},900,1200,{1000 + i % 5}")
        path.write_text("\n".join(lines), encoding="utf-8")
        manifest = SourceManifest(source_label="INTEGRATION_TEST_ONLY_NOT_LIVE", source_url="https://data.gov.in/resource/variety-wise-daily-market-prices-data-commodity", data_kind="official",
            fetched_at=captured, price_unit="INR/quintal", unit_evidence="Synthetic test schema only, not government evidence")
        with Session(engine) as session, session.begin():
            import_csv(session, path, manifest, tmp_path / "imports")
    plan = Plan(date(2026, 7, 1), date(2026, 10, 10), date(2026, 11, 2), date(2026, 12, 31), "local", "faq")
    feature = tmp_path / "feature"
    feature.mkdir()
    (feature / "metadata.json").write_text(json.dumps({"plan": plan.serializable(), "artifact_sha256": {}}))
    with Session(engine) as session:
        vintages, _ = load_vintages(session, plan)
    development = examples(vintages, date(2026, 10, 2), date(2026, 11, 2), 3, date(2026, 11, 3))
    assert len(development) >= 2
    model = fit("ridge_1", development)
    champions = tmp_path / "models"
    save_champion(champions / "champion-3d", {"champion": "ridge_1", "horizon": 3, "note": "TEST_ONLY small-sample wiring; not production model selection"}, model, development, plan, "TEST_ONLY")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps([{"feature_run": str(feature), "champions": str(champions)}]))
    monkeypatch.setenv("SAMAY_SERVICE_REGISTRY_PATH", str(registry))
    get_settings.cache_clear()


def test_imported_dataset_saved_model_reliability_and_real_optimizer_flow(api, tmp_path, monkeypatch):
    client, engine = api
    deploy_test_model(engine, tmp_path, monkeypatch)
    assert client.get("/api/v1/markets").json()[0]["name"] == "Kolar APMC"
    assert client.get("/api/v1/commodities").json()[0]["name"] == "Tomato"
    history = client.get("/api/v1/prices/history?variety=local&grade=faq").json()
    assert history["items"][0]["source"] == "INTEGRATION_TEST_ONLY_NOT_LIVE"
    latest = client.get("/api/v1/prices/latest?variety=local&grade=faq").json()
    assert latest["observation"]["report_date"] == "2026-11-01"
    prediction = client.post("/api/v1/predict", json={"variety": "local", "grade": "faq", "horizon": 3})
    assert prediction.status_code == 200, prediction.text
    predicted = prediction.json()
    assert float(predicted["prediction_inr_per_quintal"]) > 0
    assert predicted["model_version"].endswith("champion-3d")
    assert predicted["reliability_status"] == "limited evidence"
    assert predicted["intervals"] == []  # No pretend calibration from a tiny fixture.
    request = recommendation()
    result = client.post("/api/v1/recommend", json=request)
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["predictions"][0]["model_version"] == predicted["model_version"]
    assert payload["market_data"]["report_date"] == "2026-11-01"
    assert payload["market_data"]["source"] == "INTEGRATION_TEST_ONLY_NOT_LIVE"
    assert payload["optimization"]["recommended_plan"]["cash_today_inr"] == "18700.00"
    request["today_price_inr_per_quintal"] = "1200"
    changed = client.post("/api/v1/recommend", json=request).json()
    assert changed["optimization"]["recommended_plan"]["cash_today_inr"] == "22500.00"
    request["required_net_cash_inr"] = "50000"
    infeasible = client.post("/api/v1/recommend", json=request)
    assert infeasible.status_code == 409
    assert infeasible.json()["optimization"]["recommended_plan"] is None
    assert client.get("/api/v1/models/status").json()["models"][2]["model_version"] is None
    assert client.get("/api/v1/data/status").json()["official_observations"] > 0


def test_validation_cors_swagger_and_safe_errors(api, monkeypatch, caplog):
    client, engine = api
    for horizon in (0, 2, True, "3"):
        response = client.post("/api/v1/predict", json={"variety": "local", "grade": "faq", "horizon": horizon})
        assert response.status_code == 422
        assert "input" not in response.json()["error"]["details"]
    bad = recommendation()
    bad["holding_options"][0]["scenarios"] = {"reliability_status": "validated"}
    assert client.post("/api/v1/recommend", json=bad).status_code == 422
    bad = recommendation()
    bad["decision_at"] = "2099-01-01T00:00:00Z"
    assert client.post("/api/v1/recommend", json=bad).status_code == 422
    assert client.get("/api/v1/prices/latest?market=unknown&variety=local&grade=faq").status_code == 422
    preflight = client.options("/api/v1/recommend", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 200
    assert "POST" in preflight.headers["access-control-allow-methods"]
    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    assert "/api/v1/recommend" in schema.json()["paths"]
    assert client.get("/docs").status_code == 200
    import app.api_services as services
    def failure(*args):
        raise RuntimeError("PRIVATE_TOKEN_DO_NOT_LOG")
    monkeypatch.setattr(services, "model_status", failure)
    failed = client.get("/api/v1/models/status")
    assert failed.status_code == 500
    assert "PRIVATE_TOKEN" not in failed.text
    assert "PRIVATE_TOKEN" not in caplog.text
    assert failed.json()["error"]["request_id"] == failed.headers["X-Request-ID"]


def test_stale_data_missing_horizon_and_service_failure(api, tmp_path, monkeypatch):
    client, engine = api
    deploy_test_model(engine, tmp_path, monkeypatch)
    missing = client.post("/api/v1/predict", json={"variety": "local", "grade": "faq", "horizon": 7})
    assert missing.status_code == 503
    assert missing.json()["error"]["code"] == "missing_model"
    app.dependency_overrides[get_clock] = lambda: datetime(2026, 12, 1, 12, tzinfo=UTC)
    stale = client.post("/api/v1/predict", json={"variety": "local", "grade": "faq", "horizon": 3})
    assert stale.status_code == 503
    assert stale.json()["error"]["code"] == "stale_market_data"
    assert client.get("/api/v1/prices/latest?variety=local&grade=faq").json()["stale"] is True
    import app.api_services as services
    def unavailable(*args, **kwargs):
        raise OSError("PRIVATE_SERVICE_ERROR")
    monkeypatch.setattr(services, "reliable_forecast", unavailable)
    failed = client.post("/api/v1/predict", json={"variety": "local", "grade": "faq", "horizon": 3})
    assert failed.status_code == 503
    assert "PRIVATE" not in failed.text
    fallback = client.post("/api/v1/recommend", json=recommendation())
    assert fallback.status_code == 200
    assert "3d:prediction_service_unavailable" in fallback.json()["reliability_warnings"]


def test_persistence_failure_returns_503_instead_of_claiming_saved(api):
    client, engine = api
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE recommendation_history")
    failed = client.post("/api/v1/recommend", json=recommendation())
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "database_unavailable"


def test_research_registry_reports_metrics_without_deploying_predictors(api, tmp_path, monkeypatch):
    import hashlib

    from app.forecasting import metrics
    client, _ = api
    folder = tmp_path / "research"
    folder.mkdir()
    computed = metrics([1000, 1100], [990, 1090], [980, 1080])
    report = {"research_only": True, "version": "TEST_ONLY_RESEARCH", "source_fingerprint": "TEST_ONLY",
        "plan": {"market": "Kolar APMC", "commodity": "Tomato", "variety": "tomato", "grade": "local", "start": "2021-01-01",
            "train_end": "2023-12-31", "validation_end": "2024-12-31", "holdout_end": "2025-06-30"},
        "limitations": "TEST_ONLY conditional retrospective experiment", "horizons": [{"horizon": 1, "champion": "naive",
            "sample_policy": {"effective_train_samples": 120, "effective_validation_samples": 30}}],
        "final_evaluation": {"results": [{"horizon": 1, "n": 2, "metrics": computed, "baseline_metrics": {"naive": computed}}]}}
    content = json.dumps(report).encode()
    (folder / "comparison.json").write_bytes(content)
    registry = tmp_path / "research-registry.json"
    registry.write_text(json.dumps([{"directory": str(folder), "comparison_sha256": hashlib.sha256(content).hexdigest()}]))
    monkeypatch.setenv("SAMAY_RESEARCH_REGISTRY_PATH", str(registry))
    get_settings.cache_clear()
    output = client.get("/api/v1/models/status").json()
    assert output["models"] == [] and output["status"] == "no_models_deployed"
    assert output["research_studies"][0]["horizons"][0]["final_metrics"]["mae_inr_per_quintal"] == 10
    assert client.post("/api/v1/predict", json={"variety": "tomato", "grade": "local", "horizon": 1}).status_code == 503
    (folder / "comparison.json").write_text("{}")
    failed = client.get("/api/v1/models/status")
    assert failed.status_code == 503 and failed.json()["error"]["code"] == "research_registry_unavailable"
