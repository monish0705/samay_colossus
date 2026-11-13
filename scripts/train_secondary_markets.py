"""Predeclared chronological studies for four verified secondary historical series.

Varieties are selected by observed coverage, not final price outcomes. Grade
absence remains unspecified. Never reuse final outcomes to tune these studies.
"""
import argparse
import hashlib
import json
from datetime import date
from pathlib import Path

from app.db import SessionLocal
from app.features import Plan
from app.research import run

SCOPES = {
    "Copra":("Tiptur APMC","copra",date(2025,6,19),.5),
    "Arecanut":("Shivamogga Mandi","bette",date(2025,10,17),.5),
    "Onion":("Hubballi APMC","local",date(2025,10,25),.35),
    "Potato":("Bengaluru APMC","local",date(2025,2,21),.5),
}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commodity",choices=list(SCOPES),required=True)
    parser.add_argument("--register",action="store_true",help="Register this frozen research report and pin its dated prediction CSVs")
    args=parser.parse_args()
    market,variety,end,coverage=SCOPES[args.commodity]
    plan=Plan(date(2021,1,1),date(2023,12,31),date(2024,12,31),end,variety,"unspecified",market,args.commodity,
        source_kind="secondary",candidate_suite="relative_v2",min_train_coverage=coverage)
    print("FROZEN_PLAN",json.dumps(plan.serializable()),flush=True)
    print("Onion calendar coverage floor is 35% for this irregular reporting series; sample/span/CV/age checks unchanged. No constant daily frequency assumed.",flush=True)
    saved_entry=Path("reports")/f"{args.commodity.lower()}-research-entry.json"
    if saved_entry.is_file():
        previous=json.loads(saved_entry.read_text())
        folder=Path(previous["directory"])
        content=(folder/"comparison.json").read_bytes()
        if hashlib.sha256(content).hexdigest()!=previous["comparison_sha256"]:
            raise ValueError("Existing frozen report integrity failure")
        report=json.loads(content)
        if report["plan"]!=plan.serializable():
            raise ValueError("Plan changed after final feedback; choose a genuinely new untouched study")
        print("FROZEN_REUSE: existing selection and final metrics; no retuning or second final evaluation",flush=True)
    else:
        with SessionLocal() as session:
            folder,report=run(session,plan,Path("models/research"),evaluate_final=True)
    print("STATUS",report["status"],"REPORT",folder,flush=True)
    for item in (report.get("final_evaluation") or {}).get("results",[]):
        print("FINAL",json.dumps(item),flush=True)
    entry={"directory":folder.as_posix(),"comparison_sha256":hashlib.sha256((folder/"comparison.json").read_bytes()).hexdigest()}
    entry["prediction_sha256"]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.glob("final-predictions-*d.csv")}
    target=Path("reports")/f"{args.commodity.lower()}-research-entry.json"
    target.write_text(json.dumps(entry,indent=2),encoding="utf-8")
    if args.register:
        registry=Path("research-registry.json")
        entries=json.loads(registry.read_text(encoding="utf-8-sig")) if registry.is_file() else []
        entries=[old for old in entries if old["directory"]!=entry["directory"]]+[entry]
        registry.write_text(json.dumps(entries,indent=2),encoding="utf-8")
    return 0 if report["status"]=="selected" else 2

if __name__ == "__main__":
    raise SystemExit(main())
