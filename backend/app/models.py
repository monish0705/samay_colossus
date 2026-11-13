from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, UTCDateTime


class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=lambda: datetime.now(UTC))


class Market(Record, Base):
    __tablename__ = "markets"
    __table_args__ = (UniqueConstraint("name", "district", "state"),)
    name: Mapped[str] = mapped_column(String(120))
    district: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120))
    data_source: Mapped[str] = mapped_column(String(120))


class Commodity(Record, Base):
    __tablename__ = "commodities"
    name: Mapped[str] = mapped_column(String(120), unique=True)
    data_source: Mapped[str] = mapped_column(String(120))


class MandiObservation(Record, Base):
    __tablename__ = "mandi_observations"
    __table_args__ = (
        UniqueConstraint("market_id", "commodity_id", "observed_on", "variety", "grade", "data_kind", name="uq_observation_business_key"),
        CheckConstraint("min_price_inr_per_quintal >= 0 AND min_price_inr_per_quintal <= modal_price_inr_per_quintal AND modal_price_inr_per_quintal <= max_price_inr_per_quintal", name="ck_observation_price_order"),
        CheckConstraint("arrivals_quintals >= 0", name="ck_observation_arrivals"),
    )
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"))
    observed_on: Mapped[date] = mapped_column(Date)
    variety: Mapped[str] = mapped_column(String(120), default="unspecified")
    grade: Mapped[str] = mapped_column(String(120), default="unspecified", server_default="unspecified")
    data_kind: Mapped[str] = mapped_column(String(20), default="demo", server_default="demo")
    price_unit: Mapped[str] = mapped_column(String(40), default="INR/quintal", server_default="INR/quintal")
    latest_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"))
    min_price_inr_per_quintal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    modal_price_inr_per_quintal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    max_price_inr_per_quintal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    arrivals_quintals: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    data_source: Mapped[str] = mapped_column(String(120))


class ImportBatch(Record, Base):
    __tablename__ = "import_batches"
    file_sha256: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    archive_path: Mapped[str] = mapped_column(String(1000))
    source_url: Mapped[str] = mapped_column(String(1000))
    source_label: Mapped[str] = mapped_column(String(120))
    data_kind: Mapped[str] = mapped_column(String(20))
    fetched_at: Mapped[datetime] = mapped_column(UTCDateTime())
    manifest: Mapped[dict] = mapped_column(JSON)
    report: Mapped[dict] = mapped_column(JSON, default=dict)


class ImportRow(Record, Base):
    __tablename__ = "import_rows"
    __table_args__ = (UniqueConstraint("batch_id", "line_number"),)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    line_number: Mapped[int] = mapped_column()
    observation_id: Mapped[int | None] = mapped_column(ForeignKey("mandi_observations.id"))
    status: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(String(1000))
    raw: Mapped[dict] = mapped_column(JSON)
    normalized: Mapped[dict | None] = mapped_column(JSON)


class ModelVersion(Record, Base):
    __tablename__ = "model_versions"
    version: Mapped[str] = mapped_column(String(120), unique=True)
    status: Mapped[str] = mapped_column(String(40), default="untrained")
    artifact_path: Mapped[str | None] = mapped_column(String(500))
    trained_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class Prediction(Record, Base):
    __tablename__ = "predictions"
    __table_args__ = (CheckConstraint("lower_price_inr_per_quintal >= 0 AND lower_price_inr_per_quintal <= predicted_price_inr_per_quintal AND predicted_price_inr_per_quintal <= upper_price_inr_per_quintal"), CheckConstraint("interval_coverage > 0 AND interval_coverage < 1"))
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"))
    commodity_id: Mapped[int] = mapped_column(ForeignKey("commodities.id"))
    model_version_id: Mapped[int] = mapped_column(ForeignKey("model_versions.id"))
    target_date: Mapped[date] = mapped_column(Date)
    predicted_price_inr_per_quintal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    lower_price_inr_per_quintal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    upper_price_inr_per_quintal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    interval_coverage: Mapped[Decimal] = mapped_column(Numeric(5, 4))


class Recommendation(Record, Base):
    __tablename__ = "recommendations"
    __table_args__ = (CheckConstraint("quantity_quintals > 0 AND immediate_cash_need_inr >= 0 AND holding_cost_inr >= 0"), CheckConstraint("action IN ('sell_now', 'hold', 'partial_sell')"))
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"))
    quantity_quintals: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    immediate_cash_need_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    holding_cost_inr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    action: Mapped[str] = mapped_column(String(40))
    rationale: Mapped[str] = mapped_column(String(2000))


class RecommendationHistory(Record, Base):
    """Local anonymous audit: no farmer name, contact, IP or free-text input notes."""
    __tablename__ = "recommendation_history"
    request_id: Mapped[str] = mapped_column(String(36), unique=True)
    decision_at: Mapped[datetime] = mapped_column(UTCDateTime())
    scope: Mapped[dict] = mapped_column(JSON)
    outcome: Mapped[dict] = mapped_column(JSON)
