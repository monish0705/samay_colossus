"""Point-in-time feature construction; independent of any model fitting."""
import hashlib
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ImportBatch, ImportRow

VERSION = "samay-features-v1"
IST = ZoneInfo("Asia/Kolkata")
LAGS = (1, 2, 3, 7, 14, 30)
WINDOWS = (7, 14, 30)
FEATURES = [f"lag_{n}_obs_inr_per_quintal" for n in LAGS] + [f"rolling_{stat}_{n}_obs_inr_per_quintal" for n in WINDOWS for stat in ("mean", "median", "std")] + ["origin_weekday", "origin_month", "target_weekday", "target_month", "days_since_latest_report", "history_30_obs_span_days"]
DEFINITIONS = {
    "decision_time": "00:00 Asia/Kolkata on origin_date. Report date must be strictly earlier than origin_date and snapshot fetched_at <= decision_time.",
    "lag_n_obs": "Nth most recent distinct report date available at decision time, within the selected market/commodity/variety/grade. Observation lags, not calendar-day lags.",
    "rolling": "Last N available observations strictly before origin; mean, median, sample std (ddof=1), requiring all N. Equivalent to causal shift(1) before rolling on a complete series.",
    "target": "Modal wholesale price in INR/quintal on exactly origin_date + horizon calendar days; no nearest-date matching, interpolation or forward fill.",
    "labels": "Training labels frozen as known strictly before validation_start; validation labels frozen strictly before holdout_start. Later revisions cannot alter these labels.",
    "calendar": "Origin and target weekday (Monday=0) and month; deterministically known at origin.",
    "extras": "Only report recency and 30-observation calendar span. No arrivals, min/max, weather, target prices or unverified external predictors.",
}


@dataclass(frozen=True)
class Plan:
    start: date
    train_end: date
    validation_end: date
    holdout_end: date
    variety: str
    grade: str
    market: str = "Kolar APMC"
    commodity: str = "Tomato"
    min_train: int = 120
    min_validation: int = 30
    min_train_span_days: int = 180
    min_train_coverage: float = .5
    max_price_age_days: int = 7
    source_kind: str = "official"
    candidate_suite: str = "v1"

    def validate(self):
        if self.source_kind not in {"official", "secondary"}:
            raise ValueError("Only explicitly scoped official or verified secondary series are eligible")
        if self.candidate_suite not in {"v1", "relative_v2"}:
            raise ValueError("Unknown predeclared candidate suite")
        if not self.start < self.train_end < self.validation_end < self.holdout_end:
            raise ValueError("Require start < train_end < validation_end < holdout_end")
        if (self.holdout_end - self.start).days > 36600:
            raise ValueError("Date window must not exceed 100 years")
        if self.min_train < 2 or self.min_validation < 2 or self.min_train_span_days < 1 or self.max_price_age_days < 1 or not 0 < self.min_train_coverage <= 1:
            raise ValueError("Invalid reliability policy")
        supported_markets = {"Kolar APMC", "Shivamogga Mandi", "Hubballi APMC", "Tiptur APMC", "Bengaluru APMC"}
        supported_commodities = {"Tomato", "Arecanut", "Onion", "Copra", "Potato"}
        if self.market not in supported_markets or self.commodity not in supported_commodities or not self.variety.strip() or not self.grade.strip():
            raise ValueError("Select a supported Karnataka market/commodity and an explicit consistent variety/grade")

    def serializable(self):
        return {k: v.isoformat() if isinstance(v, date) else v for k, v in asdict(self).items()}


def midnight(value: date) -> pd.Timestamp:
    return pd.Timestamp(datetime.combine(value, datetime.min.time(), IST)).tz_convert("UTC")


def empty_vintages() -> pd.DataFrame:
    return pd.DataFrame(columns=["report_date", "available_at", "price", "batch_id", "row_id", "file_sha256"])


