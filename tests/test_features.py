"""Deterministic analytical test cases only; never production/training records."""
from dataclasses import replace
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from alembic import command
from alembic.config import Config
from app.analysis import write_insights, write_run
from app.config import get_settings
from app.db import make_engine
from app.features import (
    FEATURES,
    Plan,
    asof,
    build_horizon,
    empty_vintages,
    features_at,
    load_vintages,
    midnight,
)
from app.ingestion import SourceManifest, import_csv
from sqlalchemy.orm import Session
from test_backend import ROOT


def analytical_case():
    start = date(2025, 1, 1)
    rows = []
    for i in range(140):
        day = start + timedelta(days=i)
        rows.append({"report_date": day, "available_at": pd.Timestamp(midnight(day).to_pydatetime() + timedelta(hours=18)), "price": float(1000 + i), "batch_id": 1, "row_id": i + 1, "file_sha256": "TEST_ONLY"})
    return pd.DataFrame(rows)


def plan():
    return Plan(date(2025, 1, 1), date(2025, 3, 15), date(2025, 4, 15), date(2025, 5, 20), "local", "faq", min_train=2, min_validation=2, min_train_span_days=1)


def test_observation_lags_and_shifted_rolling_exact_values():
    rows = analytical_case()
    origin = date(2025, 2, 10)
    values, audit = features_at(rows, origin, 3)
    assert values["lag_1_obs_inr_per_quintal"] == 1039
    assert values["lag_30_obs_inr_per_quintal"] == 1010
    assert values["rolling_mean_7_obs_inr_per_quintal"] == np.mean(np.arange(1033, 1040))
    assert values["rolling_median_14_obs_inr_per_quintal"] == np.median(np.arange(1026, 1040))
    assert values["rolling_std_30_obs_inr_per_quintal"] == np.std(np.arange(1010, 1040), ddof=1)
    assert audit["max_feature_report_date"] == "2025-02-09"
    assert pd.Timestamp(audit["max_feature_available_at"]) <= midnight(origin)
    assert all("target_modal" not in name for name in FEATURES)


def test_future_origin_target_and_late_revision_cannot_change_features():
    original = analytical_case()
    origin = date(2025, 2, 10)
    expected, _ = features_at(original, origin, 7)
    changed = original.copy()
    changed.loc[changed.report_date >= origin, "price"] = 999999
    revision = original.iloc[[1]].copy()
    revision["price"] = 50000
    revision["available_at"] = pd.Timestamp(midnight(origin).to_pydatetime() + timedelta(days=5))
    altered, _ = features_at(pd.concat([changed, revision], ignore_index=True), origin, 7)
    assert altered == expected


def test_late_original_reports_and_missing_calendar_targets():
    rows = analytical_case()
    rows.loc[rows.report_date == date(2025, 2, 9), "available_at"] = midnight(date(2025, 2, 20))
    values, _ = features_at(rows, date(2025, 2, 10), 1)
    assert values["lag_1_obs_inr_per_quintal"] == 1038
    missing_date = date(2025, 2, 13)
    rows = rows[rows.report_date != missing_date]
    frame, _ = build_horizon(rows, plan(), 3)
    row = frame[frame.origin_date == "2025-02-10"].iloc[0]
    assert row.target_date == "2025-02-13"
    assert row.reason == "missing_target_at_label_freeze"
    assert pd.isna(row.target_modal_price_inr_per_quintal)


@pytest.mark.parametrize("horizon", [1, 3, 7])
def test_time_splits_purge_and_label_availability(horizon):
    p = plan()
    frame, summary = build_horizon(analytical_case(), p, horizon)
    assert summary["effective_train_samples"] > 0
    for split, end in [("train", p.train_end), ("validation", p.validation_end)]:
        selected = frame[(frame.split == split) & (frame.reason == "eligible")]
        assert (pd.to_datetime(selected.target_date).dt.date <= end).all()
        assert (pd.to_datetime(selected.label_available_at, utc=True) < midnight(end + timedelta(days=1))).all()
        assert ((frame.split == split) & (frame.reason == "embargo_target_crosses_split")).sum() == horizon
    assert not (frame.origin_date > p.validation_end.isoformat()).any()


