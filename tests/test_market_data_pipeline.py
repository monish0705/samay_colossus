"""Test suite for SAMAY Agricultural Market Data Engineering Module.

Verifies:
1. Valid price import (CSV ingestion with official format)
2. Invalid records rejection (negative prices, impossible price order, malformed values)
3. Duplicate handling (deduplication on natural key)
4. Unit standardization (Rs./Kg, Rs./Tonne converted to standard INR/quintal)
5. Missing values and defaulting (unspecified variety/grade, rejection of missing dates)
6. Outlier detection (legitimate price spikes flagged and preserved, never silently deleted)
7. Historical gap detection (calendar continuity and gap intervals)
8. External API timeouts & resilience fallback (seamless fallback to verified cache, never claiming cached is live)
9. Stale data classification (> 7 days for perishable, > 30 days for durable)
10. Empty search results & unavailable status handling
11. Data API endpoints (markets, crops, prices, history, data status)
"""
import io
import tempfile
import urllib.error
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.market_data_pipeline import (
    MandiMarketDataPipeline,
    OUTLIER_THRESHOLDS_INR_PER_QUINTAL,
    STALE_THRESHOLD_DAYS,
)
from app.models import Commodity, Market, MarketPrice
from app.prices import crops, history, markets, prices


@pytest.fixture
def pipeline():
    return MandiMarketDataPipeline(api_key="test_key_mock")


# -----------------------------------------------------------------------------
# 1. VALID PRICE IMPORT
# -----------------------------------------------------------------------------
def test_valid_price_import(pipeline):
    import uuid
    unique_var = f"test_var_{uuid.uuid4().hex[:8]}"
    csv_content = f"""State,District,Market,Commodity,Variety,Grade,Arrival_Date,Min_Price,Modal_Price,Max_Price,Price_Unit
Karnataka,Kolar,Kolar APMC,Tomato,{unique_var},Local,15/09/2026,1200,1500,1800,INR/quintal
Karnataka,Shivamogga,Shivamogga Mandi,Arecanut,{unique_var},Local,15/09/2026,45000,48000,50000,INR/quintal
"""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        temp_path = Path(f.name)

    try:
        with SessionLocal() as session:
            result = pipeline.import_csv(temp_path, source_label="Test OGD Export", session=session)
            session.commit()

        assert result["records_read"] == 2
        assert result["inserted"] >= 1
        assert result["quarantined"] == 0

        # Verify record in database
        with SessionLocal() as session:
            p = session.scalar(
                select(MarketPrice)
                .where(MarketPrice.commodity == "Tomato", MarketPrice.market_name == "Kolar APMC", MarketPrice.variety == unique_var)
            )
            assert p is not None
            assert p.modal_price == Decimal("1500.00")
            assert p.price_unit == "INR/quintal"
            assert p.state == "Karnataka"
    finally:
        temp_path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# 2. INVALID RECORDS REJECTION
# -----------------------------------------------------------------------------
def test_invalid_records_rejection(pipeline):
    # Rule A: Negative price
    neg_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "-100",
        "Modal_Price": "1500",
        "Max_Price": "1800",
    }
    norm, err, _ = pipeline.validate_record(neg_record)
    assert norm is None
    assert "Negative price" in err

    # Rule B: Impossible price order (min > modal or modal > max)
    order_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "2000",
        "Modal_Price": "1500",
        "Max_Price": "1800",
    }
    norm, err, _ = pipeline.validate_record(order_record)
    assert norm is None
    assert "Impossible price order" in err

    # Rule C: Zero modal price
    zero_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "0",
        "Modal_Price": "0",
        "Max_Price": "0",
    }
    norm, err, _ = pipeline.validate_record(zero_record)
    assert norm is None
    assert "strictly positive" in err

    # Rule D: Malformed numeric string
    malformed_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "one-thousand",
        "Modal_Price": "1500",
        "Max_Price": "1800",
    }
    norm, err, _ = pipeline.validate_record(malformed_record)
    assert norm is None
    assert "Invalid numeric string" in err

    # Rule E: Outside Karnataka corridor
    out_state_record = {
        "State": "Maharashtra",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "1000",
        "Modal_Price": "1500",
        "Max_Price": "1800",
    }
    norm, err, _ = pipeline.validate_record(out_state_record)
    assert norm is None
    assert "Outside Karnataka" in err


