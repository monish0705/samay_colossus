"""Read-only readiness checks; no invented data or model fallback."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, text

from app.api_services import ServiceProblem, data_status, model_status
from app.db import SessionLocal, engine


def check():
    from app.config import get_settings
    origin = get_settings().historical_demo_date or datetime.now(ZoneInfo("Asia/Kolkata")).date()
    result = {"checked_at": datetime.now(UTC).isoformat(), "database": "unavailable", "data": None, "models": None, "ready_for_authentic_forecast_demo": False, "issues": []}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        tables = set(inspect(engine).get_table_names())
        if not {"recommendation_history", "import_rows", "alembic_version"}.issubset(tables):
            result["issues"].append("Run Alembic upgrade head")
        else:
            result["database"] = "initialized"
            with SessionLocal() as session:
                result["data"] = data_status(session, origin).model_dump(mode="json")
            if not result["data"]["official_observations"]:
                result["issues"].append("No authentic official observations are prepared; fixture prices are excluded")
        result["models"] = model_status().model_dump(mode="json")
        if not any(m["model_version"] for m in result["models"]["models"]):
            result["issues"].append("No saved model/baseline is deployed")
        elif not any(m["reliability_evidence_configured"] for m in result["models"]["models"]):
            result["issues"].append("No empirical reliability evidence is configured")
    except ServiceProblem as exc:
        result["issues"].append(exc.code)
    except Exception as exc:
        result["issues"].append(f"Readiness check failed: {type(exc).__name__}")
    result["prediction_checks"] = []
    if result["data"] and result["data"]["official_observations"] and result["models"]:
        from app.api_schemas import PredictRequest
        from app.api_services import predict
        with SessionLocal() as session:
            for item in result["models"]["models"]:
                if item["model_version"] is None:
                    continue
                try:
                    query = PredictRequest(**{key: item[key] for key in ("market", "commodity", "variety", "grade")}, horizon=item["horizon"])
                    raw, _ = predict(session, query, origin, "startup-readiness")
                    result["prediction_checks"].append({"horizon": item["horizon"], "status": raw.reliability_status, "model_version": raw.model_version})
                except Exception as exc:
                    result["prediction_checks"].append({"horizon": item["horizon"], "status": "unavailable", "code": getattr(exc, "code", type(exc).__name__)})
        result["ready_for_authentic_forecast_demo"] = result["data"]["status"] != "stale" and any(row["status"] == "validated" for row in result["prediction_checks"])
        if not result["ready_for_authentic_forecast_demo"]:
            result["issues"].append("No current validated saved-model prediction passed the readiness check")
    return result
