"""TEST_ONLY controlled scenarios; not claims about actual crop profitability."""
import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from app import api_services
from app.decision_support import DecisionPolicy, rain_blocks
from app.market_context import MarketContext, WeatherDay, read_context
from app.models import RecommendationHistory
from app.reliability import ReliabilityForecast
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_api_integration import recommendation

from scripts.refresh_market_context import parse_calendar, parse_news, topics

pytest_plugins=["test_api_integration"]


def policy():
    return {"downside_fraction":".05","adverse_fraction":".10","upside_fraction":".10",
        "assumption_source":"TEST_ONLY explicit sensitivities, not estimated prediction intervals"}


def install_predictor(monkeypatch, price=1500):
    def predictor(session,body,origin,request_id,decision_at=None):
        raw=ReliabilityForecast(prediction_inr_per_quintal=price,intervals=[],horizon_calendar_days=body.horizon,
            timestamp=decision_at.isoformat(),target_date=(origin+timedelta(days=body.horizon)).isoformat(),
            model_version="TEST_ONLY_POINT_WITHOUT_INTERVAL",reliability_status="limited evidence",flags=["retrospective_research_only"],
            market=body.market,commodity=body.commodity,variety=body.variety,grade=body.grade,
            latest_report_date="2026-11-03",observation_age_calendar_days=1,data_source={"source":"TEST_ONLY"})
        return raw,api_services.api_prediction(raw,request_id)
    monkeypatch.setattr(api_services,"predict",predictor)


def test_point_without_interval_can_support_conditional_hold_and_retains_safe_fallback(api,monkeypatch):
    client,engine=api
    install_predictor(monkeypatch)
    body=recommendation()
    body["decision_policy"]=policy()
    response=client.post("/api/v1/recommend",json=body)
    assert response.status_code==200,response.text
    output=response.json()
    decision=output["decision_support"]
    assert decision["action"]=="partial_sell_and_hold" and decision["conditional"] is True
    assert decision["plan"]["recommendation_eligible"] is False
    assert Decimal(decision["plan"]["cash_today_inr"])>=10000
    assert Decimal(decision["plan"]["hold_initial_quintals"])>0
    assert decision["safe_fallback_plan"]["holding_days"]==0
    assert output["optimization"]["recommended_plan"]["holding_days"]==0
    assert output["predictions"][0]["intervals"]==[]
    with Session(engine) as session:
        saved=session.scalar(select(RecommendationHistory).where(RecommendationHistory.id==output["history_id"]))
        assert saved.outcome["decision_action"]==decision["action"]
        assert Decimal(saved.outcome["conditional_plan"]["hold_initial_quintals"])==Decimal(decision["plan"]["hold_initial_quintals"])


@pytest.mark.parametrize("condition",["falling_price","zero_storage","high_storage_cost","all_spoilage","insufficient_cash"])
def test_conditional_analysis_respects_real_constraints(api,monkeypatch,condition):
    client,_=api
    install_predictor(monkeypatch,700 if condition=="falling_price" else 1500)
    body=recommendation()
    body["decision_policy"]=policy()
    if condition=="zero_storage":
        body["storage_capacity_quintals"]="0"
    if condition=="high_storage_cost":
        body["holding_options"][0]["daily_storage_inr_per_quintal"]=["1000"]*3
    if condition=="all_spoilage":
        body["holding_options"][0]["daily_loss_fractions"]=["1","0","0"]
    if condition=="insufficient_cash":
        body["required_net_cash_inr"]="999999"
    response=client.post("/api/v1/recommend",json=body)
    assert response.status_code==(409 if condition=="insufficient_cash" else 200),response.text
    decision=response.json()["decision_support"]
    assert decision["action"]==("infeasible" if condition=="insufficient_cash" else "sell_now")


def test_long_term_buyer_quote_is_scenario_only_and_not_remapped_twice(api):
    client,_=api
    body=recommendation()
    body.update(commodity="Copra",market="Tiptur APMC",variety="other",grade="local",maximum_horizon_days=365)
    body["crop_storage_profile"].update(commodity="Copra",maximum_holding_days=180)
    option=body["holding_options"][0]
    option.update(days=90,daily_loss_fractions=["0"]*90,daily_storage_inr_per_quintal=["0"]*90,
        scenario_price_inr_per_quintal="1500",realization_multiplier=".50")
    body["decision_policy"]=policy()
    response=client.post("/api/v1/recommend",json=body)
    assert response.status_code==200,response.text
    decision=response.json()["decision_support"]
    assert decision["action"]=="partial_sell_and_hold"
    assert decision["plan"]["holding_days"]==90
    assert Decimal(decision["plan"]["assumptions"]["scenarios"]["central_inr_per_quintal"])==1500
    assert response.json()["predictions"]==[]


