"""Training-period insights and immutable feature artifacts; never evaluate holdout."""
import hashlib
import json
import platform
import tempfile
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from app.features import (
    DEFINITIONS,
    FEATURES,
    VERSION,
    Plan,
    asof,
    build_horizon,
    midnight,
)


def write_insights(vintages, plan: Plan, folder: Path, provenance: dict) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    frame = asof(vintages, midnight(plan.train_end + timedelta(days=1)), inclusive=False)
    if len(frame):
        frame = frame[(frame.report_date >= plan.start) & (frame.report_date <= plan.train_end)].copy()
    days = pd.date_range(plan.start, plan.train_end)
    observed = pd.Series(np.nan, index=days, dtype=float)
    if len(frame):
        observed.loc[pd.to_datetime(frame.report_date)] = frame.price.to_numpy()
    missing = observed.isna()
    # Volatility describes consecutive observed returns, not equal-length daily returns.
    prices = observed.dropna()
    returns = prices.pct_change(fill_method=None).dropna() * 100
    weekday, month = [], []
    for key, group in prices.groupby(prices.index.weekday):
        weekday.append({"weekday": int(key), "mean_inr_per_quintal": float(group.mean()), "count": len(group)})
    for key, group in prices.groupby(prices.index.month):
        month.append({"month": int(key), "mean_inr_per_quintal": float(group.mean()), "count": len(group)})
    summary = {
        "scope": {"market": plan.market, "commodity": plan.commodity, "variety": plan.variety, "grade": plan.grade},
        "analysis_partition": "train only; no validation or final holdout descriptive statistics",
        "observed_dates": len(prices), "calendar_dates": len(days), "missing_dates_count": int(missing.sum()),
        "date_range": [plan.start.isoformat(), plan.train_end.isoformat()],
        "missing_dates": [d.date().isoformat() for d in observed.index[missing]],
        "mean_inr_per_quintal": float(prices.mean()) if len(prices) else None,
        "median_inr_per_quintal": float(prices.median()) if len(prices) else None,
        "observed_return_std_pct": float(returns.std(ddof=1)) if len(returns) > 1 else None,
        "volatility_note": "Unannualized percent returns between consecutive observations with unequal calendar gaps; not daily volatility or forecast uncertainty",
        "weekday": weekday, "month": month,
        "price_series": [{"date": d.date().isoformat(), "modal_price_inr_per_quintal": float(p)} for d, p in prices.items()],
        "return_series": [{"date": d.date().isoformat(), "observed_return_pct": float(r)} for d, r in returns.items()],
        "quality": {"kind": "official only", "snapshot_observations": len(prices), "missing_calendar_dates": int(missing.sum()),
                    "note": "Partition-local completeness only. Source-wide quarantine counts are not exposed because they may include holdout dates."},
        "caveat": "Descriptive associations, not evidence of predictable seasonality; sparse groups and short history cannot establish seasonal effects. Wholesale prices are not farmer realization prices.",
        "status": "observations_available" if len(prices) else "insufficient_data_no_point_in_time_official_observations",
    }
    titles = {"price_over_time": "Observed modal price (INR/quintal)", "weekday_seasonality": "Weekday mean prices (descriptive)", "month_seasonality": "Month mean prices (descriptive)", "observed_volatility": "Consecutive-observation returns (%)", "missing_dates": "Calendar reporting availability", "data_quality": "Training-period reporting quality"}
    for name, title in titles.items():
        fig, ax = plt.subplots(figsize=(9, 4), constrained_layout=True)
        ax.set_title(f"{plan.market} / {plan.commodity} / {plan.variety} / {plan.grade}\n{title} — training partition only", fontsize=10)
        if not len(prices):
            ax.text(.5, .5, "INSUFFICIENT DATA\nNo authenticated point-in-time observations available.\nFixture prices are excluded; no values fabricated.", ha="center", va="center", transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        elif name == "price_over_time":
            ax.plot(observed.index, observed.values, marker=".", markersize=3)
            ax.set_ylabel("INR/quintal")
        elif name in {"weekday_seasonality", "month_seasonality"}:
            records, key = (weekday, "weekday") if name.startswith("weekday") else (month, "month")
            ax.bar([x[key] for x in records], [x["mean_inr_per_quintal"] for x in records])
            for r in records:
                ax.annotate(f"n={r['count']}", (r[key], r["mean_inr_per_quintal"]), ha="center", va="bottom", fontsize=8)
            ax.set_ylabel("Mean INR/quintal")
            ax.set_xlabel("Weekday (Monday=0)" if key == "weekday" else "Month")
        elif name == "observed_volatility":
            ax.plot(returns.index, returns.values, marker=".")
            ax.axhline(0, color="grey", linewidth=.5)
            ax.set_ylabel("Change since preceding observation (%)")
        elif name == "missing_dates":
            ax.scatter(observed.index, (~missing).astype(int), s=5)
            ax.set_yticks([0, 1], labels=["Unreported", "Observed"])
        else:
            ax.bar(["Observed dates", "Unreported dates"], [len(prices), int(missing.sum())])
            ax.set_ylabel("Calendar dates")
        fig.savefig(folder / f"{name}.png", dpi=140)
        plt.close(fig)
    (folder / "market_insights.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
    return summary


def write_run(vintages: pd.DataFrame, plan: Plan, provenance: dict, output: Path) -> tuple[Path, dict]:
    plan.validate()
    output.mkdir(parents=True, exist_ok=True)
    # A local freeze prevents casual boundary changes after inspecting development data.
    scope = {k: getattr(plan, k) for k in ("market", "commodity", "variety", "grade")}
    lock_path = output / "holdout_registry.json"
    registry = json.loads(lock_path.read_text()) if lock_path.exists() else {}
    scope_key = json.dumps(scope, sort_keys=True)
    boundaries = {k: plan.serializable()[k] for k in ("start", "train_end", "validation_end", "holdout_end")}
    if scope_key in registry and registry[scope_key] != boundaries:
        raise ValueError("Holdout boundaries already frozen for this series; do not move them after inspection")
    registry[scope_key] = boundaries
    # Exclusive creation for the first run; subsequent edits require a single operator.
    if not lock_path.exists():
        with lock_path.open("x", encoding="utf-8") as handle:
            json.dump(registry, handle, indent=2)
    else:
        lock_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    code_hashes = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ("features.py", "analysis.py")}
    payload = {"version": VERSION, "plan": plan.serializable(), "provenance": provenance, "code_sha256": code_hashes,
               "runtime": {"python": platform.python_version(), **{name: version(name) for name in ("pandas", "numpy", "matplotlib")}},
               "vintages_sha256": hashlib.sha256(vintages.to_csv(index=False).encode()).hexdigest()}
    run_id = VERSION + "-" + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]
    final = output / run_id
    if final.exists():
        # Immutable reruns reuse previously committed artifacts, detecting tampering.
        meta = json.loads((final / "metadata.json").read_text())
        for name, digest in meta["artifact_sha256"].items():
            if hashlib.sha256((final / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Changed artifact in immutable run: {name}")
        return final, meta
    with tempfile.TemporaryDirectory(prefix=".building-", dir=output) as temporary:
        folder = Path(temporary) / "run"
        folder.mkdir()
        summaries = []
        for horizon in (1, 3, 7):
            frame, summary = build_horizon(vintages, plan, horizon)
            summaries.append(summary)
            target = folder / f"horizon-{horizon}d"
            target.mkdir()
            # Audits can contain labels. Only explicitly allowlisted X columns are predictors.
            frame.to_csv(target / "development_audit.csv", index=False)
            for split in ("train", "validation"):
                eligible = frame[(frame.split == split) & (frame.reason == "eligible")]
                eligible[["origin_date"] + FEATURES].to_csv(target / f"{split}_X.csv", index=False)
                eligible[["origin_date", "target_date", "target_modal_price_inr_per_quintal"]].to_csv(target / f"{split}_y.csv", index=False)
            holdout = pd.date_range(plan.validation_end + timedelta(days=1), plan.holdout_end)
            pd.DataFrame({"origin_date": [d.date().isoformat() for d in holdout], "target_date": [(d.date() + timedelta(days=horizon)).isoformat() for d in holdout],
                          "evaluation_eligible_by_boundary": [(d.date() + timedelta(days=horizon)) <= plan.holdout_end for d in holdout]}).to_csv(target / "holdout_plan_no_values.csv", index=False)
        insights = write_insights(vintages, plan, folder, provenance)
        meta = {**payload, "run_id": run_id, "created_at": datetime.now(UTC).isoformat(),
                "status": "insufficient_data" if all(s["status"] == "insufficient_data" for s in summaries) else "development_features_available_not_trained",
                "feature_columns": FEATURES, "definitions": DEFINITIONS, "horizons": summaries,
                "holdout_policy": "No holdout features, targets, statistics or evaluation materialized. Reserve dates only. Do not tune on final holdout.",
                "fitting_policy": "Tune only on train/validation; no scalers/imputers fitted. Any future preprocessing must fit train only. Origins with missing targets/history excluded explicitly.",
                "authentication_limit": "Operator-attested official archive provenance is not independent source authentication. No fixture/demo override exists in CLI.",
                "insights_status": insights["status"]}
        meta["artifact_sha256"] = {str(path.relative_to(folder)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(folder.rglob("*")) if path.is_file()}
        (folder / "metadata.json").write_text(json.dumps(meta, indent=2, allow_nan=False), encoding="utf-8")
        folder.rename(final)
    return final, meta
