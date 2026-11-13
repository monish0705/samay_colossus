"""Conditional action selection from exact optimizer ledgers, never news sentiment prices."""
from datetime import timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from app.market_context import MarketContext
from app.selling import Input, Name, PriceScenarios, Rate, money

# Application planning ceilings, not validated shelf-life or spoilage estimates.
CROP_PLANNING_CEILINGS={"Tomato":7,"Arecanut":730,"Onion":120,"Copra":365,"Potato":180}


class DecisionPolicy(Input):
    downside_fraction: Rate = Decimal(".10")
    adverse_fraction: Rate = Decimal(".20")
    upside_fraction: Rate = Decimal(".10")
    assumption_source: Name
    long_horizon_mode: Literal["require_user_price", "flat_reference", "saved_forecast"] = "require_user_price"
    storage_exposure: Literal["protected", "outdoor", "unknown"] = "unknown"
    block_holding_on_rain_risk: bool = False
    rainfall_stop_threshold_mm: Decimal = Field(default=Decimal("20"), gt=0, le=1000, allow_inf_nan=False)

    @model_validator(mode="after")
    def stress_order(self):
        if self.adverse_fraction < self.downside_fraction:
            raise ValueError("Adverse stress must be at least the lower-scenario stress")
        if self.block_holding_on_rain_risk and self.storage_exposure != "outdoor":
            raise ValueError("Rain blocking applies only to explicitly outdoor storage")
        return self


def sensitivity_scenarios(body, option, policy, central, source, version, flags=(), *, apply_realization=True):
    """Price sensitivities are user-reviewed assumptions, NOT empirical quantiles."""
    value = Decimal(str(central)) * (option.realization_multiplier if apply_realization else 1)
    return PriceScenarios(adverse_inr_per_quintal=money(value*(1-policy.adverse_fraction)),
        lower_inr_per_quintal=money(value*(1-policy.downside_fraction)), central_inr_per_quintal=money(value),
        upper_inr_per_quintal=money(value*(1+policy.upside_fraction)), reliability_status="scenario only",
        market=body.market,commodity=body.commodity,variety=body.variety,grade=body.grade,
        target_date=body.decision_at.astimezone(ZoneInfo("Asia/Kolkata")).date()+timedelta(days=option.days),
        issued_at=body.decision_at,model_version=version,source=source,
        price_basis_assumption=option.price_basis_assumption,
        adverse_assumption=policy.assumption_source, flags=tuple(flags)+("user_sensitivity_not_prediction_interval",))


def rain_blocks(context: MarketContext, policy: DecisionPolicy, days):
    if not policy.block_holding_on_rain_risk or policy.storage_exposure!="outdoor":
        return False
    today=context.decision_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    by_date={day.date:day for day in context.weather}
    for offset in range(days+1):
        day=by_date.get(today+timedelta(days=offset))
        if day is None or day.precipitation_mm is None or Decimal(str(day.precipitation_mm)) >= policy.rainfall_stop_threshold_mm:
            return True
    return False


