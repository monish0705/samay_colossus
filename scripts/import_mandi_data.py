"""Import an operator-downloaded official CSV or an explicitly marked test fixture."""
import argparse
import csv
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from app.db import SessionLocal
from app.ingestion import SourceManifest, import_csv
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True, help="Provenance, fetched_at, units and date format JSON")
    parser.add_argument("--market", default="Kolar APMC")
    parser.add_argument("--commodity", default="Tomato")
    parser.add_argument("--start-date", type=date.fromisoformat)
    parser.add_argument("--end-date", type=date.fromisoformat)
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed/imports"))
    parser.add_argument("--suspicious-price-threshold", type=Decimal, default=Decimal(100000), help="Review threshold in INR/quintal; above this is quarantined, not automatically corrected")
    args = parser.parse_args()
    try:
        manifest = SourceManifest.model_validate_json(args.manifest.read_text(encoding="utf-8-sig"))
        with SessionLocal.begin() as session:
            report = import_csv(session, args.file, manifest, args.output_dir,
                                args.start_date, args.end_date, args.market, args.commodity,
                                args.suspicious_price_threshold)
        print(json.dumps(report, indent=2))
        print(f"COMMITTED batch {report['batch_id']}: {args.output_dir / ('batch-' + str(report['batch_id']))}")
        return 0
    except (OSError, ValueError, csv.Error, ValidationError, SQLAlchemyError) as exc:
        # Do not log database connection strings or credentials.
        message = "Database import failed; run Alembic upgrade head and inspect database availability" if isinstance(exc, SQLAlchemyError) else str(exc)
        print(f"IMPORT FAILED (database transaction rolled back): {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
