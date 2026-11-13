"""Deterministic test-only observations; no market-performance examples generated."""
import hashlib
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from app.backtesting import run_backtest
from app.features import Plan, empty_vintages, midnight
from app.reliability import (
    POLICY,
    calibrate,
    dated_predictions,
    evaluate,
    evidence_at,
    intervals_for,
    reliability_response,
)


def case():
    start = date(2025, 1, 1)
    rows = [{"report_date": start + timedelta(days=i), "available_at": pd.Timestamp(midnight(start + timedelta(days=i)).to_pydatetime() + timedelta(hours=18)),
             "price": float(1000 + (i % 7) * 10), "batch_id": 1, "row_id": i + 1, "file_sha256": "TEST_ONLY"} for i in range(270)]
    plan = Plan(start, date(2025, 6, 30), date(2025, 9, 30), date(2025, 12, 31), "local", "faq")
    return pd.DataFrame(rows), plan


def scope(plan):
    return {k: getattr(plan, k) for k in ("market", "commodity", "variety", "grade")}


def test_future_prices_and_late_revisions_never_change_historical_predictions():
    rows, plan = case()
    origin = date(2025, 4, 1)
    first = reliability_response(rows, plan, origin, 3, {"sources": ["TEST_ONLY"]})
    modified = rows.copy()
    modified.loc[modified.report_date >= origin, "price"] = 90000.
    revision = rows.iloc[[20]].copy()
    revision["price"] = 50000.
    revision["available_at"] = midnight(origin + timedelta(days=1))
    second = reliability_response(pd.concat([modified, revision]), plan, origin, 3, {"sources": ["TEST_ONLY"]})
    assert first == second
    assert first.reliability_status == "limited evidence"
    assert first.intervals == []


def test_sparse_stale_and_unsupported_safe_responses():
    rows, plan = case()
    origin = date(2025, 1, 6)
    sparse = reliability_response(rows, plan, origin, 1, {})
    assert "sparse_history" in sparse.flags
    assert sparse.reliability_status == "limited evidence"
    assert sparse.intervals == []
    stale = reliability_response(rows.iloc[:5], plan, date(2025, 2, 1), 1, {})
    assert stale.reliability_status == "stale data"
    assert stale.prediction_inr_per_quintal is None
    assert stale.intervals == []
    unsupported = reliability_response(rows, plan, origin, 2, {})
    assert unsupported.reliability_status == "unavailable"
    assert "unsupported_horizon" in unsupported.flags
    absent = reliability_response(empty_vintages(), plan, origin, 1, {})
    assert absent.prediction_inr_per_quintal is None


def test_ordered_nested_empirical_intervals_and_unseen_coverage():
    rows, plan = case()
    calibration_rows = dated_predictions(rows, plan, date(2025, 1, 1), date(2025, 4, 30), 3, date(2025, 5, 1))
    calibration = calibrate(calibration_rows, 3, date(2025, 5, 1), scope(plan), "predeclared-naive-v1")
    assert calibration["calibration_blocks"] >= 8
    intervals = intervals_for(1050, calibration)
    assert len(intervals) == 2
    assert intervals[1].lower_inr_per_quintal <= intervals[0].lower_inr_per_quintal <= 1050
    assert intervals[1].upper_inr_per_quintal >= intervals[0].upper_inr_per_quintal >= 1050
    assessment = dated_predictions(rows, plan, date(2025, 5, 1), date(2025, 7, 31), 3, date(2025, 8, 1))
    _, result = evaluate(assessment, calibration)
    assert result["n"] == 89
    assert result["metrics"] == result["naive_metrics_same_timestamps"]
    assert 0 <= result["intervals"]["0.9"]["empirical_coverage"] <= 1
    assert result["intervals"]["0.9"]["mean_width_inr_per_quintal"] >= 0
    # Evaluation changes cannot feed back into the frozen calibration radii.
    changed = rows.copy()
    changed.loc[changed.report_date >= date(2025, 5, 1), "price"] = 99999.
    repeat = calibrate(dated_predictions(changed, plan, date(2025, 1, 1), date(2025, 4, 30), 3, date(2025, 5, 1)), 3, date(2025, 5, 1), scope(plan), "predeclared-naive-v1")
    assert repeat == calibration


