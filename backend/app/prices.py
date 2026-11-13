from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.api_schemas import ErrorEnvelope
from app.config import get_settings
from app.db import SessionLocal
from app.ingestion import commodity_name, market_name
from app.models import Commodity, ImportBatch, MandiObservation, Market

router = APIRouter(prefix="/api/v1", tags=["market data"], responses={422: {"model": ErrorEnvelope}, 503: {"model": ErrorEnvelope}, 500: {"model": ErrorEnvelope}})


def get_session():
    with SessionLocal() as session:
        yield session


class MarketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    district: str
    state: str


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


class HistoryResponse(BaseModel):
    items: list[PriceResponse]
    limit: int
    offset: int
    next_offset: int | None
    note: str = "Wholesale observations, not guaranteed farmer realization prices. Observed min/max are not prediction intervals. Unreported dates are not imputed. Verified queries show the latest fetched version per date/variety/grade; individual source classes remain queryable."


@router.get("/markets", response_model=list[MarketResponse])
def markets(data_kind: Literal["verified", "official", "secondary", "fixture", "demo"] = "verified", session: Session = Depends(get_session)):
    if get_settings().environment == "production" and data_kind in {"fixture", "demo"}:
        raise HTTPException(422, "Non-official records are disabled in production")
    kinds = ("official", "secondary") if data_kind == "verified" else (data_kind,)
    return session.scalars(select(Market).where(exists().where(MandiObservation.market_id == Market.id, MandiObservation.data_kind.in_(kinds))).order_by(Market.state, Market.district, Market.name)).all()


@router.get("/prices/history", response_model=HistoryResponse)
def history(market: str = "Kolar APMC", commodity: str = "Tomato", start_date: date | None = None,
            end_date: date | None = None, variety: str | None = None, grade: str | None = None,
            data_kind: Literal["verified", "official", "secondary", "fixture", "demo"] = "verified",
            limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
            session: Session = Depends(get_session)):
    if get_settings().environment == "production" and data_kind in {"fixture", "demo"}:
        raise HTTPException(422, "Non-official records are disabled in production")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(422, "start_date must be <= end_date")
    try:
        market, commodity = market_name(market), commodity_name(commodity)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    kinds = ("official", "secondary") if data_kind == "verified" else (data_kind,)
    stmt = select(MandiObservation, Market, Commodity, ImportBatch).join(Market, MandiObservation.market_id == Market.id).join(Commodity, MandiObservation.commodity_id == Commodity.id).outerjoin(ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id).where(
        Market.name == market, Market.state == "Karnataka", Commodity.name == commodity, MandiObservation.data_kind.in_(kinds))
    if data_kind == "verified":
        ranked = select(MandiObservation.id.label("observation_id"), func.row_number().over(
            partition_by=(MandiObservation.market_id, MandiObservation.commodity_id, MandiObservation.observed_on, MandiObservation.variety, MandiObservation.grade),
            order_by=(func.coalesce(ImportBatch.fetched_at, MandiObservation.created_at).desc(),
                (MandiObservation.data_kind == "official").desc(), MandiObservation.id.desc())).label("position")).outerjoin(
                    ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id).where(MandiObservation.data_kind.in_(kinds)).subquery()
        stmt = stmt.where(MandiObservation.id.in_(select(ranked.c.observation_id).where(ranked.c.position == 1)))
    if start_date:
        stmt = stmt.where(MandiObservation.observed_on >= start_date)
    if end_date:
        stmt = stmt.where(MandiObservation.observed_on <= end_date)
    if variety:
        stmt = stmt.where(MandiObservation.variety == " ".join(variety.split()).casefold())
    if grade:
        stmt = stmt.where(MandiObservation.grade == " ".join(grade.split()).casefold())
    rows = session.execute(stmt.order_by(MandiObservation.observed_on, MandiObservation.variety, MandiObservation.grade, MandiObservation.id).limit(limit + 1).offset(offset)).all()
    items = [PriceResponse(id=o.id, market_id=m.id, commodity_id=c.id, market=m.name, commodity=c.name, report_date=o.observed_on, variety=o.variety, grade=o.grade,
        min_price_inr_per_quintal=o.min_price_inr_per_quintal, modal_price_inr_per_quintal=o.modal_price_inr_per_quintal,
        max_price_inr_per_quintal=o.max_price_inr_per_quintal, arrivals_quintals=o.arrivals_quintals, price_unit=o.price_unit,
        source=o.data_source, source_url=b.source_url if b else None, fetched_at=b.fetched_at if b else None, data_kind=o.data_kind) for o, m, c, b in rows[:limit]]
    return HistoryResponse(items=items, limit=limit, offset=offset, next_offset=offset + limit if len(rows) > limit else None)
