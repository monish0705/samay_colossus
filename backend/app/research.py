"""Explicitly authorized retrospective snapshot research; never production validation.

Download times remain intact in SQLite and audit exports. A temporary feature-view
assumes publication at next-day midnight for this conditional experiment only.
Original publication/revision histories have not been verified.
"""
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
from sqlalchemy import select

from app.features import Plan, asof, empty_vintages, midnight
from app.forecasting import examples, predict_rows, runtime_versions, save_champion, score, select_horizon
from app.ingestion import SourceManifest, district_name, market_district
from app.models import ImportBatch, ImportRow

LIMITATION = ("RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. "
              "Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. "
              "Later source revisions may be present. Metrics are conditional on this assumption, "
              "not demonstrated live/as-of performance or farmer realized-price accuracy. "
              "Artifacts cannot be deployed as validated production forecasts.")


def snapshot(session, plan: Plan, *, final=False):
    """SQL excludes holdout rows unless final evaluation was explicitly reserved."""
    end = plan.holdout_end if final else plan.validation_end
    stmt = select(ImportRow, ImportBatch).join(ImportBatch, ImportRow.batch_id == ImportBatch.id).where(
        ImportBatch.data_kind == plan.source_kind, ImportRow.status.in_(["inserted", "revised", "duplicates"]),
        ImportRow.normalized["report_date"].as_string() >= plan.start.isoformat(),
        ImportRow.normalized["report_date"].as_string() <= end.isoformat(),
        ImportRow.normalized["market"].as_string() == plan.market,
        ImportRow.normalized["commodity"].as_string() == plan.commodity,
        ImportRow.normalized["variety"].as_string() == plan.variety,
        ImportRow.normalized["grade"].as_string() == plan.grade)
    rows, sources = [], {}
    for row, batch in session.execute(stmt):
        if batch.id not in sources:
            manifest = SourceManifest.model_validate(batch.manifest)
            path = Path(batch.archive_path)
            if manifest.data_kind != plan.source_kind or manifest.source_url != batch.source_url or manifest.fetched_at != batch.fetched_at:
                raise ValueError("Snapshot source manifest mismatch")
            allowed = ("https://agmarknet.gov.in/", "https://www.agmarknet.gov.in/", "https://data.gov.in/", "https://www.data.gov.in/") if plan.source_kind == "official" else ("https://ckandev.indiadataportal.com/",)
            if not manifest.source_url.startswith(allowed):
                raise ValueError("Unsupported government provenance")
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != batch.file_sha256 or manifest.sha256 != batch.file_sha256:
                raise ValueError("Snapshot archive integrity failure")
            if any(marker in batch.source_label.casefold() for marker in ("fixture", "test_only", "demo")):
                raise ValueError("Test data cannot enter real research results")
            sources[batch.id] = {"source": batch.source_label, "url": batch.source_url, "sha256": batch.file_sha256,
                "fetched_at": batch.fetched_at.isoformat(), "source_kind":plan.source_kind,
                "upstream_source_url":manifest.upstream_source_url, "license":manifest.license}
        n = row.normalized
        prices = [float(n[key]) for key in ("min", "modal", "max")]
        if n["state"] != "Karnataka" or district_name(n["district"]) != market_district(plan.market) or n["price_unit"] != "INR/quintal" or not 0 <= prices[0] <= prices[1] <= prices[2]:
            raise ValueError("Invalid snapshot scope/units/price ordering")
        rows.append({"report_date": date.fromisoformat(n["report_date"]), "available_at": pd.Timestamp(batch.fetched_at),
            "price": prices[1], "batch_id": batch.id, "row_id": row.id, "file_sha256": batch.file_sha256})
    frame = pd.DataFrame(rows, columns=empty_vintages().columns)
    if frame.empty:
        return frame, list(sources.values())
    # Resolve revisions at actual download time before constructing an explicitly assumed view.
    frozen = asof(frame, pd.Timestamp(datetime.now(UTC)))
    frozen["actual_fetched_at"] = frozen.available_at
    frozen["available_at"] = frozen.report_date.map(lambda day: midnight(day + timedelta(days=1)))
    return frozen, list(sources.values())


