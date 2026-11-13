"""Auditable CSV ingestion. No network endpoint or government credentials assumed."""
import csv
import hashlib
import io
import json
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import pandas as pd
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Commodity, ImportBatch, ImportRow, MandiObservation, Market


class SourceManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_label: str
    source_url: str
    data_kind: Literal["official", "fixture"]
    fetched_at: datetime
    price_unit: str
    unit_evidence: str
    date_format: Literal["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"] = "%d/%m/%Y"
    sha256: str | None = None

    @field_validator("fetched_at")
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError("fetched_at must include timezone")
        if value > datetime.now(UTC) + timedelta(minutes=5):
            raise ValueError("fetched_at cannot be in the future")
        return value.astimezone(UTC)


def label(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def market_name(value: str) -> str:
    name = label(value)
    if name in {"kolar", "kolar apmc", "kolar (apmc)", "kolar a.p.m.c."}:
        return "Kolar APMC"
    raise ValueError(f"Unsupported market: {value!r}")


def commodity_name(value: str) -> str:
    if label(value) == "tomato":
        return "Tomato"
    raise ValueError(f"Unsupported commodity: {value!r}")


def unit_factor(value: str) -> Decimal:
    unit = label(value).replace("₹", "inr").replace(" ", "")
    factors = {"inr/quintal": "1", "rs/quintal": "1", "rs./quintal": "1", "inr/100kg": "1", "inr/kg": "100", "rs/kg": "100", "inr/tonne": "0.1"}
    if unit not in factors:
        raise ValueError(f"Unknown price unit {value!r}; currency and weight basis required")
    return Decimal(factors[unit])


def number(value: str) -> Decimal:
    # Accept grouped Indian or international numbers, reject malformed grouping.
    value = value.strip()
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})*,\d{3})(?:\.\d{1,2})?", value):
        raise ValueError(f"Invalid nonnegative numeric price: {value!r}")
    try:
        result = Decimal(value.replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("Invalid numeric price") from exc
    if not result.is_finite():
        raise ValueError("Nonfinite price")
    return result


ALIASES = {
    "state": "state", "district": "district", "market": "market", "commodity": "commodity",
    "variety": "variety", "grade": "grade", "arrival_date": "report_date", "arrival date": "report_date",
    "report_date": "report_date", "report date": "report_date", "date": "report_date",
    "min_price": "min", "min price": "min", "minimum price": "min",
    "max_price": "max", "max price": "max", "maximum price": "max",
    "modal_price": "modal", "modal price": "modal", "price_unit": "unit", "price unit": "unit",
}
REQUIRED = {"state", "district", "market", "commodity", "variety", "report_date", "min", "max", "modal"}


def normalize(row: dict, manifest: SourceManifest) -> dict:
    if label(row["state"]) != "karnataka" or label(row["district"]) != "kolar":
        raise ValueError("outside_scope")
    market = market_name(row["market"])
    commodity = commodity_name(row["commodity"])
    try:
        observed = datetime.strptime(row["report_date"].strip(), manifest.date_format).date()
    except ValueError as exc:
        raise ValueError("Invalid report date for manifest date_format") from exc
    if observed > manifest.fetched_at.date():
        raise ValueError("Report date is after fetched_at")
    raw_unit = row.get("unit") or manifest.price_unit
    factor = unit_factor(raw_unit)
    prices = {key: number(row[key]) * factor for key in ("min", "modal", "max")}
    if not (prices["min"] <= prices["modal"] <= prices["max"]):
        raise ValueError("Impossible min/modal/max ordering")
    if any(x > Decimal("9999999999.99") or x != x.quantize(Decimal("0.01")) for x in prices.values()):
        raise ValueError("Price exceeds database precision")
    if not row["variety"].strip():
        raise ValueError("Missing variety")
    return {"market": market, "commodity": commodity, "state": "Karnataka", "district": "Kolar",
            "report_date": observed.isoformat(), "variety": label(row["variety"]),
            "grade": label(row.get("grade", "")) or "unspecified", "raw_unit": raw_unit,
            "price_unit": "INR/quintal", **{k: str(v.quantize(Decimal("0.01"))) for k, v in prices.items()}}


def import_csv(session: Session, path: Path, manifest: SourceManifest, output: Path,
               start: date | None = None, end: date | None = None,
               market: str = "Kolar APMC", commodity: str = "Tomato",
               suspicious_threshold: Decimal = Decimal(100000)) -> dict:
    """Caller owns transaction. Every parsed record retains raw values and disposition."""
    market_name(market)
    commodity_name(commodity)
    if start and end and start > end:
        raise ValueError("start-date must be <= end-date")
    if not suspicious_threshold.is_finite() or suspicious_threshold <= 0:
        raise ValueError("Suspicious price threshold must be positive")
    url = urlsplit(manifest.source_url)
    if manifest.data_kind == "official" and (url.scheme != "https" or url.hostname not in {"data.gov.in", "www.data.gov.in", "agmarknet.gov.in", "www.agmarknet.gov.in"} or url.username or url.query or url.fragment):
        raise ValueError("Official source requires an HTTPS OGD/AGMARKNET provenance URL without credentials/query")
    if not manifest.unit_evidence.strip():
        raise ValueError("unit_evidence is required; do not assume CSV units")
    unit_factor(manifest.price_unit)
    content = path.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    if manifest.sha256 and manifest.sha256.lower() != digest:
        raise ValueError("SHA256 does not match manifest")
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""), strict=True)
    if not reader.fieldnames:
        raise ValueError("Empty CSV")
    headers = [ALIASES.get(label(x)) for x in reader.fieldnames]
    known = [h for h in headers if h]
    if len(known) != len(set(known)) or not REQUIRED.issubset(known):
        raise ValueError(f"Missing or ambiguous CSV columns; required: {sorted(REQUIRED)}")
    output.mkdir(parents=True, exist_ok=True)
    archive = output / "raw" / f"{digest}.csv"
    archive.parent.mkdir(exist_ok=True)
    if archive.exists() and hashlib.sha256(archive.read_bytes()).hexdigest() != digest:
        raise ValueError("Archived file hash mismatch")
    archive.write_bytes(content)
    batch = ImportBatch(file_sha256=digest, filename=path.name, archive_path=str(archive.resolve()),
                        source_url=manifest.source_url, source_label=manifest.source_label,
                        data_kind=manifest.data_kind, fetched_at=manifest.fetched_at,
                        manifest=manifest.model_dump(mode="json"))
    session.add(batch)
    session.flush()
    counts = dict.fromkeys(["records", "inserted", "revised", "duplicates", "stale", "quarantined", "filtered"], 0)
    accepted_dates = set()
    accepted_prices = []
    quarantine = []
    export = []
    for line, raw in enumerate(reader, 2):
        counts["records"] += 1
        normalized = None
        observation = None
        reason = None
        try:
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError("Malformed CSV row width")
            if manifest.data_kind == "official" and any("demo_data" in str(v).casefold() or "test_fixture" in str(v).casefold() for v in raw.values()):
                raise ValueError("Fixture/demo marker cannot enter official observations")
            row = {alias: raw[name] for name, alias in zip(reader.fieldnames, headers, strict=False) if alias}
            if label(row["state"]) != "karnataka" or label(row["district"]) != "kolar":
                raise LookupError("outside_scope")
            if label(row["market"]) not in {"kolar", "kolar apmc", "kolar (apmc)", "kolar a.p.m.c."} or label(row["commodity"]) != "tomato":
                raise LookupError("outside_scope")
            normalized = normalize(row, manifest)
            observed = date.fromisoformat(normalized["report_date"])
            if (start and observed < start) or (end and observed > end):
                raise LookupError("outside_date_range")
            if Decimal(normalized["max"]) > suspicious_threshold or Decimal(normalized["modal"]) == 0:
                raise ValueError("Suspicious zero modal or price above review threshold")
            m = session.scalar(select(Market).where(Market.name == normalized["market"], Market.state == "Karnataka", Market.district == "Kolar"))
            c = session.scalar(select(Commodity).where(Commodity.name == normalized["commodity"]))
            if m is None:
                m = Market(name=normalized["market"], state="Karnataka", district="Kolar", data_source=manifest.source_label)
                session.add(m)
            if c is None:
                c = Commodity(name=normalized["commodity"], data_source=manifest.source_label)
                session.add(c)
            session.flush()
            observation = session.scalar(select(MandiObservation).where(
                MandiObservation.market_id == m.id, MandiObservation.commodity_id == c.id,
                MandiObservation.observed_on == observed, MandiObservation.variety == normalized["variety"],
                MandiObservation.grade == normalized["grade"], MandiObservation.data_kind == manifest.data_kind))
            values = {f"{k}_price_inr_per_quintal": Decimal(normalized[v]) for k, v in [("min", "min"), ("modal", "modal"), ("max", "max")]}
            status = "inserted"
            if observation is not None:
                previous = session.get(ImportBatch, observation.latest_batch_id)
                if all(getattr(observation, k) == v for k, v in values.items()):
                    status = "duplicates"
                    if previous and manifest.fetched_at > previous.fetched_at:
                        # A later unchanged report confirms freshness and advances
                        # the watermark, preventing an intermediate older revision.
                        observation.latest_batch_id = batch.id
                        observation.data_source = manifest.source_label
                elif previous and manifest.fetched_at <= previous.fetched_at:
                    status, reason = "stale", "Conflicting same/older fetched_at; current value retained"
                else:
                    status = "revised"
            if status in {"inserted", "revised"}:
                if observation is None:
                    observation = MandiObservation(market_id=m.id, commodity_id=c.id, observed_on=observed,
                        variety=normalized["variety"], grade=normalized["grade"], data_kind=manifest.data_kind)
                    session.add(observation)
                for k, v in values.items():
                    setattr(observation, k, v)
                observation.data_source = manifest.source_label
                observation.latest_batch_id = batch.id
                observation.price_unit = "INR/quintal"
                # Missing arrivals stay NULL; this price dataset need not contain arrivals.
                session.flush()
            accepted_dates.add(observed)
            accepted_prices.append(float(normalized["modal"]))
            export.append({**normalized, "data_kind": manifest.data_kind, "source": manifest.source_label,
                           "fetched_at": manifest.fetched_at.isoformat(), "file_sha256": digest, "line_number": line, "disposition": status})
        except LookupError as exc:
            status, reason = "filtered", str(exc)
        except ValueError as exc:
            status, reason = "quarantined", str(exc)
        counts[status] += 1
        ledger = ImportRow(batch_id=batch.id, line_number=line, observation_id=observation.id if observation else None,
                           status=status, reason=reason, raw=raw, normalized=normalized)
        session.add(ledger)
        if status in {"quarantined", "stale"}:
            quarantine.append({"line_number": line, "status": status, "reason": reason, "raw": raw})
    lower = start or (min(accepted_dates) if accepted_dates else None)
    upper = end or (max(accepted_dates) if accepted_dates else None)
    missing = []
    if lower and upper:
        if (upper - lower).days > 36600:
            raise ValueError("Quality-report date window exceeds 100 years")
        missing = [(lower + timedelta(days=i)).isoformat() for i in range((upper - lower).days + 1) if lower + timedelta(days=i) not in accepted_dates]
    distribution = pd.Series(accepted_prices, dtype=float).describe(percentiles=[.25, .5, .75]).dropna().to_dict()
    report = {"batch_id": batch.id, "counts": counts, "data_kind": manifest.data_kind,
              "source": manifest.source_label, "source_url": manifest.source_url, "file_sha256": digest,
              "fetched_at": manifest.fetched_at.isoformat(), "generated_at": datetime.now(UTC).isoformat(),
              "date_range": [min(accepted_dates).isoformat(), max(accepted_dates).isoformat()] if accepted_dates else None,
              "missing_calendar_dates": missing, "missing_days_count": len(missing),
              "missing_days_note": "Unreported dates, not proof of data loss; no rows imputed. Union across varieties/grades.",
              "modal_price_distribution_inr_per_quintal": distribution,
              "distribution_basis": "validated in-scope input rows including duplicates/stale, not unique current observations",
              "report_age_days": (datetime.now(UTC).date() - max(accepted_dates)).days if accepted_dates else None,
              "provenance_verification": "Local file provenance asserted by operator manifest; not independently network-authenticated"}
    # Batch-specific output prevents unrelated imports overwriting one another.
    folder = output / f"batch-{batch.id}"
    folder.mkdir(exist_ok=False)
    (folder / "quarantine.json").write_text(json.dumps(quarantine, indent=2), encoding="utf-8")
    pd.DataFrame(export, columns=["state", "district", "market", "commodity", "report_date", "variety", "grade", "min", "modal", "max", "price_unit", "raw_unit", "data_kind", "source", "fetched_at", "file_sha256", "line_number", "disposition"]).to_csv(folder / "validated_input.csv", index=False)
    # A separate snapshot exports deduplicated current values, never revisions as extra observations.
    current = session.execute(select(MandiObservation, Market, Commodity).join(Market, MandiObservation.market_id == Market.id).join(Commodity, MandiObservation.commodity_id == Commodity.id).where(MandiObservation.data_kind == manifest.data_kind, Market.name == "Kolar APMC", Market.state == "Karnataka", Market.district == "Kolar", Commodity.name == "Tomato")).all()
    snapshot = []
    for obs, m, c in current:
        if (start and obs.observed_on < start) or (end and obs.observed_on > end):
            continue
        source = session.get(ImportBatch, obs.latest_batch_id)
        snapshot.append({"date": obs.observed_on.isoformat(), "state": m.state, "district": m.district, "market": m.name, "commodity": c.name, "variety": obs.variety, "grade": obs.grade,
            "min_price_inr_per_quintal": str(obs.min_price_inr_per_quintal), "modal_price_inr_per_quintal": str(obs.modal_price_inr_per_quintal), "max_price_inr_per_quintal": str(obs.max_price_inr_per_quintal),
            "data_kind": obs.data_kind, "source": obs.data_source, "source_url": source.source_url, "fetched_at": source.fetched_at.isoformat(), "file_sha256": source.file_sha256})
    pd.DataFrame(sorted(snapshot, key=lambda x: (x["date"], x["variety"], x["grade"])) , columns=["date", "state", "district", "market", "commodity", "variety", "grade", "min_price_inr_per_quintal", "modal_price_inr_per_quintal", "max_price_inr_per_quintal", "data_kind", "source", "source_url", "fetched_at", "file_sha256"]).to_csv(folder / "prices.csv", index=False)
    report["current_snapshot_records"] = len(snapshot)
    report["current_snapshot_modal_distribution_inr_per_quintal"] = pd.Series([float(x["modal_price_inr_per_quintal"]) for x in snapshot], dtype=float).describe().dropna().to_dict()
    report["output_directory"] = str(folder.resolve())
    # JSON mutations must be reassigned so SQLAlchemy persists the final report.
    batch.report = dict(report)
    (folder / "quality.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    return report
