"""Historical cash decisions: freeze inputs first, score exact later dates separately."""
import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean, median

import pandas as pd

from app.features import asof, midnight
from app.reliability import reliability_response
from app.selling import SellingRequest, money, optimize_selling, sale, scenarios_from_reliability

LIMITATIONS = [
    "Today quote is the latest observation available before midnight, multiplied by the declared realization factor.",
    "Realized sales use exact decision/target-date modal prices as a proxy, not actual farmer transaction receipts.",
    "Missing dates are unscored; no interpolation. Scoring uses revisions known at the declared freeze only.",
    "Independent decision experiments reuse the same crop quantity; this is not a cumulative trading portfolio.",
    "Costs, daily compounded deterioration, storage payment and market-step losses are explicit user assumptions.",
    "No buyer availability, disposal cost or grade-specific realization guarantee is modeled.",
    "Final holdout is inaccessible here. No valid forecasts means today-only fallback, not synthetic hold profits.",
]


def replay(vintages, plan, start, end, freeze, template, provenance, *, realization_multiplier=Decimal("1"),
           evidence=None, champions=None):
    if not plan.start <= start <= end <= plan.validation_end or not end < freeze <= plan.validation_end + timedelta(days=1):
        raise ValueError("Decision/scoring windows must stay in development; final holdout access prohibited")
    multiplier = Decimal(str(realization_multiplier))
    if not multiplier.is_finite() or not 0 < multiplier <= 2:
        raise ValueError("Explicit realization multiplier must be in (0,2]")
    base = SellingRequest.model_validate(template)
    scope = {key: getattr(plan, key) for key in ("market", "commodity", "variety", "grade")}
    if any(getattr(base, key) != value for key, value in scope.items()):
        raise ValueError("Template and source series must match")
    labels = {r.report_date: r for r in asof(vintages, midnight(freeze), inclusive=False).itertuples()}
    records, audits = [], []
    for stamp in pd.date_range(start, end):
        origin = stamp.date()
        history = asof(vintages, midnight(origin), before=origin)
        record = {"decision_date": origin.isoformat(), "status": "no_available_quote", "target_date": None,
                  "gain_vs_sell_all_inr": None, "realized_total_net_inr": None, "sell_all_realized_net_inr": None,
                  "cash_constraint_satisfied": None, "model_versions": "", "flags": "", "sell_today_quintals": None,
                  "hold_quintals": None, "cash_today_quoted_inr": None, "realized_cash_today_inr": None,
                  "actual_today_row_id": None, "actual_future_row_id": None}
        if history.empty:
            records.append(record)
            continue
        payload = base.model_dump(mode="json")
        payload["decision_at"] = midnight(origin).isoformat()
        payload["today_price_inr_per_quintal"] = str(money(Decimal(str(history.iloc[-1].price)) * multiplier))
        payload["today_price_assumption"] = "BACKTEST_PROXY latest historically available modal price × declared realization multiplier"
        versions, flags = [], []
        for option in payload["holding_options"]:
            forecast = reliability_response(vintages, plan, origin, option["days"], provenance, evidence,
                Path(champions) / f"champion-{option['days']}d" if champions else None)
            # An adverse zero-price stress is predeclared, not a forecast quantile.
            scenario = scenarios_from_reliability(forecast, adverse_inr_per_quintal=Decimal(0), realization_multiplier=multiplier,
                price_basis_assumption="BACKTEST_PROXY modal price × declared realization multiplier",
                adverse_assumption="Predeclared zero-price stress; not a probability or estimated quantile")
            option["scenarios"] = scenario.model_dump(mode="json") if scenario else None
            versions.append(forecast.model_version or "unavailable")
            flags.extend(forecast.flags)
        request = SellingRequest.model_validate(payload)
        decision = optimize_selling(request)
        chosen = decision["recommended_plan"]
        audits.append({"decision_date": origin.isoformat(), "latest_available_at": history.available_at.max().isoformat(),
                      "feature_source_row_ids": history.row_id.tolist(), "decision": decision})
        record.update(status=decision["status"], model_versions="|".join(sorted(set(versions))), flags="|".join(sorted(set(flags))))
        if chosen is None:
            records.append(record)
            continue
        target = origin + timedelta(days=chosen["holding_days"])
        record.update(target_date=target.isoformat(), sell_today_quintals=str(chosen["sell_today_quintals"]),
            hold_quintals=str(chosen["hold_initial_quintals"]), cash_today_quoted_inr=str(chosen["cash_today_inr"]))
        today = labels.get(origin)
        future = labels.get(target) if target <= end else None
        if today is None or (chosen["holding_days"] and future is None):
            record["flags"] += "|missing_exact_scoring_observation"
            records.append(record)
            continue
        actual_today_price = money(Decimal(str(today.price)) * multiplier)
        today_net = sale(chosen["sell_today_quintals"], actual_today_price, request.today_sale_costs)["net_inr"]
        today_net -= chosen["storage_paid_today_inr"]
        later_net = Decimal(0)
        if chosen["holding_days"]:
            option = next(o for o in request.holding_options if o.days == chosen["holding_days"])
            later_net = sale(chosen["later_saleable_quintals"], money(Decimal(str(future.price)) * multiplier), option.future_sale_costs)["net_inr"]
        total = today_net + later_net - chosen["storage_paid_later_inr"]
        baseline = sale(request.total_quantity_quintals, actual_today_price, request.today_sale_costs)["net_inr"]
        record.update(realized_total_net_inr=str(total), sell_all_realized_net_inr=str(baseline), gain_vs_sell_all_inr=str(total - baseline),
            realized_cash_today_inr=str(today_net), cash_constraint_satisfied=today_net >= request.required_net_cash_inr,
            actual_today_row_id=int(today.row_id), actual_future_row_id=int(future.row_id) if chosen["holding_days"] else None)
        records.append(record)
    scored = [r for r in records if r["gain_vs_sell_all_inr"] is not None]
    gains = [Decimal(r["gain_vs_sell_all_inr"]) for r in scored]
    summary = {"schema_version": "samay-decisions-v1", "status": "scored" if scored else "insufficient_data",
        "scope": scope, "decision_start": start.isoformat(), "decision_end": end.isoformat(), "scoring_freeze": freeze.isoformat(),
        "decision_dates": len(records), "scored_decisions": len(scored), "unscored_decisions": len(records) - len(scored),
        "mean_gain_inr": str(money(mean(gains))) if gains else None, "median_gain_inr": str(money(median(gains))) if gains else None,
        "win_rate": sum(g > 0 for g in gains) / len(gains) if gains else None,
        "worst_gain_inr": str(min(gains)) if gains else None, "worst_loss_inr": str(max(Decimal(0), -min(gains))) if gains else None,
        "cash_constraint_success_rate": sum(r["cash_constraint_satisfied"] for r in scored) / len(scored) if scored else None,
        "recommended_hold_count": sum(r["hold_quintals"] is not None and Decimal(r["hold_quintals"]) > 0 for r in records),
        "no_feasible_plan_count": sum(r["status"].startswith("no_feasible") for r in records),
        "realization_multiplier": str(multiplier), "source": provenance, "limitations": LIMITATIONS,
        "final_holdout": "unopened", "money_unit": "INR", "quantity_unit": "quintals"}
    return records, audits, summary


def save_report(output, records, audits, summary, template):
    manifest = {**summary, "template": template}
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True, default=str).encode()).hexdigest()[:16]
    folder = Path(output) / f"samay-decisions-v1-{digest}"
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(folder / "decisions-vs-actual.csv", index=False)
    (folder / "decisions.jsonl").write_text("\n".join(json.dumps(row, default=str) for row in audits), encoding="utf-8")
    manifest["artifact_sha256"] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.suffix in {".csv", ".jsonl"}}
    (folder / "summary.json").write_text(json.dumps(manifest, indent=2, default=str, allow_nan=False), encoding="utf-8")
    return folder
