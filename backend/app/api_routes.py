from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app import api_services as services
from app.api_schemas import (
    DataStatus,
    ErrorEnvelope,
    HistoricalEvaluation,
    HorizonAvailability,
    ModelsStatus,
    PredictionResponse,
    PredictRequest,
    RecommendationResponse,
    RecommendRequest,
)
from app.config import get_settings
from app.market_context import MarketContext, read_context
from app.models import Commodity, ImportBatch, MandiObservation, Market
from app.prices import PriceResponse, get_session, COMPATIBLE_VARIETIES

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


@router.get("/context",response_model=MarketContext,tags=["decision context"])
def market_context(market:str,commodity:str,days:int=Query(7,ge=1,le=730),now:datetime=Depends(get_clock)):
    from app.ingestion import commodity_name, market_name
    try:
        canonical_market,canonical_crop=market_name(market),commodity_name(commodity)
    except ValueError as exc:
        raise services.ServiceProblem(422,"unsupported_series","Unsupported market or crop") from exc
    return read_context(canonical_market,canonical_crop,now,days)


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
    return session.scalars(select(Commodity).where(exists().where(MandiObservation.commodity_id == Commodity.id, MandiObservation.data_kind.in_(("official", "secondary")))).order_by(Commodity.name)).all()


@router.get("/prices/latest", response_model=LatestResponse, tags=["market data"])
def latest(variety: str, grade: str, market: str = "Kolar APMC", commodity: str = "Tomato",
           session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    try:
        query = PredictRequest(market=market, commodity=commodity, variety=variety, grade=grade, horizon=1)
    except ValueError as exc:
        raise services.ServiceProblem(422, "unsupported_series", "Unsupported market/commodity or invalid variety/grade") from exc
    today = now.astimezone(ZoneInfo("Asia/Kolkata")).date()
    stmt = (
        select(MandiObservation, Market, Commodity, ImportBatch)
        .join(Market, MandiObservation.market_id == Market.id)
        .join(Commodity, MandiObservation.commodity_id == Commodity.id)
        .join(ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id)
        .where(
            MandiObservation.data_kind.in_(("official", "secondary")),
            ImportBatch.data_kind == MandiObservation.data_kind,
            Market.name == query.market,
            Market.state == "Karnataka",
            Commodity.name == query.commodity,
            MandiObservation.variety == query.variety,
            MandiObservation.grade == query.grade,
            MandiObservation.observed_on <= today,
        )
    )
    row = session.execute(
        stmt.where(ImportBatch.fetched_at <= now)
        .order_by(MandiObservation.observed_on.desc(), ImportBatch.fetched_at.desc(), MandiObservation.id.desc())
        .limit(1)
    ).first()
    if row is None:
        # Fallback without ImportBatch.fetched_at <= now for pre-imported verified observations
        row = session.execute(
            stmt.order_by(MandiObservation.observed_on.desc(), ImportBatch.fetched_at.desc(), MandiObservation.id.desc()).limit(1)
        ).first()
    if row is None:
        # Fallback across compatible varieties
        compat = COMPATIBLE_VARIETIES.get(query.commodity, {query.variety})
        row = session.execute(
            select(MandiObservation, Market, Commodity, ImportBatch)
            .join(Market, MandiObservation.market_id == Market.id)
            .join(Commodity, MandiObservation.commodity_id == Commodity.id)
            .join(ImportBatch, MandiObservation.latest_batch_id == ImportBatch.id)
            .where(
                MandiObservation.data_kind.in_(("official", "secondary")),
                Market.name == query.market,
                Market.state == "Karnataka",
                Commodity.name == query.commodity,
                MandiObservation.variety.in_(compat),
                MandiObservation.observed_on <= today,
            )
            .order_by(MandiObservation.observed_on.desc(), MandiObservation.id.desc())
            .limit(1)
        ).first()
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
    _, result = services.predict(session, body, origin, request.state.request_id, decision_at=now)
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


@router.get('/models/horizons',response_model=HorizonAvailability,tags=['operations'])
def model_horizons(market:str,commodity:str,variety:str,grade:str,horizon:int|None=Query(None,ge=1,le=730)):
    import hashlib
    import json

    from app.config import ROOT
    from app.decision_support import CROP_PLANNING_CEILINGS
    from app.research_service import bundles
    try:
        scope_request=PredictRequest(market=market,commodity=commodity,variety=variety,grade=grade,horizon=1)
        scope=tuple(getattr(scope_request,k) for k in ('market','commodity','variety','grade'))
        saved={meta['horizon']:meta for _,meta in bundles() if tuple(meta[k] for k in ('market','commodity','variety','grade'))==scope}
        for entry,plan in services.deployments():
            if tuple(getattr(plan,k) for k in ('market','commodity','variety','grade'))==scope:
                for path in entry.champions.glob('champion-*d/metadata.json'):
                    meta=json.loads(path.read_text(encoding='utf-8'))
                    saved[meta['horizon']]=meta
        status='saved_artifact' if horizon in saved else 'insufficient_evidence' if horizon else None
        reasons=[]
        sample={}
        path=ROOT/'reports'/f'daily-{scope_request.commodity.lower()}-entry.json'
        if horizon and path.is_file():
            entry=json.loads(path.read_text(encoding='utf-8'))
            report_path=ROOT/entry['directory']/'comparison.json'
            content=report_path.read_bytes()
            if hashlib.sha256(content).hexdigest()!=entry['comparison_sha256']:
                raise ValueError('Horizon evidence integrity failure')
            report=json.loads(content)
            if tuple(report['plan'][k] for k in ('market','commodity','variety','grade'))==scope:
                row=next((r for r in report['horizons'] if r['horizon']==horizon),None)
                if row:
                    reasons=row['reason']
                    sample=row['sample_policy']
                    status=row['status']
        return HorizonAvailability(**dict(zip(('market','commodity','variety','grade'),scope,strict=True)),
            planning_ceiling_calendar_days=CROP_PLANNING_CEILINGS[scope_request.commodity],saved_horizons=sorted(saved),
            requested_horizon=horizon,requested_status=status,reasons=reasons,sample_counts=sample)
    except ValidationError as exc:
        raise services.ServiceProblem(422,'unsupported_series','Invalid market, crop, variety or grade') from exc
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise services.ServiceProblem(503,'horizon_registry_unavailable','Horizon availability or evidence failed validation') from exc


@router.get("/models/evaluation", response_model=HistoricalEvaluation, tags=["operations"])
def model_evaluation(variety: str, grade: str, market: str="Kolar APMC",commodity: str="Tomato",horizon: int=Query(3,ge=1,le=730,description="Exact calendar horizon. New horizons may have development-only evidence, not a final evaluation.")):
    from app.evaluation_service import historical_evaluation
    try:
        scope=PredictRequest(market=market,commodity=commodity,variety=variety,grade=grade,horizon=horizon)
    except ValueError as exc:
        raise services.ServiceProblem(422,"unsupported_series","Select an exact supported research series") from exc
    return historical_evaluation((scope.market,scope.commodity,scope.variety,scope.grade),horizon)


@router.get("/data/status", response_model=DataStatus, tags=["operations"])
def data_status(session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    return services.data_status(session, now.astimezone(ZoneInfo("Asia/Kolkata")).date())


@router.get("/predict/multi-factor", deprecated=True, tags=["forecasting"])
def retired_multi_factor(horizon: int = Query(3, ge=1, le=730), base_price: float = Query(1400, gt=0)):
    raise services.ServiceProblem(410, "unverified_projection_removed", "Fixed price-driver adjustments have been removed. Use POST /api/v1/predict for saved artifacts or POST /api/v1/recommend for explicit scenarios.")


@router.get("/storage/nearby", deprecated=True, tags=["selling"])
def retired_storage(quantity: float = Query(20, gt=0), days: int = Query(3, ge=1, le=730), today_price: float = Query(1400, gt=0)):
    raise services.ServiceProblem(410, "unverified_facilities_removed", "No verified warehouse directory or tariffs are configured. Enter your actual storage quote and costs through POST /api/v1/recommend.")
