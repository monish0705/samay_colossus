"""Illustrative deterministic economics, not agronomic or price recommendations."""
import itertools
from copy import deepcopy
from decimal import Decimal as D

import pytest
from app.reliability import EmpiricalInterval, ReliabilityForecast
from app.selling import (
    SaleCosts,
    SellingRequest,
    optimize_selling,
    sale,
    scenarios_from_reliability,
)
from pydantic import ValidationError


def request():
    costs = {"fixed_transport_inr": "100", "transport_inr_per_quintal": "10", "commission_rate": ".05", "assumptions": "TEST_ONLY settlement costs"}
    return {"commodity": "Tomato", "market": "Kolar APMC", "variety": "local", "grade": "faq", "decision_at": "2026-11-04T08:00:00+05:30",
        "total_quantity_quintals": "20", "today_price_inr_per_quintal": "1000", "today_price_assumption": "TEST_ONLY realistic-price input, not live data",
        "required_net_cash_inr": "10000", "storage_capacity_quintals": "20", "decision_increment_quintals": "1", "market_quantity_step_quintals": ".01",
        "minimum_sale_lot_quintals": "1", "maximum_horizon_days": 7, "risk_tolerance": "balanced", "today_sale_costs": costs,
        "crop_storage_profile": {"commodity": "Tomato", "maximum_holding_days": 3, "storage_conditions": "TEST_ONLY controlled example", "assumption_source": "User-supplied test assumption, not a tomato shelf-life claim"},
        "holding_options": [{"days": 3, "daily_loss_fractions": [".01"] * 3, "daily_storage_inr_per_quintal": ["2"] * 3,
            "storage_payment": "later", "future_sale_costs": costs, "assumptions": "TEST_ONLY configured loss and costs",
            "scenarios": {"adverse_inr_per_quintal": "1200", "lower_inr_per_quintal": "1300", "central_inr_per_quintal": "1500", "upper_inr_per_quintal": "1700",
                "reliability_status": "validated", "market": "Kolar APMC", "commodity": "Tomato", "variety": "local", "grade": "faq", "target_date": "2026-11-07",
                "issued_at": "2026-11-04T00:00:00+05:30", "model_version": "TEST_ONLY", "source": "TEST_ONLY", "price_basis_assumption": "Assumed farmer sale prices, not mandi observations",
                "adverse_assumption": "TEST_ONLY stress scenario"}}]}


def test_partial_cash_aware_hold_and_break_even():
    r = request()
    output = optimize_selling(r)
    chosen = output["recommended_plan"]
    assert chosen["sell_today_quintals"] == 11  # Ten quintals cannot net INR 10,000 after fees.
    assert chosen["cash_today_inr"] == D("10240.00")
    assert chosen["hold_initial_quintals"] == 9
    assert chosen["later_saleable_quintals"] == D("8.73")
    assert chosen["total_net_inr"]["central"] > output["sell_all_now"]["sale"]["net_inr"]
    q = chosen["later_saleable_quintals"]
    price = chosen["break_even_future_price_inr_per_quintal"]
    costs = SellingRequest.model_validate(r).holding_options[0].future_sale_costs
    def total(p):
        return chosen["cash_today_inr"] + sale(q, p, costs)["net_inr"] - chosen["storage_paid_later_inr"]
    baseline = output["sell_all_now"]["sale"]["net_inr"]
    assert total(price) >= baseline
    assert total(price - D(".01")) < baseline
    assert output == optimize_selling(r)


@pytest.mark.parametrize("case", ["zero_storage", "falling_price", "high_storage", "total_spoilage", "crop_limit", "horizon_limit", "missing_prediction", "unreliable", "outdated"])
def test_prefers_sell_now_when_holding_bad_or_unsupported(case):
    r = request()
    option = r["holding_options"][0]
    if case == "zero_storage":
        r["storage_capacity_quintals"] = "0"
    elif case == "falling_price":
        for key, value in zip(("adverse", "lower", "central", "upper"), ("500", "600", "700", "800"), strict=False):
            option["scenarios"][key + "_inr_per_quintal"] = value
    elif case == "high_storage":
        option["daily_storage_inr_per_quintal"] = ["1000"] * 3
    elif case == "total_spoilage":
        option["daily_loss_fractions"] = ["1", "0", "0"]
    elif case == "crop_limit":
        r["crop_storage_profile"]["maximum_holding_days"] = 1
    elif case == "horizon_limit":
        r["maximum_horizon_days"] = 1
    elif case == "missing_prediction":
        option["scenarios"] = None
    elif case == "unreliable":
        option["scenarios"]["reliability_status"] = "limited evidence"
    else:
        option["scenarios"]["issued_at"] = "2026-11-03T00:00:00+05:30"
    output = optimize_selling(r)
    assert output["status"] == "sell_all_now"
    assert output["recommended_plan"]["sell_today_quintals"] == 20
    assert output["recommended_plan"]["hold_initial_quintals"] == 0


