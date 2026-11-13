"""Archive the official public last-week report for all five configured crops.

This endpoint does NOT provide daily historical min/max/grade. No missing fields
are inferred and these captures cannot substitute for historical training CSVs.
Parameter names are those verified in the official AGMARKNET frontend, recorded
in docs/ACQUISITION.md. Historical exports require the official report UI.
"""
import argparse
import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from fetch_official_recent import BASE, download

SCOPES = [("Tomato", "Kolar APMC"), ("Arecanut(Betelnut/Supari)", "Shimoga APMC"),
          ("Copra", "Tiptur APMC"), ("Onion", "APMC Hubballi"), ("Potato", "Bengaluru APMC")]


def parse(payload, market):
    if payload.get("success") is not True or not isinstance(payload.get("columns"), list) or not isinstance(payload.get("data"), list):
        raise ValueError("Official response schema changed")
    dates = [x["key"] for x in payload["columns"] if x["key"] not in {"variety", "unitOfPrice"}]
    for stamp in dates:
        date.fromisoformat(stamp)
    count = missing = 0
    for row in payload["data"]:
        if not row["variety"].startswith(market + " - ") or row["unitOfPrice"] != "Rs./Quintal":
            raise ValueError("Unexpected market or price unit")
        for stamp in dates:
            if row[stamp] == "NR":
                missing += 1
            else:
                value = Decimal(str(row[stamp]))
                if not value.is_finite() or value < 0:
                    raise ValueError("Invalid modal price")
                count += 1
    return count, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/official-multi-recent"))
    args = parser.parse_args()
    folder = args.output_dir / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    raw_filters, fetched = download(BASE + "daily-price-arrival/filters")
    (folder / "filters.json").write_bytes(raw_filters)
    data = json.loads(raw_filters)["data"]
    state = next(x for x in data["state_data"] if x["state_name"] == "Karnataka")
    summary = {"fetched_at": fetched.isoformat(), "filters_sha256": hashlib.sha256(raw_filters).hexdigest(), "series": [],
        "limitations": "Public last-week modal-only captures; no min/max, grade or original publication timestamps inferred. Historical daily training requires verified official CSV exports."}
    for commodity, market in SCOPES:
        result = {"market": market, "commodity": commodity, "status": "unavailable"}
        try:
            matches = [x for x in data["market_data"] if x["mkt_name"] == market and x["state_id"] == state["state_id"]]
            if len(matches) != 1:
                raise ValueError("Official market name is absent or ambiguous")
            m = matches[0]
            c = next(x for x in data["cmdt_data"] if x["cmdt_name"] == commodity)
            url = BASE + "prices-and-arrivals/market-price/lastweek?" + urlencode({"marketId": m["id"], "stateId": state["state_id"], "commodityId": c["cmdt_id"], "includeExcel": "false"})
            raw, when = download(url)
            target = folder / (commodity.split('(')[0].lower() + ".json")
            target.write_bytes(raw)
            count, missing = parse(json.loads(raw), market)
            result.update(status="captured", source_url=url, fetched_at=when.isoformat(), sha256=hashlib.sha256(raw).hexdigest(), modal_observations=count, not_reported=missing, file=target.name)
        except (OSError, ValueError, KeyError, StopIteration) as exc:
            result["error"] = f"{type(exc).__name__}: {exc}"
        summary["series"].append(result)
        print(json.dumps(result), flush=True)
    (folder / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("ARCHIVE:", folder)
    return 0 if all(x["status"] == "captured" for x in summary["series"]) else 2

if __name__ == "__main__":
    raise SystemExit(main())
