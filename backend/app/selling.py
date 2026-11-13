"""Pure, deterministic cash-constrained sale planning. No forecasts or crop-loss rates invented."""
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_UP, Decimal, localcontext
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

D = Decimal
CENT = D(".01")
MAX_PRICE = D("1000000000")
Nonnegative = Annotated[Decimal, Field(ge=0, le=MAX_PRICE, allow_inf_nan=False, max_digits=18, decimal_places=4)]
Quantity = Annotated[Decimal, Field(ge=0, le=100000, allow_inf_nan=False, max_digits=9, decimal_places=3)]
Rate = Annotated[Decimal, Field(ge=0, le=1, allow_inf_nan=False, max_digits=9, decimal_places=6)]
Name = Annotated[str, Field(min_length=1, max_length=1000)]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class SaleCosts(Input):
    fixed_transport_inr: Nonnegative = D(0)
    fixed_transaction_inr: Nonnegative = D(0)
    transport_inr_per_quintal: Nonnegative = D(0)
    handling_inr_per_quintal: Nonnegative = D(0)
    market_fee_rate: Rate = D(0)
    commission_rate: Rate = D(0)
    assumptions: Name

    @model_validator(mode="after")
    def fees(self):
        if self.market_fee_rate + self.commission_rate >= 1:
            raise ValueError("Combined market fee and commission must be <1")
        return self


class CropStorageProfile(Input):
    commodity: Name
    maximum_holding_days: Annotated[StrictInt, Field(ge=0, le=730)]
    storage_conditions: Name
    assumption_source: Name


class PriceScenarios(Input):
    adverse_inr_per_quintal: Nonnegative
    lower_inr_per_quintal: Nonnegative
    central_inr_per_quintal: Nonnegative
    upper_inr_per_quintal: Nonnegative
    reliability_status: Literal["validated", "limited evidence", "stale data", "unavailable", "scenario only"]
    market: Name
    commodity: Name
    variety: Name
    grade: Name = "unspecified"
    target_date: date
    issued_at: datetime
    model_version: Name
    source: Name
    price_basis_assumption: Name
    adverse_assumption: Name
    flags: tuple[str, ...] = ()

    @model_validator(mode="after")
    def ordered(self):
        if self.issued_at.utcoffset() is None:
            raise ValueError("Scenario issued_at must be timezone-aware")
        if not self.adverse_inr_per_quintal <= self.lower_inr_per_quintal <= self.central_inr_per_quintal <= self.upper_inr_per_quintal:
            raise ValueError("Require adverse <= lower <= central <= upper prices")
        return self


class HoldingOption(Input):
    days: Annotated[StrictInt, Field(ge=1, le=730)]
    daily_loss_fractions: tuple[Rate, ...]
    daily_storage_inr_per_quintal: tuple[Nonnegative, ...]
    fixed_storage_inr: Nonnegative = D(0)
    storage_payment: Literal["today", "later"]
    future_sale_costs: SaleCosts
    assumptions: Name
    scenarios: PriceScenarios | None = None

    @model_validator(mode="after")
    def schedules(self):
        if len(self.daily_loss_fractions) != self.days or len(self.daily_storage_inr_per_quintal) != self.days:
            raise ValueError("Provide one loss fraction and storage rate for every holding day")
        return self


