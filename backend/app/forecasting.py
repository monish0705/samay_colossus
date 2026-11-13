"""Reproducible model comparison and point-in-time prediction. No fabricated defaults."""
import hashlib
import json
import os
import pickle
import platform
from contextlib import nullcontext
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from pathlib import Path

# Set before sklearn/OpenMP initialization. Native DLL introspection through
# threadpoolctl can fail for Windows environments under non-ASCII directory names.
for _variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_variable] = "1"

import numpy as np
import pandas as pd

from app.features import FEATURES, Plan, asof, build_horizon, features_at, midnight

SEED = 42
VERSION = "samay-forecast-v1"
TARGET = "target_modal_price_inr_per_quintal"
BASELINES = ("naive", "mean_14", "median_14")


def thread_context():
    if os.name == "nt":
        return nullcontext()
    from threadpoolctl import threadpool_limits
    return threadpool_limits(limits=1)


def runtime_versions():
    runtime = {name: package_version(name) for name in ("scikit-learn", "numpy", "pandas")}
    runtime["python"] = platform.python_version()
    try:
        runtime["lightgbm"] = package_version("lightgbm")
    except PackageNotFoundError:
        runtime["lightgbm"] = None
    return runtime


def metrics(y, prediction, latest) -> dict:
    y, prediction, latest = [np.asarray(x, dtype=float) for x in (y, prediction, latest)]
    if y.ndim != 1 or y.shape != prediction.shape or y.shape != latest.shape or len(y) == 0 or not all(np.isfinite(x).all() for x in (y, prediction, latest)):
        raise ValueError("Metrics require nonempty, aligned finite vectors")
    error = prediction - y
    absolute = np.abs(error)
    denominator = np.abs(y) + np.abs(prediction)
    safe = denominator > .01
    zero = (y == 0) & (prediction == 0)
    smape = np.zeros(len(y))
    smape[safe] = 200 * absolute[safe] / denominator[safe]
    valid = safe | zero
    def sign(x):
        return np.where(np.abs(x) <= .01, 0, np.sign(x))
    return {"n": len(y), "mae_inr_per_quintal": float(absolute.mean()), "rmse_inr_per_quintal": float(np.sqrt(np.mean(error ** 2))),
            "smape_pct": float(smape[valid].mean()) if valid.any() else None, "smape_excluded_tiny_denominator": int((~valid).sum()),
            "wape_pct": float(100 * absolute.sum() / np.abs(y).sum()) if np.abs(y).sum() > .01 * len(y) else None,
            "directional_accuracy": float(np.mean(sign(prediction - latest) == sign(y - latest))),
            "p90_absolute_error_inr_per_quintal": float(np.quantile(absolute, .9)),
            "p90_overprediction_inr_per_quintal": float(np.quantile(np.maximum(error, 0), .9))}


def seasonal_value(vintages, origin, horizon):
    previous = origin + timedelta(days=horizon) - timedelta(days=7)
    while previous >= origin:
        previous -= timedelta(days=7)
    history = asof(vintages, midnight(origin), before=origin)
    match = history[history.report_date == previous]
    return float(match.iloc[-1].price) if len(match) else np.nan


def examples(vintages, start, end, horizon, freeze):
    """Reconstruct labels at each fold's freeze, never at the eventual train end."""
    labels = {r.report_date: r for r in asof(vintages, midnight(freeze), inclusive=False).itertuples()}
    rows = []
    for stamp in pd.date_range(start, end):
        origin = stamp.date()
        target = origin + timedelta(days=horizon)
        if target > end or target not in labels:
            continue
        feature, audit = features_at(vintages, origin, horizon)
        if not np.isfinite(list(feature.values())).all() or feature["days_since_latest_report"] > 7:
            continue
        rows.append({"origin_date": origin.isoformat(), "target_date": target.isoformat(), **feature,
                     TARGET: float(labels[target].price), "label_available_at": labels[target].available_at.isoformat(),
                     "seasonal_price": seasonal_value(vintages, origin, horizon)})
    return pd.DataFrame(rows, columns=["origin_date", "target_date"] + FEATURES + [TARGET, "label_available_at", "seasonal_price"])


def rolling_folds(vintages, plan, horizon):
    days = (plan.train_end - plan.start).days + 1
    boundaries = [plan.start + timedelta(days=int(days * part)) for part in (.5, .67, .84)] + [plan.train_end + timedelta(days=1)]
    folds = []
    for first, following in zip(boundaries, boundaries[1:], strict=False):
        train = examples(vintages, plan.start, first - timedelta(days=1), horizon, first)
        valid = examples(vintages, first, following - timedelta(days=1), horizon, following)
        if len(train) < 60 or len(valid) < 14:
            return []
        folds.append((train, valid))
    return folds