def test_insufficient_cash_and_negative_returns_are_not_clipped():
    r = request()
    r["required_net_cash_inr"] = "20000"
    output = optimize_selling(r)
    assert output["status"] == "no_feasible_cash_solution"
    assert output["recommended_plan"] is None
    assert output["cash_requirement_achievable_on_grid"] is False
    r = request()
    r["today_sale_costs"]["fixed_transport_inr"] = "100000"
    r["holding_options"] = []
    output = optimize_selling(r)
    assert output["sell_all_now"]["sale"]["net_inr"] < 0
    assert output["recommended_plan"] is None


def test_upfront_storage_affects_cash_and_fixed_cost_only_on_sale():
    r = request()
    r["holding_options"][0]["storage_payment"] = "today"
    r["holding_options"][0]["fixed_storage_inr"] = "500"
    output = optimize_selling(r)
    assert all(p["cash_today_inr"] >= 10000 for p in output["feasible_plans"])
    selected = output["recommended_plan"]
    if selected["holding_days"]:
        assert selected["today_sale"]["net_inr"] - selected["storage_cost_inr"] == selected["cash_today_inr"]
    costs = SaleCosts(fixed_transport_inr="100", fixed_transaction_inr="50", assumptions="TEST_ONLY")
    assert sale(D(0), D(100), costs)["net_inr"] == 0
    assert sale(D(1), D(100), costs)["net_inr"] == -50


def test_fees_minimum_lots_and_terminal_grid_boundary():
    costs = SaleCosts(market_fee_rate=".02", commission_rate=".05", transport_inr_per_quintal="10", fixed_transport_inr="100", assumptions="TEST_ONLY")
    settled = sale(D(20), D(1000), costs)
    assert settled["market_fee_inr"] == 400
    assert settled["commission_inr"] == 1000
    assert settled["net_inr"] == 18300
    r = request()
    r["total_quantity_quintals"] = "20.25"
    r["decision_increment_quintals"] = "2"
    r["minimum_sale_lot_quintals"] = "3"
    output = optimize_selling(r)
    assert any(p["sell_today_quintals"] == D("20.25") and p["holding_days"] == 0 for p in output["feasible_plans"])
    assert all(p["sell_today_quintals"] == 0 or p["sell_today_quintals"] >= 3 for p in output["feasible_plans"])
    assert all(not p["holding_days"] or p["later_saleable_quintals"] >= 3 for p in output["feasible_plans"])


def test_risk_preferences_do_not_hide_adverse_loss():
    r = request()
    r["holding_options"][0]["scenarios"].update(adverse_inr_per_quintal="500", lower_inr_per_quintal="1000", central_inr_per_quintal="3000", upper_inr_per_quintal="4000")
    r["risk_tolerance"] = "conservative"
    assert optimize_selling(r)["recommended_plan"]["holding_days"] == 0
    r["risk_tolerance"] = "aggressive"
    chosen = optimize_selling(r)["recommended_plan"]
    assert chosen["holding_days"] == 3
    assert chosen["difference_vs_sell_all_now_inr"]["adverse"] < 0


@pytest.mark.parametrize("field,value", [("total_quantity_quintals", "0"), ("today_price_inr_per_quintal", "NaN"), ("storage_capacity_quintals", "-1"), ("market_quantity_step_quintals", "0"), ("maximum_horizon_days", True), ("total_quantity_quintals", "20.001")])
def test_invalid_inputs(field, value):
    r = request()
    r[field] = value
    with pytest.raises(ValidationError):
        optimize_selling(r)


def test_invalid_schedule_scope_datetime_fees_and_resource_limit():
    mutations = [lambda r: r["holding_options"][0].update(daily_loss_fractions=[".01"]),
        lambda r: r["holding_options"][0]["scenarios"].update(market="wrong"),
        lambda r: r.update(decision_at="2026-11-04T00:00:00"),
        lambda r: r["today_sale_costs"].update(commission_rate="1"),
        lambda r: r["holding_options"][0]["scenarios"].update(issued_at="2026-11-05T00:00:00+05:30"),
        lambda r: r.update(decision_increment_quintals=".001", market_quantity_step_quintals=".001")]
    for mutate in mutations:
        r = request()
        mutate(r)
        with pytest.raises(ValidationError):
            optimize_selling(r)


def test_exhaustive_small_grid_conservation_constraints_and_argmax_property():
    for total, capacity, cash, risk in itertools.product(("1", "3", "5"), ("0", "2", "5"), ("0", "1000", "10000"), ("conservative", "balanced", "aggressive")):
        r = request()
        r.update(total_quantity_quintals=total, storage_capacity_quintals=capacity, required_net_cash_inr=cash, risk_tolerance=risk)
        output = optimize_selling(r)
        safe = []
        for p in output["feasible_plans"]:
            assert p["sell_today_quintals"] + p["hold_initial_quintals"] == D(total)
            assert p["hold_initial_quintals"] <= D(capacity)
            assert p["cash_today_inr"] >= D(cash)
            if p["holding_days"]:
                assert abs(p["later_saleable_quintals"] + p["deterioration_loss_quintals"] + p["rounding_discard_quintals"] - p["hold_initial_quintals"]) < D("1e-30")
            if p["recommendation_eligible"]:
                safe.append(p)
        chosen = output["recommended_plan"]
        if chosen:
            assert chosen["risk_adjusted_objective_inr"] == max(p["risk_adjusted_objective_inr"] for p in safe)


