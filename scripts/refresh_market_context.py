"""Capture public weather, calendar and news evidence for forward decision support.

No historical publication times are invented. Captures are usable only after
their actual fetched_at. Headlines never become numerical price adjustments.
"""
import argparse
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

MARKETS = {"Kolar APMC":"Kolar", "Tiptur APMC":"Tiptur", "Shivamogga Mandi":"Shivamogga", "Hubballi APMC":"Hubli", "Bengaluru APMC":"Bengaluru"}
CALENDAR = "https://www.lpsc.gov.in/holidaysBangalore2026.html"
PIB_DIRECTORY = "https://www.pib.gov.in/ViewRss.aspx?lang=1&reg=3"
BUSINESSLINE_RSS = "https://www.thehindubusinessline.com/economy/agri-business/feeder/default.rss"


def download(url):
    if urlsplit(url).scheme != "https":
        raise ValueError("External evidence must use HTTPS")
    for attempt in range(2):
        try:
            with urlopen(Request(url,headers={"User-Agent":"Mozilla/5.0 SAMAY research context"}),timeout=15) as response:
                raw=response.read(3_000_001)
                if len(raw)>3_000_000:
                    raise ValueError("External evidence response exceeds limit")
                return raw
        except (HTTPError,URLError,TimeoutError):
            if attempt:
                raise RuntimeError("Public source unavailable after two attempts") from None
            time.sleep(1)
    raise RuntimeError("Context retry limit")


