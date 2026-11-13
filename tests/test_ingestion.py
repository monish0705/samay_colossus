import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.config import get_settings
from app.db import make_engine
from app.ingestion import SourceManifest, import_csv, normalize, number, unit_factor
from app.main import app
from app.models import ImportBatch, ImportRow, MandiObservation
from app.prices import get_session
from fastapi.testclient import TestClient
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture
def engine(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMAY_DATABASE_URL", f"sqlite:///{(tmp_path / 'ingest.db').as_posix()}")
    get_settings.cache_clear()
    command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
    engine = make_engine(get_settings().database_url)
    yield engine
    engine.dispose()
    get_settings.cache_clear()


def manifest():
    return SourceManifest.model_validate_json((FIXTURES / "manifest.json").read_text())


def run(engine, tmp_path, source=None, spec=None, **kwargs):
    with Session(engine) as session, session.begin():
        return import_csv(session, source or FIXTURES / "mandi_fixture.csv", spec or manifest(), tmp_path / "output", **kwargs)


def test_corrupt_rows_duplicates_gaps_and_lineage(engine, tmp_path):
    report = run(engine, tmp_path, start=date(2025, 1, 1), end=date(2025, 1, 3))
    # Out-of-range rows are filtered after full date/price validation.
    assert report["counts"] == {"records": 12, "inserted": 3, "revised": 0, "duplicates": 1, "stale": 0, "quarantined": 5, "filtered": 3}
    assert report["missing_calendar_dates"] == ["2025-01-02"]
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ImportRow)) == 12
        rows = session.scalars(select(MandiObservation)).all()
        assert len(rows) == 3
        assert all(r.arrivals_quintals is None for r in rows)
        converted = session.scalar(select(ImportRow).where(ImportRow.line_number == 4))
        assert converted.raw["Price_Unit"] == "INR/kg"
        assert converted.normalized["modal"] == "1500.00"
        batch = session.get(ImportBatch, report["batch_id"])
        assert Path(batch.archive_path).read_bytes() == (FIXTURES / "mandi_fixture.csv").read_bytes()
        assert batch.fetched_at.tzinfo is not None
        assert batch.report["current_snapshot_records"] == 3
    assert len(inspect(engine).get_check_constraints("mandi_observations")) == 2
    output = tmp_path / "output" / f"batch-{report['batch_id']}"
    assert "INR/quintal" in (output / "validated_input.csv").read_text()
    assert len((output / "prices.csv").read_text().splitlines()) == 4
    assert json.loads((output / "quality.json").read_text())["missing_days_count"] == 1


def test_reimport_revisions_stale_conflicts_and_kind_isolation(engine, tmp_path):
    first = run(engine, tmp_path)
    assert first["counts"]["quarantined"] == 7
    repeated = run(engine, tmp_path)
    assert repeated["counts"]["inserted"] == 0
    assert repeated["counts"]["duplicates"] == 4
    changed = tmp_path / "revised.csv"
    changed.write_text((FIXTURES / "mandi_fixture.csv").read_text().replace("1000,2000,1500", "1000,2000,1700"))
    newer = manifest().model_copy(update={"fetched_at": datetime(2025, 1, 11, tzinfo=UTC)})
    revised = run(engine, tmp_path, changed, newer)
    assert revised["counts"]["revised"] == 1
    older = run(engine, tmp_path)
    assert older["counts"]["stale"] == 2
    with Session(engine) as session:
        current = session.scalar(select(MandiObservation).where(MandiObservation.observed_on == date(2025, 1, 1), MandiObservation.variety == "local"))
        assert current.modal_price_inr_per_quintal == Decimal(1700)
        assert session.scalar(select(func.count()).select_from(ImportRow)) == 48
    with pytest.raises(RuntimeError, match="Downgrade refused"):
        command.downgrade(Config(str(ROOT / "backend/alembic.ini")), "73bf51f6beac")


