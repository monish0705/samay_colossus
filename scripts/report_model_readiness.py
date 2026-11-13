"""Recompute frozen test metrics from dated predictions; do not retune models."""
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from app.forecasting import metrics


def main():
    result = {"created_at": datetime.now(UTC).isoformat(), "mode": "retrospective_research_only", "evaluations": [], "refits": [], "data": []}
    for entry in json.loads(Path("research-registry.json").read_text(encoding="utf-8-sig")):
        folder = Path(entry["directory"])
        raw = (folder / "comparison.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["comparison_sha256"]:
            raise ValueError("Frozen report hash mismatch")
        report = json.loads(raw)
        for final in report["final_evaluation"]["results"]:
            if not final.get("metrics"):
                result["evaluations"].append({"scope":{key:report["plan"][key] for key in ("market","commodity","variety","grade")}, "horizon":final["horizon"], "selected":final["champion"], "status":final["status"], "final_n":final["n"], "source_kind":report["plan"].get("source_kind","official"), "final_metrics":None, "naive_same_timestamps":None, "original_report":(folder/"comparison.json").as_posix()})
                continue
            rows = pd.read_csv(folder / f"final-predictions-{final['horizon']}d.csv")
            computed = metrics(rows.target_modal_price_inr_per_quintal, rows.prediction_inr_per_quintal, rows.lag_1_obs_inr_per_quintal)
            for key, expected in final["metrics"].items():
                if expected is not None and not np.isclose(computed[key],expected):
                    raise ValueError(f"Metric reproduction failed: {key}")
            naive = metrics(rows.target_modal_price_inr_per_quintal, rows.lag_1_obs_inr_per_quintal, rows.lag_1_obs_inr_per_quintal)
            item = {"scope": {key:report["plan"][key] for key in ("market","commodity","variety","grade")}, "horizon":final["horizon"], "selected":final["champion"],
                "final_metrics":computed, "naive_same_timestamps":naive,"status":final["status"],"final_n":final["n"],"source_kind":report["plan"].get("source_kind","official"),"original_report":(folder/"comparison.json").as_posix(),
                "interpretation":"Original consumed chronological holdout; metrics recomputed for integrity, not a new independent evaluation or tuning opportunity"}
            result["evaluations"].append(item)
    for entry in json.loads(Path("research-serving-registry.json").read_text()):
        meta = json.loads((Path(entry["directory"])/"metadata.json").read_text())
        result["refits"].append({key:meta[key] for key in ("version","candidate","horizon","market","commodity","variety","grade","training_samples","training_window","dataset_fingerprint","trained_before","empirical_calibration")})
    with sqlite3.connect("data/prepared/samay.db") as connection:
        rows=connection.execute("SELECT m.name,c.name,o.variety,o.grade,o.data_kind,count(*),min(o.observed_on),max(o.observed_on) FROM mandi_observations o JOIN markets m ON m.id=o.market_id JOIN commodities c ON c.id=o.commodity_id WHERE o.data_kind IN ('official','secondary') GROUP BY m.name,c.name,o.variety,o.grade,o.data_kind").fetchall()
        result["data"]=[dict(zip(("market","commodity","variety","grade","source_kind","n","first_date","last_date"),row,strict=True)) for row in rows]
    captures=sorted(Path("data/raw/official-multi-recent").glob("*/manifest.json"))
    if captures:
        result["recent_collection"] = json.loads(captures[-1].read_text())
    result["limitations"] = ["Four additional crops were trained on separately labeled India Data Portal secondary history. Their dated series are stale for current-day forecasting; no live prediction is invented.",
        "Original publication/revision vintages are unverified. All serving artifacts remain research only, limited evidence.",
        "Consumed test metrics are unchanged; current refits are not newly tested models. Do not describe 100 minus WAPE as accuracy.",
        "Intervals are secondary retrospective block-residual diagnostics for the same stateless baseline rules, not guaranteed coverage.",
        "Some selected baselines lose to naive on final observations; these results are retained without post-holdout reselection.", "Potato 3d/7d have fewer than 30 final examples; no final metric is claimed. Unspecified grades were not inferred or merged with graded data."]
    target=Path("reports/corrected-model-readiness.json")
    target.write_text(json.dumps(result,indent=2,allow_nan=False),encoding="utf-8")
    lines=["# SAMAY corrected data and model report", "", "All forecasts are retrospective research / limited evidence. This report reproduces original frozen results; it does not reopen final model selection.", "",
        "| Crop / variety / grade | Source | Horizon | Selected | Final n | MAE INR/quintal | Naive MAE | RMSE INR/quintal | WAPE % |", "|---|---|---:|---|---:|---:|---:|---:|---:|"]
    for row in result["evaluations"]:
        m=row["final_metrics"]
        scope=row["scope"]
        prefix=f"| {scope['commodity']} / {scope['variety']} / {scope['grade']} | {row['source_kind']} | {row['horizon']}d | {row['selected']} | {row['final_n']} |"
        if m is None:
            lines.append(prefix+" insufficient final samples | unavailable | unavailable | unavailable |")
        else:
            lines.append(prefix+f" {m['mae_inr_per_quintal']:.2f} | {row['naive_same_timestamps']['mae_inr_per_quintal']:.2f} | {m['rmse_inr_per_quintal']:.2f} | {m['wape_pct']:.2f} |")
    lines += ["", "## Current refits", "", "Configurations were fixed by the original studies; no new tuning against consumed final observations.", ""]
    for row in result["refits"]:
        lines.append(f"- {row['commodity']} / {row['variety']} / {row['grade']} {row['horizon']}d: {row['candidate']}; {row['training_samples']} usable refit samples; version {row['version']}.")
    lines += ["", "## Limitations", ""]+["- "+item for item in result["limitations"]]
    target.with_suffix(".md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("Frozen metrics reproduced for",len(result["evaluations"]),"horizons; saved",len(result["refits"]),"research refits")
    print(target.with_suffix(".md").read_text())

if __name__ == "__main__":
    main()
