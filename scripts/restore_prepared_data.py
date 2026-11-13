"""Restore the hash-verified public observation database only when no local DB exists."""
from pathlib import Path

from app.config import ROOT, get_settings
from app.prepared_data import restore
from sqlalchemy.engine import make_url


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