def test_outdoor_weather_constraint_blocks_hold_and_unknown_coverage_is_not_safe(api,monkeypatch):
    client,_=api
    import app.market_context as module
    install_predictor(monkeypatch)
    def context(market,crop,when,days):
        return MarketContext(market=market,commodity=crop,decision_at=when,weather=[WeatherDay(date=date(2026,11,4),precipitation_mm=30)])
    monkeypatch.setattr(module,"read_context",context)
    body=recommendation()
    body["decision_policy"]={**policy(),"storage_exposure":"outdoor","block_holding_on_rain_risk":True,"rainfall_stop_threshold_mm":"20"}
    response=client.post("/api/v1/recommend",json=body)
    assert response.status_code==200,response.text
    assert response.json()["decision_support"]["action"]=="sell_now"
    assert "user_outdoor_rainfall_constraint_blocks_holding" in response.json()["decision_support"]["reasons"]
    empty=MarketContext(market="Tiptur APMC",commodity="Copra",decision_at=datetime(2026,11,4,tzinfo=UTC))
    assert rain_blocks(empty,DecisionPolicy(**body["decision_policy"]),90) is True


def test_external_sources_never_leak_into_historical_decisions_and_tampering_fails(tmp_path):
    folder=tmp_path/"capture"
    folder.mkdir()
    raw=b'TEST_ONLY_SOURCE'
    (folder/"source.dat").write_bytes(raw)
    snapshot={"sources":[{"kind":"news","archive":"source.dat","source":{"name":"TEST_ONLY","url":"https://pib.gov.in/","fetched_at":"2026-11-05T10:00:00Z","sha256":hashlib.sha256(raw).hexdigest(),"status":"available"},
        "items":[{"title":"TEST_ONLY onion policy","url":"https://pib.gov.in/test-only","published_at":"2026-11-04T10:00:00Z","source":"TEST_ONLY","topics":["Onion"]},
                 {"title":"TEST_ONLY future policy","url":"https://pib.gov.in/test-future","published_at":"2026-11-06T10:00:00Z","source":"TEST_ONLY","topics":["Onion"]}]}]}
    content=json.dumps(snapshot).encode()
    (folder/"snapshot.json").write_bytes(content)
    (tmp_path/"latest.json").write_text(json.dumps({"file":"capture/snapshot.json","sha256":hashlib.sha256(content).hexdigest()}))
    before=read_context("Hubballi APMC","Onion",datetime(2026,11,4,12,tzinfo=UTC),directory=tmp_path)
    assert before.news==[] and "context_not_available_at_decision" in before.warnings
    after=read_context("Hubballi APMC","Onion",datetime(2026,11,5,12,tzinfo=UTC),directory=tmp_path)
    assert len(after.news)==1 and after.numeric_price_adjustment_applied is False
    (folder/"source.dat").write_bytes(b'TEST_ONLY_TAMPERED')
    assert read_context("Hubballi APMC","Onion",datetime(2026,11,5,12,tzinfo=UTC),directory=tmp_path).status=="unavailable"


def test_calendar_and_rss_are_real_parsers_not_festival_price_rules():
    events=parse_calendar(b'<table><tr><td>1</td><td>TEST_ONLY Festival</td><td>08.11.2026</td><td>Sunday</td></tr></table>')
    assert events[0]["date"]=="2026-11-08" and not any("price" in key for key in events[0])
    assert topics("Onion export policy TEST_ONLY")==["Onion"]
    with pytest.raises(ValueError,match="entities"):
        parse_news(b'<!DOCTYPE rss [<!ENTITY bad "bad">]><rss/>',"TEST_ONLY")


def test_perishable_crop_cannot_use_durable_crop_planning_horizon(api):
    client,_=api
    body=recommendation()
    body.update(maximum_horizon_days=90)
    body["crop_storage_profile"]["maximum_holding_days"]=90
    assert client.post("/api/v1/recommend",json=body).status_code==422


def test_sensitivity_overflow_is_a_validation_error_not_server_failure(api):
    client,_=api
    body=recommendation()
    body["decision_policy"]=policy()
    body["holding_options"][0]["scenario_price_inr_per_quintal"]="1000000000"
    response=client.post("/api/v1/recommend",json=body)
    assert response.status_code==422
    assert response.json()["error"]["code"]=="scenario_assumptions_invalid"
