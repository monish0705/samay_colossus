"""Private marketplace entities, deliberately separate from government APMC markets."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app import sale_models  # noqa: F401 -- register the reused identity table
from app.db import Base, UTCDateTime
from app.models import Record


class AccountRole(Base):
    __tablename__ = 'account_roles'
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), primary_key=True)
    role: Mapped[str] = mapped_column(String(40), primary_key=True)
    __table_args__ = (CheckConstraint("role IN ('FARMER','MANDI_OWNER','PRIVATE_MANDI_OWNER','PRIVATE_BUYER','MANDI_STAFF','SYSTEM_ADMIN')"),)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('mandi_users.id'))


class BusinessAccount(Record, Base):
    __tablename__ = 'business_accounts'
    __table_args__ = (CheckConstraint("business_type IN ('PRIVATE_MANDI','PRIVATE_BUYER')"),
        CheckConstraint("verification_state IN ('PENDING_VERIFICATION','VERIFIED','REJECTED','SUSPENDED')"),)
    business_type: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(200))
    contact_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(254))
    address: Mapped[str] = mapped_column(String(1000))
    district: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120))
    registration_details: Mapped[str] = mapped_column(String(2000))
    verification_information: Mapped[str] = mapped_column(String(2000))
    document_references: Mapped[list] = mapped_column(JSON, default=list)
    verification_state: Mapped[str] = mapped_column(String(30), default='PENDING_VERIFICATION', index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    version: Mapped[int] = mapped_column(default=1)
    submission_key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    __mapper_args__ = {'version_id_col': version}


class BusinessUser(Base):
    __tablename__ = 'business_users'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), primary_key=True, index=True)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey('mandi_users.id'))


class BusinessRole(Base):
    __tablename__ = 'business_roles'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), primary_key=True, index=True)
    role: Mapped[str] = mapped_column(String(40), primary_key=True)
    __table_args__ = (CheckConstraint("role IN ('PRIVATE_MANDI_OWNER','PRIVATE_BUYER','MANDI_STAFF')"),)
    approved_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))


class BusinessVerification(Record, Base):
    __tablename__ = 'business_verifications'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))
    from_state: Mapped[str] = mapped_column(String(30))
    to_state: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[str] = mapped_column(String(2000))
    contact_verified: Mapped[bool] = mapped_column(Boolean)
    registration_checked: Mapped[bool] = mapped_column(Boolean)


class PrivateMandi(Record, Base):
    __tablename__ = 'private_mandis'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), unique=True)
    operating_hours: Mapped[str] = mapped_column(String(500))


class PrivateBuyer(Record, Base):
    __tablename__ = 'private_buyers'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), unique=True)
    buyer_type: Mapped[str] = mapped_column(String(60))


class BusinessCropPreference(Base):
    __tablename__ = 'business_crop_preferences'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), primary_key=True)
    commodity_id: Mapped[int] = mapped_column(ForeignKey('commodities.id'), primary_key=True)


class BusinessMarketAssignment(Base):
    __tablename__ = 'business_market_assignments'
    business_id: Mapped[int] = mapped_column(ForeignKey('business_accounts.id'), primary_key=True)
    private_mandi_id: Mapped[int] = mapped_column(ForeignKey('private_mandis.id'), unique=True)
    approved_by: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'))


class WorkspacePreference(Base):
    __tablename__ = 'account_workspace_preferences'
    user_id: Mapped[int] = mapped_column(ForeignKey('mandi_users.id'), primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default='FARMER')
    business_id: Mapped[int | None] = mapped_column(ForeignKey('business_accounts.id'))
    role: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime())


# Idempotent applications per user, without treating unrelated businesses as duplicates.
BusinessAccount.__table__.append_constraint(UniqueConstraint('created_by', 'submission_key', name='uq_business_submission'))
