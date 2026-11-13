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


class CropDriverItem(BaseModel):
    category: str
    impact: Literal["bullish", "bearish", "neutral", "watch"]
    title: str
    description: str


class CropDomainProfile(BaseModel):
    commodity: str
    market: str
    optimal_storage_duration: str
    spoilage_risk: str
    drivers: list[CropDriverItem]


CROP_DOMAIN_PROFILES: dict[str, CropDomainProfile] = {
    "Arecanut": CropDomainProfile(
        commodity="Arecanut",
        market="Shivamogga Mandi",
        optimal_storage_duration="60 to 730 days (2 months to 2 years) in dry gunny godown",
        spoilage_risk="Very Low; vulnerable mainly to moisture reabsorption and yellow mold if humidity exceeds 70%",
        drivers=[
            CropDriverItem(
                category="Crop Yield & Production Volume",
                impact="watch",
                title="Western Ghats Malnad Harvest Flush",
                description="Peak arrivals occur from November to February. Heavy arrivals test Mandi floor capacity and MAMCOS warehouse intake.",
            ),
            CropDriverItem(
                category="Consumer Industries",
                impact="bullish",
                title="Pan Masala & Supari Industrial Demand",
                description="Industrial gutkha, supari, and pan masala processors in Kanpur, Gujarat, and Delhi drive over 70% of bulk boiled arecanut (Rashi/Bette) demand.",
            ),
            CropDriverItem(
                category="Health & Cultural Shifts",
                impact="bullish",
                title="Wedding & Religious Muhurtham Seasons",
                description="High wedding and religious festival activity in winter and spring triggers intense institutional demand for traditional supari and tamboolam.",
            ),
            CropDriverItem(
                category="Import and Export Regulations",
                impact="bullish",
                title="Minimum Import Price (MIP) Floor ₹351/kg",
                description="Government of India enforces DGFT MIP of ₹351/kg and high customs tariffs on imports from Sri Lanka and Indonesia, shielding domestic Malnad prices.",
            ),
            CropDriverItem(
                category="Pesticide and Environmental Bans",
                impact="watch",
                title="Koleroga (Fruit Rot) & Yellow Leaf Disease (YLD)",
                description="Post-monsoon Phytophthora fruit rot reduces harvest yield in Thirthahalli and Sringeri. Mandi quality testing checks for illegal chemical residues.",
            ),
            CropDriverItem(
                category="Climate Change and Weather Patterns",
                impact="neutral",
                title="Western Ghats Monsoon Precipitation",
                description="Prolonged monsoon downpours cause flower and tender nut drop, whereas sunny post-monsoon weeks accelerate farm-level sun-drying quality.",
            ),
        ],
    ),
    "Potato": CropDomainProfile(
        commodity="Potato",
        market="Bengaluru APMC",
        optimal_storage_duration="30 to 180 days (1 to 6 months) in temperature-controlled cold storage (2–4°C, 90–95% RH)",
        spoilage_risk="Medium in cold storage; high risk of sprouting and blackheart if left in ambient storage beyond 15 days",
        drivers=[
            CropDriverItem(
                category="Crop Yields and Harvest Area",
                impact="watch",
                title="Hassan/Kolar Kharif vs Northern Rabi Arrivals",
                description="Local Hassan and Kolar harvests supply Karnataka markets in July–October; North Indian (Agra/Punjab) cold storage despatches take over in November–March.",
            ),
            CropDriverItem(
                category="Cold Storage Occupancy & Release Rates",
                impact="bearish",
                title="Cold Storage Year-End Destocking Cycle",
                description="Cold godown operators clear stocks aggressively by October–November before fresh winter crop arrivals, putting periodic downward pressure on wholesale prices.",
            ),
            CropDriverItem(
                category="Storage Economics and Shrinkage",
                impact="watch",
                title="Storage Rentals & Moisture Shrinkage",
                description="Monthly storage fees of ₹30–₹40 per 50kg bag combined with 4–8% natural dehydration loss demand a minimum ₹150–₹250/qtl price premium to justify holding beyond 60 days.",
            ),
            CropDriverItem(
                category="Table vs. Processing Demand",
                impact="neutral",
                title="Contract Chipsona vs Table Consumption",
                description="Processing varieties (Chipsona, Lady Rosetta) trade at stable contracted rates with snack processors, leaving table potato (Kufri Jyoti) sensitive to open APMC arrivals.",
            ),
            CropDriverItem(
                category="Consumer Trends",
                impact="bullish",
                title="Festival Fasting Consumption Peaks",
                description="Navratri, Ekadashi, and Maha Shivratri fasting observances drive sharp spikes in retail potato demand across Bengaluru and South Indian urban centers.",
            ),
        ],
    ),
    "Onion": CropDomainProfile(
        commodity="Onion",
        market="Hubballi APMC",
        optimal_storage_duration="30 to 120 days (1 to 4 months) in ventilated bamboo/mesh Kanda Chawls",
        spoilage_risk="High in humid weather; rotting, sprouting, and moisture loss typically reach 20–30% in traditional storage",
        drivers=[
            CropDriverItem(
                category="Weather & Monsoon Variability",
                impact="watch",
                title="North Karnataka Post-Monsoon Rain Impact",
                description="Unseasonal rainfall in Dharwad, Bagalkot, and Gadag during October–November damages standing Kharif crops, delaying arrivals and creating spot price spikes.",
            ),
            CropDriverItem(
                category="Storage & Post-Harvest Losses",
                impact="bearish",
                title="Kanda Chawl Rotting & Sprouting Rate",
                description="High ambient humidity accelerates black mold and internal rot. Farmers must factor in 20–25% weight loss when evaluating holding beyond 30 days.",
            ),
            CropDriverItem(
                category="Government Policies & Interventions",
                impact="bearish",
                title="NAFED/NCCF Buffer Stock Releases & Export Tariffs",
                description="Central buffer stock releases at subsidized rates (₹25–₹35/kg), Minimum Export Price (MEP) caps, and export duties actively suppress wholesale price rallies.",
            ),
            CropDriverItem(
                category="Pests, Diseases, and Cultivation Costs",
                impact="neutral",
                title="Thrips Infestations & Fuel Freight Costs",
                description="Thrips and purple blotch fungus inflate spray costs, while rising diesel freight rates raise the breakeven price for Hubballi market despatches.",
            ),
            CropDriverItem(
                category="Forecasting Models & Data Analytics",
                impact="bullish",
                title="Kharif-to-Late Kharif Supply Transition",
                description="Historical supply arrival cliffs in late November typically produce 7–14 day price inflection points before Maharashtra Rabi inflows stabilize the market.",
            ),
        ],
    ),
    "Copra": CropDomainProfile(
        commodity="Copra",
        market="Tiptur APMC",
        optimal_storage_duration="90 to 365 days (3 to 12 months) in clean, well-aerated godowns",
        spoilage_risk="Low for mature whole Ball Copra; vulnerable to copra beetle (Necrobia rufipes) and fungus if stored damp",
        drivers=[
            CropDriverItem(
                category="Crop Yield & Regional Production",
                impact="bullish",
                title="Tiptur–Tumakuru Coconut Belt Supply",
                description="Tiptur is India's benchmark market for edible Ball Copra. Yields depend on coconut harvest cycles across Tumakuru, Hassan, and Arsikere.",
            ),
            CropDriverItem(
                category="Weather and Climate Patterns",
                impact="watch",
                title="Borewell Water Table & Nut Sizing",
                description="Successive deficit monsoon seasons in the central dry zone reduce ground water, resulting in smaller nut sizes and lower kernel thickness.",
            ),
            CropDriverItem(
                category="Palm Senility and Aging Trees",
                impact="bullish",
                title="Over-aged Palm Yield Decline & Pest Stress",
                description="Over 40% of coconut palms in the Tumakuru basin exceed 50–60 years with declining per-tree yield, compounded by Rugose Spiralling Whitefly infestations.",
            ),
            CropDriverItem(
                category="Government Support & NAFED Procurement",
                impact="bullish",
                title="NAFED Ball Copra MSP Floor Protection",
                description="Government of India Minimum Support Price (₹12,000–₹13,500/quintal) provides guaranteed floor procurement, preventing crash losses during supply flushes.",
            ),
        ],
    ),
    "Tomato": CropDomainProfile(
        commodity="Tomato",
        market="Kolar APMC",
        optimal_storage_duration="1 to 7 days in ambient shade; up to 14 days at 10–13°C",
        spoilage_risk="Extremely High; daily deterioration rate of 1.5–3.0% under ambient conditions",
        drivers=[
            CropDriverItem(
                category="Perishable Harvest Flush",
                impact="watch",
                title="Kolar Daily Auction Volume Fluctuations",
                description="Kolar APMC handles heavy daily crated arrivals. Sudden arrival gluts drop spot prices by 30–50% within 48 hours.",
            ),
            CropDriverItem(
                category="Monsoon Transit Damage",
                impact="bearish",
                title="Rainfall Skin Cracking & Transit Rot",
                description="Rainfall during picking accelerates fruit cracking and bacterial soft rot during transit to Chennai and Bengaluru wholesale markets.",
            ),
            CropDriverItem(
                category="Regional Festival Demand",
                impact="bullish",
                title="South Indian Urban Food Service Spikes",
                description="Regional temple festivals and wedding seasons trigger temporary procurement surges from Tamil Nadu and Andhra Pradesh buyers.",
            ),
        ],
    ),
}


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
    domain_profile: CropDomainProfile | None = None
    numeric_price_adjustment_applied: bool = False
    note: str = "Weather is for the market city, not the farm. News and calendar events are context, not learned causal price adjustments. Future dates beyond the weather/calendar source coverage are unknown."


def read_context(market, commodity, decision_at, days=7, directory: Path | None = None):
    if decision_at.utcoffset() is None:
        raise ValueError("Context requires an aware decision timestamp")
    root = directory or ROOT / "data/context"
    output = MarketContext(market=market, commodity=commodity, decision_at=decision_at, domain_profile=CROP_DOMAIN_PROFILES.get(commodity))
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
