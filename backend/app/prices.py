from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import exists, func, literal, select
from sqlalchemy.orm import Session

from app.api_schemas import ErrorEnvelope
from app.config import get_settings
from app.db import SessionLocal
from app.ingestion import commodity_name, market_name
from app.models import Commodity, ImportBatch, MandiObservation, Market, MarketPrice

router = APIRouter(prefix="/api/v1", tags=["market data"], responses={422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}})


def get_session():
    with SessionLocal() as session:
        yield session


class MarketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    market_name: str | None = None
    district: str
    state: str
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    data_source: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_market_name(cls, data):
        if hasattr(data, "name") and not getattr(data, "market_name", None):
            return {
                "id": data.id,
                "name": data.name,
                "market_name": data.name,
                "district": data.district,
                "state": data.state,
                "latitude": getattr(data, "latitude", None),
                "longitude": getattr(data, "longitude", None),
                "data_source": getattr(data, "data_source", None),
            }
        return data


class CropResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    crop_name: str | None = None
    category: str
    standard_unit: str
    perishability_class: str
    data_source: str | None = None

    @model_validator(mode="before")
    @classmethod
    def populate_crop_name(cls, data):
        if hasattr(data, "name") and not getattr(data, "crop_name", None):
            return {
                "id": data.id,
                "name": data.name,
                "crop_name": data.name,
                "category": getattr(data, "category", "Vegetable"),
                "standard_unit": getattr(data, "standard_unit", "INR/quintal"),
                "perishability_class": getattr(data, "perishability_class", "perishable"),
                "data_source": getattr(data, "data_source", None),
            }
        return data


class PriceItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    commodity: str
    variety: str
    market_name: str
    district: str
    state: str
    arrival_date: date
    minimum_price: Decimal
    maximum_price: Decimal
    modal_price: Decimal
    price_unit: str
    source: str
    source_record_id: str | None = None
    imported_at: datetime
    data_status: str


class PriceResponse(BaseModel):
    id: int
    market_id: int
    commodity_id: int
    market: str
    commodity: str
    report_date: date
    variety: str
    grade: str
    min_price_inr_per_quintal: Decimal
    modal_price_inr_per_quintal: Decimal
    max_price_inr_per_quintal: Decimal
    arrivals_quintals: Decimal | None
    price_unit: str
    source: str
    source_url: str | None
    fetched_at: datetime | None
    data_kind: str
    data_status: str = "CACHED"


class HistoryResponse(BaseModel):
    items: list[PriceResponse]
    limit: int
    offset: int
    next_offset: int | None
    note: str = "Wholesale observations, not guaranteed farmer realization prices. Observed min/max are not prediction intervals. Unreported dates are not imputed. Verified queries show the latest fetched version per date/variety/grade; individual source classes remain queryable."


@router.get("/markets", response_model=list[MarketResponse])
def markets(
    district: str | None = None,
    state: str | None = None,
    data_kind: Literal["verified", "official", "secondary", "fixture", "demo"] = "verified",
    session: Session = Depends(get_session),
):
    if get_settings().environment == "production" and data_kind in {"fixture", "demo"}:
        raise HTTPException(422, "Non-official records are disabled in production")
    kinds = ("official", "secondary") if data_kind == "verified" else (data_kind,)
    stmt = (
        select(Market)
        .where(exists().where(MandiObservation.market_id == Market.id, MandiObservation.data_kind.in_(kinds)))
    )
    if district:
        stmt = stmt.where(func.lower(Market.district) == district.strip().lower())
    if state:
        stmt = stmt.where(func.lower(Market.state) == state.strip().lower())
    return session.scalars(stmt.order_by(Market.state, Market.district, Market.name)).all()


@router.get("/crops", response_model=list[CropResponse])
def crops(
    category: str | None = None,
    perishability_class: str | None = None,
    session: Session = Depends(get_session),
):
    stmt = select(Commodity).where(
        exists().where(MandiObservation.commodity_id == Commodity.id, MandiObservation.data_kind.in_(("official", "secondary")))
    )
    if category:
        stmt = stmt.where(func.lower(Commodity.category) == category.strip().lower())
    if perishability_class:
        stmt = stmt.where(func.lower(Commodity.perishability_class) == perishability_class.strip().lower())
    return session.scalars(stmt.order_by(Commodity.name)).all()


@router.get("/prices", response_model=list[PriceItemResponse])
def prices(
    crop: str | None = None,
    commodity: str | None = None,
    mandi: str | None = None,
    market: str | None = None,
    variety: str | None = None,
    data_status: Literal["LIVE", "CACHED", "SAMPLE", "STALE", "all"] = "all",
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    session: Session = Depends(get_session),
):
    """Retrieve prices with provenance, source, and quality status."""
    crop_name_filter = crop or commodity
    mandi_name_filter = mandi or market

    stmt = select(MarketPrice)

    if crop_name_filter:
        try:
            norm_crop = commodity_name(crop_name_filter)
            stmt = stmt.where(MarketPrice.commodity == norm_crop)
        except ValueError:
            stmt = stmt.where(func.lower(MarketPrice.commodity) == crop_name_filter.strip().lower())

    if mandi_name_filter:
        try:
            norm_mandi = market_name(mandi_name_filter)
            stmt = stmt.where(MarketPrice.market_name == norm_mandi)
        except ValueError:
            stmt = stmt.where(func.lower(MarketPrice.market_name) == mandi_name_filter.strip().lower())

    if variety:
        stmt = stmt.where(func.lower(MarketPrice.variety) == variety.strip().lower())

    if data_status != "all":
        stmt = stmt.where(MarketPrice.data_status == data_status)

    return session.scalars(stmt.order_by(MarketPrice.arrival_date.desc(), MarketPrice.id.desc()).limit(limit).offset(offset)).all()



