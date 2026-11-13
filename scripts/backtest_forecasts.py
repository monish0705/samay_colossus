import argparse
import os
import sys
from datetime import date
from pathlib import Path

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

from app.backtesting import run_backtest
from app.db import SessionLocal
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description="Chronological reliability assessment; never opens the final test set")
    parser.add_argument("--feature-run", type=Path, required=True)
    parser.add_argument("--calibration-start", type=date.fromisoformat, required=True)
    parser.add_argument("--calibration-end", type=date.fromisoformat, required=True)
    parser.add_argument("--evaluation-end", type=date.fromisoformat, required=True)
    parser.add_argument("--champions", type=Path, help="Optional fixed champion run; must predate calibration. Default is a predeclared naive baseline")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/backtests"))
    args = parser.parse_args()
    try:
        with SessionLocal() as session:
            folder, report = run_backtest(session, args.feature_run, args.calibration_start, args.calibration_end, args.evaluation_end, args.output_dir, args.champions)
        print(f"STATUS: {report['status']}")
        for row in report["horizons"]:
            print(f"horizon={row['horizon']}d calibration_n={row['calibration']['calibration_n']} unseen_pairs={row['assessment']['n']} metrics={row['assessment']['metrics']}")
        print(f"REPORT: {folder / 'summary.json'}")
        print("Final holdout: unopened. Nominal interval levels are not confidence guarantees.")
        return 2 if report["status"] == "insufficient_data" else 0
    except (OSError, ValueError, ImportError, SQLAlchemyError) as exc:
        print("BACKTEST FAILED: " + ("Database unavailable" if isinstance(exc, SQLAlchemyError) else str(exc)), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
