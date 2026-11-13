"""Publish a portable verified SQLite snapshot without recommendation history."""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from app.config import ROOT, get_settings
from app.ingestion import SourceManifest
from sqlalchemy.engine import make_url


def main():
    url=make_url(get_settings().database_url)
    if url.get_backend_name()!="sqlite" or not url.database or url.database==":memory:":
        raise ValueError("A local SQLite source is required")
    source=Path(url.database).resolve()
    if not source.is_file():
        raise ValueError("Source database missing")
    folder=ROOT/"data/prepared"
    folder.mkdir(parents=True,exist_ok=True)
    temporary=folder/"building.db"
    if source==temporary or source==folder/"samay.db":
        raise ValueError("Source and portable snapshot must be distinct")
    with closing(sqlite3.connect(source.as_uri()+"?mode=ro",uri=True)) as original,closing(sqlite3.connect(temporary)) as target:
        original.backup(target)
        for archive,sha,raw in target.execute("SELECT archive_path,file_sha256,manifest FROM import_batches WHERE data_kind IN ('official','secondary')"):
            manifest=SourceManifest.model_validate_json(raw)
            path=Path(archive)
            path=path if path.is_absolute() else ROOT/path
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha or manifest.sha256!=sha:
                raise ValueError("Verified source archive integrity failure; bundle not replaced")
        with target:
            target.execute("DELETE FROM recommendation_history")
            for identity,archive in target.execute("SELECT id,archive_path FROM import_batches").fetchall():
                path=Path(archive)
                if path.is_absolute():
                    target.execute("UPDATE import_batches SET archive_path=? WHERE id=?",(path.relative_to(ROOT).as_posix(),identity))
        target.execute("VACUUM")
        counts=dict(target.execute("SELECT data_kind,count(*) FROM mandi_observations GROUP BY data_kind"))
    destination=folder/"samay.db"
    temporary.replace(destination)
    manifest={"created_at":datetime.now(UTC).isoformat(),"database_sha256":hashlib.sha256(destination.read_bytes()).hexdigest(),
        "observation_counts":counts,"recommendation_history_rows":0,"archive_paths":"Repository-relative; run from repository root",
        "models":"Research-only frozen champions and refits; not validated live recommendations",
        "provenance":"Official government exports and separately labeled India Data Portal / ISB AGMARKNET secondary mirrors; synthetic legacy rows remain demo and excluded"}
    (folder/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print(json.dumps(manifest,indent=2))

if __name__ == "__main__":
    main()
