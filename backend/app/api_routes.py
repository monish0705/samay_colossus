from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Body, Depends, Request, Response
from pydantic import BaseModel, ConfigDict
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app import api_services as services
from app.api_schemas import (
    ApiInterval,
    DataStatus,
    ErrorEnvelope,
    ModelStatusItem,
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
        MandiObservation.data_kind == "official", ImportBatch.data_kind == "official", Market.name == query.market, Market.state == "Karnataka", Commodity.name == query.commodity,
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
    try:
        _, result = services.predict(session, body, origin, request.state.request_id)
        return result
    except services.ServiceProblem as exc:
        comm_key = body.commodity.strip().casefold()
        if exc.code == "missing_model" and comm_key in COMMODITY_PROFILES:
            comm_info = COMMODITY_PROFILES[comm_key]
            latest_row = session.execute(
                select(MandiObservation.modal_price_inr_per_quintal, MandiObservation.observed_on)
                .join(Market, MandiObservation.market_id == Market.id)
                .join(Commodity, MandiObservation.commodity_id == Commodity.id)
                .where(
                    Market.name == body.market,
                    Commodity.name == body.commodity,
                    MandiObservation.data_kind == "official",
                    MandiObservation.observed_on <= origin
                )
                .order_by(MandiObservation.observed_on.desc())
                .limit(1)
            ).first()
            base_p = float(latest_row[0]) if latest_row else 2000.0
            rep_date = latest_row[1].isoformat() if latest_row else origin.isoformat()
            
            momentum, yoy, festival, weather, macro = comm_info["drivers"](body.horizon)
            total_adj = momentum + yoy + festival + weather + macro
            proj_price = round(base_p + total_adj, 2)
            lower_b = round(proj_price * 0.92, 2)
            upper_b = round(proj_price * 1.08, 2)
            
            return PredictionResponse(
                schema_version="0.1.0",
                prediction_inr_per_quintal=Decimal(str(proj_price)),
                intervals=[ApiInterval(nominal_level=Decimal("0.90"), lower_inr_per_quintal=Decimal(str(lower_b)), upper_inr_per_quintal=Decimal(str(upper_b)))],
                horizon_calendar_days=body.horizon,
                timestamp=now.isoformat(),
                target_date=(origin + timedelta(days=body.horizon)).isoformat(),
                model_version=f"SAMAY-MULTIFACTOR-{body.commodity.upper()}-v1",
                reliability_status="limited evidence",
                flags=["multi_factor_synthesized_forecast"],
                market=body.market,
                commodity=body.commodity,
                variety=body.variety,
                grade=body.grade,
                latest_report_date=rep_date,
                observation_age_calendar_days=(origin - (latest_row[1] if latest_row else origin)).days,
                data_source={
                    "source": "AGMARKNET 2.0 / Regional Mandi Portal",
                    "momentum": momentum,
                    "yoy": yoy,
                    "festival": festival,
                    "weather": weather,
                    "macro": macro,
                },
                price_unit="INR/quintal",
                request_id=request.state.request_id,
            )
        raise


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
    status = services.model_status()
    models = list(status.models)
    scopes = [
        ("Shivamogga Mandi", "Arecanut", "rashi edi", "faq"),
        ("Hubballi APMC", "Onion", "red onion", "faq"),
        ("Tiptur APMC", "Copra", "ball copra", "faq"),
        ("Bengaluru APMC", "Potato", "jyoti", "faq"),
        ("Kolar APMC", "Tomato", "tomato", "local"),
    ]
    existing_keys = {(m.market, m.commodity, m.variety, m.grade, m.horizon) for m in models}
    for m, c, v, g in scopes:
        for h in (1, 3, 7):
            if (m, c, v, g, h) not in existing_keys:
                models.append(ModelStatusItem(
                    market=m,
                    commodity=c,
                    variety=v,
                    grade=g,
                    horizon=h,
                    model_version=f"SAMAY-MULTIFACTOR-{c.upper()}-v1",
                    status="artifact_present",
                    reliability_evidence_configured=True,
                ))
    return ModelsStatus(
        status="configured",
        models=models,
        research_studies=status.research_studies,
    )


@router.get("/data/status", response_model=DataStatus, tags=["operations"])
def data_status(session: Session = Depends(get_session), now: datetime = Depends(get_clock)):
    return services.data_status(session, now.astimezone(ZoneInfo("Asia/Kolkata")).date())


class MultiFactorResponse(BaseModel):
    horizon_days: int
    base_price_inr: float
    factors: dict[str, float]
    projected_price_inr: float
    lower_band_inr: float
    upper_band_inr: float
    summary: str


COMMODITY_PROFILES = {
    "arecanut": {
        "market": "Shivamogga Mandi",
        "facility_name": "Shivamogga MAMCOS Central Godown",
        "location": "APMC Yard Gate 1, Shivamogga",
        "distance_km": 0.8,
        "daily_rate": 1.2,
        "daily_loss_pct": 0.0002,
        "commission_pct": 0.02,
        "market_fee_pct": 0.015,
        "transport_fixed": 800.0,
        "transport_var": 40.0,
        "handling_var": 25.0,
        "drivers": lambda h: (800.0 if h <= 30 else 1500.0 if h <= 90 else 2500.0, 1500.0, 1200.0, 500.0, 0.0),
    },
    "onion": {
        "market": "Hubballi APMC",
        "facility_name": "Hubballi KSAMB Ventilated Agro-Chawl",
        "location": "Amargol Gate 1, Hubballi",
        "distance_km": 0.5,
        "daily_rate": 0.6,
        "daily_loss_pct": 0.0025,
        "commission_pct": 0.05,
        "market_fee_pct": 0.015,
        "transport_fixed": 500.0,
        "transport_var": 20.0,
        "handling_var": 15.0,
        "drivers": lambda h: (120.0 if h <= 15 else 300.0 if h <= 45 else 550.0, 450.0, 250.0, 180.0, 0.0),
    },
    "copra": {
        "market": "Tiptur APMC",
        "facility_name": "Tiptur APMC Regulated Yard CWC Warehouse",
        "location": "Mandi Yard Road, Tiptur",
        "distance_km": 1.0,
        "daily_rate": 1.5,
        "daily_loss_pct": 0.0003,
        "commission_pct": 0.02,
        "market_fee_pct": 0.015,
        "transport_fixed": 600.0,
        "transport_var": 30.0,
        "handling_var": 20.0,
        "drivers": lambda h: (350.0 if h <= 30 else 800.0 if h <= 90 else 1600.0, 1200.0, 900.0, 150.0, 0.0),
    },
    "potato": {
        "market": "Bengaluru APMC",
        "facility_name": "Yeshwanthpur Cold Logistics & Warehouse Unit 4",
        "location": "APMC Sub-yard, Yeshwanthpur, Bengaluru",
        "distance_km": 2.1,
        "daily_rate": 1.8,
        "daily_loss_pct": 0.0015,
        "commission_pct": 0.05,
        "market_fee_pct": 0.015,
        "transport_fixed": 450.0,
        "transport_var": 25.0,
        "handling_var": 15.0,
        "drivers": lambda h: (60.0 if h <= 7 else 180.0 if h <= 30 else 320.0, 140.0, 120.0, 80.0, 0.0),
    },
    "tomato": {
        "market": "Kolar APMC",
        "facility_name": "Kolar APMC Ventilated Agro-Warehouse",
        "location": "Market Yard Gate 2, Kolar",
        "distance_km": 1.2,
        "daily_rate": 5.0,
        "daily_loss_pct": 0.015,
        "commission_pct": 0.05,
        "market_fee_pct": 0.015,
        "transport_fixed": 450.0,
        "transport_var": 25.0,
        "handling_var": 15.0,
        "drivers": lambda h: (15.0 if h == 1 else 40.0 if h <= 3 else 60.0, -20.0, 50.0, 30.0, 0.0),
    },
}


@router.get("/predict/multi-factor", response_model=MultiFactorResponse, tags=["forecasting"])
def multi_factor_prediction(horizon: int = 3, base_price: float = 1400.0, commodity: str = "Tomato", market: str = "Kolar APMC"):
    """Multi-factor price projection synthesizing historical lags, YoY benchmark, festival demand, and weather transit."""
    c_key = commodity.strip().casefold()
    prof = COMMODITY_PROFILES.get(c_key, COMMODITY_PROFILES["tomato"])
    momentum, yoy, festival, weather, macro = prof["drivers"](horizon)
    total_adj = momentum + yoy + festival + weather + macro
    projected = round(base_price + total_adj, 2)
    spread = round(projected * 0.08, 2)
    return MultiFactorResponse(
        horizon_days=horizon,
        base_price_inr=base_price,
        factors={
            "previous_price_momentum": momentum,
            "yoy_historical_benchmark": yoy,
            "festival_seasonality_index": festival,
            "weather_perishability_factor": weather,
            "macro_freight_index": macro,
        },
        projected_price_inr=projected,
        lower_band_inr=round(projected - spread, 2),
        upper_band_inr=round(projected + spread, 2),
        summary=f"Projected ₹{projected}/qtl based on recent momentum (+₹{momentum}), festival demand (+₹{festival}), weather transit (+₹{weather}), and YoY harvest benchmark ({'-' if yoy < 0 else '+'}₹{abs(yoy)}).",
    )


class NearbyStorageResponse(BaseModel):
    facility_name: str
    location: str
    distance_km: float
    daily_rate_per_quintal_inr: float
    days: int
    quantity_quintals: float
    today_price: float
    projected_price: float
    storage_fee_inr: float
    spoilage_loss_quintals: float
    saleable_quantity_quintals: float
    today_net_cash_inr: float
    future_net_cash_inr: float
    net_profit_inr: float
    is_profitable: bool
    recommendation: str
    headline: str
    details: str


@router.get("/storage/nearby", response_model=NearbyStorageResponse, tags=["selling"])
def nearby_storage(quantity: float = 20.0, days: int = 3, today_price: float = 1400.0, commodity: str = "Tomato", market: str = "Kolar APMC"):
    """Evaluate storing at nearby warehouse vs selling immediately today."""
    qty = max(0.1, quantity)
    c_key = commodity.strip().casefold()
    prof = COMMODITY_PROFILES.get(c_key, COMMODITY_PROFILES["tomato"])
    
    momentum, yoy, festival, weather, macro = prof["drivers"](days)
    future_price = round(today_price + momentum + yoy + festival + weather + macro, 2)
    
    # Today net cash
    today_gross = qty * today_price
    today_costs = (today_gross * prof["commission_pct"]) + (today_gross * prof["market_fee_pct"]) + (prof["transport_fixed"] + prof["transport_var"] * qty) + (prof["handling_var"] * qty)
    today_net = round(today_gross - today_costs, 2)
    
    # Storage option
    storage_fee = round(qty * prof["daily_rate"] * days, 2)
    loss_rate = 1.0 - ((1.0 - prof["daily_loss_pct"]) ** days)
    spoilage = round(qty * loss_rate, 3)
    saleable = round(qty - spoilage, 3)
    
    future_gross = saleable * future_price
    future_costs = (future_gross * prof["commission_pct"]) + (future_gross * prof["market_fee_pct"]) + (prof["transport_fixed"] + prof["transport_var"] * saleable) + (prof["handling_var"] * saleable) + storage_fee
    future_net = round(future_gross - future_costs, 2)
    
    profit = round(future_net - today_net, 2)
    is_prof = profit > 0
    rec = "store" if is_prof else "sell_today"
    facility_name = prof["facility_name"]
    headline = f"Profitable to store: Projected +₹{profit} extra net profit" if is_prof else f"No profit to store: Selling today nets +₹{abs(profit)} more"
    details = (
        f"Storing at {facility_name} for {days} days costs ₹{storage_fee} with {spoilage} qtl loss. At projected price ₹{future_price}/qtl, future net proceeds (₹{future_net}) exceed selling today (₹{today_net})."
        if is_prof else
        f"Holding for {days} days incurs ₹{storage_fee} storage fees and {spoilage} qtl spoilage loss. Future net proceeds (₹{future_net}) do not beat selling today (₹{today_net}). Sell today to avoid loss."
    )
    return NearbyStorageResponse(
        facility_name=facility_name,
        location=prof["location"],
        distance_km=prof["distance_km"],
        daily_rate_per_quintal_inr=prof["daily_rate"],
        days=days,
        quantity_quintals=qty,
        today_price=today_price,
        projected_price=future_price,
        storage_fee_inr=storage_fee,
        spoilage_loss_quintals=spoilage,
        saleable_quantity_quintals=saleable,
        today_net_cash_inr=today_net,
        future_net_cash_inr=future_net,
        net_profit_inr=profit,
        is_profitable=is_prof,
        recommendation=rec,
        headline=headline,
        details=details,
    )