def run(session, plan: Plan, output: Path, evaluate_final=False):
    plan.validate()
    development, sources = snapshot(session, plan)
    fingerprint = hashlib.sha256(development.to_csv(index=False).encode()).hexdigest()
    identity = {"plan": plan.serializable(), "source_fingerprint": fingerprint, "mode": LIMITATION,
        "runtime": runtime_versions(), "code_sha256": {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
            for name in ("research.py", "forecasting.py", "features.py")}}
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    folder = output / ("research-snapshot-v1-" + run_id)
    report_file = folder / "comparison.json"
    if report_file.is_file():
        previous = json.loads(report_file.read_text(encoding="utf-8"))
        if evaluate_final and previous.get("final_evaluation") is None and previous["status"] == "selected":
            raise ValueError("Existing frozen run has no final evaluation; do not refit automatically after feedback")
        return folder, previous
    output.mkdir(parents=True, exist_ok=True)
    # Refuse new selection against a holdout that has already supplied research feedback.
    registry = output / "final_evaluation_registry"
    from app.holdout_guard import assert_untouched
    for horizon in (1,3,7):
        assert_untouched(registry,plan,horizon)
    keys = {}
    for horizon in (1, 3, 7):
        key = {k: getattr(plan, k) for k in ("market", "commodity", "variety", "grade")}
        key.update(horizon=horizon, start=(plan.validation_end + timedelta(days=1)).isoformat(), end=plan.holdout_end.isoformat())
        keys[horizon] = registry / (hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest() + ".json")
    if any(path.exists() for path in keys.values()):
        raise ValueError("This research holdout has already been reserved; no new tuning or selection against it")
    folder.mkdir()
    development.to_csv(folder / "development-view-with-actual-fetch-times.csv", index=False)
    report = {**identity, "version": folder.name, "research_only": True, "created_at": datetime.now(UTC).isoformat(),
        "source": sources, "horizons": [], "final_evaluation": None, "status": "insufficient_data",
        "final_holdout": "unopened", "limitations": LIMITATION,
        "selection_policy": "Validation MAE primary, identical chronological CV; advanced candidate must consistently beat naive and rolling baselines"}
    selected = []
    for horizon in (1, 3, 7):
        comparison, model, frame = select_horizon(development, plan, horizon)
        report["horizons"].append(comparison)
        if comparison["champion"]:
            champion = folder / f"champion-{horizon}d"
            meta = save_champion(champion, comparison, model, frame, plan, fingerprint)
            meta.update(research_only=True, limitations=LIMITATION, trained_before=datetime.now(UTC).isoformat())
            (champion / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            selected.append((horizon, comparison, model))
    report["status"] = "selected" if selected else "insufficient_data"
    # Freeze every selection before any final observation is loaded.
    report_file.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    if evaluate_final and selected:
        registry.mkdir(exist_ok=True)
        for horizon, _, _ in selected:
            with keys[horizon].open("x", encoding="utf-8") as handle:
                json.dump({"state": "reserved_before_read", "run": folder.name, "plan": plan.serializable()}, handle)
        final, final_sources = snapshot(session, plan, final=True)
        final_results = []
        for horizon, comparison, model in selected:
            test = examples(final, plan.validation_end + timedelta(days=1), plan.holdout_end, horizon, plan.holdout_end + timedelta(days=2))
            result = {"horizon": horizon, "champion": comparison["champion"], "n": len(test),
                "status": "evaluated" if len(test) >= 30 else "insufficient_final_samples", "metrics": None, "baseline_metrics": None}
            if len(test) >= 30:
                result["metrics"] = score(comparison["champion"], model, test)
                result["baseline_metrics"] = {name: score(name, None, test) for name in ("naive", "mean_14", "median_14")}
                dated = test[["origin_date", "target_date", "target_modal_price_inr_per_quintal", "lag_1_obs_inr_per_quintal"]].copy()
                dated["prediction_inr_per_quintal"] = predict_rows(comparison["champion"], model, test)
                dated.to_csv(folder / f"final-predictions-{horizon}d.csv", index=False)
            final_results.append(result)
            keys[horizon].write_text(json.dumps({"state": "consumed", "run": folder.name, "plan":plan.serializable(), "result": result}, indent=2), encoding="utf-8")
        report.update(final_holdout="consumed once after selection frozen", final_evaluation={"results": final_results,
            "source": final_sources, "evaluated_at": datetime.now(UTC).isoformat()})
        report_file.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    lines = ["# SAMAY retrospective snapshot research", "", LIMITATION, "", f"Run: {folder.name}",
        f"Train: {plan.start}–{plan.train_end}; selection: {plan.train_end + timedelta(days=1)}–{plan.validation_end}; final: {plan.validation_end + timedelta(days=1)}–{plan.holdout_end}",
        "", "| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in report["horizons"]:
        final_row = next((r for r in (report["final_evaluation"] or {}).get("results", []) if r["horizon"] == row["horizon"]), {})
        m, b = final_row.get("metrics") or {}, (final_row.get("baseline_metrics") or {}).get("naive", {})
        def value(key, metrics=m):
            return f"{metrics[key]:.2f}" if metrics.get(key) is not None else "unavailable"
        lines.append(f"| {row['horizon']}d | {row['champion']} | {row['sample_policy']['effective_train_samples']} | {row['sample_policy']['effective_validation_samples']} | {final_row.get('n', 0)} | {value('mae_inr_per_quintal')} | {b.get('mae_inr_per_quintal', 'unavailable')} | {value('rmse_inr_per_quintal')} | {value('smape_pct')} | {value('wape_pct')} | {100*m['directional_accuracy'] if m.get('directional_accuracy') is not None else 'unavailable'} |")
    lines += ["", "Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.",
        "Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.",
        "No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim."]
    (folder / "comparison.md").write_text("\n".join(lines), encoding="utf-8")
    return folder, report