def estimator(name):
    if name.startswith("ridge_"):
        from sklearn.linear_model import Ridge
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
        return make_pipeline(StandardScaler(), Ridge(alpha=float(name.split("_")[1])))
    if name == "hist_gradient_boosting":
        from sklearn.ensemble import HistGradientBoostingRegressor
        return HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=15, learning_rate=.05, l2_regularization=1, random_state=SEED, early_stopping=False)
    if name == "lightgbm":
        from lightgbm import LGBMRegressor
        return LGBMRegressor(n_estimators=100, num_leaves=15, learning_rate=.05, reg_lambda=1, random_state=SEED, n_jobs=1, verbosity=-1, deterministic=True, force_col_wise=True)
    return None


def fit(name, frame):
    model = estimator(name)
    if model is not None:
        with thread_context():
            model.fit(frame[FEATURES], frame[TARGET])
    return model


def predict_rows(name, model, frame):
    if name == "naive":
        result = frame["lag_1_obs_inr_per_quintal"].to_numpy()
    elif name in {"mean_14", "median_14"}:
        stat = name.split("_")[0]
        result = frame[f"rolling_{stat}_14_obs_inr_per_quintal"].to_numpy()
    elif name == "seasonal_naive":
        # Registered fallback is part of this candidate, identical in all partitions.
        result = frame.seasonal_price.fillna(frame.lag_1_obs_inr_per_quintal).to_numpy()
    else:
        with thread_context():
            result = model.predict(frame[FEATURES])
    result = np.asarray(result, dtype=float)
    if not np.isfinite(result).all():
        raise ValueError("Model produced nonfinite predictions")
    return np.maximum(result, 0)  # Shared, predeclared nonnegative-price constraint.


def score(name, model, frame):
    prediction = predict_rows(name, model, frame)
    return metrics(frame[TARGET], prediction, frame.lag_1_obs_inr_per_quintal)


def select_horizon(vintages, plan: Plan, horizon):
    _, reliability = build_horizon(vintages, plan, horizon)
    result = {"horizon": horizon, "sample_policy": reliability, "status": "insufficient_data", "comparisons": [], "champion": None}
    if reliability["status"] == "insufficient_data":
        result["reason"] = reliability["reasons"]
        return result, None, None
    folds = rolling_folds(vintages, plan, horizon)
    if not folds:
        result["reason"] = ["Need three chronological CV folds with >=60 training and >=14 validation examples each"]
        return result, None, None
    train = examples(vintages, plan.start, plan.train_end, horizon, plan.train_end + timedelta(days=1))
    validation = examples(vintages, plan.train_end + timedelta(days=1), plan.validation_end, horizon, plan.validation_end + timedelta(days=1))
    candidates = list(BASELINES) + ["ridge_1", "ridge_10", "ridge_100", "hist_gradient_boosting"]
    seasonal_supported = all(len(t) >= 56 and v.seasonal_price.notna().mean() >= .9 for t, v in folds)
    if seasonal_supported:
        # Initial coverage qualifies a seasonal candidate; CV skill gates promotion below.
        candidates.append("seasonal_naive")
    skips = {"seasonal_naive": "Insufficient training-fold weekly coverage"} if not seasonal_supported else {}
    if min(len(t) for t, _ in folds) >= 500:
        try:
            import lightgbm  # noqa: F401
            candidates.append("lightgbm")
        except ImportError:
            skips["lightgbm"] = "Optional LightGBM dependency not installed"
    else:
        skips["lightgbm"] = "Requires >=500 reliable training samples in every CV fold"
    fitted = {}
    for name in candidates:
        fold_metrics = []
        for t, v in folds:
            fold_metrics.append(score(name, fit(name, t), v))
        fitted[name] = fit(name, train)
        validation_metrics = score(name, fitted[name], validation)
        result["comparisons"].append({"candidate": name, "cv": fold_metrics, "cv_mean_mae": float(np.mean([m["mae_inr_per_quintal"] for m in fold_metrics])),
            "cv_std_mae": float(np.std([m["mae_inr_per_quintal"] for m in fold_metrics])), "validation": validation_metrics})
    comparisons = {r["candidate"]: r for r in result["comparisons"]}
    def rank(r):
        return (r["validation"]["mae_inr_per_quintal"], r["cv_std_mae"], r["validation"]["p90_overprediction_inr_per_quintal"], r["candidate"])
    baselines = [comparisons[n] for n in BASELINES]
    reference = min(baselines, key=rank)
    admissible = list(baselines)
    for name, row in comparisons.items():
        if name in BASELINES:
            continue
        wins = sum(all(row["cv"][i]["mae_inr_per_quintal"] < comparisons[b]["cv"][i]["mae_inr_per_quintal"] for b in BASELINES) for i in range(len(folds)))
        row["cv_folds_beating_all_baselines"] = wins
        row["promotion_eligible"] = wins >= 2 and row["cv_mean_mae"] < reference["cv_mean_mae"] and row["validation"]["mae_inr_per_quintal"] < reference["validation"]["mae_inr_per_quintal"]
        if row["promotion_eligible"]:
            admissible.append(row)
    winner = min(admissible, key=rank)["candidate"]
    result.update(status="selected", champion=winner, skipped=skips,
                  selection_reason="Lowest validation MAE among reliable candidates; CV variability and p90 overprediction break ties. ML/seasonal promotion requires beating every core baseline in >=2/3 CV folds and beating the best validation baseline on validation and mean CV MAE.",
                  folds=[{"train_n": len(t), "validation_n": len(v), "train_start": t.origin_date.min(), "train_end": t.origin_date.max(), "validation_start": v.origin_date.min(), "validation_end": v.origin_date.max()} for t, v in folds])
    # Refit selected fixed configuration on all development labels known at holdout start.
    development = examples(vintages, plan.start, plan.validation_end, horizon, plan.validation_end + timedelta(days=1))
    return result, fit(winner, development), development


