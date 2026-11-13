"""Application orchestration. Domain forecasting, reliability and optimization stay in their services."""
import hashlib
import json
from datetime import date, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from app.api_schemas import (
    DataStatus,
    Freshness,
    ModelsStatus,
    ModelStatusItem,
    PredictionResponse,
    PredictRequest,
    RecommendationResponse,
    RecommendRequest,
    ResearchStudy,
)
from app.config import ROOT, get_settings
from app.features import Plan, asof, load_vintages, midnight
from app.models import Commodity, ImportBatch, MandiObservation, Market, RecommendationHistory
from app.reliability import reliable_forecast
from app.selling import money, optimize_selling, scenarios_from_reliability
from app.training import read_plan


class ServiceProblem(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


class Deployment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feature_run: Path
    champions: Path
    evidence: Path | None = None


def deployments():
    path = get_settings().service_registry_path
    if path is None:
        return []
    path = path if path.is_absolute() else ROOT / path
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        entries = [Deployment.model_validate(entry) for entry in raw]
        bundles = []
        for entry in entries:
            for field in ("feature_run", "champions", "evidence"):
                value = getattr(entry, field)
                if value is not None and not value.is_absolute():
                    setattr(entry, field, ROOT / value)
            plan, _ = read_plan(entry.feature_run)
            bundles.append((entry, plan))
        keys = [(p.market, p.commodity, p.variety, p.grade) for _, p in bundles]
        if len(keys) != len(set(keys)):
            raise ValueError("Duplicate deployed series")
        return bundles
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise ServiceProblem(503, "registry_unavailable", "Saved service registry is unavailable or invalid") from exc


def resolve(scope, horizon):
    for entry, plan in deployments():
        if tuple(getattr(plan, k) for k in ("market", "commodity", "variety", "grade")) == scope:
            artifact = entry.champions / f"champion-{horizon}d"
            if not (artifact / "metadata.json").is_file():
                raise ServiceProblem(503, "missing_model", "No saved champion exists for this series/horizon")
            return entry, plan, artifact
    raise ServiceProblem(503, "missing_model", "No saved model is deployed for this series")


def api_prediction(result, request_id, session=None):
    payload = result.model_dump()
    pred_val = None
    if result.prediction_inr_per_quintal is not None:
        pred_val = money(Decimal(str(result.prediction_inr_per_quintal)))
        payload["prediction_inr_per_quintal"] = pred_val
    payload["intervals"] = [{"nominal_level": Decimal(str(i.nominal_level)),
        "lower_inr_per_quintal": Decimal(str(i.lower_inr_per_quintal)).quantize(Decimal(".01"), rounding=ROUND_FLOOR),
        "upper_inr_per_quintal": Decimal(str(i.upper_inr_per_quintal)).quantize(Decimal(".01"), rounding=ROUND_CEILING)} for i in result.intervals]
    if pred_val is not None:
        from app.prediction_attribution import build_attribution
        payload["attribution"] = build_attribution(
            commodity=result.commodity,
            market=result.market,
            horizon=result.horizon_calendar_days,
            predicted_price=pred_val,
            session=session,
            variety=result.variety,
            grade=result.grade
        )
    return PredictionResponse(**payload, request_id=request_id)


def predict(session, body: PredictRequest, origin, request_id, decision_at=None):
    scope = (body.market, body.commodity, body.variety, body.grade)
    try:
        entry, plan, artifact = resolve(scope, body.horizon)
    except ServiceProblem as exc:
        if exc.code != "missing_model" or not get_settings().enable_research_forecasts:
            raise
        from app.research_service import ResearchInputsUnavailable, forecast
        try:
            result = forecast(session, scope, origin, body.horizon, decision_at)
        except ResearchInputsUnavailable as failure:
            raise ServiceProblem(503,failure.code,"The selected series/horizon has no usable saved forecast, insufficient evidence or stale inputs; inspect model availability and dated evaluation") from failure
        except (ValueError, OSError, KeyError, ImportError) as failure:
            raise ServiceProblem(503, "research_forecast_unavailable", "No usable saved research forecast exists for these historical inputs; no price was invented") from failure
        return result, api_prediction(result, request_id, session=session)
    try:
        result = reliable_forecast(session, plan, origin, body.horizon, entry.evidence, artifact)
    except (ValueError, OSError, KeyError, ImportError) as exc:
        raise ServiceProblem(503, "prediction_service_unavailable", "Saved prediction service or source evidence is unavailable") from exc
    if result.prediction_inr_per_quintal is None:
        code = "stale_market_data" if result.reliability_status == "stale data" else "forecast_unavailable"
        raise ServiceProblem(503, code, "No usable historically available forecast for this request")
    return result, api_prediction(result, request_id, session=session)


def freshness(session, scope, origin, decision_at=None):
    kinds = set(session.scalars(select(MandiObservation.data_kind).join(Market,MandiObservation.market_id==Market.id).join(Commodity,MandiObservation.commodity_id==Commodity.id).where(
        Market.name==scope[0], Commodity.name==scope[1], MandiObservation.variety==scope[2], MandiObservation.grade==scope[3], MandiObservation.data_kind.in_(("official","secondary"))).distinct()).all())
    kind = "official" if "official" in kinds or not kinds else "secondary"
    plan = Plan(date(2000, 1, 1), date(2001, 1, 1), origin, origin + timedelta(days=1), scope[2], scope[3], scope[0], scope[1], source_kind=kind)
    try:
        vintages, _ = load_vintages(session, plan)
        available = asof(vintages, midnight(origin) if decision_at is None else decision_at, before=origin)
    except (ValueError, OSError, KeyError) as exc:
        raise ServiceProblem(503, "market_source_unavailable", "Historical source evidence is unavailable") from exc
    if available.empty:
        return Freshness()
    row = available.iloc[-1]
    batch = session.get(ImportBatch, int(row.batch_id))
    return Freshness(report_date=row.report_date, fetched_at=row.available_at.to_pydatetime(), source=batch.source_label,
                     source_url=batch.source_url, file_sha256=batch.file_sha256, stale=(origin - row.report_date).days > 7,
                     data_kind=batch.data_kind, reference_modal_price_inr_per_quintal=money(Decimal(str(row.price))))


def recommend(session, body: RecommendRequest, request_id):
    origin = body.decision_at.astimezone(ZoneInfo("Asia/Kolkata")).date()
    scope = (body.market, body.commodity, body.variety, body.grade)
    data = freshness(session, scope, origin,body.decision_at)
    forecasts, warnings, holding = [], [], []
    from app.decision_support import rain_blocks, sensitivity_scenarios, summarize_decision
    from app.market_context import read_context
    policy = body.decision_policy
    context = read_context(body.market,body.commodity,body.decision_at,max((o.days for o in body.holding_options),default=7)) if policy else None
    constraint_flags = []
    def conditional_scenarios(*args,**kwargs):
        try:
            return sensitivity_scenarios(*args,**kwargs)
        except ValueError as failure:
            raise ServiceProblem(422,"scenario_assumptions_invalid","Sensitivity bounds are invalid or exceed the supported monetary range") from failure
    if data.report_date is None:
        warnings.append("no_official_market_observations; today's quote is user supplied")
    elif data.stale:
        warnings.append("stale_market_data")
    for option in body.holding_options:
        payload = option.model_dump(exclude={"realization_multiplier", "price_basis_assumption", "adverse_inr_per_quintal", "adverse_assumption", "scenarios", "scenario_price_inr_per_quintal"})
        payload["scenarios"] = None
        if policy and rain_blocks(context,policy,option.days):
            constraint_flags.append("user_outdoor_rainfall_constraint_blocks_holding")
            continue
        if option.scenario_price_inr_per_quintal is not None:
            from app.selling import PriceScenarios
            central = option.scenario_price_inr_per_quintal
            if option.adverse_inr_per_quintal > central:
                raise ServiceProblem(422, "scenario_assumptions_invalid", "Adverse price must not exceed the central user scenario")
            payload["scenarios"] = conditional_scenarios(body,option,policy,central,"User-entered future buyer quote; not a model forecast","user_scenario_only",apply_realization=False) if policy else PriceScenarios(adverse_inr_per_quintal=option.adverse_inr_per_quintal,
                lower_inr_per_quintal=option.adverse_inr_per_quintal, central_inr_per_quintal=central, upper_inr_per_quintal=central,
                reliability_status="scenario only", market=body.market, commodity=body.commodity, variety=body.variety, grade=body.grade,
                target_date=origin+timedelta(days=option.days), issued_at=body.decision_at,
                model_version="user_scenario_only", source="User-entered assumption; not a forecast",
                price_basis_assumption=option.price_basis_assumption, adverse_assumption=option.adverse_assumption,
                flags=("scenario_only_simulation",))
            warnings.append(f"{option.days}d:scenario_only_simulation")
        elif option.days > 7 and policy and policy.long_horizon_mode != "saved_forecast":
            warnings.append(f"{option.days}d:unsupported_horizon")
            if policy and policy.long_horizon_mode=="flat_reference" and not data.stale and data.reference_modal_price_inr_per_quintal is not None:
                payload["scenarios"] = conditional_scenarios(body,option,policy,data.reference_modal_price_inr_per_quintal,
                    f"Flat reference sensitivity from dated {data.report_date} observation; NOT a trained {option.days}-day price forecast",
                    "flat_reference_scenario",("long_horizon_not_validated",))
                warnings.append(f"{option.days}d:flat_reference_not_a_forecast")
        else:
            query = PredictRequest(market=body.market, commodity=body.commodity, variety=body.variety, grade=body.grade, horizon=option.days, origin_date=origin)
            try:
                raw, formatted = predict(session, query, origin, request_id, decision_at=body.decision_at)
                forecasts.append(formatted)
                try:
                    payload["scenarios"] = conditional_scenarios(body,option,policy,raw.prediction_inr_per_quintal,
                        "Saved forecast point with user-reviewed sensitivity assumptions; these bounds are not prediction intervals",raw.model_version,raw.flags) if policy else scenarios_from_reliability(raw, adverse_inr_per_quintal=option.adverse_inr_per_quintal,
                        realization_multiplier=option.realization_multiplier, price_basis_assumption=option.price_basis_assumption, adverse_assumption=option.adverse_assumption)
                except ValueError as exc:
                    raise ServiceProblem(422, "scenario_assumptions_invalid", "Adverse price or realization assumptions conflict with the service scenario bounds") from exc
                warnings.extend(f"{option.days}d:{flag}" for flag in raw.flags)
                if raw.reliability_status != "validated":
                    warnings.append(f"{option.days}d:{raw.reliability_status}")
            except ServiceProblem as exc:
                if exc.status < 500:
                    raise
                warnings.append(f"{option.days}d:{exc.code}")
        holding.append(payload)
    request_data = body.model_dump(exclude={"holding_options", "decision_policy"})
    request_data["holding_options"] = holding
    try:
        result = optimize_selling(request_data)
    except ValueError as exc:
        raise ServiceProblem(422, "economic_assumptions_invalid", "Economic assumptions conflict with the trusted forecast inputs") from exc
    chosen = result["recommended_plan"]
    decision = summarize_decision(result,context,requested_holding=bool(body.holding_options),
        scenarios_available=any(o["scenarios"] is not None for o in holding),constraints=constraint_flags) if policy else None
    warnings.extend(constraint_flags)
    # Deliberately omit free-text cost/source notes, personal details, IP and raw body.
    history = RecommendationHistory(request_id=request_id, decision_at=body.decision_at,
        scope={k: getattr(body, k) for k in ("market", "commodity", "variety", "grade")},
        outcome={"status": result["status"], "sell_today_quintals": str(chosen["sell_today_quintals"]) if chosen else None,
            "hold_quintals": str(chosen["hold_initial_quintals"]) if chosen else None,
            "cash_today_inr": str(chosen["cash_today_inr"]) if chosen else None,
            "source_report_date": data.report_date.isoformat() if data.report_date else None,
            "model_versions": [f.model_version for f in forecasts], "reliability_warnings": sorted(set(warnings)),
            "decision_action":decision["action"] if decision else None,
            "conditional_plan":{key:str(decision["plan"][key]) for key in ("sell_today_quintals","hold_initial_quintals","holding_days","cash_today_inr")} if decision and decision["plan"] else None,
            "context_source_hashes":[s.sha256 for s in context.sources] if context else []})
    session.add(history)
    session.commit()
    session.refresh(history)
    return RecommendationResponse(request_id=request_id, history_id=history.id, market_data=data, predictions=forecasts,
        reliability_warnings=sorted(set(warnings)), optimization=result,decision_support=decision)


def model_status():
    items = []
    for entry, plan in deployments():
        for horizon in (1, 3, 7):
            path = entry.champions / f"champion-{horizon}d" / "metadata.json"
            version = None
            trained_before = None
            fingerprint = None
            validation_metrics = None
            final_metrics = None
            status = "missing_model"
            if path.is_file():
                try:
                    meta = json.loads(path.read_text())
                    version = meta["version"]
                    trained_before = meta.get("trained_before")
                    fingerprint = meta.get("dataset_fingerprint")
                    validation_metrics = next((row.get("validation") for row in meta.get("comparison", {}).get("comparisons", []) if row.get("candidate") == meta.get("candidate")), None)
                    comparison_file = entry.champions / "comparison.json"
                    if comparison_file.is_file():
                        try:
                            final_report = json.loads(comparison_file.read_text())
                            final_metrics = next((row.get("metrics") for row in (final_report.get("final_evaluation") or {}).get("results", []) if row.get("horizon") == horizon and row.get("status") == "evaluated"), None)
                        except (OSError, ValueError, TypeError):
                            final_metrics = None
                    status = "artifact_present_not_a_reliability_claim"
                except (OSError, ValueError, KeyError):
                    status = "invalid_artifact"
            items.append(ModelStatusItem(**{k: getattr(plan, k) for k in ("market", "commodity", "variety", "grade")}, horizon=horizon, model_version=version, status=status,
                trained_before=trained_before, dataset_fingerprint=fingerprint, reliability_evidence_configured=entry.evidence is not None,
                validation_metrics=validation_metrics, final_holdout_metrics=final_metrics))
    studies = research_status()
    research_models = []
    if get_settings().enable_research_forecasts:
        from app.research_service import bundles
        try:
            for _, meta in bundles():
                research_models.append(ModelStatusItem(**{k:meta[k] for k in ("market","commodity","variety","grade","horizon")},
                    model_version=meta["version"], status="research_only_limited_evidence", trained_before=meta["trained_before"],
                    dataset_fingerprint=meta["dataset_fingerprint"], reliability_evidence_configured=False,source_kind=meta["plan"].get("source_kind","official"),
                    evidence_status=meta.get('horizon_evidence_status'),model_name=meta['candidate'],
                    validation_metrics=next((r['validation'] for r in meta.get('comparison',{}).get('comparisons',[]) if r['candidate']==meta['candidate']),None),
                    retrospective_benchmark_metrics=meta.get('comparison',{}).get('retrospective_benchmark')))
        except (OSError, ValueError, KeyError) as exc:
            raise ServiceProblem(503, "research_registry_unavailable", "Research serving registry failed integrity checks") from exc
    return ModelsStatus(status="configured" if items else "research_only_configured" if research_models else "no_models_deployed", models=items, research_studies=studies, research_models=research_models)


def research_status():
    registry = get_settings().research_registry_path
    if registry is None:
        return []
    registry = registry if registry.is_absolute() else ROOT / registry
    try:
        studies = []
        for entry in json.loads(registry.read_text(encoding="utf-8-sig")):
            folder = Path(entry["directory"])
            folder = folder if folder.is_absolute() else ROOT / folder
            content = (folder / "comparison.json").read_bytes()
            if hashlib.sha256(content).hexdigest() != entry["comparison_sha256"]:
                raise ValueError("Research report hash mismatch")
            report = json.loads(content)
            if report.get("research_only") is not True:
                raise ValueError("Research registry requires explicitly labeled research evidence")
            plan = report["plan"]
            finals = {r["horizon"]: r for r in (report.get("final_evaluation") or {}).get("results", [])}
            horizons = []
            for row in report["horizons"]:
                final = finals.get(row["horizon"], {})
                horizons.append({"horizon": row["horizon"], "selected_model": row["champion"],
                    "train_n": row["sample_policy"]["effective_train_samples"], "validation_n": row["sample_policy"]["effective_validation_samples"],
                    "final_n": final.get("n", 0), "final_metrics": final.get("metrics"),
                    "naive_metrics": (final.get("baseline_metrics") or {}).get("naive")})
            studies.append(ResearchStudy(**{key: plan[key] for key in ("market", "commodity", "variety", "grade")},
                source_kind=plan.get("source_kind","official"),
                version=report["version"], train_start=plan["start"], train_end=plan["train_end"], validation_end=plan["validation_end"],
                test_end=plan["holdout_end"], limitations=report["limitations"], source_fingerprint=report["source_fingerprint"], horizons=horizons))
        return studies
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ServiceProblem(503, "research_registry_unavailable", "Retrospective research report registry is invalid or unavailable") from exc


def data_status(session, today):
    counts = dict(session.execute(select(MandiObservation.data_kind, func.count()).group_by(MandiObservation.data_kind)).all())
    latest = session.scalar(select(func.max(MandiObservation.observed_on)).where(MandiObservation.data_kind == "official"))
    fetched = session.scalar(select(func.max(ImportBatch.fetched_at)).where(ImportBatch.data_kind == "official"))
    secondary = session.scalar(select(func.max(MandiObservation.observed_on)).where(MandiObservation.data_kind == "secondary"))
    secondary_fetched = session.scalar(select(func.max(ImportBatch.fetched_at)).where(ImportBatch.data_kind == "secondary"))
    available = max((d for d in (latest,secondary) if d is not None),default=None)
    return DataStatus(historical_demo_date=get_settings().historical_demo_date, status="unavailable" if available is None else "stale" if (today - available).days > 7 else "observations_available",
        official_observations=counts.get("official", 0), secondary_observations=counts.get("secondary",0), latest_secondary_report_date=secondary,
        latest_secondary_fetched_at=secondary_fetched,
        fixture_observations=counts.get("fixture", 0), demo_observations=counts.get("demo", 0),
        latest_official_report_date=latest, latest_official_fetched_at=fetched)