def test_reliability_adapter_never_promotes_unavailable_predictions():
    response = ReliabilityForecast(horizon_calendar_days=3, timestamp="2026-11-03T18:30:00+00:00", market="Kolar APMC", commodity="Tomato", variety="local", grade="faq", data_source={})
    args = dict(adverse_inr_per_quintal=D(0), realization_multiplier=D(".8"), price_basis_assumption="TEST_ONLY mapping", adverse_assumption="TEST_ONLY stress")
    assert scenarios_from_reliability(response, **args) is None
    response.prediction_inr_per_quintal = 1500
    response.target_date = "2026-11-07"
    response.model_version = "TEST_ONLY"
    response.reliability_status = "limited evidence"
    response.intervals = [EmpiricalInterval(nominal_level=.9, lower_inr_per_quintal=1000, upper_inr_per_quintal=2000)]
    scenario = scenarios_from_reliability(response, **args)
    assert scenario.central_inr_per_quintal == 1200
    assert scenario.reliability_status == "limited evidence"
    r = request()
    r["holding_options"][0]["scenarios"] = scenario.model_dump()
    assert optimize_selling(r)["recommended_plan"]["holding_days"] == 0


def test_ties_prefer_liquidity_and_input_is_not_mutated():
    r = request()
    r["today_sale_costs"] = {"assumptions": "TEST_ONLY no costs"}
    option = r["holding_options"][0]
    option.update(daily_loss_fractions=["0"] * 3, daily_storage_inr_per_quintal=["0"] * 3, future_sale_costs={"assumptions": "TEST_ONLY no costs"})
    for key in ("adverse", "lower", "central", "upper"):
        option["scenarios"][key + "_inr_per_quintal"] = "1000"
    original = deepcopy(r)
    assert optimize_selling(r)["recommended_plan"]["sell_today_quintals"] == 20
    assert r == original


def test_no_cash_feasibility_claim_when_upfront_costs_block_every_plan():
    r = request()
    r["today_sale_costs"]["fixed_transport_inr"] = "100000"
    r["required_net_cash_inr"] = "0"
    option = r["holding_options"][0]
    option.update(storage_payment="today", fixed_storage_inr="100")
    result = optimize_selling(r)
    assert result["maximum_today_net_cash_upper_bound_inr"] == 0
    assert result["cash_requirement_achievable_on_grid"] is False
    assert result["recommended_plan"] is None


def test_arecanut_long_term_storage():
    """Verify long-term holding (180 days) for durable crops like Arecanut at Shivamogga Mandi."""
    costs = {"fixed_transport_inr": "800", "transport_inr_per_quintal": "40", "commission_rate": ".02", "market_fee_rate": ".015", "assumptions": "MAMCOS auction costs"}
    days = 180
    r = {
        "commodity": "Arecanut",
        "market": "Shivamogga Mandi",
        "variety": "rashi edi",
        "grade": "faq",
        "decision_at": "2026-11-04T08:00:00+05:30",
        "total_quantity_quintals": "10",
        "today_price_inr_per_quintal": "48000",
        "today_price_assumption": "MAMCOS official rate",
        "required_net_cash_inr": "100000",
        "storage_capacity_quintals": "10",
        "decision_increment_quintals": "1",
        "market_quantity_step_quintals": ".01",
        "minimum_sale_lot_quintals": "1",
        "maximum_horizon_days": 730,
        "risk_tolerance": "balanced",
        "today_sale_costs": costs,
        "crop_storage_profile": {
            "commodity": "Arecanut",
            "maximum_holding_days": 730,
            "storage_conditions": "Ventilated gunny bag warehouse",
            "assumption_source": "MAMCOS storage practice",
        },
        "holding_options": [{
            "days": days,
            "daily_loss_fractions": [".0002"] * days,
            "daily_storage_inr_per_quintal": ["1.2"] * days,
            "storage_payment": "later",
            "future_sale_costs": costs,
            "assumptions": "MAMCOS central godown",
            "scenarios": {
                "adverse_inr_per_quintal": "49000",
                "lower_inr_per_quintal": "51000",
                "central_inr_per_quintal": "54000",
                "upper_inr_per_quintal": "56000",
                "reliability_status": "validated",
                "market": "Shivamogga Mandi",
                "commodity": "Arecanut",
                "variety": "rashi edi",
                "grade": "faq",
                "target_date": "2027-05-03",
                "issued_at": "2026-11-04T00:00:00+05:30",
                "model_version": "arecanut-naive-v1",
                "source": "MAMCOS",
                "price_basis_assumption": "Farmer sale prices",
                "adverse_assumption": "Stress scenario",
            }
        }]
    }
    result = optimize_selling(r)
    chosen = result["recommended_plan"]
    assert chosen is not None
    assert chosen["holding_days"] == 180
    assert chosen["hold_initial_quintals"] > 0
    assert chosen["cash_today_inr"] >= D("100000")
