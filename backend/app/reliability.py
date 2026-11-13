"""Point-in-time reliability and chronological residual calibration. No coverage guarantee."""
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel

from app.features import Plan, asof, load_vintages, midnight
from app.forecasting import _forecast_with_vintages, metrics

VERSION = "samay-reliability-v1"
LEVELS = (.8, .9)
POLICY = {"minimum_history": 30, "maximum_age_days": 7, "minimum_calibration_errors": 30,
          "minimum_calibration_blocks": 8, "block_calendar_days": 7, "minimum_validation_errors": 60,
          "minimum_validation_span_days": 60, "volatility_threshold": .2,
          "maximum_calibration_age_days": 180, "maximum_error_evidence_age_days": 30,
          "maximum_relative_interval_width": 1.0}
DISCLAIMER = ("Empirical uncertainty for mandi modal wholesale prices only. Coverage is not guaranteed. "
              "This does not capture individual farmer grade, quality, sorting, fees, transport, bargaining or transaction-price uncertainty, "
              "and is not a guaranteed realized selling price or advice to hold produce.")


class EmpiricalInterval(BaseModel):
    nominal_level: float
    lower_inr_per_quintal: float
    upper_inr_per_quintal: float


class ReliabilityForecast(BaseModel):
    schema_version: str = VERSION
    prediction_inr_per_quintal: float | None = None
    intervals: list[EmpiricalInterval] = []
    horizon_calendar_days: int
    timestamp: str
    target_date: str | None = None
    model_version: str | None = None
    reliability_status: Literal["validated", "limited evidence", "stale data", "unavailable"] = "unavailable"
    flags: list[str] = []
    market: str
    commodity: str
    variety: str
    grade: str
    latest_report_date: str | None = None
    observation_age_calendar_days: int | None = None
    data_source: dict
    disclaimer: str = DISCLAIMER


def point(vintages, plan, origin, horizon, champion=None):
    """Predeclared baseline or artifact that existed before this historical decision."""
    history = asof(vintages, midnight(origin), before=origin)
    response = {"prediction": None, "model_version": None, "flags": [], "history_count": len(history),
                "latest_report_date": None, "age": None, "volatility": None}
    if horizon not in (1, 3, 7):
        response["flags"].append("unsupported_horizon")
        return response
    supported_markets = {"Kolar APMC", "Shivamogga Mandi", "Hubballi APMC", "Tiptur APMC", "Bengaluru APMC"}
    supported_commodities = {"Tomato", "Arecanut", "Onion", "Copra", "Potato"}
    if plan.market not in supported_markets or plan.commodity not in supported_commodities:
        response["flags"].append("unsupported_series")
        return response
    if len(history) < POLICY["minimum_history"]:
        response["flags"].append("sparse_history")
    if not len(history):
        response["flags"].append("no_official_observations")
        return response
    response["latest_report_date"] = history.iloc[-1].report_date.isoformat()
    response["age"] = (origin - history.iloc[-1].report_date).days
    if response["age"] > POLICY["maximum_age_days"]:
        response["flags"].append("stale_data")
        return response
    returns = history.tail(30).price.pct_change(fill_method=None).dropna()
    if len(returns) >= 7:
        response["volatility"] = float(returns.std(ddof=1))
        if response["volatility"] > POLICY["volatility_threshold"]:
            response["flags"].append("excessive_volatility")
    if len(history) < 2:
        return response
    if champion is None:
        response.update(prediction=float(history.iloc[-1].price), model_version="predeclared-naive-v1")
    else:
        try:
            prediction = _forecast_with_vintages(champion, vintages, origin, horizon, plan.market, plan.commodity, plan.variety, plan.grade)
        except ValueError:
            response["flags"].append("champion_unavailable_at_decision")
            return response
        response.update(prediction=prediction["prediction_inr_per_quintal"], model_version=prediction["model_version"])
    return response


