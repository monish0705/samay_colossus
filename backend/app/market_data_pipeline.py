"""SAMAY Agricultural Market Data Engineering Module.

Provides robust, auditable ingestion, quality validation, outlier detection,
historical gap analysis, provenance tracking, and resilient API fallback
for Karnataka APMC mandis (focused on Kolar APMC, Shivamogga, Hubballi, Tiptur, Bengaluru).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Literal

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db import SessionLocal, engine
from app.db_migration import upgrade_database
from app.ingestion import commodity_name, market_name
from app.models import Commodity, MandiObservation, Market, MarketPrice

logger = logging.getLogger("samay.market_data")

# Known Karnataka APMC Corridors
SUPPORTED_MARKETS: dict[str, str] = {
    "kolar": "Kolar APMC",
    "kolar apmc": "Kolar APMC",
    "kolar mandi": "Kolar APMC",
    "shivamogga": "Shivamogga Mandi",
    "shivamogga mandi": "Shivamogga Mandi",
    "shivamogga apmc": "Shivamogga Mandi",
    "shimoga": "Shivamogga Mandi",
    "shimoga apmc": "Shivamogga Mandi",
    "hubballi": "Hubballi APMC",
    "hubballi apmc": "Hubballi APMC",
    "hubli": "Hubballi APMC",
    "hubli apmc": "Hubballi APMC",
    "amargol": "Hubballi APMC",
    "apmc amargol": "Hubballi APMC",
    "tiptur": "Tiptur APMC",
    "tiptur apmc": "Tiptur APMC",
    "tiptur mandi": "Tiptur APMC",
    "bengaluru": "Bengaluru APMC",
    "bengaluru apmc": "Bengaluru APMC",
    "bangalore": "Bengaluru APMC",
    "bangalore apmc": "Bengaluru APMC",
    "yeshwanthpur": "Bengaluru APMC",
    "yeshwanthpur apmc": "Bengaluru APMC",
}

MARKET_DISTRICTS: dict[str, str] = {
    "Kolar APMC": "Kolar",
    "Shivamogga Mandi": "Shivamogga",
    "Hubballi APMC": "Dharwad",
    "Tiptur APMC": "Tumakuru",
    "Bengaluru APMC": "Bengaluru Urban",
}

SUPPORTED_COMMODITIES: dict[str, str] = {
    "tomato": "Tomato",
    "tomatoes": "Tomato",
    "arecanut": "Arecanut",
    "areca nut": "Arecanut",
    "betelnut": "Arecanut",
    "betel nut": "Arecanut",
    "adike": "Arecanut",
    "supari": "Arecanut",
    "onion": "Onion",
    "onions": "Onion",
    "eerulli": "Onion",
    "pyaz": "Onion",
    "copra": "Copra",
    "kobbari": "Copra",
    "ball copra": "Copra",
    "copra (kobbari)": "Copra",
    "dry coconut": "Copra",
    "potato": "Potato",
    "potatoes": "Potato",
    "aaloo": "Potato",
    "alugadde": "Potato",
}

UNIT_FACTORS: dict[str, Decimal] = {
    "inr/quintal": Decimal("1"),
    "rs/quintal": Decimal("1"),
    "rs./quintal": Decimal("1"),
    "inr/100kg": Decimal("1"),
    "rs/100kg": Decimal("1"),
    "inr/kg": Decimal("100"),
    "rs/kg": Decimal("100"),
    "rs./kg": Decimal("100"),
    "inr/tonne": Decimal("0.1"),
    "rs/tonne": Decimal("0.1"),
}

# Outlier review thresholds (Never silently deleted; flagged for audit)
OUTLIER_THRESHOLDS_INR_PER_QUINTAL: dict[str, Decimal] = {
    "Tomato": Decimal("15000"),
    "Arecanut": Decimal("120000"),
    "Onion": Decimal("10000"),
    "Copra": Decimal("45000"),
    "Potato": Decimal("10000"),
}

# Freshness thresholds (calendar days)
STALE_THRESHOLD_DAYS: dict[str, int] = {
    "Tomato": 7,      # Perishable: 7 days
    "Arecanut": 30,   # Cash crop durable
    "Onion": 14,      # Semi-perishable
    "Copra": 30,      # Durable
    "Potato": 14,     # Cold storage / semi-perishable
}

OGD_API_DAILY_RESOURCE = "9ef84268-d588-465a-a308-a864a43d0070"
OGD_API_VARIETY_RESOURCE = "35985678-0d79-46b4-9ed6-6f13308a1d24"


class MandiMarketDataPipeline:
    """Production-grade agricultural market data pipeline for SAMAY."""

    def __init__(self, api_key: str | None = None, timeout_seconds: float = 5.0):
        self.api_key = api_key or os.getenv("OGD_API_KEY") or os.getenv("DATA_GOV_IN_API_KEY")
        self.timeout_seconds = timeout_seconds

    # -------------------------------------------------------------------------
    # NORMALIZATION ENGINE
    # -------------------------------------------------------------------------
    @staticmethod
    def normalize_crop(name: str) -> str:
        try:
            return commodity_name(str(name))
        except ValueError as exc:
            key = re.sub(r"\s+", " ", str(name).strip()).casefold()
            if key in SUPPORTED_COMMODITIES:
                return SUPPORTED_COMMODITIES[key]
            raise ValueError(f"Unsupported commodity: {name!r}") from exc

    @staticmethod
    def normalize_mandi(name: str) -> str:
        try:
            return market_name(str(name))
        except ValueError as exc:
            key = re.sub(r"\s+", " ", str(name).strip()).casefold()
            if key in SUPPORTED_MARKETS:
                return SUPPORTED_MARKETS[key]
            raise ValueError(f"Unsupported market/mandi: {name!r}") from exc

    @staticmethod
    def normalize_variety(variety: str | None) -> str:
        if not variety:
            return "unspecified"
        clean = re.sub(r"\s+", " ", str(variety).strip()).casefold()
        return clean or "unspecified"

    @staticmethod
    def normalize_grade(grade: str | None) -> str:
        if not grade:
            return "unspecified"
        clean = re.sub(r"\s+", " ", str(grade).strip()).casefold()
        return clean or "unspecified"

    @staticmethod
    def parse_reporting_date(raw_date: Any, date_format: str | None = None) -> date:
        if isinstance(raw_date, date):
            return raw_date
        if isinstance(raw_date, datetime):
            return raw_date.date()
        date_str = str(raw_date).strip()
        if not date_str:
            raise ValueError("Empty arrival/report date")

        formats = [date_format] if date_format else ["%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d/%b/%Y", "%d-%b-%Y"]
        for fmt in formats:
            if not fmt:
                continue
            try:
                parsed = datetime.strptime(date_str, fmt).date()
                if parsed > datetime.now(UTC).date() + timedelta(days=1):
                    raise ValueError(f"Reporting date cannot be in the future: {parsed}")
                return parsed
            except ValueError:
                continue

        # ISO format fallback
        try:
            parsed = date.fromisoformat(date_str)
            if parsed > datetime.now(UTC).date() + timedelta(days=1):
                raise ValueError(f"Reporting date cannot be in the future: {parsed}")
            return parsed
        except ValueError:
            pass

        raise ValueError(f"Unable to parse reporting date: {raw_date!r}")

    @staticmethod
    def parse_number(value: Any) -> Decimal:
        if value is None:
            raise ValueError("Numeric value is missing")
        if isinstance(value, (int, float, Decimal)):
            val = Decimal(str(value))
        else:
            cleaned = str(value).strip().replace(",", "")
            if not re.fullmatch(r"^-?\d+(?:\.\d+)?$", cleaned):
                raise ValueError(f"Invalid numeric string: {value!r}")
            try:
                val = Decimal(cleaned)
            except InvalidOperation as exc:
                raise ValueError(f"Invalid decimal price: {value!r}") from exc

        if not val.is_finite():
            raise ValueError("Non-finite numeric price")
        return val

    @staticmethod
    def normalize_unit_factor(unit_raw: str | None) -> Decimal:
        if not unit_raw:
            return Decimal("1")
        clean = re.sub(r"\s+", "", str(unit_raw).strip().lower()).replace("₹", "inr").replace("rs.", "rs")
        for k, factor in UNIT_FACTORS.items():
            if k.replace(".", "").replace("/", "") in clean or clean in k:
                return factor
        return Decimal("1")

    # -------------------------------------------------------------------------
    # QUALITY & VALIDATION ENGINE
    # -------------------------------------------------------------------------
    def validate_record(self, raw: dict, default_unit: str = "INR/quintal") -> tuple[dict | None, str | None, bool]:
        """Validate an individual price record.
        
        Returns: (normalized_record, error_reason, is_outlier_spike)
        Rejects:
          - Negative prices
          - Missing required fields
          - Price ordering violation (min > modal or modal > max)
          - Unsupported market or commodity outside Karnataka corridors
        Preserves:
          - Legitimate price spikes (flagged with is_outlier=True, not deleted)
        """
        try:
            # Map common aliases
            state = raw.get("State") or raw.get("state") or "Karnataka"
            if re.sub(r"\s+", " ", str(state).strip()).casefold() != "karnataka":
                return None, "Outside Karnataka scope", False

            raw_market = raw.get("Market") or raw.get("market") or raw.get("market_name")
            if not raw_market:
                return None, "Missing market name", False
            market_name = self.normalize_mandi(raw_market)

            raw_crop = raw.get("Commodity") or raw.get("commodity") or raw.get("crop_name")
            if not raw_crop:
                return None, "Missing commodity name", False
            commodity = self.normalize_crop(raw_crop)

            variety = self.normalize_variety(raw.get("Variety") or raw.get("variety"))
            grade = self.normalize_grade(raw.get("Grade") or raw.get("grade"))

            raw_date = raw.get("Arrival_Date") or raw.get("arrival_date") or raw.get("report_date") or raw.get("date")
            arrival_date = self.parse_reporting_date(raw_date)

            # Parse unit and factor
            raw_unit = raw.get("Price_Unit") or raw.get("price_unit") or raw.get("unit") or default_unit
            factor = self.normalize_unit_factor(raw_unit)

            # Prices
            min_raw = raw.get("Min_Price") if "Min_Price" in raw else (raw.get("min_price") if "min_price" in raw else raw.get("min"))
            modal_raw = raw.get("Modal_Price") if "Modal_Price" in raw else (raw.get("modal_price") if "modal_price" in raw else raw.get("modal"))
            max_raw = raw.get("Max_Price") if "Max_Price" in raw else (raw.get("max_price") if "max_price" in raw else raw.get("max"))

            min_price = (self.parse_number(min_raw) * factor).quantize(Decimal("0.01"))
            modal_price = (self.parse_number(modal_raw) * factor).quantize(Decimal("0.01"))
            max_price = (self.parse_number(max_raw) * factor).quantize(Decimal("0.01"))

            # Quality Rule 1: Negative Price Rejection
            if min_price < 0 or modal_price < 0 or max_price < 0:
                return None, "Negative price rejected", False

            # Quality Rule 2: Invalid Price Order
            if not (min_price <= modal_price <= max_price):
                return None, f"Impossible price order: min({min_price}) <= modal({modal_price}) <= max({max_price}) violated", False

            # Quality Rule 3: Zero modal price rejection
            if modal_price <= 0:
                return None, "Modal price must be strictly positive", False

            district = raw.get("District") or raw.get("district") or MARKET_DISTRICTS.get(market_name, "Kolar")

            # Outlier Detection (Quality Rule: Never silently delete legitimate spikes)
            spike_threshold = OUTLIER_THRESHOLDS_INR_PER_QUINTAL.get(commodity, Decimal("50000"))
            is_spike = modal_price > spike_threshold

            normalized = {
                "commodity": commodity,
                "variety": variety,
                "grade": grade,
                "market_name": market_name,
                "district": district,
                "state": "Karnataka",
                "arrival_date": arrival_date,
                "minimum_price": min_price,
                "modal_price": modal_price,
                "maximum_price": max_price,
                "price_unit": "INR/quintal",
                "raw_unit": str(raw_unit),
                "source": raw.get("source") or "Government of India Open Government Data (data.gov.in)",
                "source_record_id": str(raw.get("source_record_id") or raw.get("id") or ""),
                "is_outlier": is_spike,
            }
            return normalized, None, is_spike

        except Exception as exc:
            return None, str(exc), False

    # -------------------------------------------------------------------------
    # HISTORICAL GAP DETECTION
    # -------------------------------------------------------------------------
    @staticmethod
    def detect_historical_gaps(dates: list[date]) -> dict[str, Any]:
        """Analyze time series continuity and identify unreported calendar intervals."""
        if not dates:
            return {"total_observations": 0, "missing_days": 0, "gaps": []}
        sorted_dates = sorted(set(dates))
        start_date = sorted_dates[0]
        end_date = sorted_dates[-1]
        calendar_days = (end_date - start_date).days + 1
        observed_set = set(sorted_dates)

        missing_dates = []
        gaps = []
        current_gap: list[date] = []

        curr = start_date
        while curr <= end_date:
            if curr not in observed_set:
                missing_dates.append(curr)
                current_gap.append(curr)
            else:
                if current_gap:
                    gaps.append({
                        "gap_start": current_gap[0].isoformat(),
                        "gap_end": current_gap[-1].isoformat(),
                        "days_count": len(current_gap),
                    })
                    current_gap = []
            curr += timedelta(days=1)

        if current_gap:
            gaps.append({
                "gap_start": current_gap[0].isoformat(),
                "gap_end": current_gap[-1].isoformat(),
                "days_count": len(current_gap),
            })

        return {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "calendar_days": calendar_days,
            "observed_days": len(sorted_dates),
            "missing_days_count": len(missing_dates),
            "reporting_completeness_pct": round(len(sorted_dates) / max(calendar_days, 1) * 100, 2),
            "gaps": gaps,
        }

    # -------------------------------------------------------------------------
    # RESILIENT EXTERNAL INGESTION (OGD / AGMARKNET)
    # -------------------------------------------------------------------------
    def fetch_live_mandi_prices(self, commodity: str = "Tomato", market: str = "Kolar APMC") -> dict[str, Any]:
        """Fetch current prices from Government of India OGD platform with fallback resilience.
        
        If API key is missing or network/endpoint fails, seamlessly falls back to
        the verified cached snapshot and transparently returns data_status='CACHED'
        with its last updated timestamp.
        """
        canonical_crop = self.normalize_crop(commodity)
        canonical_market = self.normalize_mandi(market)

        if not self.api_key:
            logger.info("No OGD API key configured; activating verified cache fallback.")
            return self._fallback_from_cache(canonical_crop, canonical_market, reason="api_key_not_configured")

        # Query OGD API
        params = {
            "api-key": self.api_key,
            "format": "json",
            "limit": 50,
            "filters[State]": "Karnataka",
            "filters[Market]": canonical_market,
            "filters[Commodity]": canonical_crop,
            "sort[Arrival_Date]": "desc",
        }
        query_string = urllib.parse.urlencode(params)
        url = f"https://api.data.gov.in/resource/{OGD_API_VARIETY_RESOURCE}?{query_string}"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SAMAY-AgriTech/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    records = data.get("records", [])
                    if records:
                        return {
                            "status": "success",
                            "data_status": "LIVE",
                            "source": "Government of India Open Government Data (data.gov.in)",
                            "fetched_at": datetime.now(UTC).isoformat(),
                            "records_count": len(records),
                            "records": records,
                        }
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            logger.warning("OGD API fetch failed (%s); activating verified cache fallback.", exc)
            return self._fallback_from_cache(canonical_crop, canonical_market, reason=f"network_or_api_error: {exc}")

        return self._fallback_from_cache(canonical_crop, canonical_market, reason="no_records_returned")

    def _fallback_from_cache(self, commodity: str, market: str, reason: str = "fallback") -> dict[str, Any]:
        """Retrieve latest verified cached observations from database when external API is unreachable."""
        with SessionLocal() as session:
            latest_price = session.scalar(
                select(MarketPrice)
                .where(MarketPrice.commodity == commodity, MarketPrice.market_name == market)
                .order_by(MarketPrice.arrival_date.desc(), MarketPrice.id.desc())
            )

            if latest_price is None:
                return {
                    "status": "unavailable",
                    "data_status": "UNAVAILABLE",
                    "message": f"No verified price observations exist for {commodity} at {market}",
                    "reason": reason,
                    "records_count": 0,
                    "records": [],
                }

            days_old = (datetime.now(UTC).date() - latest_price.arrival_date).days
            freshness_limit = STALE_THRESHOLD_DAYS.get(commodity, 14)
            data_status = "STALE" if days_old > freshness_limit else "CACHED"

            return {
                "status": "success",
                "data_status": data_status,
                "reason": f"External API unavailable ({reason}); served from verified historical cache",
                "source": latest_price.source,
                "last_updated": latest_price.arrival_date.isoformat(),
                "age_calendar_days": days_old,
                "latest_record": {
                    "commodity": latest_price.commodity,
                    "variety": latest_price.variety,
                    "market_name": latest_price.market_name,
                    "district": latest_price.district,
                    "arrival_date": latest_price.arrival_date.isoformat(),
                    "modal_price": float(latest_price.modal_price),
                    "minimum_price": float(latest_price.minimum_price),
                    "maximum_price": float(latest_price.maximum_price),
                    "price_unit": latest_price.price_unit,
                    "data_status": data_status,
                    "source": latest_price.source,
                },
            }

    # -------------------------------------------------------------------------
    # CSV DATASET INGESTION
    # -------------------------------------------------------------------------
    def import_csv(
        self,
        path: Path | str,
        source_label: str = "Official Mandi Export",
        default_unit: str = "INR/quintal",
        data_status: Literal["LIVE", "CACHED", "SAMPLE", "STALE"] = "CACHED",
        session: Session | None = None,
    ) -> dict[str, Any]:
        """Ingest a CSV file into market_prices with validation, deduplication, and quality tracking."""
        csv_path = Path(path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        raw_bytes = csv_path.read_bytes()
        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()

        reader = csv.DictReader(io.StringIO(raw_bytes.decode("utf-8-sig"), newline=""))
        if not reader.fieldnames:
            raise ValueError("CSV has no headers or is empty")

        own_session = session is None
        db_session = session or SessionLocal()

        stats = {
            "records_read": 0,
            "inserted": 0,
            "duplicates": 0,
            "quarantined": 0,
            "outliers_flagged": 0,
            "file_sha256": file_sha256,
            "quarantine_reasons": {},
        }
        observed_dates = []

        try:
            for row in reader:
                stats["records_read"] += 1
                row["source"] = source_label
                row["source_record_id"] = f"{file_sha256[:8]}-{stats['records_read']}"

                normalized, error_reason, is_spike = self.validate_record(row, default_unit=default_unit)
                if normalized is None:
                    stats["quarantined"] += 1
                    stats["quarantine_reasons"][error_reason] = stats["quarantine_reasons"].get(error_reason, 0) + 1
                    continue

                if is_spike:
                    stats["outliers_flagged"] += 1

                # Idempotent deduplication on natural key
                existing = db_session.scalar(
                    select(MarketPrice).where(
                        MarketPrice.commodity == normalized["commodity"],
                        MarketPrice.variety == normalized["variety"],
                        MarketPrice.market_name == normalized["market_name"],
                        MarketPrice.arrival_date == normalized["arrival_date"],
                    )
                )

                if existing is not None:
                    stats["duplicates"] += 1
                    # Refresh values if identical
                    continue

                mp = MarketPrice(
                    commodity=normalized["commodity"],
                    variety=normalized["variety"],
                    market_name=normalized["market_name"],
                    district=normalized["district"],
                    state=normalized["state"],
                    arrival_date=normalized["arrival_date"],
                    minimum_price=normalized["minimum_price"],
                    maximum_price=normalized["maximum_price"],
                    modal_price=normalized["modal_price"],
                    price_unit=normalized["price_unit"],
                    source=source_label,
                    source_record_id=normalized["source_record_id"],
                    imported_at=datetime.now(UTC),
                    data_status=data_status,
                )
                db_session.add(mp)
                stats["inserted"] += 1
                observed_dates.append(normalized["arrival_date"])

            db_session.commit()

            gap_analysis = self.detect_historical_gaps(observed_dates) if observed_dates else {}
            stats["gap_analysis"] = gap_analysis
            logger.info("Imported CSV %s: %s", csv_path.name, stats)
            return stats

        finally:
            if own_session:
                db_session.close()

    # -------------------------------------------------------------------------
    # PIPELINE STATUS REPORTING
    # -------------------------------------------------------------------------
    def get_status(self, session: Session | None = None) -> dict[str, Any]:
        """Comprehensive pipeline health, freshness, and provenance summary."""
        own_session = session is None
        db_session = session or SessionLocal()

        try:
            total_prices = db_session.scalar(select(func.count()).select_from(MarketPrice)) or 0
            markets_count = db_session.scalar(select(func.count()).select_from(Market)) or 0
            commodities_count = db_session.scalar(select(func.count()).select_from(Commodity)) or 0

            # Group by commodity
            crops_summary = []
            crop_groups = db_session.execute(
                select(
                    MarketPrice.commodity,
                    MarketPrice.market_name,
                    func.count(MarketPrice.id),
                    func.min(MarketPrice.arrival_date),
                    func.max(MarketPrice.arrival_date),
                )
                .group_by(MarketPrice.commodity, MarketPrice.market_name)
            ).all()

            today = datetime.now(UTC).date()
            for crop, market, cnt, min_date, max_date in crop_groups:
                age_days = (today - max_date).days if max_date else None
                limit = STALE_THRESHOLD_DAYS.get(crop, 14)
                status = "STALE" if (age_days is not None and age_days > limit) else "CACHED"
                crops_summary.append({
                    "crop": crop,
                    "market": market,
                    "records_count": cnt,
                    "earliest_date": min_date.isoformat() if min_date else None,
                    "latest_date": max_date.isoformat() if max_date else None,
                    "age_days": age_days,
                    "status": status,
                })

            # Check external API availability
            api_status = "configured" if self.api_key else "offline_cache_mode"

            return {
                "pipeline": "SAMAY AgriTech Market Data Pipeline",
                "version": "1.0.0",
                "database_status": "operational",
                "total_price_records": total_prices,
                "total_mandis": markets_count,
                "total_commodities": commodities_count,
                "external_api": {
                    "source": "Government of India Open Government Data (data.gov.in)",
                    "catalog_url": "https://www.data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi",
                    "status": api_status,
                    "primary_corridor": "Kolar APMC (Tomato)",
                },
                "series": crops_summary,
            }
        finally:
            if own_session:
                db_session.close()


# Module singleton instance
pipeline = MandiMarketDataPipeline()
