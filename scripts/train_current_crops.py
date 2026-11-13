"""Predeclared current-grade studies; no tuning against consumed final tests.

An explicit verified-source plan combines only identical market/crop/variety/grade
keys. The latest actual fetched vintage resolves overlaps; per-source hashes and
timestamps remain in the report. Unspecified grades are never merged into Local.
"""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from app.db import SessionLocal
from app.features import Plan, build_horizon
from app.forecasting import rolling_folds
from app.research import run, snapshot

SCOPES = {
    "Copra": ("Tiptur APMC", "Copra", "other", "local"),
    "Arecanut": ("Shivamogga Mandi", "Arecanut", "rashi", "local"),
    "Onion": ("Hubballi APMC", "Onion", "puna", "local"),
    "Potato": ("Bengaluru APMC", "Potato", "local", "medium"),
}


def study_plan(name):
    market, crop, variety, grade = SCOPES[name]
    train_end = date(2026, 7, 31) if name in {"Copra", "Arecanut"} else date(2026, 7, 15)
    return Plan(date(2025, 10, 27), train_end, date(2026, 9, 15), date(2026, 11, 4),
        variety, grade, market, crop, min_train=90, min_validation=20, min_train_span_days=90,
        source_kind="verified", candidate_suite="recent_v3")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commodity", choices=[*SCOPES, "all"], default="all")
    parser.add_argument("--check", action="store_true", help="Inspect only development eligibility; never load final prices")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    selected = SCOPES if args.commodity == "all" else [args.commodity]
    for name in selected:
        plan = study_plan(name)
        print("FROZEN_PLAN", name, json.dumps(plan.serializable()), flush=True)
        if args.check:
            with SessionLocal() as session:
                development, _ = snapshot(session, plan)
            for horizon in (1, 3, 7):
                _, policy = build_horizon(development, plan, horizon)
                folds = rolling_folds(development, plan, horizon)
                print("DEVELOPMENT", horizon, json.dumps({**policy, "fold_sizes": [(len(t), len(v)) for t, v in folds]}, default=str), flush=True)
            continue
        saved = Path("reports") / f"current-{name.lower()}-research-entry.json"
        if saved.exists():
            entry = json.loads(saved.read_text(encoding="utf-8"))
            folder = Path(entry["directory"])
            content = (folder / "comparison.json").read_bytes()
            if hashlib.sha256(content).hexdigest() != entry["comparison_sha256"]:
                raise ValueError("Frozen current-crop report integrity failure")
            report = json.loads(content)
            if report["plan"] != plan.serializable():
                raise ValueError("Frozen current-crop plan changed; reserve a genuinely new test")
            print("FROZEN_REUSE; no retuning or second final evaluation", flush=True)
        else:
            with SessionLocal() as session:
                folder, report = run(session, plan, Path("models/research"), evaluate_final=True)
        entry = {"directory": folder.as_posix(), "comparison_sha256": hashlib.sha256((folder/"comparison.json").read_bytes()).hexdigest(),
            "prediction_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("final-predictions-*d.csv")}}
        saved.write_text(json.dumps(entry, indent=2), encoding="utf-8")
        if args.register:
            registry = Path("research-registry.json")
            entries = json.loads(registry.read_text(encoding="utf-8-sig"))
            entries = [old for old in entries if old["directory"] != entry["directory"]] + [entry]
            registry.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        print("STATUS", name, report["status"], "REPORT", folder, flush=True)
        for result in (report.get("final_evaluation") or {}).get("results", []):
            print("FINAL", name, json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
