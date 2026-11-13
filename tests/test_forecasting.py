"""Hand-defined deterministic unit cases, never production training records."""
import hashlib
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
from app.features import Plan, midnight
from app.forecasting import (
    _forecast_with_vintages,
    metrics,
    rolling_folds,
    save_champion,
    select_horizon,
)
from app.training import train_run


def case():
    start = date(2024, 1, 1)
    rows = [{"report_date": start + timedelta(days=i), "available_at": pd.Timestamp(midnight(start + timedelta(days=i)).to_pydatetime() + timedelta(hours=18)),
             "price": 1000., "batch_id": 1, "row_id": i + 1, "file_sha256": "TEST_ONLY"} for i in range(430)]
    plan = Plan(start, date(2024, 9, 30), date(2024, 11, 30), date(2025, 2, 28), "local", "faq")
    return pd.DataFrame(rows), plan


def test_metric_values_and_zero_guards():
    result = metrics([100, 200], [110, 180], [90, 210])
    assert result["mae_inr_per_quintal"] == 15
    assert result["rmse_inr_per_quintal"] == pytest.approx(np.sqrt(250))
    assert result["wape_pct"] == 10
    assert result["directional_accuracy"] == 1
    assert metrics([0, 0], [0, 0], [0, 0])["wape_pct"] is None
    assert metrics([0], [0], [0])["smape_pct"] == 0
    assert metrics([.001], [.002], [0])["smape_pct"] is None
    with pytest.raises(ValueError):
        metrics([], [], [])
    with pytest.raises(ValueError):
        metrics([1], [np.nan], [1])


def test_folds_have_causal_labels_and_horizon_embargo():
    rows, plan = case()
    for horizon in (1, 3, 7):
        folds = rolling_folds(rows, plan, horizon)
        assert len(folds) == 3
        for train, valid in folds:
            assert train.target_date.max() < valid.origin_date.min()
            first = date.fromisoformat(valid.origin_date.min())
            assert (pd.to_datetime(train.label_available_at, utc=True) < midnight(first)).all()


def test_cv_training_labels_ignore_later_revisions():
    rows, plan = case()
    first_train, first_valid = rolling_folds(rows, plan, 1)[0]
    altered = rows.iloc[[35]].copy()
    altered["price"] = 9999.
    altered["available_at"] = midnight(date.fromisoformat(first_valid.origin_date.min()) + timedelta(days=3))
    changed_train, _ = rolling_folds(pd.concat([rows, altered], ignore_index=True), plan, 1)[0]
    assert changed_train.iloc[0].target_modal_price_inr_per_quintal == first_train.iloc[0].target_modal_price_inr_per_quintal
    assert (changed_train.target_modal_price_inr_per_quintal == 1000).all()


def test_selection_promotes_baseline_and_saved_forecast_is_causal(tmp_path):
    rows, plan = case()
    result, model, development = select_horizon(rows, plan, 1)
    assert result["champion"] in {"naive", "mean_14", "median_14"}
    for item in result["comparisons"]:
        assert item["validation"]["mae_inr_per_quintal"] == 0
        assert len(item["cv"]) == 3
    folder = tmp_path / "test-only-champion"
    save_champion(folder, result, model, development, plan, "TEST_ONLY")
    origin = date(2024, 12, 10)
    output = _forecast_with_vintages(folder, rows, origin, 1)
    assert output["prediction_inr_per_quintal"] == 1000.
    changed = rows.copy()
    changed.loc[changed.report_date >= origin, "price"] = 99999
    assert _forecast_with_vintages(folder, changed, origin, 1) == output
    with pytest.raises(ValueError, match="Unsupported"):
        _forecast_with_vintages(folder, rows, origin, 7)
    with pytest.raises(ValueError, match="not available"):
        _forecast_with_vintages(folder, rows, date(2024, 8, 1), 1)
    with pytest.raises(ValueError, match="stale"):
        _forecast_with_vintages(folder, rows.iloc[:5], origin, 1)


def test_training_freezes_selection_before_one_shot_holdout(tmp_path, monkeypatch):
    import app.training as module
    rows, plan = case()
    development = rows[rows.report_date <= plan.validation_end].copy()
    feature_run = tmp_path / "features"
    feature_run.mkdir()
    (feature_run / "metadata.json").write_text(json.dumps({"plan": plan.serializable(), "artifact_sha256": {}, "vintages_sha256": hashlib.sha256(development.to_csv(index=False).encode()).hexdigest()}))
    final_calls = []
    provenance = {"sources": ["TEST_ONLY"]}
    def loader(session, selected, final_evaluation=False):
        if final_evaluation:
            final_calls.append(1)
            assert list((tmp_path / "models").glob("*/comparison.json"))
            return rows, provenance
        return development, provenance
    monkeypatch.setattr(module, "load_vintages", loader)
    actual = select_horizon
    def select(vintages, selected, horizon):
        if horizon != 1:
            return {"horizon": horizon, "champion": None, "comparisons": [], "reason": ["TEST_ONLY skip"]}, None, None
        return actual(vintages, selected, horizon)
    monkeypatch.setattr(module, "select_horizon", select)
    output, report = train_run(None, feature_run, tmp_path / "models", True)
    assert final_calls == [1]
    assert report["final_evaluation"]["results"][0]["status"] == "evaluated"
    assert report["final_evaluation"]["results"][0]["metrics"]["mae_inr_per_quintal"] == 0
    # Idempotent rerun returns the persisted result and never reopens test targets.
    again, _ = train_run(None, feature_run, tmp_path / "models", True)
    assert again == output
    assert final_calls == [1]
    # A new development provenance/version may not re-evaluate the same holdout.
    provenance["new_version"] = "TEST_ONLY"
    with pytest.raises(ValueError, match="already reserved"):
        train_run(None, feature_run, tmp_path / "models", True)
    assert final_calls == [1]
