"""Download selected public India Data Portal AGMARKNET mirror records.

Resource IDs and the DataStore API are discovered from the publisher's dataset
page and its linked API documentation. No token, CAPTCHA or guessed IDs.
Archive exact JSON responses before converting a separate import CSV.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request, urlopen

PAGE = "https://ckandev.indiadataportal.com/dataset/agriculture-marketing"
API = "https://ckandev.indiadataportal.com/api/action/datastore_search"
SCOPES = [
    ("Copra", "Tiptur", "Tiptur Apmc"),
    ("Arecanut(Betelnut/Supari)", "Shimoga", "Shimoga Apmc"),
    ("Onion", "Hubli (Amaragol)", "Hubballi Apmc"),
    ("Potato", "Bangalore", "Bengaluru Apmc"),
]


def fetch(url, body=None):
    for attempt in range(3):
        try:
            request = Request(url, data=json.dumps(body).encode() if body is not None else None,
                headers={"User-Agent":"Mozilla/5.0 SAMAY research archive", "Content-Type":"application/json"})
            with urlopen(request, timeout=45) as response:
                return response.read(30_000_001)
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("Download failed")


def collect(output):
    folder = output / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    html = fetch(PAGE)
    (folder/"publisher-dataset-page.html").write_bytes(html)
    links = re.findall(r'href=["\']([^"\']+)',html.decode())
    sources = {}
    for kind in ("old","new"):
        candidates = {urljoin(PAGE,link) for link in links if f"/download/apmc-arrivals-and-prices-{kind}-source.csv" in link}
        if len(candidates) != 1:
            raise ValueError("Publisher download links changed or are ambiguous")
        url = candidates.pop()
        resource = url.split("/resource/")[1].split("/")[0]
        source_page = url.split("/download/")[0]
        metadata = fetch(source_page)
        api_doc = fetch(f"https://ckandev.indiadataportal.com/api/1/util/snippet/api_info.html?resource_id={resource}")
        if "/api/action/datastore_search" not in api_doc.decode() or "Open Data Commons Attribution License" not in metadata.decode():
            raise ValueError("Publisher API or license attestation absent")
        (folder/f"{kind}-resource.html").write_bytes(metadata)
        (folder/f"{kind}-api-documentation.html").write_bytes(api_doc)
        sources[kind] = (resource,url)
    catalog = {"publisher":"India Data Portal / ISB", "source_kind":"secondary", "upstream":"https://agmarknet.gov.in/",
        "license":"Open Data Commons Attribution License", "fetched_at":datetime.now(UTC).isoformat(), "series":[],
        "limitations":"Secondary mirror; original historical publication/revision timestamps unverified. Old source has no grade field; it is not assigned FAQ or merged with graded observations."}
    fields = ["State","District","Market","Commodity","Variety","Grade","Arrival_Date","Min_Price","Max_Price","Modal_Price","Price_Unit"]
    for kind,(resource,url) in sources.items():
        market_field = "market_center" if kind == "old" else "market_center_name"
        for commodity,old_market,new_market in SCOPES:
            market = old_market if kind == "old" else new_market
            slug = commodity.split('(')[0].lower()
            part = folder/f"{slug}-{kind}"
            part.mkdir()
            records, pages, seen = [], [], set()
            offset = 0
            while True:
                query={"resource_id":resource,"filters":{"state_name":"Karnataka","commodity_name":commodity,market_field:market},
                    "limit":1000,"offset":offset,"include_total":False,"sort":"_id asc"}
                raw=fetch(API,query)
                if len(raw)>30_000_000:
                    raise ValueError("API page too large")
                path=part/f"page-{offset:06}.json"
                path.write_bytes(raw)
                data=json.loads(raw)
                if data.get("success") is not True or data["result"]["resource_id"] != resource:
                    raise ValueError("Publisher response validation failed")
                page=data["result"]["records"]
                for row in page:
                    if row["_id"] in seen or row["state_name"]!="Karnataka" or row["commodity_name"]!=commodity or row[market_field]!=market:
                        raise ValueError("Wrong scope or repeated pagination ID")
                    seen.add(row["_id"])
                records.extend(page)
                pages.append({"file":path.name,"sha256":hashlib.sha256(raw).hexdigest(),"request":query,"records":len(page),"fetched_at":datetime.now(UTC).isoformat()})
                if len(page)<1000:
                    break
                offset += len(page)
            text=io.StringIO(newline="")
            writer=csv.DictWriter(text,fieldnames=fields,lineterminator="\n")
            writer.writeheader()
            for row in records:
                writer.writerow(dict(zip(fields,[row["state_name"],row["district_name"],row[market_field],row["commodity_name"],row["variety"],
                    row.get("grade") or "unspecified",row.get("report_date") or row["date"],row["min_price"],row["max_price"],row["modal_price"],row["price_unit"]],strict=True)))
            content=text.getvalue().encode()
            (part/"observations.csv").write_bytes(content)
            when=datetime.now(UTC).isoformat()
            manifest={"source_label":"India Data Portal AGMARKNET mirror (secondary)","source_url":url,"data_kind":"secondary",
                "fetched_at":when,"price_unit":"INR/quintal","unit_evidence":"Publisher price_unit and data dictionary: Rs/Quintal or Rs./Quintal; response pages retained unchanged",
                "date_format":"%Y-%m-%d","sha256":hashlib.sha256(content).hexdigest(),"upstream_source_url":"https://agmarknet.gov.in/",
                "license":"Open Data Commons Attribution License"}
            (part/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
            retrieval={"source_page":url.split('/download/')[0],"download_url":url,"api_url":API,"resource_id":resource,"pages":pages,
                "records":len(records),"conversion":"Map documented headers only; preserve all observed dates, varieties, grades, prices and units. Grade missing in old source is explicitly unspecified.",
                "first_date":min((r.get('report_date') or r['date'] for r in records),default=None),"last_date":max((r.get('report_date') or r['date'] for r in records),default=None)}
            (part/"retrieval.json").write_text(json.dumps(retrieval,indent=2),encoding="utf-8")
            summary={"commodity":commodity,"market":market,"source":kind,"n":len(records),"first_date":retrieval["first_date"],"last_date":retrieval["last_date"],"folder":part.as_posix()}
            catalog["series"].append(summary)
            print(json.dumps(summary),flush=True)
    (folder/"catalog.json").write_text(json.dumps(catalog,indent=2),encoding="utf-8")
    print("ARCHIVE:",folder,flush=True)
    return folder

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("data/raw/idp-history"))
    collect(parser.parse_args().output_dir)
