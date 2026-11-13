"""Summarize frozen current-grade experiments without selecting or refitting."""
import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from train_current_crops import SCOPES


def main():
    output = {"generated_at": datetime.now(UTC).isoformat(), "research_only": True, "horizons": [], "source_overlap": []}
    for crop in SCOPES:
        entry = json.loads((Path("reports")/f"current-{crop.lower()}-research-entry.json").read_text(encoding="utf-8"))
        folder = Path(entry["directory"])
        raw = (folder/"comparison.json").read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["comparison_sha256"]:
            raise ValueError("Current-crop report hash mismatch")
        report = json.loads(raw)
        for item in report["horizons"]:
            final = next((f for f in (report.get("final_evaluation") or {}).get("results", []) if f["horizon"] == item["horizon"]), {})
            selected = next((c for c in item["comparisons"] if c["candidate"] == item["champion"]), {})
            output["horizons"].append({"commodity":crop,"market":report["plan"]["market"],"variety":report["plan"]["variety"],"grade":report["plan"]["grade"],
                "horizon":item["horizon"],"selected":item["champion"],"train_n":item["sample_policy"]["effective_train_samples"],
                "validation_n":item["sample_policy"]["effective_validation_samples"],"validation_metrics":selected.get("validation"),
                "final_n":final.get("n",0),"final_status":final.get("status"),"final_metrics":final.get("metrics"),
                "naive_final_metrics":(final.get("baseline_metrics") or {}).get("naive"),"candidate_count":len(item["comparisons"]),
                "learned_model_eligible":item.get("learned_model_eligible"),"comparison_report":(folder/"comparison.json").as_posix(),
                "plan":report["plan"]})
        market,commodity,variety,grade=SCOPES[crop]
        with sqlite3.connect("samay.db") as connection:
            rows=connection.execute("""SELECT a.observed_on,a.modal_price_inr_per_quintal,b.modal_price_inr_per_quintal
                FROM mandi_observations a JOIN mandi_observations b ON a.market_id=b.market_id AND a.commodity_id=b.commodity_id
                    AND a.observed_on=b.observed_on AND a.variety=b.variety AND a.grade=b.grade
                JOIN markets m ON a.market_id=m.id JOIN commodities c ON a.commodity_id=c.id
                WHERE a.data_kind='official' AND b.data_kind='secondary' AND m.name=? AND c.name=? AND a.variety=? AND a.grade=?
                ORDER BY a.observed_on""",(market,commodity,variety,grade)).fetchall()
        output["source_overlap"].append({"commodity":crop,"overlapping_dates":len(rows),"matching_modal_prices":sum(a==b for _,a,b in rows),
            "different_modal_prices":[{"report_date":d,"official":a,"secondary":b} for d,a,b in rows if a!=b],
            "policy":"Latest actual fetched vintage per identical series/date; original source rows retained. Cross-source changes are not assumed to be verified original publication vintages."})
    path=Path("reports/current-crop-models.json")
    path.write_text(json.dumps(output,indent=2,allow_nan=False),encoding="utf-8")
    lines=["# Current APMC crop model results — 5 November 2026","", "Frozen chronological study; retrospective snapshot research, not prospectively validated accuracy.","",
        "| Crop / variety / grade | Days | Selected | Train / validation / final n | Candidate count | Validation MAE | Final MAE | Final naive MAE | Final WAPE error % |",
        "|---|---:|---|---|---:|---:|---:|---:|---:|"]
    def fmt(value):
        return f"{value:.2f}" if value is not None else "insufficient final evidence"
    for row in output["horizons"]:
        m=row["final_metrics"] or {}
        n=row["naive_final_metrics"] or {}
        v=row["validation_metrics"] or {}
        lines.append(f"| {row['commodity']} / {row['variety']} / {row['grade']} | {row['horizon']} | {row['selected']} | {row['train_n']} / {row['validation_n']} / {row['final_n']} | {row['candidate_count']} | {fmt(v.get('mae_inr_per_quintal'))} | {fmt(m.get('mae_inr_per_quintal'))} | {fmt(n.get('mae_inr_per_quintal'))} | {fmt(m.get('wape_pct'))} |")
    lines += ["", "MAE and RMSE use INR/quintal. WAPE is error, not an accuracy score. Final metrics require >=30 examples; sparse final sets retain their counts without a reliable final score.",
        "", "All selected configurations remain baselines. Some final errors exceed naive; frozen selections were not changed after testing.",
        "", "Current-grade source overlap checks (identical variety and grade only):"]
    for row in output["source_overlap"]:
        lines.append(f"- {row['commodity']}: {row['overlapping_dates']} overlapping dates, {row['matching_modal_prices']} matching modal prices, {len(row['different_modal_prices'])} differences retained in JSON.")
    path.with_suffix(".md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("REPORT",path.with_suffix(".md"))
    print(path.with_suffix(".md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
