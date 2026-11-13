"""TEST_ONLY deterministic economic and chronology checks, never published performance."""
import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from app.decision_backtesting import replay, save_report
from app.features import empty_vintages, midnight
from app.reliability import EmpiricalInterval, ReliabilityForecast
from test_backend import ROOT
from test_reliability import case


def template():
    return json.loads((ROOT / "docs/examples/selling-example.json").read_text())


def test_empty_source_has_null_metrics_and_never_invents_outcomes(tmp_path):
    _, plan = case()
    records, audits, report = replay(empty_vintages(), plan, date(2025, 4, 1), date(2025, 4, 5), date(2025, 4, 6), template(), {})
    assert report["scored_decisions"] == 0
    assert report["mean_gain_inr"] is None and report["win_rate"] is None
    assert audits == [] and len(records) == 5
    folder = save_report(tmp_path, records, audits, report, template())
    assert (folder / "decisions-vs-actual.csv").exists()


@pytest.mark.parametrize("future", [500, 1000, 2000])
def test_future_prices_do_not_change_frozen_decision_and_fallback_matches_sell_all(future):
    rows, plan = case()
    start, end = date(2025, 4, 1), date(2025, 4, 5)
    records, decisions, report = replay(rows, plan, start, end, end + timedelta(days=1), template(), {})
    changed = rows.copy()
    changed.loc[changed.report_date >= start, "price"] = float(future)
    other, audit, result = replay(changed, plan, start, end, end + timedelta(days=1), template(), {})
    assert decisions[0] == audit[0]  # Same as-of inputs even when scoring outcomes change.
    assert result["recommended_hold_count"] == 0
    assert all(r["gain_vs_sell_all_inr"] in {"0.00", None} for r in other)
    if future == 500:
        assert result["no_feasible_plan_count"] > 0
        assert result["cash_constraint_success_rate"] == 0
    assert report["final_holdout"] == "unopened"
    assert records[0]["actual_today_row_id"] is not None


def test_cash_shortfall_and_zero_storage_remain_explicit():
    rows, plan = case()
    request = template()
    request["storage_capacity_quintals"] = "0"
    _, _, result = replay(rows, plan, date(2025, 4, 1), date(2025, 4, 3), date(2025, 4, 4), request, {})
    assert result["recommended_hold_count"] == 0 and result["cash_constraint_success_rate"] == 1
    request["required_net_cash_inr"] = "999999"
    records, _, report = replay(rows, plan, date(2025, 4, 1), date(2025, 4, 3), date(2025, 4, 4), request, {})
    assert report["no_feasible_plan_count"] == 3
    assert report["scored_decisions"] == 0
    assert all(r["status"] == "no_feasible_cash_solution" for r in records)


def test_exact_dates_missing_labels_and_holdout_guard():
    rows, plan = case()
    rows = rows[rows.report_date != date(2025, 4, 1)]
    records, _, summary = replay(rows, plan, date(2025, 4, 1), date(2025, 4, 3), date(2025, 4, 4), template(), {})
    assert records[0]["gain_vs_sell_all_inr"] is None
    assert summary["scored_decisions"] == 2
    with pytest.raises(ValueError, match="holdout"):
        replay(rows, plan, plan.validation_end, plan.holdout_end, plan.holdout_end + timedelta(days=1), template(), {})
    with pytest.raises(ValueError, match="multiplier"):
        replay(rows, plan, date(2025, 4, 1), date(2025, 4, 2), date(2025, 4, 3), template(), {}, realization_multiplier=Decimal("NaN"))


@pytest.mark.parametrize("future_price", [500, 1000, 2000])
def test_realized_hold_outcomes_apply_the_same_loss_and_cost_ledger(monkeypatch, future_price):
    # Force a prospective TEST_ONLY high-price scenario to exercise scoring math.
    # This is a unit test of settlement, not evidence of forecasting reliability.
    import app.decision_backtesting as decisions
    from app.selling import HoldingOption, SaleCosts, sale, stored_quantity
    rows, plan = case()
    origin, end = date(2025, 4, 1), date(2025, 4, 5)
    def forecast(*args):
        day, horizon = args[2:4]
        return ReliabilityForecast(prediction_inr_per_quintal=3000, intervals=[EmpiricalInterval(nominal_level=.9, lower_inr_per_quintal=2800, upper_inr_per_quintal=3200)],
            horizon_calendar_days=horizon, timestamp=midnight(day).isoformat(), target_date=(day + timedelta(days=horizon)).isoformat(),
            model_version="TEST_ONLY_PROSPECTIVE_SCENARIO", reliability_status="validated", data_source={"source": "TEST_ONLY"},
            market=plan.market, commodity=plan.commodity, variety=plan.variety, grade=plan.grade)
    monkeypatch.setattr(decisions, "reliability_response", forecast)
    request = template()
    request["risk_tolerance"] = "aggressive"
    changed = rows.copy()
    changed.loc[changed.report_date == origin + timedelta(days=3), "price"] = float(future_price)
    records, audit, _ = replay(changed, plan, origin, end, end + timedelta(days=1), request, {"source": "TEST_ONLY"})
    chosen = audit[0]["decision"]["recommended_plan"]
    assert chosen["hold_initial_quintals"] > 0
    option_data = dict(request["holding_options"][0], scenarios=None)
    option = HoldingOption.model_validate(option_data)
    marketable, _, _, storage = stored_quantity(chosen["hold_initial_quintals"], option, Decimal(request["market_quantity_step_quintals"]))
    later = sale(marketable, Decimal(future_price), SaleCosts.model_validate(option_data["future_sale_costs"]))["net_inr"]
    actual_today = sale(chosen["sell_today_quintals"], Decimal(str(changed.loc[changed.report_date == origin].price.iloc[0])), SaleCosts.model_validate(request["today_sale_costs"]))["net_inr"]
    assert Decimal(records[0]["realized_total_net_inr"]) == actual_today + later - storage
