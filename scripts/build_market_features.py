"""Generate official-only point-in-time EDA/features without fitting or holdout evaluation."""
import argparse
import sys
from datetime import date
from pathlib import Path

from app.analysis import write_run
from app.db import SessionLocal
from app.features import Plan, load_vintages
from app.ingestion import commodity_name, label, market_name
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("start", "train-end", "validation-end", "holdout-end"):
        parser.add_argument("--" + name, type=date.fromisoformat, required=True)
    parser.add_argument("--market", default="Kolar APMC")
    parser.add_argument("--commodity", default="Tomato")
    parser.add_argument("--variety", required=True)
    parser.add_argument("--grade", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    try:
        plan = Plan(args.start, args.train_end, args.validation_end, args.holdout_end, label(args.variety), label(args.grade), market_name(args.market), commodity_name(args.commodity))
        plan.validate()
        with SessionLocal() as session:
            vintages, provenance = load_vintages(session, plan)
        folder, meta = write_run(vintages, plan, provenance, args.output_dir)
        print(f"STATUS: {meta['status']}")
        print("horizon_days | effective_train | effective_validation | status")
        for summary in meta["horizons"]:
            print(f"{summary['horizon_calendar_days']:12} | {summary['effective_train_samples']:15} | {summary['effective_validation_samples']:20} | {summary['status']}")
        print(f"ARTIFACTS: {folder}")
        print("Final holdout: reserved; no values read for analysis/evaluation. No model trained.")
        return 2 if meta["status"] == "insufficient_data" else 0
    except (ValueError, OSError, SQLAlchemyError, ImportError) as exc:
        message = "Database unavailable or unmigrated; run Alembic upgrade head" if isinstance(exc, SQLAlchemyError) else str(exc)
        print(f"FEATURE BUILD FAILED: {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