def test_late_labels_do_not_enter_earlier_splits():
    rows = analytical_case()
    rows.loc[rows.report_date == date(2025, 2, 11), "available_at"] = midnight(date(2025, 4, 1))
    frame, _ = build_horizon(rows, plan(), 1)
    assert frame[frame.origin_date == "2025-02-10"].iloc[0].reason == "missing_target_at_label_freeze"


def test_changing_holdout_values_cannot_change_development_features_or_labels():
    rows = analytical_case()
    expected, _ = build_horizon(rows, plan(), 7)
    changed = rows.copy()
    changed.loc[changed.report_date > plan().validation_end, "price"] = 999999
    actual, _ = build_horizon(changed, plan(), 7)
    pd.testing.assert_frame_equal(expected, actual)


def test_missing_data_is_insufficient_for_every_horizon():
    for horizon in (1, 3, 7):
        frame, summary = build_horizon(empty_vintages(), plan(), horizon)
        assert summary["effective_train_samples"] == 0
        assert summary["status"] == "insufficient_data"
    _, summary = build_horizon(analytical_case(), replace(plan(), min_train=120, min_train_span_days=180), 1)
    assert summary["status"] == "insufficient_data"


def test_revisions_only_apply_after_availability_and_ties_fail():
    rows = analytical_case()
    revised = rows.iloc[[1]].copy()
    revised["price"] = 8000
    revised["available_at"] = midnight(date(2025, 2, 1))
    changed = pd.concat([rows, revised], ignore_index=True)
    before = asof(changed, midnight(date(2025, 1, 31)))
    after = asof(changed, midnight(date(2025, 2, 2)))
    assert before[before.report_date == date(2025, 1, 2)].iloc[0].price == 1001
    assert after[after.report_date == date(2025, 1, 2)].iloc[0].price == 8000
    revised["available_at"] = rows.iloc[1].available_at
    with pytest.raises(ValueError, match="Conflicting"):
        asof(pd.concat([rows, revised]), midnight(date(2025, 2, 1)))


def test_versioned_outputs_are_reproducible_holdout_sealed_and_detect_tamper(tmp_path):
    rows = empty_vintages()
    folder, meta = write_run(rows, plan(), {"sources": []}, tmp_path)
    repeat, _ = write_run(rows, plan(), {"sources": []}, tmp_path)
    assert repeat == folder
    assert len(list(folder.glob("*.png"))) == 6
    assert meta["horizons"][0]["effective_train_samples"] == 0
    held = pd.read_csv(folder / "horizon-1d" / "holdout_plan_no_values.csv")
    assert set(held.columns) == {"origin_date", "target_date", "evaluation_eligible_by_boundary"}
    assert set(pd.read_csv(folder / "horizon-1d" / "train_X.csv").columns) == set(FEATURES + ["origin_date"])
    with pytest.raises(ValueError, match="already frozen"):
        write_run(rows, replace(plan(), train_end=date(2025, 3, 14)), {"sources": []}, tmp_path)
    (folder / "market_insights.json").write_text("{}")
    with pytest.raises(ValueError, match="Changed artifact"):
        write_run(rows, plan(), {"sources": []}, tmp_path)


def test_fixture_ledger_never_becomes_feature_input(tmp_path, monkeypatch):
    monkeypatch.setenv("SAMAY_DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    get_settings.cache_clear()
    engine = None
    try:
        command.upgrade(Config(str(ROOT / "backend/alembic.ini")), "head")
        engine = make_engine(get_settings().database_url)
        with Session(engine) as session, session.begin():
            spec = SourceManifest.model_validate_json((ROOT / "tests/fixtures/manifest.json").read_text())
            import_csv(session, ROOT / "tests/fixtures/mandi_fixture.csv", spec, tmp_path / "import")
        with Session(engine) as session:
            rows, provenance = load_vintages(session, plan())
            assert rows.empty
            assert provenance["sources"] == []
    finally:
        if engine is not None:
            engine.dispose()
        get_settings.cache_clear()


def test_training_insights_do_not_change_with_validation_or_holdout_prices(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    rows = analytical_case()
    original = write_insights(rows, plan(), first, {})
    rows.loc[rows.report_date > plan().train_end, "price"] = 999999
    changed = write_insights(rows, plan(), second, {})
    assert original == changed
    assert original["observed_dates"] == 74
    assert len(original["weekday"]) == 7
    assert original["quality"]["snapshot_observations"] == 74
