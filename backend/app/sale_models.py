"""Marketplace identity and audit tables. No operational accounts are seeded."""
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime
from app.models import Record


def now():
    return datetime.now(UTC)


class SaleUser(Record, Base):
    __tablename__ = 'mandi_users'
    __table_args__ = (CheckConstraint("role IN ('FARMER','MANDI_OWNER','MANDI_STAFF','SYSTEM_ADMIN')"),)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(2), default='en')


class SaleSession(Base):
    __tablename__ = 'sale_sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())


class MandiRegistration(Base):
    __tablename__ = 'mandi_registrations'
    market_id: Mapped[int] = mapped_column(ForeignKey('markets.id'), primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    registration_details: Mapped[str] = mapped_column(String(1000))
    approved_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    approved_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    # Registry-backed commodity IDs; no invented fixed number of crops/markets.
    commodity_ids: Mapped[list] = mapped_column(JSON)


class MandiAssignment(Base):
    __tablename__ = 'mandi_user_market_assignments'
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), primary_key=True)
    market_id: Mapped[int] = mapped_column(ForeignKey('markets.id'), primary_key=True)
    can_transact: Mapped[bool] = mapped_column(Boolean, default=False)


class SaleInvitation(Record, Base):
    __tablename__ = 'sale_invitations'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(30))
    market_id: Mapped[int] = mapped_column(ForeignKey('markets.id'))
    approved_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    identity_evidence: Mapped[str] = mapped_column(String(1000))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class ContactChallenge(Record, Base):
    __tablename__ = 'sale_contact_challenges'
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class SaleRequest(Record, Base):
    __tablename__ = 'sale_requests'
    __table_args__ = (UniqueConstraint('farmer_id', 'idempotency_key'),
        CheckConstraint('requested_quantity > 0 AND requested_quantity <= total_harvest_quantity'),
        CheckConstraint('expected_price_per_quintal > 0 AND estimated_costs_inr >= 0 AND version >= 1'),
        CheckConstraint("status IN ('SUBMITTED','NOTIFICATION_PENDING','NOTIFIED','VIEWED','MANDI_ACCEPTED','COUNTER_OFFERED','FARMER_CONFIRMED','ARRIVAL_SCHEDULED','ARRIVED','WEIGHED','COMPLETED','REJECTED','CANCELLED','EXPIRED')"))
    public_request_id: Mapped[str] = mapped_column(String(80), unique=True)
    farmer_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), index=True)
    mandi_id: Mapped[int] = mapped_column(ForeignKey('markets.id'), index=True)
    crop_id: Mapped[int] = mapped_column(ForeignKey('commodities.id'))
    variety: Mapped[str] = mapped_column(String(120))
    grade: Mapped[str] = mapped_column(String(120))
    total_harvest_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    requested_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    expected_price_per_quintal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    reference_modal_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    reference_price_observation_id: Mapped[int | None] = mapped_column(ForeignKey('mandi_observations.id'))
    preferred_arrival_at: Mapped[datetime] = mapped_column(UTCDateTime())
    estimated_costs_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    farmer_message: Mapped[str] = mapped_column(String(2000), default='')
    contact_sharing_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(40), index=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now)
    version: Mapped[int] = mapped_column(default=1)
    idempotency_key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))


class SaleEvent(Record, Base):
    __tablename__ = 'sale_request_events'
    request_id: Mapped[int] = mapped_column(ForeignKey('sale_requests.id'), index=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    from_status: Mapped[str | None] = mapped_column(String(40))
    to_status: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class SaleOffer(Record, Base):
    __tablename__ = 'sale_request_offers'
    __table_args__ = (CheckConstraint('quantity > 0 AND price > 0'),)
    request_id: Mapped[int] = mapped_column(ForeignKey('sale_requests.id'), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    kind: Mapped[str] = mapped_column(String(30))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    arrival_at: Mapped[datetime] = mapped_column(UTCDateTime())
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    message: Mapped[str] = mapped_column(String(2000), default='')


class ArrivalBooking(Record, Base):
    __tablename__ = 'sale_arrival_bookings'
    request_id: Mapped[int] = mapped_column(ForeignKey('sale_requests.id'), unique=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey('sale_request_offers.id'))
    arrival_at: Mapped[datetime] = mapped_column(UTCDateTime())
    confirmed_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    arrived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    received_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))


class SaleTransaction(Record, Base):
    __tablename__ = 'sale_transaction_records'
    __table_args__ = (CheckConstraint('weighed_quantity > 0 AND final_price > 0 AND deductions_inr >= 0 AND deductions_inr <= gross_inr AND net_inr >= 0'),)
    request_id: Mapped[int] = mapped_column(ForeignKey('sale_requests.id'), unique=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    weighed_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    final_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    quality: Mapped[str] = mapped_column(String(1000))
    gross_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    deductions_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    net_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    payment_status: Mapped[str] = mapped_column(String(30))
    payment_reference: Mapped[str] = mapped_column(String(255), default='')


class Notification(Record, Base):
    __tablename__ = 'notifications'
    recipient_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), index=True)
    mandi_id: Mapped[int] = mapped_column(ForeignKey('markets.id'))
    request_id: Mapped[int] = mapped_column(ForeignKey('sale_requests.id'))
    event_id: Mapped[int] = mapped_column(ForeignKey('sale_request_events.id'))
    __table_args__ = (UniqueConstraint('recipient_id', 'event_id'),)
    message: Mapped[dict] = mapped_column(JSON)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class NotificationPreference(Base):
    __tablename__ = 'notification_preferences'
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), primary_key=True)
    email: Mapped[bool] = mapped_column(Boolean, default=False)
    sms: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp: Mapped[bool] = mapped_column(Boolean, default=False)


class NotificationDelivery(Record, Base):
    __tablename__ = 'notification_deliveries'
    notification_id: Mapped[int] = mapped_column(ForeignKey('notifications.id'))
    channel: Mapped[str] = mapped_column(String(20))
    __table_args__ = (UniqueConstraint('notification_id', 'channel'),)
    recipient: Mapped[str] = mapped_column(String(254))
    provider: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(40), default='PENDING')
    provider_id: Mapped[str | None] = mapped_column(String(100))
    attempts: Mapped[int] = mapped_column(default=0)
    attempted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_reason: Mapped[str | None] = mapped_column(String(100))


class NotificationOutbox(Base):
    __tablename__ = 'notification_outbox'
    delivery_id: Mapped[int] = mapped_column(ForeignKey('notification_deliveries.id'), primary_key=True)
    due_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=now, index=True)
    claimed_until: Mapped[datetime | None] = mapped_column(UTCDateTime())
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class AuthThrottle(Base):
    __tablename__ = 'sale_auth_throttles'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    attempts: Mapped[int] = mapped_column(default=0)
    reset_at: Mapped[datetime] = mapped_column(UTCDateTime())
