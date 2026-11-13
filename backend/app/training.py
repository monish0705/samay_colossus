"""Artifact-backed development selection and one-shot chronological evaluation."""
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.features import Plan, load_vintages
from app.forecasting import (
    VERSION,
    examples,
    runtime_versions,
    save_champion,
    score,
    select_horizon,
)


def read_plan(feature_run: Path):
    metadata = json.loads((feature_run / "metadata.json").read_text())
    for name, expected in metadata["artifact_sha256"].items():
        path = (feature_run / name).resolve()
        if not path.is_relative_to(feature_run.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Feature run integrity check failed")
    raw = dict(metadata["plan"])
    for name in ("start", "train_end", "validation_end", "holdout_end"):
        raw[name] = date.fromisoformat(raw[name])
    plan = Plan(**raw)
    plan.validate()
    return plan, metadata


def train_run(session, feature_run: Path, output: Path, evaluate_final=False):
    plan, feature_meta = read_plan(feature_run)
    vintages, provenance = load_vintages(session, plan)
    data_hash = hashlib.sha256(vintages.to_csv(index=False).encode()).hexdigest()
    if data_hash != feature_meta["vintages_sha256"]:
        raise ValueError("Source ledger changed; build a new versioned feature run first")
    code = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ("training.py", "forecasting.py", "features.py")}
    fingerprint = hashlib.sha256(json.dumps({"source": data_hash, "plan": plan.serializable(), "provenance": provenance, "code": code,
        "runtime": runtime_versions()}, sort_keys=True).encode()).hexdigest()
    root = output / (VERSION + "-" + fingerprint[:16])
    report_path = root / "comparison.json"
    if report_path.exists():
        report = json.loads(report_path.read_text())
        # Reruns return the existing frozen comparison, never fit against final feedback.
        if evaluate_final and report.get("status") == "selected" and report.get("final_evaluation") is None:
            raise ValueError("Frozen run exists without final evaluation; use a fresh explicitly reviewed evaluation workflow, not automatic retraining")
        return root, report
    from app.holdout_guard import assert_untouched
    for horizon in (1,3,7):
        assert_untouched(output/"final_evaluation_registry",plan,horizon)
    root.mkdir(parents=True, exist_ok=False)
    report = {"version": root.name, "dataset_fingerprint": fingerprint, "source_vintages_sha256": data_hash,
        "runtime": runtime_versions(),
        "source": provenance, "plan": plan.serializable(), "code_sha256": code,
        "metric_policy": "INR/quintal MAE/RMSE; percentage sMAPE/WAPE; tiny denominator threshold INR .01; direction includes ties within .01. p90 overprediction is downside risk from optimistic prices.",
        "horizons": [], "final_evaluation": None}
    selected = []
    for horizon in (1, 3, 7):
        comparison, model, development = select_horizon(vintages, plan, horizon)
        report["horizons"].append(comparison)
        if comparison["champion"]:
            folder = root / f"champion-{horizon}d"
            save_champion(folder, comparison, model, development, plan, fingerprint)
            selected.append((horizon, comparison, model, folder))
    report["status"] = "selected" if selected else "insufficient_data"
    # Write frozen selection BEFORE any final target loader can execute.
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    if evaluate_final and selected:
        locks = []
        audit = output / "final_evaluation_registry"
        audit.mkdir(exist_ok=True)
        for horizon, _, _, folder in selected:
            # Key excludes model version, dataset and code to stop re-testing new champions
            # on the same series/holdout after seeing its final outcomes.
            key = {k: getattr(plan, k) for k in ("market", "commodity", "variety", "grade")}
            key.update(horizon=horizon, holdout_start=(plan.validation_end + timedelta(days=1)).isoformat(), holdout_end=plan.holdout_end.isoformat())
            lock = audit / (hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest() + ".json")
            try:
                with lock.open("x", encoding="utf-8") as handle:
                    json.dump({"state": "reserved_before_read", "model_version": root.name, "model_sha256": hashlib.sha256((folder / "model.pkl").read_bytes()).hexdigest(), "key": key}, handle)
            except FileExistsError as exc:
                raise ValueError("Final holdout already reserved/evaluated for this series/horizon; no second evaluation permitted") from exc
            locks.append(lock)
        final_vintages, final_provenance = load_vintages(session, plan, final_evaluation=True)
        final = []
        for (horizon, comparison, model, _), lock in zip(selected, locks, strict=False):
            test = examples(final_vintages, plan.validation_end + timedelta(days=1), plan.holdout_end, horizon, plan.holdout_end + timedelta(days=1))
            result = {"horizon": horizon, "champion": comparison["champion"], "n": len(test), "status": "evaluated" if len(test) >= 30 else "insufficient_final_samples",
                      "metrics": score(comparison["champion"], model, test) if len(test) >= 30 else None}
            result["naive_metrics_same_timestamps"] = score("naive", None, test) if len(test) >= 30 else None
            result["rolling_median_metrics_same_timestamps"] = score("median_14", None, test) if len(test) >= 30 else None
            if len(test) >= 30:
                from app.forecasting import predict_rows
                predictions = test[["origin_date", "target_date", "target_modal_price_inr_per_quintal"]].copy()
                predictions["prediction_inr_per_quintal"] = predict_rows(comparison["champion"], model, test)
                predictions.to_csv(root / f"final-predictions-{horizon}d.csv", index=False)
            final.append(result)
            reservation=json.loads(lock.read_text())
            lock.write_text(json.dumps({"state": "consumed", "model_version": root.name, "key":reservation["key"], "result": result}, indent=2), encoding="utf-8")
        report["final_evaluation"] = {"results": final, "source": final_provenance, "evaluated_at": datetime.now(UTC).isoformat()}
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    lines = ["# SAMAY model comparison", "", f"Status: {report['status']}", "", "Wholesale modal prices in INR/quintal. No percentage here represents guaranteed farmer outcomes.", ""]
    for item in report["horizons"]:
        lines.extend([f"## Horizon {item['horizon']} calendar days", "", f"Champion: {item['champion'] or 'none — insufficient data'}", "", "| Candidate | Validation MAE | CV mean MAE | CV MAE std | Validation p90 overprediction |", "| --- | ---: | ---: | ---: | ---: |"])
        for row in item["comparisons"]:
            lines.append(f"| {row['candidate']} | {row['validation']['mae_inr_per_quintal']:.4f} | {row['cv_mean_mae']:.4f} | {row['cv_std_mae']:.4f} | {row['validation']['p90_overprediction_inr_per_quintal']:.4f} |")
        if not item["comparisons"]:
            lines.append("\nNo comparison metrics computed: " + "; ".join(item.get("reason", [])))
    lines.extend(["", "Final evaluation: " + ("see comparison.json" if report["final_evaluation"] else "not opened / not evaluated"), "", "No comparison metrics have been fabricated. Validation is used for selection and is not an unbiased final performance estimate."])
    (root / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    return root, report
