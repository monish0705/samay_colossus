import argparse
import os
import sys
from pathlib import Path

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"

from app.db import SessionLocal
from app.training import train_run
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description="Select SAMAY horizon champions; final evaluation is one-shot and never tunes models")
    parser.add_argument("--feature-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("models/forecasts"))
    parser.add_argument("--evaluate-final", action="store_true", help="After freezing all champions, reserve and evaluate the chronological holdout once")
    args = parser.parse_args()
    try:
        with SessionLocal() as session:
            folder, report = train_run(session, args.feature_run, args.output_dir, args.evaluate_final)
        print(f"STATUS: {report['status']}")
        for row in report["horizons"]:
            policy = row["sample_policy"]
            print(f"horizon={row['horizon']}d train={policy['effective_train_samples']} validation={policy['effective_validation_samples']} champion={row['champion'] or 'NONE'} comparisons={len(row['comparisons'])}")
        print("FINAL HOLDOUT: " + ("consumed; see report" if report["final_evaluation"] else "unopened / not evaluated"))
        print(f"REPORT: {folder / 'comparison.md'}")
        return 2 if report["status"] == "insufficient_data" else 0
    except (ValueError, OSError, ImportError, SQLAlchemyError) as exc:
        print("TRAINING FAILED: " + ("database unavailable; run migrations" if isinstance(exc, SQLAlchemyError) else str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
