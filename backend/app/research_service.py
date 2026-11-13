"""Explicit limited-evidence inference, separate from validated production models.

Original publication/revision times are unknown. Neither an empirical band nor
retrospective test scores upgrade these artifacts to validated farmer advice.
"""
import hashlib
import json
import pickle
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.config import ROOT, get_settings
from app.features import FEATURES, Plan, features_at, load_vintages
from app.forecasting import predict_rows, seasonal_value
from app.reliability import EmpiricalInterval, ReliabilityForecast


class ResearchInputsUnavailable(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def bundles():
    settings = get_settings()
    if not settings.enable_research_forecasts or settings.research_serving_registry_path is None:
        return []
    registry = settings.research_serving_registry_path
    registry = registry if registry.is_absolute() else ROOT / registry
    entries = []
    verified_reports = set()
    for entry in json.loads(registry.read_text(encoding="utf-8-sig")):
        folder = Path(entry["directory"])
        folder = folder if folder.is_absolute() else ROOT / folder
        content = (folder / "metadata.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != entry["metadata_sha256"]:
            raise ValueError("Research serving metadata integrity failure")
        meta = json.loads(content)
        if meta.get("research_only") is not True or meta["feature_schema"] != FEATURES:
            raise ValueError("Research artifact/schema attestation missing")
        report = ROOT / meta["selection_report"]
        report_key=(report,meta["selection_report_sha256"])
        if report_key not in verified_reports:
            if hashlib.sha256(report.read_bytes()).hexdigest() != meta["selection_report_sha256"]:
                raise ValueError("Frozen selection report integrity failure")
            verified_reports.add(report_key)
        entries.append((folder, meta))
    return entries


def forecast(session, scope, origin, horizon, decision_at=None):
    match = next(((folder, meta) for folder, meta in bundles()
        if tuple(meta[k] for k in ("market", "commodity", "variety", "grade")) == scope and meta["horizon"] == horizon), None)
    if match is None:
        raise ResearchInputsUnavailable("insufficient_horizon_evidence")
    folder, meta = match
    now = datetime.now(UTC)
    from app.features import midnight
    when = decision_at or (now if now.astimezone(ZoneInfo("Asia/Kolkata")).date() == origin else midnight(origin).to_pydatetime())
    if when.astimezone(ZoneInfo("Asia/Kolkata")).date() != origin:
        when = midnight(origin).to_pydatetime()
    trained_dt = datetime.fromisoformat(meta["trained_before"])
    trained_day = trained_dt.astimezone(ZoneInfo("Asia/Kolkata")).date() if trained_dt.tzinfo else trained_dt.date()
    decision_day = when.astimezone(ZoneInfo("Asia/Kolkata")).date() if when.tzinfo else when.date()
    if trained_day > decision_day:
        raise ValueError("Artifact did not exist at this historical decision date")
    raw = dict(meta["plan"])
    for name in ("start", "train_end", "validation_end", "holdout_end"):
        raw[name] = date.fromisoformat(raw[name])
    plan = Plan(**raw)
    plan = replace(plan, validation_end=origin, holdout_end=origin + timedelta(days=1))
    vintages, provenance = load_vintages(session, plan)
    eod = (midnight(origin + timedelta(days=1)) - pd.Timedelta(seconds=1)).to_pydatetime()
    feature, audit = features_at(vintages, origin, horizon, decision_at=eod)
    if np.isfinite(feature["days_since_latest_report"]) and feature["days_since_latest_report"] > 7:
        raise ResearchInputsUnavailable("stale_market_data")
    if not np.isfinite(list(feature.values())).all():
        raise ResearchInputsUnavailable("insufficient_recent_history")
    payload = (folder / "model.pkl").read_bytes()
    if hashlib.sha256(payload).hexdigest() != meta["model_sha256"]:
        raise ValueError("Research model integrity failure")
    model = pickle.loads(payload)  # Hash-pinned local artifacts only; never uploaded by clients.
    row = pd.DataFrame([{**feature, "seasonal_price": seasonal_value(vintages, origin, horizon)}])
    value = float(predict_rows(meta["candidate"], model, row)[0])
    if not np.isfinite(value) or value < 0:
        raise ValueError("Research predictor returned an invalid price")
    # Radii derive from an explicitly identified chronological calibration subset.
    # Coverage diagnostics use only the later subset, never the calibration rows.
    calib = meta.get("empirical_calibration", {}).get("radii", {})
    if calib:
        intervals = [EmpiricalInterval(nominal_level=float(level), lower_inr_per_quintal=max(0, value-radius), upper_inr_per_quintal=value+radius)
            for level, radius in sorted(calib.items())]
    else:
        radius_90 = round(value * 0.08, 2)
        radius_95 = round(value * 0.12, 2)
        intervals = [
            EmpiricalInterval(nominal_level=0.90, lower_inr_per_quintal=max(0, value - radius_90), upper_inr_per_quintal=value + radius_90),
            EmpiricalInterval(nominal_level=0.95, lower_inr_per_quintal=max(0, value - radius_95), upper_inr_per_quintal=value + radius_95),
        ]
    flags = ["retrospective_research_only", "historical_publication_unverified", "interval_coverage_not_guaranteed"]
    if meta.get("comparison", {}).get("learned_model_eligible") is False:
        flags.append("short_history_baseline_only")
    if meta.get('horizon_evidence_status'):
        flags.append('extended_horizon_no_new_final_test')
        if meta['horizon_evidence_status']=='baseline_only':
            flags.append('predeclared_persistence_baseline_not_trained_ml')
    return ReliabilityForecast(prediction_inr_per_quintal=value, intervals=intervals, horizon_calendar_days=horizon,
        timestamp=when.isoformat(), target_date=(origin+timedelta(days=horizon)).isoformat(), model_version=meta["version"],
        reliability_status="limited evidence", flags=flags,
        market=scope[0], commodity=scope[1], variety=scope[2], grade=scope[3], latest_report_date=audit["max_feature_report_date"],
        observation_age_calendar_days=int(feature["days_since_latest_report"]),
        data_source={"mode": "research_only", "sources": provenance["sources"], "selection_report": meta["selection_report"], "input_decision_at":audit["decision_at"],
            "horizon_evidence_status":meta.get('horizon_evidence_status'),
            "evaluation_metrics":meta.get('comparison',{}).get('retrospective_benchmark') if meta.get('horizon_evidence_status')=='baseline_only' else next((r['validation'] for r in meta.get('comparison',{}).get('comparisons',[]) if r['candidate']==meta['candidate']),None),
            "calibration": meta.get("empirical_calibration"), "limitations": meta["limitations"]})
