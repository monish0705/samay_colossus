"""Private purchasing records; quantities are integer thousandths of a quintal."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import business_models  # noqa: F401
from app.db import Base, UTCDateTime
from app.models import Record
from app.sale_models import now


class PurchaseOffer(Record, Base):
    __tablename__ = "purchase_offers"
    __table_args__ = (
        UniqueConstraint("business_id", "submission_key"),
        CheckConstraint(
            "total_milli > 0 AND reserved_milli >= 0 AND committed_milli >= 0 AND reserved_milli + committed_milli <= total_milli"
        ),
        CheckConstraint("status IN ('DRAFT','PUBLISHED','PAUSED','PARTIALLY_FILLED','FULLY_FILLED','EXPIRED','CANCELLED')"),
    )
    business_id: Mapped[int] = mapped_column(ForeignKey("business_accounts.id"), index=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"))
    total_milli: Mapped[int]
    reserved_milli: Mapped[int] = mapped_column(default=0)
    committed_milli: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    version: Mapped[int] = mapped_column(default=1)
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)
    price_updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    submission_key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))


class PurchaseRequirements(Base):
    __tablename__ = "purchase_offer_requirements"
    offer_id: Mapped[int] = mapped_column(ForeignKey("purchase_offers.id"), primary_key=True)
    terms: Mapped[dict] = mapped_column(JSON)


class PurchasePrice(Record, Base):
    __tablename__ = "purchase_offer_prices"
    offer_id: Mapped[int] = mapped_column(ForeignKey("purchase_offers.id"), index=True)
    revision: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    price_kind: Mapped[str] = mapped_column(String(30))
    actor_id: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"))


class PurchaseHistory(Record, Base):
    __tablename__ = "purchase_offer_history"
    offer_id: Mapped[int] = mapped_column(ForeignKey("purchase_offers.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"))
    action: Mapped[str] = mapped_column(String(40))
    revision: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSON)


class FarmerPurchaseRequest(Record, Base):
    __tablename__ = "farmer_sale_requests"
    __table_args__ = (
        UniqueConstraint("farmer_id", "submission_key"),
        CheckConstraint("quantity_milli > 0 AND expected_price > 0"),
        CheckConstraint("status IN ('SUBMITTED','ACCEPTED','COUNTEROFFERED','CONFIRMED','REJECTED','CANCELLED','EXPIRED')"),
    )
    public_id: Mapped[str] = mapped_column(String(80), unique=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("purchase_offers.id"), index=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"), index=True)
    quantity_milli: Mapped[int]
    expected_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    arrival_at: Mapped[datetime] = mapped_column(UTCDateTime())
    details: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default="SUBMITTED")
    version: Mapped[int] = mapped_column(default=1)
    submission_key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))


class BusinessResponse(Record, Base):
    __tablename__ = "business_responses"
    request_id: Mapped[int] = mapped_column(ForeignKey("farmer_sale_requests.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    quantity_milli: Mapped[int]
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    arrival_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    terms: Mapped[dict] = mapped_column(JSON)


class PurchaseReservation(Record, Base):
    __tablename__ = "purchase_offer_quantity_reservations"
    __table_args__ = (CheckConstraint("quantity_milli > 0"), CheckConstraint("state IN ('HELD','COMMITTED','RELEASED')"))
    offer_id: Mapped[int] = mapped_column(ForeignKey("purchase_offers.id"), index=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("business_responses.id"), unique=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("farmer_sale_requests.id"), index=True)
    quantity_milli: Mapped[int]
    arrival_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    state: Mapped[str] = mapped_column(String(20), default="HELD")


class PurchaseRequestHistory(Record, Base):
    __tablename__ = "private_purchase_request_history"
    request_id: Mapped[int] = mapped_column(ForeignKey("farmer_sale_requests.id"), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"))
    action: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON)


class PurchaseNotification(Record, Base):
    __tablename__ = "private_purchase_notifications"
    recipient_id: Mapped[int] = mapped_column(ForeignKey("mandi_users.id"), index=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("business_accounts.id"), index=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("purchase_offers.id"))
    request_id: Mapped[int | None] = mapped_column(ForeignKey("farmer_sale_requests.id"))
    message: Mapped[dict] = mapped_column(JSON)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
