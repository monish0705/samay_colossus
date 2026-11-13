from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app import api_services as services
from app.api_schemas import (
    DataStatus,
    ErrorEnvelope,
    ModelsStatus,
    PredictionResponse,
    PredictRequest,
    RecommendationResponse,
    RecommendRequest,
)
from app.config import get_settings
from app.models import Commodity, ImportBatch, MandiObservation, Market
from app.prices import PriceResponse, get_session

ERRORS = {code: {"model": ErrorEnvelope, "description": description} for code, description in
          [(404, "No official observation"), (409, "No feasible cash/physical plan; recommendation endpoint returns its full comparison"),
           (422, "Invalid scope, horizon, future decision or economic assumptions"), (503, "Missing model/data, stale forecast or unavailable source/service"), (500, "Unexpected server error") ]}
router = APIRouter(prefix="/api/v1", responses=ERRORS)
EXAMPLE_RECOMMEND = {"commodity": "Tomato", "market": "Kolar APMC", "variety": "local", "grade": "faq", "decision_at": "2026-11-04T08:00:00+05:30",
    "total_quantity_quintals": "20", "today_price_inr_per_quintal": "1000", "today_price_assumption": "EXAMPLE_ONLY farmer quote, not live data",
    "required_net_cash_inr": "10000", "storage_capacity_quintals": "0", "decision_increment_quintals": "1", "market_quantity_step_quintals": ".01",
    "minimum_sale_lot_quintals": "1", "maximum_horizon_days": 3, "risk_tolerance": "conservative",
    "crop_storage_profile": {"commodity": "Tomato", "maximum_holding_days": 0, "storage_conditions": "EXAMPLE_ONLY no storage", "assumption_source": "EXAMPLE_ONLY"},
    "today_sale_costs": {"fixed_transport_inr": "100", "transport_inr_per_quintal": "10", "commission_rate": ".05", "assumptions": "EXAMPLE_ONLY quotation"}, "holding_options": []}


def get_clock():
    replay = get_settings().historical_demo_date
    if replay is not None:
        return datetime(replay.year, replay.month, replay.day, 12, tzinfo=ZoneInfo("Asia/Kolkata"))
    return datetime.now(UTC)


class CommodityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    data_source: str


class LatestResponse(BaseModel):
    observation: PriceResponse
    stale: bool
    age_calendar_days: int
    note: str = "Latest stored official wholesale observation, not a live buyer quote or guaranteed farmer realization."


@router.get("/commodities", response_model=list[CommodityResponse], tags=["market data"])
def commodities(session: Session = Depends(get_session)):
    return session.scalars(select(Commodity).where(exists().where(MandiObservation.commodity_id == Commodity.id, MandiObservation.data_kind == "official")).order_by(Commodity.name)).all()


@router.get("/prices/latest", response_model=LatestResponse, tags=["market data"])
def latest(variety: str, grade: str, market: str = "Kolar APMC", commodity: str = "Tomato",
           session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    try:
        query = PredictRequest(market=market, commodity=commodity, variety=variety, grade=grade, horizon=1)
    except ValueError as exc:
        raise services.ServiceProblem(422, "unsupported_series", "Unsupported market/commodity or invalid variety/grade") from exc
    today = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    row = session.execute(select(MandiObservation, Market, Commodity, ImportBatch).join(Market, MandiObservation.market_id == Market.id).join(Commodity, MandiObservation.commodity_id == Commodity.id).join(ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id).where(
        MandiObservation.data_kind == "official", ImportBatch.data_kind == "official", Market.name == query.market, Market.state == "Karnataka", Market.district == "Kolar", Commodity.name == query.commodity,
        MandiObservation.variety == query.variety, MandiObservation.grade == query.grade, MandiObservation.observed_on <= today, ImportBatch.fetched_at <= now).order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc()).limit(1)).first()
    if row is None:
        raise services.ServiceProblem(404, "no_official_observation", "No official price observation exists for this series")
    o, m, c, b = row
    observation = PriceResponse(id=o.id, market_id=m.id, commodity_id=c.id, market=m.name, commodity=c.name, report_date=o.observed_on,
        variety=o.variety, grade=o.grade, min_price_inr_per_quintal=o.min_price_inr_per_quintal, modal_price_inr_per_quintal=o.modal_price_inr_per_quintal,
        max_price_inr_per_quintal=o.max_price_inr_per_quintal, arrivals_quintals=o.arrivals_quintals, price_unit=o.price_unit,
        source=b.source_label, source_url=b.source_url, fetched_at=b.fetched_at, data_kind=o.data_kind)
    age = (today - o.observed_on).days
    return LatestResponse(observation=observation, stale=age > 7, age_calendar_days=age)


@router.post("/predict", response_model=PredictionResponse, tags=["forecasting"])
def predict(body: PredictRequest, request: Request, session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    today = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    origin = body.origin_date or today
    if origin > today:
        raise services.ServiceProblem(422, "future_decision", "Forecast decision date cannot be in the future")
    _, result = services.predict(session, body, origin, request.state.request_id)
    return result


@router.post("/recommend", response_model=RecommendationResponse,
             responses={409: {"model": RecommendationResponse, "description": "No feasible cash/lot/storage plan; full explanation retained"}}, tags=["selling"])
def recommend(body: Annotated[RecommendRequest, Body(openapi_examples={"cash_only_example": {"summary": "EXAMPLE ONLY: 20 quintals and INR 10,000 cash, no storage or live-price claim", "value": EXAMPLE_RECOMMEND}})],
              request: Request, response: Response, session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    if body.decision_at > now:
        raise services.ServiceProblem(422, "future_decision", "Selling decision timestamp cannot be in the future")
    result = services.recommend(session, body, request.state.request_id)
    if result.optimization.status in {"no_feasible_cash_solution", "no_feasible_plan"}:
        response.status_code = 409
    return result


@router.get("/models/status", response_model=ModelsStatus, tags=["operations"])
def models_status():
    return services.model_status()


@router.get("/data/status", response_model=DataStatus, tags=["operations"])
def data_status(session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    return services.data_status(session, now.astimezone(ZoneInfo("Asia/Kolkata")).date())
