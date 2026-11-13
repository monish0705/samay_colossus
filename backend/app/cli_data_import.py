"""SAMAY Mandi Market Data Pipeline CLI.

Sample usage:
  python backend/app/cli_data_import.py --status
  python backend/app/cli_data_import.py --sync-db
  python backend/app/cli_data_import.py --source data/raw/official-history/kolar-tomato-2021.csv --crop Tomato --mandi "Kolar APMC"
  python backend/app/cli_data_import.py --fetch-live --crop Tomato --mandi "Kolar APMC"
"""
import argparse
import json
import sys
from pathlib import Path

# Ensure backend is on sys.path
backend_path = Path(__file__).resolve().parents[1]
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.db_migration import upgrade_database
from app.market_data_pipeline import pipeline


def main():
    parser = argparse.ArgumentParser(description="SAMAY Mandi Market Data Pipeline CLI")
    parser.add_argument("--source", type=str, help="Path to input CSV file to ingest")
    parser.add_argument("--crop", type=str, default="Tomato", help="Target crop/commodity name")
    parser.add_argument("--mandi", type=str, default="Kolar APMC", help="Target APMC mandi name")
    parser.add_argument("--unit", type=str, default="INR/quintal", help="Default price unit")
    parser.add_argument("--data-status", choices=["LIVE", "CACHED", "SAMPLE", "STALE"], default="CACHED", help="Provenance status")
    parser.add_argument("--source-label", type=str, default="Official APMC Records", help="Attribution label")
    parser.add_argument("--sync-db", action="store_true", help="Upgrade schema and sync existing verified observations")
    parser.add_argument("--fetch-live", action="store_true", help="Fetch latest live prices with resilient cache fallback")
    parser.add_argument("--status", action="store_true", help="Show pipeline health, freshness, and records summary")

    args = parser.parse_args()

    if args.sync_db:
        print("Upgrading database schema and syncing initial observations...")
        result = upgrade_database()
        print(json.dumps(result, indent=2))
        return

    if args.status:
        status = pipeline.get_status()
        print(json.dumps(status, indent=2))
        return

    if args.fetch_live:
        print(f"Fetching prices for {args.crop} at {args.mandi} (OGD API with cache fallback)...")
        result = pipeline.fetch_live_mandi_prices(commodity=args.crop, market=args.mandi)
        print(json.dumps(result, indent=2))
        return

    if args.source:
        csv_path = Path(args.source)
        if not csv_path.exists():
            print(f"Error: file not found: {csv_path}", file=sys.stderr)
            sys.exit(1)
        print(f"Ingesting CSV: {csv_path}...")
        stats = pipeline.import_csv(
            path=csv_path,
            source_label=args.source_label,
            default_unit=args.unit,
            data_status=args.data_status,
        )
        print(json.dumps(stats, indent=2))
        return

    # If no flags passed, display pipeline status
    status = pipeline.get_status()
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()

