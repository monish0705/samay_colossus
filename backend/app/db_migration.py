"""Database schema upgrade & seeding for agricultural market data engineering module."""
import logging
from decimal import Decimal
from datetime import UTC, datetime
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from app.db import engine, Base
from app.models import Market, Commodity, MarketPrice, MandiObservation

logger = logging.getLogger("samay.db_migration")

DEFAULT_MARKET_COORDINATES = {
    "Kolar APMC": (Decimal("13.136700"), Decimal("78.134800")),
    "Bengaluru APMC": (Decimal("13.028000"), Decimal("77.540400")),
    "Shivamogga Mandi": (Decimal("13.929900"), Decimal("75.568100")),
    "Hubballi APMC": (Decimal("15.364700"), Decimal("75.124000")),
    "Tiptur APMC": (Decimal("13.263500"), Decimal("76.477000")),
}

COMMODITY_METADATA = {
    "Tomato": {
        "category": "Vegetable",
        "standard_unit": "INR/quintal",
        "perishability_class": "Highly Perishable (1-7 days)",
    },
    "Arecanut": {
        "category": "Cash Crop / Plantation",
        "standard_unit": "INR/quintal",
        "perishability_class": "Very Durable (60-730 days)",
    },
    "Onion": {
        "category": "Vegetable / Bulb",
        "standard_unit": "INR/quintal",
        "perishability_class": "Semi-Perishable (30-120 days)",
    },
    "Copra": {
        "category": "Oilseed / Dried Nut",
        "standard_unit": "INR/quintal",
        "perishability_class": "High Storability (90-365 days)",
    },
    "Potato": {
        "category": "Tuber",
        "standard_unit": "INR/quintal",
        "perishability_class": "Perishable / Cold Storage (30-180 days)",
    },
}


def upgrade_database(bind=None) -> dict:
    """Ensure all tables, columns and seed data exist."""
    db_bind = bind or engine
    Base.metadata.create_all(db_bind)
    
    with db_bind.connect() as conn:
        inspector = inspect(db_bind)
        
        # Check markets columns
        market_cols = [c["name"] for c in inspector.get_columns("markets")]
        if "latitude" not in market_cols:
            conn.execute(text("ALTER TABLE markets ADD COLUMN latitude NUMERIC(9, 6)"))
        if "longitude" not in market_cols:
            conn.execute(text("ALTER TABLE markets ADD COLUMN longitude NUMERIC(9, 6)"))
            
        # Check commodities columns
        comm_cols = [c["name"] for c in inspector.get_columns("commodities")]
        if "category" not in comm_cols:
            conn.execute(text("ALTER TABLE commodities ADD COLUMN category VARCHAR(60) DEFAULT 'Vegetable'"))
        if "standard_unit" not in comm_cols:
            conn.execute(text("ALTER TABLE commodities ADD COLUMN standard_unit VARCHAR(40) DEFAULT 'INR/quintal'"))
        if "perishability_class" not in comm_cols:
            conn.execute(text("ALTER TABLE commodities ADD COLUMN perishability_class VARCHAR(60) DEFAULT 'perishable'"))
            
        conn.commit()

    # Seed coordinates & metadata, and sync initial market_prices
    with Session(db_bind) as session:
        # Seed markets
        for m in session.scalars(select(Market)).all():
            if m.name in DEFAULT_MARKET_COORDINATES:
                lat, lon = DEFAULT_MARKET_COORDINATES[m.name]
                if m.latitude is None or m.longitude is None:
                    m.latitude = lat
                    m.longitude = lon

        # Seed commodities
        for c in session.scalars(select(Commodity)).all():
            if c.name in COMMODITY_METADATA:
                meta = COMMODITY_METADATA[c.name]
                c.category = meta["category"]
                c.standard_unit = meta["standard_unit"]
                c.perishability_class = meta["perishability_class"]

        session.commit()

        # Check if market_prices has data; if empty, sync from verified observations
        mp_count = session.scalar(select(text("COUNT(*)")).select_from(MarketPrice))
        synced = 0
        if mp_count == 0:
            obs_rows = session.execute(
                select(MandiObservation, Market, Commodity)
                .join(Market, MandiObservation.market_id == Market.id)
                .join(Commodity, MandiObservation.commodity_id == Commodity.id)
                .where(MandiObservation.data_kind.in_(("official", "secondary")))
            ).all()

            seen_keys = set()
            for obs, m, c in obs_rows:
                key = (c.name, obs.variety, m.name, obs.observed_on)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # Determine data status
                days_old = (datetime.now(UTC).date() - obs.observed_on).days
                threshold = 7 if c.name == "Tomato" else 30
                status = "STALE" if days_old > threshold else "CACHED"
                if obs.data_kind == "fixture":
                    status = "SAMPLE"

                mp = MarketPrice(
                    commodity=c.name,
                    variety=obs.variety,
                    market_name=m.name,
                    district=m.district,
                    state=m.state,
                    arrival_date=obs.observed_on,
                    minimum_price=obs.min_price_inr_per_quintal,
                    maximum_price=obs.max_price_inr_per_quintal,
                    modal_price=obs.modal_price_inr_per_quintal,
                    price_unit=obs.price_unit or "INR/quintal",
                    source=obs.data_source,
                    source_record_id=str(obs.id),
                    imported_at=obs.created_at or datetime.now(UTC),
                    data_status=status,
                )
                session.add(mp)
                synced += 1

            session.commit()
            logger.info("Synchronized %d initial verified records into market_prices", synced)

    return {"status": "ok", "synced_records": synced}


if __name__ == "__main__":
    res = upgrade_database()
    print("Database upgrade complete:", res)

