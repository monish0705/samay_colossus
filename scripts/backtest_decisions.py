"""Backtest actual recommendation policy; never upgrades unreliable forecasts to validated."""
import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.db import SessionLocal
from app.decision_backtesting import replay, save_report
from app.features import load_vintages
from app.training import read_plan
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-run", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True, help="SellingRequest JSON with explicit costs/storage; scenarios are ignored")
    for name in ("start", "end", "scoring-freeze"):
        parser.add_argument("--" + name, type=date.fromisoformat, required=True)
    parser.add_argument("--realization-multiplier", type=Decimal, required=True)
    parser.add_argument("--champions", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/decision-backtests"))
    args = parser.parse_args()
    try:
        plan, metadata = read_plan(args.feature_run)
        with SessionLocal() as session:
            vintages, source = load_vintages(session, plan)
        source_hash = hashlib.sha256(vintages.to_csv(index=False).encode()).hexdigest()
        if source_hash != metadata["vintages_sha256"]:
            raise ValueError("Source ledger changed; rebuild versioned features before decision evaluation")
        template = json.loads(args.template.read_text(encoding="utf-8-sig"))
        records, audits, summary = replay(vintages, plan, args.start, args.end, args.scoring_freeze, template, source,
            realization_multiplier=args.realization_multiplier, champions=args.champions, evidence=args.evidence)
        summary["source_vintages_sha256"] = source_hash
        summary["implementation_sha256"] = hashlib.sha256(Path(__file__).parents[1].joinpath("backend/app/decision_backtesting.py").read_bytes()).hexdigest()
        folder = save_report(args.output_dir, records, audits, summary, template)
        print(json.dumps(summary, indent=2, allow_nan=False))
        print(f"REPORT: {folder / 'summary.json'}")
        return 0 if summary["status"] == "scored" else 2
    except (ValueError, OSError, KeyError, SQLAlchemyError) as exc:
        print(f"DECISION BACKTEST FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