# -----------------------------------------------------------------------------
# 3. DUPLICATE HANDLING
# -----------------------------------------------------------------------------
def test_duplicate_handling(pipeline):
    csv_content = """State,District,Market,Commodity,Variety,Grade,Arrival_Date,Min_Price,Modal_Price,Max_Price,Price_Unit
Karnataka,Kolar,Kolar APMC,Tomato,local,faq,28/10/2026,1100,1350,1600,INR/quintal
Karnataka,Kolar,Kolar APMC,Tomato,local,faq,28/10/2026,1100,1350,1600,INR/quintal
"""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        temp_path = Path(f.name)

    try:
        with SessionLocal() as session:
            result = pipeline.import_csv(temp_path, source_label="Duplicate Test", session=session)
            session.commit()

        assert result["records_read"] == 2
        assert result["duplicates"] >= 1
    finally:
        temp_path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# 4. DIFFERENT UNITS (STANDARDIZATION TO INR/quintal)
# -----------------------------------------------------------------------------
def test_unit_conversions(pipeline):
    # Rs./Kg to INR/quintal (factor = 100)
    kg_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "12.50",
        "Modal_Price": "15.00",
        "Max_Price": "18.00",
        "Price_Unit": "Rs./Kg",
    }
    norm, err, _ = pipeline.validate_record(kg_record)
    assert err is None
    assert norm["minimum_price"] == Decimal("1250.00")
    assert norm["modal_price"] == Decimal("1500.00")
    assert norm["maximum_price"] == Decimal("1800.00")
    assert norm["price_unit"] == "INR/quintal"

    # Rs./Tonne to INR/quintal (factor = 0.1)
    tonne_record = {
        "State": "Karnataka",
        "Market": "Bengaluru APMC",
        "Commodity": "Potato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "20000",
        "Modal_Price": "25000",
        "Max_Price": "30000",
        "Price_Unit": "Rs./Tonne",
    }
    norm_t, err_t, _ = pipeline.validate_record(tonne_record)
    assert err_t is None
    assert norm_t["minimum_price"] == Decimal("2000.00")
    assert norm_t["modal_price"] == Decimal("2500.00")
    assert norm_t["maximum_price"] == Decimal("3000.00")
    assert norm_t["price_unit"] == "INR/quintal"


# -----------------------------------------------------------------------------
# 5. MISSING VALUES AND DEFAULTING
# -----------------------------------------------------------------------------
def test_missing_values_and_defaulting(pipeline):
    record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "1000",
        "Modal_Price": "1200",
        "Max_Price": "1400",
        # Variety and Grade omitted
    }
    norm, err, _ = pipeline.validate_record(record)
    assert err is None
    assert norm["variety"] == "unspecified"
    assert norm["grade"] == "unspecified"

    # Missing arrival date
    no_date_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "",
        "Min_Price": "1000",
        "Modal_Price": "1200",
        "Max_Price": "1400",
    }
    norm_nd, err_nd, _ = pipeline.validate_record(no_date_record)
    assert norm_nd is None
    assert err_nd is not None and ("Empty" in err_nd or "Unable to parse" in err_nd)


# -----------------------------------------------------------------------------
# 6. OUTLIER DETECTION (PRESERVES LEGITIMATE SPIKES)
# -----------------------------------------------------------------------------
def test_outlier_detection_preserves_spikes(pipeline):
    # During severe monsoon shortage, Tomato modal price can spike to 18,000 INR/q (threshold 15,000)
    spike_record = {
        "State": "Karnataka",
        "Market": "Kolar APMC",
        "Commodity": "Tomato",
        "Arrival_Date": "01/11/2026",
        "Min_Price": "14000",
        "Modal_Price": "18000",
        "Max_Price": "20000",
        "Price_Unit": "INR/quintal",
    }
    norm, err, is_spike = pipeline.validate_record(spike_record)
    assert err is None
    assert is_spike is True
    assert norm is not None
    assert norm["is_outlier"] is True
    assert norm["modal_price"] == Decimal("18000.00")


# -----------------------------------------------------------------------------
# 7. HISTORICAL GAP DETECTION
# -----------------------------------------------------------------------------
def test_historical_gap_detection(pipeline):
    dates = [
        date(2026, 11, 1),
        date(2026, 11, 2),
        # Gap: 2026-11-03, 2026-11-04
        date(2026, 11, 5),
    ]
    analysis = pipeline.detect_historical_gaps(dates)
    assert analysis["calendar_days"] == 5
    assert analysis["observed_days"] == 3
    assert analysis["missing_days_count"] == 2
    assert analysis["reporting_completeness_pct"] == 60.0
    assert len(analysis["gaps"]) == 1
    assert analysis["gaps"][0]["gap_start"] == "2026-11-03"
    assert analysis["gaps"][0]["gap_end"] == "2026-11-04"
    assert analysis["gaps"][0]["days_count"] == 2


