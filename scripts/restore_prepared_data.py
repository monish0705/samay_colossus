"""Restore the hash-verified public observation database only when no local DB exists."""
import hashlib
import json
from pathlib import Path

from app.config import ROOT, get_settings
from sqlalchemy.engine import make_url


def restore(source: Path, manifest: Path, target: Path):
    if target.exists():
        return "Existing local database preserved"
    content = source.read_bytes()
    expected = json.loads(manifest.read_text(encoding="utf-8"))["database_sha256"]
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError("Prepared database hash mismatch; refusing restoration")
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open("xb") as handle:
            handle.write(content)
    except FileExistsError:
        return "Existing local database preserved"
    return "Prepared official observations restored; recommendation history is empty"


def main():
    bundle = ROOT / "data/prepared"
    if not (bundle / "manifest.json").is_file():
        print("No prepared database bundle; migrations will initialize an empty database")
        return
    url = make_url(get_settings().database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        print("Custom database configuration preserved")
        return
    target = Path(url.database).resolve()
    if target != (ROOT / "samay.db").resolve():
        print("Custom SQLite path preserved; import or restore explicitly")
        return
    print(restore(bundle / "samay.db", bundle / "manifest.json", target))


if __name__ == "__main__":
    main()
