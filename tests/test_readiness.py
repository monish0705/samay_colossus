from datetime import date

import pytest
from app.config import Settings
from app.readiness import check


def test_readiness_never_claims_a_missing_model_is_ready(monkeypatch):
    import app.readiness as readiness
    monkeypatch.setattr(readiness, "model_status", lambda: __import__("app.api_schemas", fromlist=["ModelsStatus"]).ModelsStatus(status="no_models_deployed", models=[]))
    result = check()
    assert result["ready_for_authentic_forecast_demo"] is False
    assert "No saved model/baseline is deployed" in result["issues"]


def test_historical_replay_is_explicit_and_never_allowed_in_production():
    assert Settings(environment="test", historical_demo_date=date(2025, 11, 4)).historical_demo_date == date(2025, 11, 4)
    with pytest.raises(ValueError, match="replay"):
        Settings(environment="production", historical_demo_date=date(2025, 11, 4))
    with pytest.raises(ValueError, match="past"):
        Settings(environment="development", historical_demo_date=date(2099, 1, 1))
