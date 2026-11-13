"""Exercise real saved forecasts plus explicitly illustrative farmer constraints.

No source data, forecasts or metrics are modified. These calculations create
anonymous local recommendation-history entries, not actual sales or contracts.
"""
import argparse
import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request(base,path,payload=None):
    try:
        with urlopen(Request(base.rstrip("/")+path,data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type":"application/json"}),timeout=45) as response:
            return response.status,json.load(response)
    except HTTPError as exc:
        return exc.code,json.load(exc)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url",default="http://127.0.0.1:8011")
    parser.add_argument("--output",type=Path,default=Path("reports/sell-hold-live-verification.json"))
    args=parser.parse_args()
    body=json.loads(Path("docs/examples/selling-example.json").read_text())
    body.update(commodity="Copra",market="Tiptur APMC",variety="other",grade="local",total_quantity_quintals="20",
        today_price_inr_per_quintal="15000",required_net_cash_inr="10000",storage_capacity_quintals="10",maximum_horizon_days=365,
        today_price_assumption="EXAMPLE_ONLY assumed farmer buyer quote of INR 15000/quintal, not a live realization price")
    body["crop_storage_profile"].update(commodity="Copra",maximum_holding_days=180,
        storage_conditions="EXAMPLE_ONLY protected dry storage, not a verified facility",assumption_source="EXAMPLE_ONLY farmer storage and cost assumptions")
    body["decision_policy"]={"downside_fraction":".10","adverse_fraction":".20","upside_fraction":".10",
        "assumption_source":"EXAMPLE_ONLY sensitivity percentages, not empirical prediction intervals","storage_exposure":"protected"}
    option=body["holding_options"][0]
    option.pop("scenarios")
    option.update(realization_multiplier="1",price_basis_assumption="EXAMPLE_ONLY assume future gross realization equals mandi forecast; no discount modeled",
        adverse_inr_per_quintal="0",adverse_assumption="EXAMPLE_ONLY legacy stress field; explicit policy governs sensitivities",
        daily_loss_fractions=[".0003"]*3,daily_storage_inr_per_quintal=["1.5"]*3)
    checks=[]
    variants={"saved_forecast_conditional_comparison":{},"zero_storage":{},"infeasible_cash":{},"falling_user_future_quote":{},"high_storage_cost":{},
        "ninety_day_buyer_quote":{},"ninety_day_outdoor_weather_rule":{},"thirty_day_saved_forecast":{},"unsupported_year_forecast":{}}
    for name in variants:
        candidate=copy.deepcopy(body)
        candidate["decision_at"]=datetime.now(UTC).isoformat()
        future=candidate["holding_options"][0]
        if name=="zero_storage":
            candidate["storage_capacity_quintals"]="0"
        elif name=="infeasible_cash":
            candidate["required_net_cash_inr"]="9999999"
        elif name=="falling_user_future_quote":
            future["scenario_price_inr_per_quintal"]="10000"
        elif name=="high_storage_cost":
            future["daily_storage_inr_per_quintal"]=["30000"]*3
        elif name.startswith("ninety_day"):
            future.update(days=90,daily_loss_fractions=[".0003"]*90,daily_storage_inr_per_quintal=["1.5"]*90,scenario_price_inr_per_quintal="20000")
            if name.endswith("weather_rule"):
                candidate["decision_policy"].update(storage_exposure="outdoor",block_holding_on_rain_risk=True,rainfall_stop_threshold_mm="20")
        elif name in {"thirty_day_saved_forecast","unsupported_year_forecast"}:
            days=30 if name=="thirty_day_saved_forecast" else 365
            candidate["crop_storage_profile"]["maximum_holding_days"]=365
            candidate["decision_policy"]["long_horizon_mode"]="saved_forecast"
            future.update(days=days,daily_loss_fractions=[".0003"]*days,daily_storage_inr_per_quintal=["1.5"]*days)
        status,result=request(args.base_url,"/api/v1/recommend",candidate)
        expected_status=409 if name=="infeasible_cash" else 200
        if status!=expected_status:
            raise RuntimeError(f"{name}: HTTP {status}; see source/service availability, not fabricated replacements")
        decision=result["decision_support"]
        if name in {"zero_storage","falling_user_future_quote","high_storage_cost","ninety_day_outdoor_weather_rule"}:
            assert decision["action"]=="sell_now",(name,decision["action"])
        if name in {"saved_forecast_conditional_comparison","ninety_day_buyer_quote","thirty_day_saved_forecast"}:
            assert decision["action"]=="partial_sell_and_hold",(name,decision["action"])
        if name=="thirty_day_saved_forecast":
            assert result["predictions"][0]["horizon_calendar_days"]==30
        if name=="unsupported_year_forecast":
            assert decision["action"]=="insufficient_evidence" and decision["safe_fallback_plan"]["holding_days"]==0
        checks.append({"name":name,"http_status":status,"request":candidate,"response":result})
        plan=decision.get("plan") or {}
        print(name,status,decision["action"],"sell",plan.get("sell_today_quintals"),"hold",plan.get("hold_initial_quintals"),"days",plan.get("holding_days"),flush=True)
    context_status,context=request(args.base_url,"/api/v1/context?market=Tiptur%20APMC&commodity=Copra&days=90")
    assert context_status==200 and context["numeric_price_adjustment_applied"] is False
    report={"verified_at":datetime.now(UTC).isoformat(),"examples_are_not_live_farmer_quotes":True,"cases":checks,"external_context":context,
        "limitations":"Short/monthly horizons use saved retrospective research forecasts/baselines. Ninety-day prices are EXAMPLE_ONLY user quotes, not trained forecasts. Unsupported year forecast remains unavailable. Weather is a city proxy; headlines/calendar have no learned numeric price effects."}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding="utf-8")
    print("REPORT",args.output)


if __name__=="__main__":
    main()