def dated_predictions(vintages, plan, start, end, horizon, freeze, champion=None):
    """Predict without labels first; attach exact targets only at the declared scoring freeze."""
    labels = {r.report_date: r for r in asof(vintages, midnight(freeze), inclusive=False).itertuples()}
    rows = []
    for stamp in pd.date_range(start, end):
        origin = stamp.date()
        target = origin + timedelta(days=horizon)
        p = point(vintages, plan, origin, horizon, champion)
        history = asof(vintages, midnight(origin), before=origin)
        label = labels.get(target) if target <= end else None
        flags = list(p["flags"])
        if target > end:
            flags.append("target_crosses_partition")
        elif label is None:
            flags.append("missing_target_observation")
        actual = float(label.price) if label is not None else np.nan
        prediction = p["prediction"]
        rows.append({"origin_date": origin.isoformat(), "decision_at": midnight(origin).isoformat(), "target_date": target.isoformat(),
            "horizon": horizon, "prediction": prediction, "actual": actual,
            "actual_available_at": label.available_at.isoformat() if label is not None else None,
            "actual_source_row_id": int(label.row_id) if label is not None else None,
            "absolute_error": abs(prediction - actual) if prediction is not None and label is not None else np.nan,
            "residual": actual - prediction if prediction is not None and label is not None else np.nan,
            "naive_prediction": float(history.iloc[-1].price) if len(history) else np.nan,
            "model_version": p["model_version"], "flags": "|".join(flags),
            "feature_report_date": p["latest_report_date"],
            "feature_source_row_ids": json.dumps(history.tail(30).row_id.tolist()),
            "feature_latest_available_at": history.available_at.max().isoformat() if len(history) else None})
    return pd.DataFrame(rows)


