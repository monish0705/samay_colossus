"""Archive a browser-downloaded official AGMARKNET CSV and make a traceable import CSV."""
import argparse
import csv
import hashlib
import io
import json
from datetime import UTC, datetime
from pathlib import Path

from app.ingestion import SourceManifest

MAPPING = {"State/UT": "State", "District": "District", "Market": "Market", "Commodity": "Commodity", "Variety": "Variety",
           "Grade": "Grade", "Min Price": "Min_Price", "Max Price": "Max_Price", "Modal Price": "Modal_Price",
           "Price Unit": "Price_Unit", "Price Date": "Arrival_Date"}


def convert(raw, manifest, start, end):
    rows = [row for row in csv.reader(io.StringIO(raw.decode("utf-8-sig"))) if any(cell.strip() for cell in row)]
    if not rows or not any("Daily Price Report" in cell for cell in rows[0]):
        raise ValueError("Missing official report title prelude")
    if len(rows) < 2 or not set(MAPPING).issubset(rows[1]) or len(set(rows[1])) != len(rows[1]):
        raise ValueError("Official CSV header changed or required fields absent")
    fields = rows[1]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(MAPPING.values()))
    writer.writeheader()
    count = 0
    for cells in rows[2:]:
        if len(cells) != len(fields):
            raise ValueError("Malformed official CSV row width")
        source = dict(zip(fields, cells, strict=True))
        # Validate dates/scope/units now; business-quality quarantines remain the importer's responsibility.
        if source["State/UT"] != "Karnataka" or source["District"] != "Kolar" or source["Market"] != "Kolar APMC" or source["Commodity"] != "Tomato":
            raise ValueError("Unexpected official export scope")
        report_date = datetime.strptime(source["Price Date"], "%d-%m-%Y").date()
        if not start <= report_date <= end:
            raise ValueError("Source row lies outside requested annual batch")
        if source["Price Unit"] != "Rs./Quintal":
            raise ValueError("Unexpected official unit")
        writer.writerow({target: source[key] for key, target in MAPPING.items()})
        count += 1
    return output.getvalue().encode("utf-8"), count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/official-history"))
    args = parser.parse_args()
    from datetime import date
    start, end = date(args.year, 1, 1), date(args.year, 12, 31)
    raw = args.file.read_bytes()
    fetched = datetime.fromtimestamp(args.file.stat().st_mtime, UTC)
    base = f"kolar-tomato-{args.year}"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    original = args.output_dir / f"{base}.original.csv"
    if original.exists() and original.read_bytes() != raw:
        raise ValueError("Existing annual archive differs; preserve revisions in a separate output directory")
    original.write_bytes(raw)
    manifest = SourceManifest(source_label="AGMARKNET 2.0 official browser CSV export", source_url="https://agmarknet.gov.in/daily-price-and-arrival-report",
        data_kind="official", fetched_at=fetched, price_unit="INR/quintal", unit_evidence="Original government export Price Unit column: Rs./Quintal; original bytes and SHA256 retained alongside import CSV", date_format="%d-%m-%Y")
    normalized, count = convert(raw, manifest, start, end)
    target = args.output_dir / f"{base}.csv"
    target.write_bytes(normalized)
    manifest = manifest.model_copy(update={"sha256": hashlib.sha256(normalized).hexdigest()})
    (args.output_dir / f"{base}.manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    provenance = {"original_sha256": hashlib.sha256(raw).hexdigest(), "import_csv_sha256": manifest.sha256,
        "original_filename": args.file.name, "fetched_at": fetched.isoformat(), "rows": count,
        "transformation": "Remove report title prelude/blank lines, map documented source headers to importer aliases; retain prices, units, variety, grade and dates unchanged",
        "original_publication_revision_times": "unverified; current-snapshot retrospective study only"}
    (args.output_dir / f"{base}.provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    print(f"Archived {count} source records: {target}\nOriginal SHA256: {provenance['original_sha256']}\nFetched: {fetched.isoformat()}")


if __name__ == "__main__":
    main()
