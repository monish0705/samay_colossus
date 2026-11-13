"""TEST_ONLY cases: research scope/causality/holdout safeguards, no market claims."""
import json
from dataclasses import replace
from datetime import timedelta

import pytest
from app.forecasting import _forecast_with_vintages, fit, save_champion
from app.research import run
from test_forecasting import case


def test_research_artifacts_are_rejected_by_production_predictor(tmp_path):
    from app.forecasting import examples
    rows, plan = case()
    data = examples(rows, plan.start, plan.validation_end, 1, plan.validation_end + timedelta(days=1))
    artifact = tmp_path / "champion-1d"
    metadata = save_champion(artifact, {"champion": "naive", "horizon": 1}, fit("naive", data), data, plan, "TEST_ONLY")
    metadata["research_only"] = True
    (artifact / "metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="research"):
        _forecast_with_vintages(artifact, rows, plan.validation_end + timedelta(days=1), 1)


def test_research_freezes_selection_before_loading_final_and_consumes_once(tmp_path, monkeypatch):
    import app.research as research
    rows, plan = case()
    calls = []
    def loader(session, incoming, *, final=False):
        calls.append(final)
        if final:
            frozen = list(tmp_path.glob("research-snapshot-*/comparison.json"))
            assert frozen
            assert json.loads(frozen[0].read_text())["final_evaluation"] is None
        end = plan.holdout_end if final else plan.validation_end
        return rows[rows.report_date <= end].copy(), [{"source": "TEST_ONLY"}]
    monkeypatch.setattr(research, "snapshot", loader)
    # Avoid repeated ML fitting here: use the real naive rows and settlement-free metric path.
    from app.forecasting import examples
    def select(frame, incoming, horizon):
        development = examples(frame, plan.start, plan.validation_end, horizon, plan.validation_end + timedelta(days=1))
        return {"champion": "naive", "horizon": horizon, "sample_policy": {"effective_train_samples": 100, "effective_validation_samples": 30}}, None, development
    monkeypatch.setattr(research, "select_horizon", select)
    folder, result = run(None, plan, tmp_path, True)
    assert calls == [False, True]
    assert result["research_only"] is True
    assert all(r["n"] >= 30 for r in result["final_evaluation"]["results"])
    assert all(r["metrics"] == r["baseline_metrics"]["naive"] for r in result["final_evaluation"]["results"])
    before = (folder / "comparison.json").read_bytes()
    _, repeat = run(None, plan, tmp_path, True)
    assert repeat == result and before == (folder / "comparison.json").read_bytes()
    # Altering a development plan cannot grant a second evaluation on the same holdout.
    with pytest.raises(ValueError, match="already.*reserved"):
        run(None, replace(plan, train_end=plan.train_end - timedelta(days=1)), tmp_path, True)
    # Changing just the end date must not allow overlapping held-out targets to
    # become a new test after their outcomes have supplied feedback.
    with pytest.raises(ValueError, match="overlapping date boundaries"):
        run(None, replace(plan, holdout_end=plan.holdout_end - timedelta(days=1)), tmp_path, True)
