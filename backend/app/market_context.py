"""Dated external evidence. Never convert headlines or holidays into invented prices."""
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.config import ROOT


class ContextSource(BaseModel):
    name: str
    url: str
    fetched_at: datetime
    sha256: str
    status: str
    note: str = ""


class WeatherDay(BaseModel):
    date: date
    max_temperature_c: float | None = Field(default=None,ge=-100,le=70,allow_inf_nan=False)
    precipitation_mm: float | None = Field(default=None,ge=0,allow_inf_nan=False)
    precipitation_probability_percent: float | None = Field(default=None,ge=0,le=100,allow_inf_nan=False)


class CalendarEvent(BaseModel):
    name: str
    date: date
    source_url: str
    note: str = "Published calendar event; not a confirmed mandi closure or an estimated price increase."


class NewsItem(BaseModel):
    title: str
    url: str
    published_at: datetime
    source: str
    topics: list[str] = Field(default_factory=list)


class MarketContext(BaseModel):
    status: Literal["available", "partial", "unavailable"] = "unavailable"
    market: str
    commodity: str
    decision_at: datetime
    location_label: str | None = None
    weather: list[WeatherDay] = Field(default_factory=list)
    events: list[CalendarEvent] = Field(default_factory=list)
    news: list[NewsItem] = Field(default_factory=list)
    sources: list[ContextSource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    numeric_price_adjustment_applied: bool = False
    note: str = "Weather is for the market city, not the farm. News and calendar events are context, not learned causal price adjustments. Future dates beyond the weather/calendar source coverage are unknown."


def read_context(market, commodity, decision_at, days=7, directory: Path | None = None):
    if decision_at.utcoffset() is None:
        raise ValueError("Context requires an aware decision timestamp")
    root = directory or ROOT / "data/context"
    output = MarketContext(market=market, commodity=commodity, decision_at=decision_at)
    try:
        index = json.loads((root / "latest.json").read_text(encoding="utf-8"))
        path = (root / index["file"]).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Invalid context archive path")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != index["sha256"]:
            raise ValueError("Context archive hash mismatch")
        snapshot = json.loads(content)
        today = decision_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
        end = today + timedelta(days=min(days, 730))
        for record in snapshot["sources"]:
            source = ContextSource.model_validate(record["source"])
            # Actual first download availability is mandatory for historical use.
            if source.fetched_at > decision_at:
                output.warnings.append("context_not_available_at_decision")
                continue
            source_path = (path.parent / record["archive"]).resolve()
            if not source_path.is_relative_to(path.parent) or hashlib.sha256(source_path.read_bytes()).hexdigest() != source.sha256:
                raise ValueError("External source archive hash mismatch")
            output.sources.append(source)
            if source.status != "available":
                continue
            age = decision_at - source.fetched_at
            if record["kind"] == "weather" and record.get("market") == market:
                if age > timedelta(hours=18):
                    output.warnings.append("weather_context_stale")
                    continue
                output.location_label = record["location_label"]
                output.weather = [WeatherDay.model_validate(d) for d in record["days"] if today <= date.fromisoformat(d["date"]) <= end]
                if not output.weather or end > max(d.date for d in output.weather):
                    output.warnings.append("weather_does_not_cover_entire_holding_period")
            elif record["kind"] == "calendar":
                output.events.extend(CalendarEvent.model_validate(e) for e in record["events"] if today <= date.fromisoformat(e["date"]) <= end)
                years = record.get("covered_years", [])
                if end.year not in years:
                    output.warnings.append("festival_calendar_coverage_incomplete")
            elif record["kind"] == "news":
                if age > timedelta(hours=48):
                    output.warnings.append("news_context_stale")
                    continue
                for raw in record["items"]:
                    item = NewsItem.model_validate(raw)
                    if item.published_at.utcoffset() is None:
                        continue
                    if decision_at-timedelta(days=14) <= item.published_at <= decision_at and (commodity in item.topics or "general_agriculture" in item.topics):
                        output.news.append(item)
        output.news = sorted({n.url: n for n in output.news}.values(), key=lambda n: n.published_at, reverse=True)[:8]
        if not output.news:
            output.warnings.append("no_matching_recent_news_in_collected_feeds")
        if not output.weather:
            output.warnings.append("weather_context_unavailable")
        output.warnings = sorted(set(output.warnings))
        output.status = "available" if output.weather and output.events and output.news and not output.warnings else "partial" if output.weather or output.events or output.news else "unavailable"
    except (OSError, ValueError, KeyError, TypeError):
        output.warnings.append("context_archive_unavailable_or_invalid")
        output.status = "unavailable"
        output.weather, output.events, output.news = [], [], []
    return output


def current_context(market, commodity, days=7):
    return read_context(market, commodity, datetime.now(UTC), days)
