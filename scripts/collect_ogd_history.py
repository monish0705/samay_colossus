"""Download current-named APMC histories from the publisher-linked OGD resource.

The resource URL and public download credential are discovered from data.gov.in,
never guessed. An operator key can override the published download credential.
Credentials and credential-bearing publisher HTML are never archived or logged.
"""
import argparse
import csv
import hashlib
import html
import io
import json
import os
import re
import time
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from app.db import SessionLocal
from app.ingestion import SourceManifest, import_csv
from app.models import ImportBatch
from sqlalchemy import select

PAGE = "https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity"
SCOPES = {
    "Copra": ("Tiptur APMC", "Copra"),
    "Arecanut": ("Shimoga APMC", "Arecanut(Betelnut/Supari)"),
    "Onion": ("APMC Hubballi", "Onion"),
    "Potato": ("Bengaluru APMC", "Potato"),
}
LEGACY_SCOPES = {
    "Copra": ("Tiptur", "Copra"),
    "Arecanut": ("Shimoga", "Arecanut(Betelnut/Supari)"),
    "Onion": ("Hubli (Amaragol)", "Onion"),
    "Potato": ("Bangalore", "Potato"),
}
FIELDS = ("State", "District", "Market", "Commodity", "Variety", "Grade",
          "Arrival_Date", "Min_Price", "Max_Price", "Modal_Price")


