import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.db import make_engine
from app.main import app
from app.models import MandiObservation, Market
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]


def test_health():
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "samay", "version": "0.1.0"}


def test_cors():
    response = TestClient(app).get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    response = TestClient(app).get("/api/health", headers={"Origin": "https://untrusted.example"})
    assert "access-control-allow-origin" not in response.headers


def test_migration_initialization_and_utc(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    monkeypatch.setenv("SAMAY_DATABASE_URL", url)
    get_settings.cache_clear()
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    try:
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        engine = make_engine(url)
        assert set(inspect(engine).get_table_names()) == {"alembic_version", "markets", "commodities", "mandi_observations", "model_versions", "predictions", "recommendations", "import_batches", "import_rows", "recommendation_history"}
        monkeypatch.setenv("SAMAY_ENVIRONMENT", "development")
        for _ in range(2):
            subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], check=True, capture_output=True)
        with Session(engine) as session:
            assert len(session.scalars(select(Market)).all()) == 1
            assert len(session.scalars(select(MandiObservation)).all()) == 1
        monkeypatch.setenv("SAMAY_ENVIRONMENT", "production")
        blocked = subprocess.run([sys.executable, str(ROOT / "scripts" / "seed_demo.py")], capture_output=True, text=True)
        assert blocked.returncode != 0
        assert "only in development" in blocked.stderr
        with Session(engine) as session:
            session.add(Market(name="DEMO_DATA", district="Demo", state="Demo", data_source="DEMO_DATA"))
            session.commit()
            record = session.scalar(select(Market))
            assert record.created_at.utcoffset().total_seconds() == 0
            record.created_at = datetime(2025, 1, 1)
            with pytest.raises(StatementError, match="timezone-aware"):
                session.commit()
            session.rollback()
            session.add(MandiObservation(market_id=999, commodity_id=999, observed_on=datetime.now(UTC).date(), min_price_inr_per_quintal=1, modal_price_inr_per_quintal=2, max_price_inr_per_quintal=3, arrivals_quintals=1, data_source="DEMO_DATA"))
            with pytest.raises(IntegrityError):
                session.commit()
        engine.dispose()
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    finally:
        get_settings.cache_clear()