def calibrate(rows, horizon, freeze, scope, model_version):
    valid = rows.dropna(subset=["absolute_error"]).copy()
    valid = valid[(pd.to_datetime(valid.actual_available_at, utc=True) < midnight(freeze)) & (valid.target_date < freeze.isoformat())]
    if len(valid) and set(valid.model_version) != {model_version}:
        raise ValueError("Calibration must use exactly one frozen model version")
    if len(valid):
        # Seven-calendar-day maxima reduce optimism from overlapping nearby errors.
        anchors = pd.to_datetime(valid.origin_date)
        valid["block"] = ((anchors - anchors.min()).dt.days // POLICY["block_calendar_days"]).astype(int)
        block_errors = valid.groupby("block").absolute_error.max().to_numpy()
    else:
        block_errors = np.array([])
    enough = len(valid) >= POLICY["minimum_calibration_errors"] and len(block_errors) >= POLICY["minimum_calibration_blocks"]
    return {"version": VERSION, "horizon": horizon, "scope": scope, "model_version": model_version,
            "frozen_at": midnight(freeze).isoformat(), "calibration_n": len(valid), "calibration_blocks": len(block_errors),
            "calibration_mae": float(valid.absolute_error.mean()) if len(valid) else None,
            "calibration_p90_error": float(valid.absolute_error.quantile(.9)) if len(valid) else None,
            "radii": {str(level): float(np.quantile(block_errors, level, method="higher")) for level in LEVELS} if enough else {},
            "method": "Empirical higher quantiles of seven-calendar-day block maximum absolute errors; fixed chronological calibration, no IID/exchangeability coverage claim"}


def intervals_for(prediction, evidence):
    if prediction is None:
        return []
    return [EmpiricalInterval(nominal_level=float(level), lower_inr_per_quintal=max(0, prediction - radius), upper_inr_per_quintal=prediction + radius)
            for level, radius in sorted(evidence.get("radii", {}).items(), key=lambda pair: float(pair[0]))]


def evaluate(rows, calibration):
    rows = rows.copy()
    valid = rows.dropna(subset=["prediction", "actual", "naive_prediction"])
    summary = {"n": len(valid), "metrics": None, "naive_metrics_same_timestamps": None, "intervals": {}}
    if len(valid):
        summary["metrics"] = metrics(valid.actual, valid.prediction, valid.naive_prediction)
        summary["naive_metrics_same_timestamps"] = metrics(valid.actual, valid.naive_prediction, valid.naive_prediction)
    for level, radius in calibration["radii"].items():
        lower = np.maximum(0, rows.prediction - radius)
        upper = rows.prediction + radius
        rows[f"lower_{level}"] = lower
        rows[f"upper_{level}"] = upper
        eligible = rows.prediction.notna() & rows.actual.notna()
        n = int(eligible.sum())
        summary["intervals"][level] = {"n": n, "empirical_coverage": float(((rows.actual >= lower) & (rows.actual <= upper))[eligible].mean()) if n else None,
                                       "mean_width_inr_per_quintal": float((upper - lower)[eligible].mean()) if n else None}
    return rows, summary


def evidence_at(folder, horizon, origin, scope, model_version):
    if folder is None:
        return None, pd.DataFrame()
    meta = json.loads((folder / "summary.json").read_text())
    if meta["scope"] != scope or meta["policy"] != POLICY:
        raise ValueError("Reliability evidence scope/policy mismatch")
    for name, expected in meta["artifact_sha256"].items():
        path = (folder / name).resolve()
        if not path.is_relative_to(folder.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Reliability artifact integrity failure")
    item = next((r for r in meta["horizons"] if r["horizon"] == horizon), None)
    if item is None:
        return None, pd.DataFrame()
    calibration = item["calibration"]
    if calibration["model_version"] != model_version or pd.Timestamp(calibration["frozen_at"]) > midnight(origin):
        return None, pd.DataFrame()
    # Future scoring outcomes cannot establish reliability for an earlier origin.
    errors = pd.read_csv(folder / f"evaluation-{horizon}d.csv")
    known = errors.dropna(subset=["absolute_error"]).copy()
    known = known[(pd.to_datetime(known.actual_available_at, utc=True) < midnight(origin)) & (known.target_date < origin.isoformat())]
    return calibration, known


def reliability_response(vintages, plan, origin, horizon, provenance, evidence_folder=None, champion=None):
    scope = {key: getattr(plan, key) for key in ("market", "commodity", "variety", "grade")}
    p = point(vintages, plan, origin, horizon, champion)
    response = ReliabilityForecast(horizon_calendar_days=horizon, timestamp=midnight(origin).isoformat(),
        target_date=(origin + timedelta(days=horizon)).isoformat() if horizon in (1, 3, 7) else None,
        model_version=p["model_version"], flags=p["flags"], data_source=provenance, **scope,
        latest_report_date=p["latest_report_date"], observation_age_calendar_days=p["age"])
    if "stale_data" in response.flags:
        response.reliability_status = "stale data"
        return response
    if p["prediction"] is None:
        return response
    response.prediction_inr_per_quintal = p["prediction"]
    response.reliability_status = "limited evidence"
    try:
        calibration, recent = evidence_at(evidence_folder, horizon, origin, scope, p["model_version"])
    except (ValueError, OSError, KeyError):
        response.flags.append("invalid_reliability_evidence")
        response.prediction_inr_per_quintal = None
        response.reliability_status = "unavailable"
        return response
    if calibration is None or not calibration["radii"]:
        response.flags.append("insufficient_calibration")
        return response
    response.intervals = intervals_for(p["prediction"], calibration)
    if (midnight(origin) - pd.Timestamp(calibration["frozen_at"])).days > POLICY["maximum_calibration_age_days"]:
        response.flags.append("stale_calibration")
    if any(i.upper_inr_per_quintal - i.lower_inr_per_quintal > POLICY["maximum_relative_interval_width"] * p["prediction"] for i in response.intervals):
        response.flags.append("wide_empirical_interval")
    if len(recent) and (midnight(origin) - pd.to_datetime(recent.actual_available_at, utc=True).max()).days > POLICY["maximum_error_evidence_age_days"]:
        response.flags.append("stale_error_evidence")
    if len(recent) >= 20:
        recent = recent.sort_values("origin_date")
        if recent.tail(20).absolute_error.mean() > 2 * calibration["calibration_mae"] + 1:
            response.flags.append("model_drift")
        if recent.tail(5).absolute_error.mean() > max(.2 * p["prediction"], calibration["calibration_p90_error"]):
            response.flags.append("large_recent_forecast_errors")
    enough = len(recent) >= POLICY["minimum_validation_errors"]
    span = (pd.to_datetime(recent.origin_date).max() - pd.to_datetime(recent.origin_date).min()).days + 1 if len(recent) else 0
    covered = all(((recent.actual >= np.maximum(0, recent.prediction - radius)) & (recent.actual <= recent.prediction + radius)).mean() >= float(level) - .1 for level, radius in calibration["radii"].items()) if len(recent) else False
    if enough and span >= POLICY["minimum_validation_span_days"] and covered and not response.flags:
        response.reliability_status = "validated"
    else:
        response.flags.append("limited_unseen_interval_evidence")
    return response


def reliable_forecast(session, plan: Plan, origin: date, horizon: int, evidence_folder: Path | None = None, champion: Path | None = None) -> ReliabilityForecast:
    """Stable public service: official scoped data only; no arbitrary caller price arrays."""
    from dataclasses import replace
    vintages, source = load_vintages(session, replace(plan, validation_end=origin))
    return reliability_response(vintages, plan, origin, horizon, source, evidence_folder, champion)
