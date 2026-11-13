"""Read immutable dated historical predictions; never fit or select a model here."""
import csv
import hashlib
import io
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from app.api_services import ServiceProblem
from app.config import ROOT, get_settings
from app.selling import money


def historical_evaluation(scope, horizon):
    registry=get_settings().research_registry_path
    if registry is None:
        raise ServiceProblem(404,"no_research_evaluation","No historical research registry is configured")
    registry=registry if registry.is_absolute() else ROOT/registry
    try:
        for entry in json.loads(registry.read_text(encoding="utf-8-sig")):
            folder=Path(entry["directory"])
            folder=folder if folder.is_absolute() else ROOT/folder
            content=(folder/"comparison.json").read_bytes()
            if hashlib.sha256(content).hexdigest()!=entry["comparison_sha256"]:
                raise ValueError("Historical report integrity failure")
            report=json.loads(content)
            plan=report["plan"]
            if tuple(plan[k] for k in ("market","commodity","variety","grade"))!=scope:
                continue
            if report.get("research_only") is not True:
                raise ValueError("Historical endpoint requires explicit research labeling")
            final=next((x for x in (report.get("final_evaluation") or {}).get("results",[]) if x["horizon"]==horizon),None)
            if final is None:
                raise ServiceProblem(404,"no_research_evaluation","This horizon has no frozen final evaluation")
            points=[]
            filename=f"final-predictions-{horizon}d.csv"
            if final.get("metrics"):
                raw=(folder/filename).read_bytes()
                if hashlib.sha256(raw).hexdigest()!=entry.get("prediction_sha256",{}).get(filename):
                    raise ValueError("Dated prediction integrity failure")
                for row in csv.DictReader(io.StringIO(raw.decode("utf-8-sig"))):
                    actual=money(Decimal(row["target_modal_price_inr_per_quintal"]))
                    prediction=money(Decimal(row["prediction_inr_per_quintal"]))
                    points.append({"origin_date":row["origin_date"],"target_date":row["target_date"],"actual_inr_per_quintal":actual,
                        "prediction_inr_per_quintal":prediction,"absolute_error_inr_per_quintal":abs(actual-prediction)})
                if len(points)!=final["n"]:
                    raise ValueError("Dated prediction count mismatch")
            from datetime import date
            return {"research_only":True,"source_kind":plan.get("source_kind","official"),"scope":dict(zip(("market","commodity","variety","grade"),scope,strict=True)),
                "horizon":horizon,"selected_model":final["champion"],"model_version":report["version"],"status":final["status"],
                "final_n":final["n"],"metrics":final.get("metrics"),"naive_metrics":(final.get("baseline_metrics") or {}).get("naive"),
                "train_end":plan["train_end"],"validation_end":plan["validation_end"],"test_start":(date.fromisoformat(plan["validation_end"])+timedelta(days=1)).isoformat(),
                "test_end":plan["holdout_end"],"source":report["source"],"limitations":report["limitations"],"points":points,"price_unit":"INR/quintal",
                "rounding_note":"Displayed prices/errors are rounded to INR .01; aggregate metrics use the original full-precision frozen predictions. This is historical evaluation, not a current forecast."}
    except (OSError,ValueError,KeyError,TypeError) as exc:
        raise ServiceProblem(503,"evaluation_integrity_failure","Historical evaluation is unavailable or failed its integrity checks") from exc
    raise ServiceProblem(404,"no_research_evaluation","No frozen study matches this exact market, crop, variety and grade")