def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 SAMAY data research"}), timeout=45) as response:
                raw = response.read(15_000_001)
                if len(raw) > 15_000_000:
                    raise ValueError("Publisher response exceeds archive limit")
                return raw
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise RuntimeError(f"Official OGD HTTP {exc.code}; no credential or URL logged") from None
        except (URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("Official OGD connection failed after three attempts") from None
        time.sleep(2 ** attempt)
    raise RuntimeError("Official OGD retries exhausted")


def discover(page):
    match = re.search(r'field_datafile_url:("(?:[^"\\]|\\.)*")', page.decode("utf-8"))
    if not match:
        raise ValueError("Official resource no longer publishes its download URL")
    published = html.unescape(json.loads(match.group(1)))
    parsed = urlsplit(published)
    if parsed.scheme != "https" or parsed.hostname != "api.data.gov.in" or not re.fullmatch(r"/resource/[0-9a-f-]{36}", parsed.path):
        raise ValueError("Unexpected publisher-linked resource endpoint")
    params = dict(parse_qsl(parsed.query))
    key = os.getenv("SAMAY_OGD_API_KEY") or params.get("api-key")
    if not key:
        raise ValueError("Set SAMAY_OGD_API_KEY; no API credential was published")
    endpoint = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return endpoint, key


def validate_page(payload, commodity, market, offset, expected_total=None):
    if payload.get("status") not in {"ok", "success"} or not isinstance(payload.get("records"), list):
        raise ValueError("Official OGD returned an error or changed response schema")
    rows = payload["records"]
    total = int(payload["total"])
    if int(payload["offset"]) != offset or int(payload["count"]) != len(rows) or len(rows) > 1000:
        raise ValueError("Official OGD pagination mismatch")
    if expected_total is not None and total != expected_total:
        raise ValueError("Official source changed during pagination; discard capture and retry")
    for row in rows:
        if not all(key in row for key in FIELDS):
            raise ValueError("Required official fields are missing; none will be inferred")
        if (row["State"], row["Market"], row["Commodity"]) != ("Karnataka", market, commodity):
            raise ValueError("Official response ignored the requested market/crop filters")
        datetime.strptime(row["Arrival_Date"], "%d/%m/%Y")
    if not rows and offset < total:
        raise ValueError("Official OGD returned an incomplete historical page")
    return rows, total


def collect(output, do_import=False, *, legacy=False, start=date(2021, 1, 1)):
    endpoint, credential = discover(fetch(PAGE))
    folder = output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    catalog = {"publisher_page": PAGE, "endpoint": endpoint, "source_kind": "official", "series": [],
        "discovery": "Resource and download credential discovered from the official publisher page; credential omitted from archives.",
        "unit_evidence": "AGMARKNET public last-week reports for these four APMCs explicitly return unitOfPrice=Rs./Quintal; archived under data/raw/official-multi-recent/.",
        "limitations": "Current retrospective government snapshot. Original publication/revision timestamps unavailable; grade/variety breaks remain separate."}
    for crop, (market, commodity) in (LEGACY_SCOPES if legacy else SCOPES).items():
        part = folder / crop.lower()
        part.mkdir()
        records, pages, offset, total = [], [], 0, None
        while total is None or offset < total:
            query = {"format": "json", "offset": offset, "limit": 1000,
                "filters[State]": "Karnataka", "filters[Market]": market,
                "filters[Commodity]": commodity, "sort[Arrival_Date]": "asc",
                "sort[Variety]": "asc", "sort[Grade]": "asc"}
            raw = fetch(endpoint + "?" + urlencode({**query, "api-key": credential}))
            payload = json.loads(raw)
            rows, total = validate_page(payload, commodity, market, offset, total)
            # The API metadata may repeat its source URL. Never persist credentials.
            if credential.encode() in raw:
                raise ValueError("Publisher echoed a credential; refusing to archive response")
            name = f"page-{offset:06}.json"
            (part / name).write_bytes(raw)
            fetched_at = datetime.now(UTC)
            pages.append({"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "fetched_at": fetched_at.isoformat(), "query": query})
            records.extend(rows)
            offset += len(rows)
        if len(records) != total or not records:
            raise ValueError("Empty or incomplete official crop history")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=[*FIELDS, "Price_Unit"], lineterminator="\n")
        writer.writeheader()
        included = [row for row in records if datetime.strptime(row["Arrival_Date"], "%d/%m/%Y").date() >= start]
        writer.writerows({**{k: row[k] for k in FIELDS}, "Price_Unit": "INR/quintal"} for row in included)
        content = stream.getvalue().encode("utf-8")
        (part / "observations.csv").write_bytes(content)
        manifest = SourceManifest(source_label="Official OGD / AGMARKNET historical APMC observations",
            source_url=PAGE, data_kind="official", fetched_at=fetched_at, price_unit="INR/quintal",
            unit_evidence=catalog["unit_evidence"], sha256=hashlib.sha256(content).hexdigest(),
            license="Government Open Data License - India")
        (part / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        retrieval = {"endpoint": endpoint, "publisher_page": PAGE, "total": total, "pages": pages,
            "import_start": start.isoformat(), "import_records": len(included),
            "transformation": "Original JSON pages unchanged. CSV retains dates >= import_start with exact published field values; no prices, dates, varieties or grades changed. Unit from independently archived official report."}
        (part / "retrieval.json").write_text(json.dumps(retrieval, indent=2), encoding="utf-8")
        result = {"commodity": crop, "market": market, "records": total, "import_records": len(included), "folder": part.as_posix(),
            "first_date": min(datetime.strptime(r["Arrival_Date"], "%d/%m/%Y").date().isoformat() for r in records),
            "last_date": max(datetime.strptime(r["Arrival_Date"], "%d/%m/%Y").date().isoformat() for r in records)}
        if do_import:
            with SessionLocal() as session, session.begin():
                existing = session.scalar(select(ImportBatch).where(ImportBatch.file_sha256 == manifest.sha256,
                    ImportBatch.source_url == PAGE, ImportBatch.data_kind == "official"))
                if existing:
                    result["import"] = {"status": "already_imported", "batch_id": existing.id}
                else:
                    report = import_csv(session, part / "observations.csv", manifest, Path("data/processed/imports"), market=market, commodity=crop)
                    result["import"] = {"counts": report["counts"]}
        catalog["series"].append(result)
        print(json.dumps(result), flush=True)
    (folder / "catalog.json").write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print("ARCHIVE", folder, flush=True)
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/ogd-history"))
    parser.add_argument("--import", dest="do_import", action="store_true")
    parser.add_argument("--legacy", action="store_true", help="Also-needed former market spellings, discovered from actual official records")
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2021, 1, 1), help="CSV import lower date bound; raw pages remain unchanged")
    args = parser.parse_args()
    collect(args.output_dir, args.do_import, legacy=args.legacy, start=args.start_date)


if __name__ == "__main__":
    main()
