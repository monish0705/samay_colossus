"""Train explicitly labeled retrospective research models, never validated production artifacts."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from app.db import SessionLocal
from app.features import Plan
from app.research import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("start", "train-end", "validation-end", "test-end"):
        parser.add_argument("--" + name, type=date.fromisoformat, required=True)
    parser.add_argument("--variety", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--market", default="Kolar APMC")
    parser.add_argument("--commodity", default="Tomato")
    parser.add_argument("--source-kind", choices=["official", "secondary"], default="official")
    parser.add_argument("--acknowledge-retrospective-limitations", action="store_true", required=True)
    parser.add_argument("--evaluate-final", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("models/research"))
    args = parser.parse_args()
    plan = Plan(args.start, args.train_end, args.validation_end, args.test_end, args.variety, args.grade, args.market, args.commodity, source_kind=args.source_kind)
    with SessionLocal() as session:
        folder, report = run(session, plan, args.output_dir, args.evaluate_final)
    print("MODE: RETROSPECTIVE RESEARCH ONLY\n" + report["limitations"])
    print("STATUS: " + report["status"])
    for row in (report["final_evaluation"] or {}).get("results", []):
        print(json.dumps(row, allow_nan=False))
    print(f"REPORT: {folder / 'comparison.md'}")
    return 0 if report["status"] == "selected" else 2


if __name__ == "__main__":
    sys.exit(main())
