"""Auditable development-window backtests; the final test remains protected."""
import hashlib
import json
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from app.features import load_vintages, midnight
from app.reliability import (
    DISCLAIMER,
    POLICY,
    VERSION,
    calibrate,
    dated_predictions,
    evaluate,
)
from app.training import read_plan


def plots(folder, frames):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    all_rows = pd.concat(frames, ignore_index=True)
    valid = all_rows.dropna(subset=["actual", "prediction"])
    for name in ("predicted_vs_actual", "residuals_over_time", "error_by_horizon", "error_by_season"):
        fig, ax = plt.subplots(figsize=(10, 4), constrained_layout=True)
        ax.set_title(name.replace("_", " ").title() + " — unseen development assessment")
        if valid.empty:
            ax.text(.5, .5, "UNAVAILABLE\nNo authenticated held-out prediction/actual pairs.\nNo synthetic market results substituted.", ha="center", va="center", transform=ax.transAxes)
            ax.set_xticks([])
            ax.set_yticks([])
        elif name == "predicted_vs_actual":
            for horizon, group in valid.groupby("horizon"):
                ax.plot(pd.to_datetime(group.target_date), group.prediction, label=f"{horizon}d predicted", alpha=.8)
                ax.scatter(pd.to_datetime(group.target_date), group.actual, s=5, label=f"{horizon}d actual")
            ax.set_ylabel("INR/quintal")
            ax.legend(fontsize=8)
        elif name == "residuals_over_time":
            for horizon, group in valid.groupby("horizon"):
                ax.scatter(pd.to_datetime(group.target_date), group.residual, s=8, label=f"{horizon}d")
            ax.axhline(0, color="grey", linewidth=.6)
            ax.set_ylabel("Actual − predicted (INR/quintal)")
            ax.legend()
        elif name == "error_by_horizon":
            group = valid.groupby("horizon").absolute_error.agg(["mean", "count"])
            ax.bar(group.index, group["mean"])
            for horizon, row in group.iterrows():
                ax.annotate(f"n={int(row['count'])}", (horizon, row["mean"]), ha="center")
            ax.set_ylabel("MAE (INR/quintal)")
            ax.set_xlabel("Calendar-day horizon")
        else:
            copy = valid.copy()
            # Month is explicit; avoid asserting agronomic seasons without a local definition.
            copy["month"] = pd.to_datetime(copy.target_date).dt.month
            for horizon, group in copy.groupby("horizon"):
                average = group.groupby("month").absolute_error.agg(["mean", "count"])
                ax.plot(average.index, average["mean"], marker="o", label=f"{horizon}d")
                for month, row in average.iterrows():
                    ax.annotate(f"n={int(row['count'])}", (month, row["mean"]), fontsize=7)
            ax.set_xlabel("Target calendar month (descriptive seasonality)")
            ax.set_ylabel("MAE (INR/quintal)")
            ax.legend()
        fig.savefig(folder / f"{name}.png", dpi=140)
        plt.close(fig)


def run_backtest(session, feature_run: Path, calibration_start, calibration_end, evaluation_end,
                 output: Path = Path("reports/backtests"), champions: Path | None = None):
    plan, metadata = read_plan(feature_run)
    if not plan.start <= calibration_start < calibration_end < evaluation_end <= plan.validation_end:
        raise ValueError("Require plan.start <= calibration_start < calibration_end < evaluation_end <= validation_end; final holdout access is prohibited")
    scope = {key: getattr(plan, key) for key in ("market", "commodity", "variety", "grade")}
    # The production loader still excludes final holdout dates and later snapshots.
    vintages, source = load_vintages(session, plan)
    source_hash = hashlib.sha256(vintages.to_csv(index=False).encode()).hexdigest()
    if source_hash != metadata["vintages_sha256"]:
        raise ValueError("Source ledger changed; rebuild versioned feature artifacts first")
    models = {}
    for horizon in (1, 3, 7):
        model = champions / f"champion-{horizon}d" if champions else None
        model_version = "predeclared-naive-v1"
        digest = None
        if model is not None:
            meta = json.loads((model / "metadata.json").read_text())
            if pd.Timestamp(meta["trained_before"]) > midnight(calibration_start) or meta["horizon"] != horizon or any(meta[key] != value for key, value in scope.items()):
                raise ValueError("Champion must be frozen before calibration starts and match the selected series/horizon")
            if meta["feature_schema"] != metadata["feature_columns"]:
                raise ValueError("Champion/feature schema mismatch")
            digest = hashlib.sha256((model / "model.pkl").read_bytes()).hexdigest()
            if digest != meta["model_sha256"]:
                raise ValueError("Champion integrity mismatch")
            model_version = meta["version"]
        models[horizon] = (model, model_version, digest)
    config = {"version": VERSION, "price_unit": "INR/quintal", "scope": scope, "calibration_start": calibration_start.isoformat(), "calibration_end": calibration_end.isoformat(),
              "evaluation_end": evaluation_end.isoformat(), "source_sha256": source_hash, "source": source, "policy": POLICY,
              "models": {str(h): {"version": v, "model_sha256": digest} for h, (_, v, digest) in models.items()},
              "code": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ("backtesting.py", "reliability.py", "forecasting.py", "features.py")}}
    fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:16]
    final = output / (VERSION + "-" + fingerprint)
    output.mkdir(parents=True, exist_ok=True)
    if final.exists():
        summary = json.loads((final / "summary.json").read_text())
        for name, digest in summary["artifact_sha256"].items():
            if hashlib.sha256((final / name).read_bytes()).hexdigest() != digest:
                raise ValueError("Immutable backtest artifact was modified")
        return final, summary
    with tempfile.TemporaryDirectory(prefix=".building-", dir=output) as temporary:
        folder = Path(temporary) / "run"
        folder.mkdir()
        horizons, frames = [], []
        for horizon in (1, 3, 7):
            model, model_version, _ = models[horizon]
            calibration_rows = dated_predictions(vintages, plan, calibration_start, calibration_end, horizon, calibration_end + timedelta(days=1), model)
            calibration = calibrate(calibration_rows, horizon, calibration_end + timedelta(days=1), scope, model_version)
            evaluation_rows = dated_predictions(vintages, plan, calibration_end + timedelta(days=1), evaluation_end, horizon, evaluation_end + timedelta(days=1), model)
            evaluation_rows, result = evaluate(evaluation_rows, calibration)
            calibration_rows.to_csv(folder / f"calibration-{horizon}d.csv", index=False)
            evaluation_rows.to_csv(folder / f"evaluation-{horizon}d.csv", index=False)
            frames.append(evaluation_rows)
            horizons.append({"horizon": horizon, "model_version": model_version, "calibration": calibration, "assessment": result,
                             "flag_counts": evaluation_rows["flags"].str.split("|").explode().loc[lambda s: s != ""].value_counts().to_dict()})
        plots(folder, frames)
        summary = {**config, "created_at": datetime.now(UTC).isoformat(), "horizons": horizons,
                   "status": "assessment_available" if any(h["assessment"]["n"] for h in horizons) else "insufficient_data",
                   "final_holdout": "unopened; all rows are in the development partition", "disclaimer": DISCLAIMER,
                   "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()}}
        (folder / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False), encoding="utf-8")
        folder.rename(final)
    return final, summary