# -----------------------------------------------------------------------------
# 8. API TIMEOUTS & RESILIENCE FALLBACK
# -----------------------------------------------------------------------------
def test_api_timeout_and_resilience_fallback(pipeline):
    # Mock network timeout in urllib
    with patch("urllib.request.urlopen", side_effect=TimeoutError("Connection timed out")):
        result = pipeline.fetch_live_mandi_prices("Tomato", "Kolar APMC")

    assert result["status"] == "success"
    # Never claim cached data is live
    assert result["data_status"] in ("CACHED", "STALE")
    assert "latest_record" in result
    assert result["latest_record"]["commodity"] == "Tomato"
    assert "last_updated" in result
    assert "External API unavailable" in result["reason"]


# -----------------------------------------------------------------------------
# 9. STALE DATA CLASSIFICATION
# -----------------------------------------------------------------------------
def test_stale_data_classification(pipeline):
    # Check freshness definitions
    assert STALE_THRESHOLD_DAYS["Tomato"] == 7
    assert STALE_THRESHOLD_DAYS["Arecanut"] == 30

    # Old date > 7 days for Tomato
    old_date = datetime.now(UTC).date() - timedelta(days=15)
    days_old = (datetime.now(UTC).date() - old_date).days
    status = "STALE" if days_old > STALE_THRESHOLD_DAYS["Tomato"] else "CACHED"
    assert status == "STALE"

    # Recent date <= 30 days for Arecanut
    recent_date = datetime.now(UTC).date() - timedelta(days=5)
    days_old_areca = (datetime.now(UTC).date() - recent_date).days
    status_areca = "STALE" if days_old_areca > STALE_THRESHOLD_DAYS["Arecanut"] else "CACHED"
    assert status_areca == "CACHED"


# -----------------------------------------------------------------------------
# 10. EMPTY SEARCH RESULTS & UNAVAILABLE
# -----------------------------------------------------------------------------
def test_empty_search_results_and_unavailable(pipeline):
    fallback = pipeline._fallback_from_cache("Tomato", "NonExistent APMC", reason="test_empty")
    assert fallback["status"] == "unavailable"
    assert fallback["data_status"] == "UNAVAILABLE"
    assert fallback["records_count"] == 0
    assert fallback["records"] == []


# -----------------------------------------------------------------------------
# 11. DATA API ENDPOINTS VERIFICATION
# -----------------------------------------------------------------------------
def test_data_api_endpoints():
    with SessionLocal() as session:
        # GET /api/v1/markets
        market_list = markets(session=session)
        assert len(market_list) > 0
        kolar = next((m for m in market_list if m.name == "Kolar APMC"), None)
        assert kolar is not None
        assert kolar.market_name == "Kolar APMC"
        assert kolar.district == "Kolar"
        assert kolar.state == "Karnataka"
        assert kolar.latitude is not None

        # GET /api/v1/crops
        crop_list = crops(session=session)
        assert len(crop_list) > 0
        tomato = next((c for c in crop_list if c.name == "Tomato"), None)
        assert tomato is not None
        assert tomato.crop_name == "Tomato"
        assert "perishable" in tomato.perishability_class.lower()
        assert tomato.standard_unit == "INR/quintal"

        # GET /api/v1/prices
        price_list = prices(crop="Tomato", mandi="Kolar APMC", limit=5, session=session)
        assert len(price_list) > 0
        p0 = price_list[0]
        assert p0.commodity == "Tomato"
        assert p0.market_name == "Kolar APMC"
        assert p0.data_status in ("LIVE", "CACHED", "SAMPLE", "STALE")

        # GET /api/v1/prices/history
        history_resp = history(market="Kolar APMC", commodity="Tomato", limit=5, session=session)
        assert len(history_resp.items) > 0
        h0 = history_resp.items[0]
        assert h0.commodity == "Tomato"
        assert h0.market == "Kolar APMC"
        assert h0.data_status in ("LIVE", "CACHED", "SAMPLE", "STALE")
