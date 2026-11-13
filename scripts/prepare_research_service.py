"""Refit frozen selected configurations on verified history, without reopening model selection.

Previously consumed final holdouts remain consumed. Their original scores stay
unchanged. Separate interval diagnostics below are labeled secondary analysis.
"""
import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from app.db import SessionLocal
from app.features import Plan
from app.forecasting import examples, fit, save_champion
from app.research import LIMITATION, snapshot


def calibration(folder, horizon, candidate):
    path = folder / f"final-predictions-{horizon}d.csv"
    if candidate not in {"naive", "mean_14", "median_14", "blend_naive_mean14_25", "blend_naive_mean14_50"} or not path.is_file():
        return {"radii": {}, "reason": "No calibration transfers to a refitted learned model"}
    rows = pd.read_csv(path).sort_values("origin_date")
    split = len(rows)//2
    first, later = rows.iloc[:split], rows.iloc[split:]
    # Embargo target overlap between calibration and diagnostic periods.
    if len(first):
        later = later[later.origin_date > first.target_date.max()]
    if len(first) < 25 or len(later) < 15:
        return {"radii": {}, "reason": "Insufficient separated calibration/diagnostic observations"}
    errors = np.abs(first.prediction_inr_per_quintal-first.target_modal_price_inr_per_quintal)
    blocks = ((pd.to_datetime(first.origin_date)-pd.to_datetime(first.origin_date).min()).dt.days//7)
    maxima = errors.groupby(blocks).max()
    if len(maxima) < 4:
        return {"radii": {}, "reason": "Insufficient chronological blocks"}
    radii = {str(level): float(np.quantile(maxima,level,method="higher")) for level in (.8,.9)}
    coverage = {}
    for level, radius in radii.items():
        lower = (later.prediction_inr_per_quintal-radius).clip(lower=0)
        upper = later.prediction_inr_per_quintal+radius
        coverage[level] = {"coverage": float(((later.target_modal_price_inr_per_quintal >= lower)&(later.target_modal_price_inr_per_quintal <= upper)).mean()),
            "mean_width_inr_per_quintal": float((upper-lower).mean()), "n": len(later)}
    return {"radii": radii, "calibration_n": len(first), "calibration_blocks": len(maxima), "diagnostic_n": len(later),
        "calibration_end": first.target_date.max(), "diagnostic_start": later.origin_date.min(), "later_subset_coverage": coverage,
        "limitations": "Secondary retrospective analysis of previously reported holdout predictions; not a new untouched final test. Frozen stateless baseline rule only. No coverage guarantee or live-vintage validation."}


def main():
    registry = json.loads(Path("research-registry.json").read_text(encoding="utf-8-sig"))
    serving = []
    serving_registry=Path('research-serving-registry.json')
    if serving_registry.is_file():
        # Preserve separately frozen daily extensions when refitting old studies.
        # Every retained entry must still pass the service's integrity checks.
        from app.config import get_settings
        from app.research_service import bundles
        settings=get_settings()
        if settings.enable_research_forecasts and settings.research_serving_registry_path:
            extensions={folder.resolve() for folder,meta in bundles() if meta.get('horizon_evidence_status')}
            serving=[entry for entry in json.loads(serving_registry.read_text(encoding='utf-8-sig')) if Path(entry['directory']).resolve() in extensions]
        else:
            # A disabled service must not silently erase independently saved models.
            for entry in json.loads(serving_registry.read_text(encoding='utf-8-sig')):
                folder=Path(entry['directory'])
                raw=(folder/'metadata.json').read_bytes()
                if hashlib.sha256(raw).hexdigest()!=entry['metadata_sha256']:
                    raise ValueError('Existing serving metadata integrity failure')
                if json.loads(raw).get('horizon_evidence_status'):
                    serving.append(entry)
    for entry in registry:
        selected = Path(entry["directory"])
        report_bytes = (selected/"comparison.json").read_bytes()
        digest = hashlib.sha256(report_bytes).hexdigest()
        if digest != entry["comparison_sha256"]:
            raise ValueError("Frozen report integrity failure")
        report = json.loads(report_bytes)
        raw = dict(report["plan"])
        for name in ("start","train_end","validation_end","holdout_end"):
            raw[name] = date.fromisoformat(raw[name])
        original = Plan(**raw)
        today = datetime.now(UTC).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).date()
        plan = replace(original, validation_end=today-timedelta(days=1),holdout_end=today)
        with SessionLocal() as session:
            vintages, sources = snapshot(session, plan)
        fingerprint = hashlib.sha256(vintages.to_csv(index=False).encode()).hexdigest()
        for comparison in report["horizons"]:
            if not comparison.get("champion"):
                continue
            horizon = comparison["horizon"]
            frame = examples(vintages, plan.start, plan.validation_end, horizon, today)
            if len(frame) < 30:
                print("INSUFFICIENT",original.market,original.commodity,horizon,len(frame))
                continue
            identity = hashlib.sha256((digest+fingerprint+str(horizon)).encode()).hexdigest()[:16]
            folder = Path("models/research-serving")/identity/f"champion-{horizon}d"
            if not (folder/"metadata.json").is_file():
                model = fit(comparison["champion"], frame)
                meta = save_champion(folder, comparison, model, frame, plan, fingerprint)
                meta.update(research_only=True,limitations=LIMITATION,trained_before=datetime.now(UTC).isoformat(),
                    selection_report=(selected/"comparison.json").as_posix(),selection_report_sha256=digest,
                    refit_policy="Frozen selected configuration; all eligible current snapshot rows. No retuning or new final evaluation.",
                    empirical_calibration=calibration(selected,horizon,comparison["champion"]),source=sources)
                (folder/"metadata.json").write_text(json.dumps(meta,indent=2,allow_nan=False),encoding="utf-8")
                feature_meta={"plan":plan.serializable(),"artifact_sha256":{}}
                (folder/"metadata-plan.json").write_text(json.dumps(feature_meta,indent=2))
            metadata = (folder/"metadata.json").read_bytes()
            serving.append({"directory":folder.as_posix(),"metadata_sha256":hashlib.sha256(metadata).hexdigest()})
            print("REFIT",original.market,original.commodity,original.variety,original.grade,f"{horizon}d",comparison["champion"],f"samples={len(frame)}",folder,flush=True)
    Path("research-serving-registry.json").write_text(json.dumps(serving,indent=2),encoding="utf-8")
    print("All artifacts remain RESEARCH ONLY / LIMITED EVIDENCE; original final metrics unchanged")

if __name__ == "__main__":
    main()
