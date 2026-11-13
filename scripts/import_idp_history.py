"""Idempotently import a captured India Data Portal archive; never download or invent data."""
import argparse
import json
from pathlib import Path

from app.db import SessionLocal
from app.ingestion import SourceManifest, commodity_name, import_csv, market_name
from app.models import ImportBatch
from sqlalchemy import select


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-dir",type=Path)
    args=parser.parse_args()
    if args.archive_dir is None:
        catalogs=sorted(Path("data/raw/idp-history").glob("*/catalog.json"))
        if not catalogs:
            raise ValueError("No captured catalog exists; run collect_idp_history.py first")
        folder=catalogs[-1].parent
    else:
        folder=args.archive_dir
    catalog=json.loads((folder/"catalog.json").read_text())
    summary=[]
    for item in catalog["series"]:
        part=Path(item["folder"])
        if not part.resolve().is_relative_to(folder.resolve()):
            raise ValueError("Catalog entry lies outside its archive directory")
        manifest=SourceManifest.model_validate_json((part/"manifest.json").read_text())
        with SessionLocal.begin() as session:
            previous=session.scalar(select(ImportBatch).where(ImportBatch.file_sha256==manifest.sha256,ImportBatch.data_kind==manifest.data_kind,
                ImportBatch.source_url==manifest.source_url,ImportBatch.fetched_at==manifest.fetched_at))
            if previous is not None:
                result={"status":"already_imported","batch_id":previous.id,"counts":previous.report.get("counts",{})}
            else:
                result=import_csv(session,part/"observations.csv",manifest,Path("data/processed/imports"),market=market_name(item["market"]),commodity=commodity_name(item["commodity"]))
        summary.append({"commodity":item["commodity"],"market":item["market"],"source":item["source"],**result})
        print(json.dumps({"commodity":item["commodity"],"source":item["source"],"status":result.get("status","imported"),"counts":result["counts"]}),flush=True)
    Path("reports/idp-import-summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")

if __name__ == "__main__":
    main()
