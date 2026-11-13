"""Explicit, idempotent development-only DEMO_DATA seed; never a live feed."""
from datetime import date
from decimal import Decimal

from app.config import get_settings
from app.db import SessionLocal
from app.models import Commodity, MandiObservation, Market
from sqlalchemy import select


def main():
    if get_settings().environment != "development":
        raise SystemExit("DEMO_DATA seed is allowed only in development")
    with SessionLocal.begin() as session:
        market = session.scalar(select(Market).where(Market.name == "DEMO_DATA Market", Market.district == "Demo District", Market.state == "Demo State"))
        if market is None:
            market = Market(name="DEMO_DATA Market", district="Demo District", state="Demo State", data_source="DEMO_DATA")
            session.add(market)
        commodity = session.scalar(select(Commodity).where(Commodity.name == "DEMO_DATA Wheat"))
        if commodity is None:
            commodity = Commodity(name="DEMO_DATA Wheat", data_source="DEMO_DATA")
            session.add(commodity)
        session.flush()
        existing = session.scalar(select(MandiObservation).where(MandiObservation.market_id == market.id, MandiObservation.commodity_id == commodity.id, MandiObservation.observed_on == date(2025, 1, 1), MandiObservation.variety == "DEMO_DATA"))
        if existing is None:
            session.add(MandiObservation(market_id=market.id, commodity_id=commodity.id, observed_on=date(2025, 1, 1), variety="DEMO_DATA", min_price_inr_per_quintal=Decimal(2000), modal_price_inr_per_quintal=Decimal(2100), max_price_inr_per_quintal=Decimal(2200), arrivals_quintals=Decimal(100), data_source="DEMO_DATA"))
    print("DEMO_DATA initialized. Synthetic development fixture; not market evidence.")


if __name__ == "__main__":
    main()