class SellingRequest(Input):
    commodity: Name
    market: Name
    variety: Name
    grade: Name = "unspecified"
    decision_at: datetime
    total_quantity_quintals: Annotated[Quantity, Field(gt=0)]
    today_price_inr_per_quintal: Nonnegative
    today_price_assumption: Name
    required_net_cash_inr: Nonnegative
    storage_capacity_quintals: Quantity
    decision_increment_quintals: Annotated[Quantity, Field(gt=0)]
    market_quantity_step_quintals: Annotated[Quantity, Field(gt=0)]
    minimum_sale_lot_quintals: Annotated[Quantity, Field(gt=0)]
    maximum_horizon_days: Annotated[StrictInt, Field(ge=0, le=730)]
    crop_storage_profile: CropStorageProfile
    today_sale_costs: SaleCosts
    holding_options: tuple[HoldingOption, ...] = ()
    risk_tolerance: Literal["conservative", "balanced", "aggressive"] = "conservative"

    @model_validator(mode="after")
    def consistent(self):
        if self.decision_at.utcoffset() is None:
            raise ValueError("decision_at must be timezone-aware")
        if self.commodity.casefold() != self.crop_storage_profile.commodity.casefold():
            raise ValueError("Crop-specific storage profile must match commodity")
        step = self.market_quantity_step_quintals
        if any(q % step for q in (self.total_quantity_quintals, self.decision_increment_quintals, self.minimum_sale_lot_quintals)):
            raise ValueError("Total, decision increment and minimum lot must be multiples of market quantity step")
        if len({o.days for o in self.holding_options}) != len(self.holding_options):
            raise ValueError("Holding durations must be unique")
        if (int(self.total_quantity_quintals // self.decision_increment_quintals) + 2) * max(1, len(self.holding_options)) > 10000:
            raise ValueError("Search exceeds 10,000 evaluations; increase decision increment")
        today = self.decision_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        for option in self.holding_options:
            scenario = option.scenarios
            if scenario and (scenario.market != self.market or scenario.commodity != self.commodity or scenario.variety != self.variety or scenario.grade != self.grade or scenario.target_date != today + timedelta(days=option.days)):
                raise ValueError("Scenario scope/target date must match the request and holding duration")
            if scenario and scenario.issued_at > self.decision_at:
                raise ValueError("Future-issued scenarios cannot inform today's plan")
        return self


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def sale(quantity, price, costs):
    if quantity == 0:
        return {k: D("0.00") for k in ("gross_inr", "commission_inr", "market_fee_inr", "transport_inr", "handling_inr", "fixed_transaction_inr", "net_inr")}
    gross = money(quantity * price)
    fees = money(gross * (costs.market_fee_rate + costs.commission_rate))
    commission = money(gross * costs.commission_rate)
    transport = money(costs.fixed_transport_inr + quantity * costs.transport_inr_per_quintal)
    handling = money(quantity * costs.handling_inr_per_quintal)
    fixed = money(costs.fixed_transaction_inr)
    return {"gross_inr": gross, "commission_inr": commission, "market_fee_inr": fees - commission,
            "transport_inr": transport, "handling_inr": handling, "fixed_transaction_inr": fixed,
            "net_inr": gross - fees - transport - handling - fixed}


def stored_quantity(held, option, step):
    remaining = held
    storage = money(option.fixed_storage_inr)
    for loss, cost in zip(option.daily_loss_fractions, option.daily_storage_inr_per_quintal, strict=False):
        storage += money(remaining * cost)  # Charge on each day's opening quantity.
        remaining *= 1 - loss
    marketable = (remaining / step).to_integral_value(rounding=ROUND_FLOOR) * step
    return marketable, held - remaining, remaining - marketable, storage


def break_even_price(marketable, costs, cash, later_storage, baseline):
    """Lowest price on a paise grid matching sell-all-now net under settlement rounding."""
    def total(cents):
        return cash + sale(marketable, D(cents) * CENT, costs)["net_inr"] - later_storage
    upper = int(MAX_PRICE / CENT)
    if total(upper) < baseline:
        return None
    low = 0
    while low < upper:
        middle = (low + upper) // 2
        if total(middle) >= baseline:
            upper = middle
        else:
            low = middle + 1
    return D(low) * CENT


def risk_score(totals, tolerance):
    weight = {"conservative": D(0), "balanced": D(".5"), "aggressive": D(".8")}[tolerance]
    return money(weight * totals["central"] + (1 - weight) * totals["adverse"])


def _optimize(request):
    r = request
    baseline_sale = sale(r.total_quantity_quintals, r.today_price_inr_per_quintal, r.today_sale_costs)
    baseline = baseline_sale["net_inr"]
    plans, rejected = [], {}
    today_date = r.decision_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    def reject(reason):
        rejected[reason] = rejected.get(reason, 0) + 1
    def plan(sell_now, held, days, cash, costs_today, marketable, loss, rounding_loss, storage, later, scenario_sales, eligible, warning, option=None):
        totals = {key: cash + value["net_inr"] - later for key, value in scenario_sales.items()}
        scores = risk_score(totals, r.risk_tolerance)
        return {"sell_today_quintals": sell_now, "hold_initial_quintals": held, "holding_days": days,
            "later_saleable_quintals": marketable, "deterioration_loss_quintals": loss,
            "rounding_discard_quintals": rounding_loss, "storage_cost_inr": storage,
            "storage_paid_today_inr": storage - later, "storage_paid_later_inr": later,
            "today_sale": costs_today, "cash_today_inr": cash, "cash_surplus_inr": cash - r.required_net_cash_inr,
            "later_sales": scenario_sales, "central_later_net_after_storage_inr": scenario_sales["central"]["net_inr"] - later,
            "total_net_inr": totals, "downside_total_net_inr": totals["adverse"],
            "difference_vs_sell_all_now_inr": {k: v - baseline for k, v in totals.items()},
            "risk_adjusted_objective_inr": scores, "recommendation_eligible": eligible, "warnings": warning,
            "break_even_future_price_inr_per_quintal": break_even_price(marketable, option.future_sale_costs, cash, later, baseline) if option else None,
            "assumptions": option.model_dump(mode="json") if option else {"today": r.today_price_assumption}}
    zero_sale = sale(D(0), D(0), r.today_sale_costs)
    if r.total_quantity_quintals >= r.minimum_sale_lot_quintals and baseline >= r.required_net_cash_inr:
        plans.append(plan(r.total_quantity_quintals, D(0), 0, baseline, baseline_sale, D(0), D(0), D(0), D(0), D(0),
                          {key: zero_sale for key in ("adverse", "lower", "central", "upper")}, True, []))
    else:
        reject("sell_all_below_minimum_lot_or_cash_requirement")
    quantities = [D(i) * r.decision_increment_quintals for i in range(int(r.total_quantity_quintals // r.decision_increment_quintals) + 1)]
    for option in sorted(r.holding_options, key=lambda o: o.days):
        if option.days > min(r.maximum_horizon_days, r.crop_storage_profile.maximum_holding_days):
            reject("holding_duration_exceeds_crop_or_horizon_limit")
            continue
        if option.scenarios is None:
            reject("missing_price_scenarios")
            continue
        scenario = option.scenarios
        current = scenario.issued_at.astimezone(ZoneInfo("Asia/Kolkata")).date() == today_date
        eligible = scenario.reliability_status == "validated" and not scenario.flags and current
        warning = [] if eligible else ["scenario_only_unreliable_or_outdated_prediction"]
        for now in quantities:
            held = r.total_quantity_quintals - now
            if held <= 0:
                continue
            if now and now < r.minimum_sale_lot_quintals:
                reject("today_quantity_below_minimum_lot")
                continue
            if held > r.storage_capacity_quintals:
                reject("storage_capacity")
                continue
            marketable, loss, rounding_loss, storage = stored_quantity(held, option, r.market_quantity_step_quintals)
            if marketable < r.minimum_sale_lot_quintals:
                reject("future_quantity_below_minimum_lot_after_loss")
                continue
            upfront = storage if option.storage_payment == "today" else D(0)
            today_sale = sale(now, r.today_price_inr_per_quintal, r.today_sale_costs)
            cash = today_sale["net_inr"] - upfront
            if cash < r.required_net_cash_inr:
                reject("immediate_net_cash_shortfall")
                continue
            future = {key: sale(marketable, getattr(scenario, key + "_inr_per_quintal"), option.future_sale_costs) for key in ("adverse", "lower", "central", "upper")}
            plans.append(plan(now, held, option.days, cash, today_sale, marketable, loss, rounding_loss, storage, storage - upfront, future, eligible, warning, option))
    def rank(p):
        return (p["risk_adjusted_objective_inr"], p["total_net_inr"]["central"], p["downside_total_net_inr"], -p["holding_days"])
    safe = [p for p in plans if p["recommendation_eligible"]]
    selected = max(safe, key=rank) if safe else None
    best_scenario = max(plans, key=rank) if plans else None
    # Upper bound of cash from marketable today-only transactions; upfront costs
    # cannot improve it. It is an achievability check, not a promise of a buyer.
    today_quantities = sorted(set(quantities + [r.total_quantity_quintals]))
    max_cash = max([D(0)] + [sale(q, r.today_price_inr_per_quintal, r.today_sale_costs)["net_inr"] for q in today_quantities if q >= r.minimum_sale_lot_quintals])
    if selected:
        status = "recommended" if selected["holding_days"] else "sell_all_now"
    elif plans:
        status = "scenario_only_no_validated_recommendation"
    else:
        status = "no_feasible_plan" if r.total_quantity_quintals < r.minimum_sale_lot_quintals else "no_feasible_cash_solution"
    explanations = [
        "All money is INR, prices INR/quintal and quantity quintals. Each sale pays gross less percentage fees, transport, handling and fixed transaction costs.",
        "Fixed sale costs apply only to a nonzero transaction. Separate today and future sales incur separate fixed costs.",
        "Percentage fees are rounded once on the combined rate; commission is allocated first and the residual fee goes to the market-fee line.",
        "Daily deterioration compounds on remaining quantity. Storage charges use that day's opening quantity. Storage payment timing changes cash today.",
        "Future marketable quantity rounds down to the market step. Deterioration and rounding discards have zero assumed salvage value; disposal costs are not included.",
        "Central later proceeds are a planning scenario, not a probability-weighted expected value. Risk weights are utility preferences, not scenario probabilities.",
        "Conservative objective=adverse net; balanced=.5 central+.5 adverse; aggressive=.8 central+.2 adverse. Ties prefer downside, more sold today, then shorter holding.",
        "All enumerated plans meet mandatory immediate cash and storage/lot constraints. Scenario-only plans cannot be promoted as hold recommendations.",
        "Crop holding limits, loss schedules, price-realization adjustments and cost assumptions are user-supplied; no universal tomato spoilage rate is assumed.",
        "Forecast bands describe wholesale mandi statistics, not guaranteed farmer transaction prices. No plan guarantees a buyer, future cash or profit.",
    ]
    unreliable = any(o.scenarios is None or o.scenarios.reliability_status != "validated" or o.scenarios.flags or o.scenarios.issued_at.astimezone(ZoneInfo("Asia/Kolkata")).date() != today_date for o in r.holding_options)
    basis = "validated_scenario_risk_objective" if selected and selected["holding_days"] else "today_only_safe_fallback" if selected and unreliable else "sell_all_by_costs_constraints_or_objective" if selected else "no_validated_recommendation"
    return {"schema_version": "samay-selling-v1", "status": status, "recommendation_basis": basis,
        "has_unreliable_or_missing_scenarios": bool(unreliable), "decision_at": r.decision_at.isoformat(),
        "scope": {k: getattr(r, k) for k in ("commodity", "market", "variety", "grade")}, "units": {"money": "INR", "price": "INR/quintal", "quantity": "quintals"},
        "sell_all_now": {"sale": baseline_sale, "meets_minimum_lot": r.total_quantity_quintals >= r.minimum_sale_lot_quintals, "meets_cash_requirement": baseline >= r.required_net_cash_inr},
        "maximum_today_net_cash_upper_bound_inr": max_cash, "cash_requirement_achievable_on_grid": bool(plans),
        "recommended_plan": selected, "best_scenario_only_or_validated_plan": best_scenario,
        "feasible_plans": plans, "rejected_counts": rejected, "risk_tolerance": r.risk_tolerance,
        "request_and_assumptions": r.model_dump(mode="json"), "explanations": explanations}


def optimize_selling(request: SellingRequest | dict) -> dict:
    """No I/O, clock access, random numbers, fitted models or mutable global state."""
    with localcontext() as context:
        context.prec = 40
        context.rounding = ROUND_HALF_UP
        validated = SellingRequest.model_validate(request)
        return _optimize(validated)


def scenarios_from_reliability(response, *, adverse_inr_per_quintal: Decimal,
                               realization_multiplier: Decimal, price_basis_assumption: str,
                               adverse_assumption: str) -> PriceScenarios | None:
    """Bridge the reliability service, explicitly mapping mandi prices to farmer sale scenarios."""
    if response.prediction_inr_per_quintal is None or not response.intervals:
        return None
    multiplier = D(str(realization_multiplier))
    if not multiplier.is_finite() or not D(0) < multiplier <= D(2):
        raise ValueError("Realization multiplier must be finite and in (0,2]")
    interval = max(response.intervals, key=lambda i: i.nominal_level)
    return PriceScenarios(adverse_inr_per_quintal=adverse_inr_per_quintal,
        lower_inr_per_quintal=money(D(str(interval.lower_inr_per_quintal)) * multiplier),
        central_inr_per_quintal=money(D(str(response.prediction_inr_per_quintal)) * multiplier),
        upper_inr_per_quintal=money(D(str(interval.upper_inr_per_quintal)) * multiplier),
        reliability_status=response.reliability_status, market=response.market, commodity=response.commodity,
        variety=response.variety, grade=response.grade, target_date=response.target_date, issued_at=response.timestamp,
        model_version=response.model_version,
        source="Saved forecast service: " + str(response.data_source.get("source") or response.data_source.get("mode") or "official archived observations")[:800] + "; full source lineage is in predictions.data_source",
        flags=tuple(response.flags),
        price_basis_assumption=price_basis_assumption, adverse_assumption=adverse_assumption)