def summarize_decision(result, context, *, requested_holding, scenarios_available, constraints=()):
    safe = result["recommended_plan"]
    candidate = result["best_scenario_only_or_validated_plan"]
    reasons = list(constraints)
    held = [p for p in result["feasible_plans"] if p["holding_days"] > 0]
    best_holding = max(held, key=lambda p: (p["total_net_inr"]["central"], p["downside_total_net_inr"], -p["holding_days"])) if held else None
    baseline = result["sell_all_now"]["sale"]["net_inr"]

    holding_econ = None
    if best_holding:
        central_diff = best_holding["total_net_inr"]["central"] - baseline
        is_profitable = central_diff > 0
        holding_econ = {
            "is_profitable": bool(is_profitable),
            "projected_diff_inr": f"{central_diff:+.2f}",
            "today_net_sale_inr": f"{baseline:.2f}",
            "later_central_net_inr": f"{best_holding['total_net_inr']['central']:.2f}",
            "holding_days": best_holding["holding_days"],
            "sell_today_quintals": f"{best_holding['sell_today_quintals']:.2f}",
            "hold_quintals": f"{best_holding['hold_initial_quintals']:.2f}",
            "storage_cost_inr": f"{best_holding['storage_cost_inr']:.2f}",
            "deterioration_loss_quintals": f"{best_holding['deterioration_loss_quintals']:.2f}",
            "break_even_price_inr_per_quintal": f"{best_holding['break_even_future_price_inr_per_quintal']:.2f}" if best_holding.get("break_even_future_price_inr_per_quintal") else None,
            "verdict_title": f"Holding Recommended: +₹{central_diff:,.2f} Projected Profit" if is_profitable else f"Selling Today Recommended: Holding Results in -₹{abs(central_diff):,.2f} Net Loss",
            "verdict_reason": (
                f"Holding {best_holding['hold_initial_quintals']} qtl for {best_holding['holding_days']} days delivers a projected gain of +₹{central_diff:,.2f} after storage costs and quantity shrinkage."
                if is_profitable else
                f"Holding for {best_holding['holding_days']} days is projected to lose ₹{abs(central_diff):,.2f} versus selling today. Predicted future price does not cover storage costs (₹{best_holding['storage_cost_inr']:,.2f}) and deterioration ({best_holding['deterioration_loss_quintals']} qtl)."
            ),
        }

    if candidate is None:
        action, basis = "infeasible", "cash_or_physical_constraints"
        reasons.append("cash_requirement_not_achievable")
    elif requested_holding and not scenarios_available and not constraints:
        action, basis = "insufficient_evidence", "no_defensible_future_price_scenario"
        reasons.append("holding_cannot_be_assessed_without_future_scenarios")
        candidate = None
    elif best_holding and (best_holding["total_net_inr"]["central"] > baseline):
        candidate = best_holding
        action = "partial_sell_and_hold" if candidate["sell_today_quintals"] else "hold"
        basis = "validated_forecast" if candidate["recommendation_eligible"] else "conditional_scenario_analysis"
        diff = candidate["total_net_inr"]["central"] - baseline
        reasons += ["mandatory_cash_and_storage_constraints_satisfied", "risk_adjusted_net_exceeds_immediate_sale", f"projected_profit_gain_inr:{diff:.2f}"]
    elif candidate and candidate["holding_days"]:
        action = "partial_sell_and_hold" if candidate["sell_today_quintals"] else "hold"
        basis = "validated_forecast" if candidate["recommendation_eligible"] else "conditional_scenario_analysis"
        reasons += ["mandatory_cash_and_storage_constraints_satisfied", "risk_adjusted_net_exceeds_immediate_sale"]
    else:
        action, basis = "sell_now", "constraints_and_supplied_scenarios"
        if best_holding:
            loss = baseline - best_holding["total_net_inr"]["central"]
            reasons.append(f"holding_projected_loss_inr:{loss:.2f}")
            reasons.append("storage_and_deterioration_exceed_future_price_gain")
        else:
            reasons.append("holding_does_not_improve_risk_adjusted_net_or_is_infeasible")
        candidate = safe or candidate

    comparisons = []
    for days in sorted({p["holding_days"] for p in result["feasible_plans"]}):
        options = [p for p in result["feasible_plans"] if p["holding_days"] == days]
        best = max(options, key=lambda p: (p["risk_adjusted_objective_inr"], p["total_net_inr"]["central"], p["downside_total_net_inr"]))
        comparisons.append(best)

    return {
        "action": action,
        "basis": basis,
        "conditional": bool(candidate and not candidate["recommendation_eligible"]),
        "plan": candidate,
        "safe_fallback_plan": safe,
        "best_holding_plan": best_holding,
        "holding_economics": holding_econ,
        "reasons": reasons,
        "horizon_comparisons": comparisons,
        "context": context,
        "note": "Compare conditional scenarios with the safe fallback. Calendar/news do not imply a price rise. Longer flat-reference scenarios are not trained long-horizon forecasts.",
    }