def parse_calendar(raw):
    events=[]
    for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>",raw.decode("utf-8"),re.S|re.I):
        cells=[html.unescape(re.sub(r"<[^>]+>"," ",td)).strip() for td in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>",tr,re.S|re.I)]
        if len(cells)!=4 or not re.fullmatch(r"\d{2}\.\d{2}\.\d{4}",cells[2]):
            continue
        day=datetime.strptime(cells[2],"%d.%m.%Y").date()
        events.append({"name":" ".join(cells[1].split()),"date":day.isoformat(),"source_url":CALENDAR})
    if not events:
        raise ValueError("Official calendar table changed")
    return events


def topics(title):
    terms={"Tomato":("tomato","vegetable"),"Onion":("onion","vegetable"),"Potato":("potato","vegetable"),
        "Copra":("copra","coconut"),"Arecanut":("arecanut","areca nut","betel nut","betelnut","supari")}
    words=title.casefold()
    matched=[crop for crop,keys in terms.items() if any(re.search(r"\b"+re.escape(key)+r"\w*\b",words) for key in keys)]
    if "karnataka" in words and any(t in words for t in ("rain","flood","storm","weather","monsoon")):
        matched=list(terms)
    if not matched and any(t in words for t in ("fertiliz","fertilis","monsoon","cold chain","storage","agricultur","climate","farm")):
        matched=["general_agriculture"]
    return matched


def parse_news(raw,name):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("RSS entities are disabled")
    tree=ET.fromstring(raw.decode("utf-8-sig"))
    items=[]
    for item in tree.findall(".//item"):
        title=" ".join(html.unescape(item.findtext("title") or "").split())
        url=(item.findtext("link") or "").strip()
        published=item.findtext("pubDate")
        if not title or not published or urlsplit(url).scheme!="https":
            continue
        stamp=parsedate_to_datetime(published)
        if stamp.utcoffset() is None:
            continue
        items.append({"title":title[:500],"url":url,"published_at":stamp.astimezone(UTC).isoformat(),"source":name,"topics":topics(title)})
    return items


def refresh(root):
    folder=root/datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    folder.mkdir(parents=True)
    snapshot={"schema_version":"samay-context-v1","sources":[],"note":"Live evidence starts at actual capture time. No headline sentiment or festival multiplier was applied to market prices."}
    counter=0
    def capture(url,name,kind,parser,**extra):
        nonlocal counter
        counter+=1
        archive=f"source-{counter:02}.dat"
        try:
            raw=download(url)
            (folder/archive).write_bytes(raw)
            values=parser(raw)
            status,note="available",""
        except (OSError,ValueError,RuntimeError,ET.ParseError) as exc:
            if not (folder/archive).exists():
                (folder/archive).write_bytes(b"")
            raw=(folder/archive).read_bytes()
            values={}
            status,note="unavailable",f"{type(exc).__name__}: source unavailable or schema invalid; no substitute data"
        source={"name":name,"url":url,"fetched_at":datetime.now(UTC).isoformat(),"sha256":hashlib.sha256(raw).hexdigest(),"status":status,"note":note}
        record={"source":source,"kind":kind,"archive":archive,**extra,**values}
        snapshot["sources"].append(record)
        print(name,status,flush=True)
        return record
    for market,city in MARKETS.items():
        geo_url="https://geocoding-api.open-meteo.com/v1/search?"+urlencode({"name":city+", Karnataka","countryCode":"IN","count":10,"language":"en","format":"json"})
        def parse_geo(raw):
            rows=json.loads(raw).get("results",[])
            match=next((r for r in rows if r.get("country_code")=="IN" and r.get("admin1")=="Karnataka" and r.get("feature_code","").startswith("PPL")),None)
            if match is None:
                raise ValueError("No unambiguous Karnataka city point")
            return {"location":{k:match[k] for k in ("name","latitude","longitude","country_code","admin1")}}
        geo=capture(geo_url,"Open-Meteo / GeoNames city lookup","geocoding",parse_geo,market=market)
        if geo["source"]["status"]!="available":
            continue
        point=geo["location"]
        weather_url="https://api.open-meteo.com/v1/forecast?"+urlencode({"latitude":point["latitude"],"longitude":point["longitude"],
            "daily":"temperature_2m_max,precipitation_sum,precipitation_probability_max","timezone":"Asia/Kolkata","forecast_days":16})
        def parse_weather(raw):
            data=json.loads(raw)
            units=data["daily_units"]
            if units["precipitation_sum"]!="mm" or units["temperature_2m_max"]!="°C" or units["precipitation_probability_max"]!="%":
                raise ValueError("Weather units changed")
            d=data["daily"]
            keys=("time","temperature_2m_max","precipitation_sum","precipitation_probability_max")
            if len({len(d[k]) for k in keys})!=1:
                raise ValueError("Weather daily arrays have different lengths")
            return {"days":[{"date":day,"max_temperature_c":temp,"precipitation_mm":rain,"precipitation_probability_percent":prob}
                for day,temp,rain,prob in zip(*(d[k] for k in keys),strict=True)]}
        capture(weather_url,"Open-Meteo city weather forecast","weather",parse_weather,market=market,location_label=f"{point['name']}, Karnataka — market-city proxy, not farm conditions")
    capture(CALENDAR,"LPSC / ISRO Bengaluru 2026 calendar","calendar",lambda raw:{"events":parse_calendar(raw),"covered_years":[2026]})
    directory=capture(PIB_DIRECTORY,"PIB official RSS directory","news_directory",lambda raw:{"html_links":re.findall(r'href=["\']([^"\']+)',html.unescape(raw.decode("utf-8")))})
    links=directory.get("html_links",[])
    feeds=[]
    for link in links:
        absolute=urljoin(PIB_DIRECTORY,link)
        parsed=urlsplit(absolute)
        query={k.casefold():v for k,v in parse_qsl(parsed.query)}
        if parsed.scheme=="https" and parsed.hostname in {"pib.gov.in","www.pib.gov.in"} and parsed.path.casefold()=="/rssmain.aspx" and query.get("modid")=="6":
            feeds.append(absolute)
    directory.pop("html_links",None)
    for url in sorted(set(feeds))[:1]:
        capture(url,"Press Information Bureau government releases","news",lambda raw:{"items":parse_news(raw,"PIB")})
    capture(BUSINESSLINE_RSS,"The Hindu BusinessLine agriculture headlines","news",lambda raw:{"items":parse_news(raw,"The Hindu BusinessLine")})
    target=folder/"snapshot.json"
    target.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False),encoding="utf-8",newline="\n")
    usable=[s for s in snapshot["sources"] if s["kind"] in {"weather","calendar","news"} and s["source"]["status"]=="available"]
    if not usable and (root/"latest.json").exists():
        print("No usable sources; previous cache index preserved. Failed attempt remains archived.",flush=True)
        return snapshot
    index={"file":target.relative_to(root).as_posix(),"sha256":hashlib.sha256(target.read_bytes()).hexdigest()}
    temporary=root/"latest.tmp"
    temporary.write_text(json.dumps(index,indent=2),encoding="utf-8",newline="\n")
    temporary.replace(root/"latest.json")
    print("ARCHIVE",folder,flush=True)
    return snapshot


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=Path("data/context"))
    parser.add_argument("--watch-minutes",type=int,default=0,help="Optional forward collection loop; zero means one capture")
    args=parser.parse_args()
    if args.watch_minutes and not 5<=args.watch_minutes<=1440:
        parser.error("watch interval must be between 5 and 1440 minutes")
    while True:
        try:
            report=refresh(args.output_dir)
            complete=sum(s["kind"]=="weather" and s["source"]["status"]=="available" for s in report["sources"])==len(MARKETS)
            if not args.watch_minutes:
                raise SystemExit(0 if complete else 2)
        except (OSError,ValueError,RuntimeError) as exc:
            print(f"Context refresh failed: {type(exc).__name__}; no substitute evidence",flush=True)
            if not args.watch_minutes:
                raise SystemExit(2) from None
        time.sleep(args.watch_minutes*60)