def save_champion(folder: Path, comparison, model, development, plan, fingerprint):
    folder.mkdir(parents=True, exist_ok=False)
    payload = pickle.dumps(model, protocol=5)
    (folder / "model.pkl").write_bytes(payload)
    version = folder.parent.name + "-" + folder.name
    metadata = {"version": version, "algorithm_version": VERSION, "candidate": comparison["champion"], "horizon": comparison["horizon"],
        "market": plan.market, "commodity": plan.commodity, "variety": plan.variety, "grade": plan.grade, "feature_schema": FEATURES,
        "training_window": [development.origin_date.min(), development.origin_date.max()], "trained_before": midnight(plan.validation_end + timedelta(days=1)).isoformat(),
        "seed": SEED, "dataset_fingerprint": fingerprint, "model_sha256": hashlib.sha256(payload).hexdigest(),
        "comparison": comparison, "created_at": datetime.now(UTC).isoformat()}
    metadata["plan"] = plan.serializable()
    metadata["training_samples"] = len(development)
    metadata["runtime"] = runtime_versions()
    (folder / "metadata.json").write_text(json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    return metadata


def _forecast_with_vintages(folder: Path, vintages, origin: date, horizon: int, market="Kolar APMC", commodity="Tomato", variety="local", grade="faq"):
    if not (folder / "metadata.json").exists():
        raise ValueError("Unsupported or untrained series/horizon; no champion artifact")
    meta = json.loads((folder / "metadata.json").read_text())
    if meta.get("research_only"):
        raise ValueError("Retrospective research artifacts cannot be used by the production forecasting service")
    if (market, commodity, variety, grade, horizon) != tuple(meta[k] for k in ("market", "commodity", "variety", "grade", "horizon")) or horizon not in (1, 3, 7):
        raise ValueError("Unsupported series/horizon combination")
    if meta["feature_schema"] != FEATURES or midnight(origin) < pd.Timestamp(meta["trained_before"]):
        raise ValueError("Feature schema mismatch or model not available at requested origin")
    feature, audit = features_at(vintages, origin, horizon)
    if not np.isfinite(list(feature.values())).all() or feature["days_since_latest_report"] > 7:
        raise ValueError("Insufficient or stale historically available inputs")
    content = (folder / "model.pkl").read_bytes()
    if hashlib.sha256(content).hexdigest() != meta["model_sha256"]:
        raise ValueError("Model integrity check failed")
    model = pickle.loads(content)  # Trusted local artifacts only; never accept user uploads.
    row = pd.DataFrame([{**feature, "seasonal_price": seasonal_value(vintages, origin, horizon)}])
    value = float(predict_rows(meta["candidate"], model, row)[0])
    return {"prediction_inr_per_quintal": value, "model_version": meta["version"], "horizon_calendar_days": horizon,
            "market": market, "commodity": commodity, "variety": variety, "grade": grade, "origin_date": origin.isoformat(),
            "target_date": (origin + timedelta(days=horizon)).isoformat(), "latest_report_date": audit["max_feature_report_date"],
            "latest_available_at": audit["max_feature_available_at"], "observation_age_calendar_days": feature["days_since_latest_report"]}


def forecast(session, folder: Path, origin: date, horizon: int, market="Kolar APMC", commodity="Tomato", variety="local", grade="faq"):
    """Public inference: load scoped official historical inputs from the trusted ledger."""
    from app.features import load_vintages
    if not (folder / "metadata.json").exists():
        raise ValueError("Unsupported or untrained series/horizon; no champion artifact")
    meta = json.loads((folder / "metadata.json").read_text())
    raw = dict(meta["plan"])
    for key in ("start", "train_end", "validation_end", "holdout_end"):
        raw[key] = date.fromisoformat(raw[key])
    # Loader includes the decision day, but features_at strictly enforces origin time.
    raw["validation_end"] = origin
    plan = Plan(**raw)
    vintages, _ = load_vintages(session, plan)
    return _forecast_with_vintages(folder, vintages, origin, horizon, market, commodity, variety, grade)