COMPATIBLE_VARIETIES: dict[str, set[str]] = {
    "Arecanut": {"rashi", "bette", "gorabalu", "saraku", "other", "new variety", "sippegotu"},
    "Copra": {"other", "copra", "ball copra"},
    "Onion": {"puna", "local", "other", "telagi"},
    "Potato": {"local", "potato", "chips"},
    "Tomato": {"tomato", "hybrid"},
}


@router.get("/prices/history", response_model=HistoryResponse)
def history(market: str = "Kolar APMC", commodity: str = "Tomato",
            crop: str | None = None, mandi: str | None = None,
            start_date: date | None = None, end_date: date | None = None,
            variety: str | None = None, grade: str | None = None,
            data_kind: Literal["verified", "official", "secondary", "fixture", "demo"] = "verified",
            limit: Annotated[int, Query(ge=1, le=1000)] = 100,
            offset: Annotated[int, Query(ge=0)] = 0,
            session: Session = Depends(get_session)):
    if get_settings().environment == "production" and data_kind in {"fixture", "demo"}:
        raise HTTPException(422, "Non-official records are disabled in production")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be <= end_date")
    try:
        market, commodity = market_name(mandi or market), commodity_name(crop or commodity)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    kinds = ("official", "secondary") if data_kind == "verified" else (data_kind,)
    stmt = select(MandiObservation, Market, Commodity, ImportBatch).join(Market, MandiObservation.market_id == Market.id).join(Commodity, MandiObservation.commodity_id == Commodity.id).outerjoin(ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id).where(
        Market.name == market, Market.state == "Karnataka", Commodity.name == commodity, MandiObservation.data_kind.in_(kinds))

    target_v = " ".join(variety.split()).casefold() if variety else None
    target_g = " ".join(grade.split()).casefold() if grade else None
    allowed_v = (COMPATIBLE_VARIETIES.get(commodity, set()) | {target_v}) if target_v else None
    allowed_g = {target_g, "local", "medium", "unspecified", "faq"} if target_g else None

    if data_kind == "verified":
        ranked = select(MandiObservation.id.label("observation_id"), func.row_number().over(
            partition_by=(MandiObservation.market_id, MandiObservation.commodity_id, MandiObservation.observed_on),
            order_by=(
                (MandiObservation.variety == target_v).desc() if target_v else literal(1),
                (MandiObservation.grade == target_g).desc() if target_g else literal(1),
                (MandiObservation.data_kind == "official").desc(),
                func.coalesce(ImportBatch.fetched_at, MandiObservation.created_at).desc(),
                MandiObservation.id.desc())).label("position")).outerjoin(
                    ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id).where(MandiObservation.data_kind.in_(kinds)).subquery()
        stmt = stmt.where(MandiObservation.id.in_(select(ranked.c.observation_id).where(ranked.c.position == 1)))

    if start_date:
        stmt = stmt.where(MandiObservation.observed_on >= start_date)
    if end_date:
        stmt = stmt.where(MandiObservation.observed_on <= end_date)
    if allowed_v:
        stmt = stmt.where(MandiObservation.variety.in_(allowed_v))
    elif variety:
        stmt = stmt.where(MandiObservation.variety == target_v)
    if allowed_g:
        stmt = stmt.where(MandiObservation.grade.in_(allowed_g))
    elif grade:
        stmt = stmt.where(MandiObservation.grade == target_g)

    rows = session.execute(stmt.order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc()).limit(limit + 1).offset(offset)).all()
    # Return chronologically ascending
    rows_page = list(reversed(rows[:limit]))
    items = [PriceResponse(id=o.id, market_id=m.id, commodity_id=c.id, market=m.name, commodity=c.name, report_date=o.observed_on, variety=o.variety, grade=o.grade,
        min_price_inr_per_quintal=o.min_price_inr_per_quintal, modal_price_inr_per_quintal=o.modal_price_inr_per_quintal,
        max_price_inr_per_quintal=o.max_price_inr_per_quintal, arrivals_quintals=o.arrivals_quintals, price_unit=o.price_unit,
        source=o.data_source, source_url=b.source_url if b else None, fetched_at=b.fetched_at if b else None, data_kind=o.data_kind,
        data_status="SAMPLE" if o.data_kind == "fixture" else ("STALE" if (datetime.now(UTC).date() - o.observed_on).days > (7 if c.name == "Tomato" else 30) else "CACHED")) for o, m, c, b in rows_page]
    return HistoryResponse(items=items, limit=limit, offset=offset, next_offset=offset + limit if len(rows) > limit else None)
