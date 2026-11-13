"""Repair only the identified synthetic batch; update the portable bundle hash."""
import argparse
import hashlib
import json
from pathlib import Path

from app.provenance_repair import repair

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("samay.db"))
    parser.add_argument("--bundle-manifest", type=Path)
    args = parser.parse_args()
    if not args.database.is_file():
        raise SystemExit("Database does not exist; nothing repaired")
    result = repair(args.database)
    if args.bundle_manifest:
        manifest = json.loads(args.bundle_manifest.read_text())
        manifest.update(database_sha256=hashlib.sha256(args.database.read_bytes()).hexdigest(), observation_counts=result["observations_by_kind"], provenance_repair=result)
        args.bundle_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