def load_vintages(session: Session, plan: Plan, *, final_evaluation: bool = False) -> tuple[pd.DataFrame, dict]:
    """Only official, hash-verified archived rows. SQL excludes final holdout values.

    Local archive hashing establishes integrity, not independent publisher authentication.
    Operator source attestation is retained, never upgraded to a stronger claim.
    """
    end = plan.holdout_end if final_evaluation else plan.validation_end
    stmt = select(ImportRow, ImportBatch).join(ImportBatch, ImportRow.batch_id == ImportBatch.id).where(
        ImportBatch.data_kind == plan.source_kind,
        ImportBatch.fetched_at < midnight(end + timedelta(days=1)).to_pydatetime(),
        ImportRow.normalized["report_date"].as_string() <= end.isoformat(),
        ImportRow.normalized["market"].as_string() == plan.market,
        ImportRow.normalized["commodity"].as_string() == plan.commodity,
        ImportRow.normalized["variety"].as_string() == plan.variety,
        ImportRow.normalized["grade"].as_string() == plan.grade,
    ).order_by(ImportBatch.fetched_at, ImportRow.id)
    rows, batches, dispositions = [], {}, {}
    for row, batch in session.execute(stmt):
        dispositions[row.status] = dispositions.get(row.status, 0) + 1
        if row.status not in {"inserted", "revised", "duplicates"}:
            continue
        if batch.id not in batches:
            from urllib.parse import urlsplit

            from app.ingestion import SourceManifest
            manifest = SourceManifest.model_validate(batch.manifest)
            if manifest.source_label != batch.source_label or (manifest.sha256 and manifest.sha256.lower() != batch.file_sha256) or any(marker in batch.source_label.casefold() for marker in ("fixture", "demo_data")):
                raise ValueError(f"Source label/hash mismatch or fixture marker in official batch {batch.id}")
            parsed = urlsplit(batch.source_url)
            hosts = {"data.gov.in", "www.data.gov.in", "agmarknet.gov.in", "www.agmarknet.gov.in"} if plan.source_kind == "official" else {"ckandev.indiadataportal.com"}
            if manifest.data_kind != plan.source_kind or manifest.source_url != batch.source_url or manifest.fetched_at != batch.fetched_at or not manifest.unit_evidence.strip() or parsed.scheme != "https" or parsed.hostname not in hosts or parsed.query or parsed.username or parsed.fragment:
                raise ValueError(f"Invalid official source attestation for batch {batch.id}")
            archive = Path(batch.archive_path)
            if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != batch.file_sha256:
                raise ValueError(f"Missing/tampered raw archive for batch {batch.id}")
            batches[batch.id] = {"batch_id": batch.id, "sha256": batch.file_sha256, "source_url": batch.source_url, "source_label": batch.source_label, "fetched_at": batch.fetched_at.isoformat(), "unit_evidence": manifest.unit_evidence}
        n = row.normalized
        from app.ingestion import district_name, market_district
        if n["state"] != "Karnataka" or district_name(n["district"]) != market_district(plan.market) or n["price_unit"] != "INR/quintal":
            raise ValueError("Scope/unit mismatch in normalized ledger")
        prices = [float(n[k]) for k in ("min", "modal", "max")]
        if not all(np.isfinite(prices)) or not 0 <= prices[0] <= prices[1] <= prices[2] or prices[1] <= 0:
            raise ValueError("Invalid normalized ledger price")
        rows.append({"report_date": date.fromisoformat(n["report_date"]), "available_at": pd.Timestamp(batch.fetched_at), "price": prices[1], "batch_id": batch.id, "row_id": row.id, "file_sha256": batch.file_sha256})
    return pd.DataFrame(rows, columns=empty_vintages().columns), {"sources": list(batches.values()), "development_ledger_dispositions": dispositions, "provenance": "Official operator-attested manifests and SHA256-verified local archives; independent publisher authentication not established by this pipeline"}


def asof(vintages: pd.DataFrame, cutoff: pd.Timestamp, before: date | None = None, inclusive: bool = True) -> pd.DataFrame:
    if vintages.empty:
        return empty_vintages()
    mask = vintages.available_at <= cutoff if inclusive else vintages.available_at < cutoff
    if before is not None:
        mask &= vintages.report_date < before
    frame = vintages.loc[mask].copy()
    if frame.empty:
        return frame
    # The common immutable snapshot has one vintage per report date. Avoid a
    # repeated groupby over its entire history; the result is exactly identical.
    if frame.report_date.is_unique:
        return frame.sort_values("report_date")
    # Do not silently resolve ambiguous simultaneous source vintages.
    if (frame.groupby(["report_date", "available_at"]).price.nunique() > 1).any():
        raise ValueError("Conflicting prices at identical report/availability timestamp")
    return frame.sort_values(["report_date", "available_at", "row_id"]).drop_duplicates("report_date", keep="last").sort_values("report_date")


