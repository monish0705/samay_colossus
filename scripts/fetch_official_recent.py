"""Download the verified AGMARKNET public last-week report; not training history.

Endpoints and parameters verified against the official government SPA bundle:
https://agmarknet.gov.in/static/js/main.8c489c92.js
No CAPTCHA/authentication endpoints are called by this script.
"""
import argparse
import hashlib
import json
import time
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://api.agmarknet.gov.in/v1/"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
           "Origin": "https://agmarknet.gov.in", "Referer": "https://agmarknet.gov.in/"}


def download(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=30) as response:
                content = response.read(10_000_001)
                if len(content) > 10_000_000:
                    raise ValueError("Response exceeds size limit")
                return content, datetime.now(UTC)
        except HTTPError as exc:
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Download retry limit exceeded")


def parse_recent(payload):
    if payload.get("success") is not True or not isinstance(payload.get("columns"), list) or not isinstance(payload.get("data"), list):
        raise ValueError("Official last-week response schema changed")
    dates = [column["key"] for column in payload["columns"] if column["key"] not in {"variety", "unitOfPrice"}]
    for stamp in dates:
        date.fromisoformat(stamp)
    observations, missing = [], []
    for row in payload["data"]:
        if not row["variety"].startswith("Kolar APMC - ") or row["unitOfPrice"] != "Rs./Quintal":
            raise ValueError("Unexpected scope or unit")
        variety = row["variety"].removeprefix("Kolar APMC - ")
        for stamp in dates:
            value = row[stamp]
            if value == "NR":
                missing.append({"date": stamp, "variety": variety})
                continue
            price = Decimal(str(value))
            if not price.is_finite() or price < 0:
                raise ValueError("Invalid official modal price")
            observations.append({"report_date": stamp, "market": "Kolar APMC", "commodity": "Tomato", "variety": variety,
                "modal_price_inr_per_quintal": str(price), "raw_price_unit": row["unitOfPrice"], "price_unit": "INR/quintal"})
    keys = [(row["report_date"], row["variety"]) for row in observations]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate last-week observations")
    return observations, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/official-recent"))
    args = parser.parse_args()
    filters_raw, _ = download(BASE + "daily-price-arrival/filters")
    filters = json.loads(filters_raw)["data"]
    market = next(row for row in filters["market_data"] if row["mkt_name"] == "Kolar APMC")
    state = next(row for row in filters["state_data"] if row["state_name"] == "Karnataka")
    district = next(row for row in filters["district_data"] if row["district_name"] == "Kolar" and row["state_id"] == state["state_id"])
    commodity = next(row for row in filters["cmdt_data"] if row["cmdt_name"] == "Tomato")
    if market["state_id"] != state["state_id"] or market["district_id"] != district["id"]:
        raise ValueError("Official market identifiers do not match requested district/state")
    query = {"marketId": market["id"], "stateId": state["state_id"], "commodityId": commodity["cmdt_id"], "includeExcel": "false"}
    url = BASE + "prices-and-arrivals/market-price/lastweek?" + urlencode(query)
    raw, fetched = download(url)
    observations, missing = parse_recent(json.loads(raw))
    digest = hashlib.sha256(raw).hexdigest()
    folder = args.output_dir / (fetched.strftime("%Y%m%dT%H%M%SZ") + "-" + digest[:12])
    folder.mkdir(parents=True)
    (folder / "response.json").write_bytes(raw)
    (folder / "filters.json").write_bytes(filters_raw)
    manifest = {"source": "Official AGMARKNET 2.0", "source_url": url, "fetched_at": fetched.isoformat(), "sha256": digest,
        "observations": observations, "not_reported": missing, "limitations": [
            "Last week only; insufficient for training.", "No minimum/maximum prices or grade in this response; none inferred.",
            "Current downloaded snapshot; original historical publication/revision times are not established.",
            "Not imported into the complete min/modal/max observation table because required fields are absent."]}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Official observations downloaded: {len(observations)}; not reported: {len(missing)}")
    print(f"SOURCE: {url}\nARCHIVE: {folder}\nSHA256: {digest}")
    print("Training: insufficient history; min/max/grade not fabricated.")


if __name__ == "__main__":
    main()