def test_missing_targets_delayed_actuals_and_volatility_flags():
    rows, plan = case()
    rows = rows[rows.report_date != date(2025, 4, 4)].copy()
    scored = dated_predictions(rows, plan, date(2025, 4, 1), date(2025, 4, 10), 3, date(2025, 4, 11))
    assert "missing_target_observation" in scored.iloc[0]["flags"]
    assert pd.isna(scored.iloc[0].actual)
    assert pd.isna(scored.iloc[0].absolute_error)
    rows.loc[rows.report_date == date(2025, 4, 5), "available_at"] = midnight(date(2025, 5, 1))
    delayed = dated_predictions(rows, plan, date(2025, 4, 1), date(2025, 4, 10), 3, date(2025, 4, 11))
    assert pd.isna(delayed.iloc[1].actual)
    volatile = rows.copy()
    volatile["price"] = np.where(np.arange(len(volatile)) % 2 == 0, 100, 10000)
    response = reliability_response(volatile, plan, date(2025, 4, 1), 1, {})
    assert "excessive_volatility" in response.flags


def test_future_evaluation_errors_cannot_establish_reliability(tmp_path):
    rows, plan = case()
    cal_rows = dated_predictions(rows, plan, date(2025, 1, 1), date(2025, 4, 30), 1, date(2025, 5, 1))
    cal = calibrate(cal_rows, 1, date(2025, 5, 1), scope(plan), "predeclared-naive-v1")
    ev = dated_predictions(rows, plan, date(2025, 5, 1), date(2025, 7, 31), 1, date(2025, 8, 1))
    ev.to_csv(tmp_path / "evaluation-1d.csv", index=False)
    digest = hashlib.sha256((tmp_path / "evaluation-1d.csv").read_bytes()).hexdigest()
    (tmp_path / "summary.json").write_text(json.dumps({"scope": scope(plan), "policy": POLICY,
        "artifact_sha256": {"evaluation-1d.csv": digest}, "horizons": [{"horizon": 1, "calibration": cal}]}))
    unavailable, known = evidence_at(tmp_path, 1, date(2025, 4, 1), scope(plan), "predeclared-naive-v1")
    assert unavailable is None
    assert known.empty
    limited = reliability_response(rows, plan, date(2025, 5, 5), 1, {}, tmp_path)
    assert limited.reliability_status == "limited evidence"
    valid = reliability_response(rows, plan, date(2025, 8, 1), 1, {}, tmp_path)
    assert valid.reliability_status == "validated"
    # Adverse unseen errors downgrade status using only resolved past targets.
    ev.loc[ev.absolute_error.notna(), "absolute_error"] = 10000
    ev.to_csv(tmp_path / "evaluation-1d.csv", index=False)
    manifest = json.loads((tmp_path / "summary.json").read_text())
    manifest["artifact_sha256"]["evaluation-1d.csv"] = hashlib.sha256((tmp_path / "evaluation-1d.csv").read_bytes()).hexdigest()
    (tmp_path / "summary.json").write_text(json.dumps(manifest))
    drift = reliability_response(rows, plan, date(2025, 8, 1), 1, {}, tmp_path)
    assert "model_drift" in drift.flags
    assert "large_recent_forecast_errors" in drift.flags
    assert drift.reliability_status == "limited evidence"
    (tmp_path / "evaluation-1d.csv").write_text("tampered")
    invalid = reliability_response(rows, plan, date(2025, 8, 1), 1, {}, tmp_path)
    assert invalid.reliability_status == "unavailable"
    assert invalid.prediction_inr_per_quintal is None
    assert "invalid_reliability_evidence" in invalid.flags


def test_final_holdout_is_rejected_and_insufficient_backtest_is_reproducible(tmp_path, monkeypatch):
    import app.backtesting as module
    rows, plan = case()
    monkeypatch.setattr(module, "read_plan", lambda _: (plan, {"vintages_sha256": hashlib.sha256(empty_vintages().to_csv(index=False).encode()).hexdigest()}))
    monkeypatch.setattr(module, "load_vintages", lambda session, selected: (empty_vintages(), {"sources": []}))
    with pytest.raises(ValueError, match="final holdout"):
        run_backtest(None, tmp_path, date(2025, 1, 1), date(2025, 6, 30), date(2025, 10, 1), tmp_path / "out")
    folder, summary = run_backtest(None, tmp_path, date(2025, 1, 1), date(2025, 6, 30), date(2025, 9, 30), tmp_path / "out")
    assert summary["status"] == "insufficient_data"
    assert all(h["assessment"]["metrics"] is None for h in summary["horizons"])
    assert len(list(folder.glob("*.png"))) == 4
    assert run_backtest(None, tmp_path, date(2025, 1, 1), date(2025, 6, 30), date(2025, 9, 30), tmp_path / "out")[0] == folder