def features_at(vintages: pd.DataFrame, origin: date, horizon: int, *, decision_at=None) -> tuple[dict, dict]:
    if horizon not in (1, 3, 7):
        raise ValueError("Supported horizons: 1, 3, 7 calendar days")
    cutoff = midnight(origin) if decision_at is None else pd.Timestamp(decision_at)
    if cutoff.tzinfo is None or not midnight(origin) <= cutoff < midnight(origin+timedelta(days=1)):
        raise ValueError("Decision timestamp must be timezone-aware and inside the selected origin date")
    history = asof(vintages, cutoff, before=origin)
    values = history.price.to_numpy(dtype=float)
    features = {f"lag_{n}_obs_inr_per_quintal": float(values[-n]) if len(values) >= n else np.nan for n in LAGS}
    for n in WINDOWS:
        chunk = values[-n:]
        for stat, fn in (("mean", np.mean), ("median", np.median), ("std", lambda x: np.std(x, ddof=1))):
            features[f"rolling_{stat}_{n}_obs_inr_per_quintal"] = float(fn(chunk)) if len(values) >= n else np.nan
    target = origin + timedelta(days=horizon)
    age = (origin - history.iloc[-1].report_date).days if len(history) else np.nan
    features.update(origin_weekday=origin.weekday(), origin_month=origin.month, target_weekday=target.weekday(), target_month=target.month, days_since_latest_report=age,
                    history_30_obs_span_days=(history.iloc[-1].report_date - history.iloc[-30].report_date).days if len(history) >= 30 else np.nan)
    used = history.tail(30)
    audit = {"decision_at": cutoff.isoformat(), "history_count": len(history),
             "max_feature_report_date": used.report_date.max().isoformat() if len(used) else None,
             "max_feature_available_at": used.available_at.max().isoformat() if len(used) else None,
             "source_row_ids": used.row_id.tolist()}
    return features, audit


def build_horizon(vintages: pd.DataFrame, plan: Plan, horizon: int) -> tuple[pd.DataFrame, dict]:
    plan.validate()
    rows = []
    train_freeze = midnight(plan.train_end + timedelta(days=1))
    validation_freeze = midnight(plan.validation_end + timedelta(days=1))
    labels = {"train": asof(vintages, train_freeze, inclusive=False), "validation": asof(vintages, validation_freeze, inclusive=False)}
    label_maps = {key: {r.report_date: r for r in frame.itertuples()} for key, frame in labels.items()}
    for stamp in pd.date_range(plan.start, plan.validation_end, freq="D"):
        origin = stamp.date()
        split = "train" if origin <= plan.train_end else "validation"
        end = plan.train_end if split == "train" else plan.validation_end
        target = origin + timedelta(days=horizon)
        feature, audit = features_at(vintages, origin, horizon)
        label = label_maps[split].get(target)
        reason = "eligible"
        if target > end:
            reason = "embargo_target_crosses_split"
            label = None  # Never open labels from the next partition.
        elif label is None:
            reason = "missing_target_at_label_freeze"
        elif not all(np.isfinite(list(feature.values()))):
            reason = "insufficient_causal_history"
        elif feature["days_since_latest_report"] > plan.max_price_age_days:
            reason = "stale_causal_history"
        rows.append({"origin_date": origin.isoformat(), "target_date": target.isoformat(), "split": split,
                     "reason": reason, **feature, **audit,
                     "target_modal_price_inr_per_quintal": float(label.price) if label is not None else np.nan,
                     "label_available_at": label.available_at.isoformat() if label is not None else None,
                     "label_source_row_id": label.row_id if label is not None else None})
    frame = pd.DataFrame(rows)
    counts = {split: int(((frame.split == split) & (frame.reason == "eligible")).sum()) for split in ("train", "validation")}
    training = frame[(frame.split == "train") & (frame.reason == "eligible")]
    span = (date.fromisoformat(training.origin_date.max()) - date.fromisoformat(training.origin_date.min())).days + 1 if len(training) else 0
    training_snapshot = labels["train"]
    date_count = sum(plan.start <= d <= plan.train_end for d in training_snapshot.report_date)
    coverage = date_count / ((plan.train_end - plan.start).days + 1)
    problems = []
    if counts["train"] < plan.min_train:
        problems.append(f"train {counts['train']} < minimum {plan.min_train}")
    if counts["validation"] < plan.min_validation:
        problems.append(f"validation {counts['validation']} < minimum {plan.min_validation}")
    if span < plan.min_train_span_days:
        problems.append(f"eligible training span {span} < minimum {plan.min_train_span_days} calendar days")
    if coverage < plan.min_train_coverage:
        problems.append(f"training observed-date coverage {coverage:.3f} < minimum {plan.min_train_coverage}")
    summary = {"horizon_calendar_days": horizon, "status": "insufficient_data" if problems else "development_viable_not_trained",
               "effective_train_samples": counts["train"], "effective_validation_samples": counts["validation"],
               "train_span_calendar_days": span, "training_observed_date_coverage": coverage,
               "exclusions": frame.groupby(["split", "reason"]).size().to_dict(), "reasons": problems,
               "holdout_samples": "reserved_not_evaluated", "embargo": f"Purge origins whose exact +{horizon}-calendar-day target crosses partition end; labels must be available before next partition begins"}
    summary["exclusions"] = {f"{split}/{reason}": int(n) for (split, reason), n in summary["exclusions"].items()}
    return frame, summary