def test_history_api_and_default_fixture_exclusion(engine, tmp_path):
    run(engine, tmp_path)
    def dependency():
        with Session(engine) as session:
            yield session
    app.dependency_overrides[get_session] = dependency
    try:
        client = TestClient(app)
        assert client.get("/api/v1/markets").json() == []
        assert client.get("/api/v1/prices/history").json()["items"] == []
        markets = client.get("/api/v1/markets?data_kind=fixture").json()
        assert markets[0]["name"] == "Kolar APMC"
        result = client.get("/api/v1/prices/history", params={"data_kind": "fixture", "market": "kolar", "limit": 2}).json()
        assert len(result["items"]) == 2
        assert result["next_offset"] == 2
        assert result["items"][0]["fetched_at"].endswith("Z")
        assert result["items"][0]["arrivals_quintals"] is None
        assert len(client.get("/api/v1/prices/history?data_kind=fixture&offset=2").json()["items"]) == 1
        for query in ["limit=0", "start_date=2025-02-01&end_date=2025-01-01", "market=Unknown", "start_date=invalid"]:
            assert client.get("/api/v1/prices/history?" + query).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_unchanged_newer_fetch_advances_revision_watermark(engine, tmp_path):
    run(engine, tmp_path)
    run(engine, tmp_path, spec=manifest().model_copy(update={"fetched_at": datetime(2025, 1, 13, tzinfo=UTC)}))
    changed = tmp_path / "older.csv"
    changed.write_text((FIXTURES / "mandi_fixture.csv").read_text().replace("1000,2000,1500", "1000,2000,1700"))
    report = run(engine, tmp_path, source=changed, spec=manifest().model_copy(update={"fetched_at": datetime(2025, 1, 12, tzinfo=UTC)}))
    assert report["counts"]["revised"] == 0
    assert report["counts"]["stale"] == 2


@pytest.mark.parametrize("value", ["-1", "NaN", "inf", "1,00", "1.234", ""])
def test_invalid_numbers(value):
    with pytest.raises(ValueError):
        number(value)


@pytest.mark.parametrize("format,value", [("%Y-%m-%d", "2025-01-01"), ("%d-%m-%Y", "01-01-2025"), ("%d/%m/%Y", "01/01/2025")])
def test_explicit_dates_and_numeric_units(format, value):
    row = {"state": "Karnataka", "district": "Kolar", "market": "Kolar", "commodity": "Tomato", "variety": "Local", "report_date": value, "min": "1,000", "modal": "1,500", "max": "2,000"}
    normalized = normalize(row, manifest().model_copy(update={"date_format": format}))
    assert normalized["report_date"] == "2025-01-01"
    assert normalized["grade"] == "unspecified"
    assert normalized["modal"] == "1500.00"
    assert number("1,00,000.00") == Decimal(100000)
    assert unit_factor("INR/tonne") == Decimal("0.1")


def test_manifest_and_file_failures(engine, tmp_path):
    for update in [{"fetched_at": "2025-01-01T00:00:00"}, {"date_format": "%m/%d/%Y"}]:
        with pytest.raises(ValueError):
            SourceManifest.model_validate({**manifest().model_dump(), **update})
    with pytest.raises(ValueError, match="Unknown price unit"):
        unit_factor("USD/kg")
    for update, message in [({"sha256": "bad"}, "SHA256"), ({"data_kind": "official", "source_url": "https://example.com/data.csv"}, "Official source"), ({"unit_evidence": ""}, "unit_evidence")]:
        with pytest.raises(ValueError, match=message):
            run(engine, tmp_path, spec=manifest().model_copy(update=update))
    bad = tmp_path / "bad.csv"
    bad.write_text("date,price\n2025-01-01,12\n")
    with pytest.raises(ValueError, match="columns"):
        run(engine, tmp_path, source=bad)
    with Session(engine) as session:
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0
