"""Reject overlapping final-test reuse, including changed interval boundaries."""
import json
from datetime import date, timedelta


def assert_untouched(registry, plan, horizon):
    start,end=plan.validation_end+timedelta(days=1),plan.holdout_end
    scope=tuple(getattr(plan,k) for k in ("market","commodity","variety","grade"))
    if not registry.is_dir():
        return
    for path in registry.glob("*.json"):
        record=json.loads(path.read_text())
        if "key" in record:
            key=record["key"]
            previous_scope=tuple(key[k] for k in ("market","commodity","variety","grade"))
            previous_horizon=key["horizon"]
            previous_start=date.fromisoformat(key["holdout_start"])
            previous_end=date.fromisoformat(key["holdout_end"])
        else:
            run_name=record.get("run") or record.get("model_version")
            if not run_name:
                raise ValueError("Final holdout audit is incomplete; refusing evaluation")
            run=(registry.parent/run_name).resolve()
            if not run.is_relative_to(registry.parent.resolve()):
                raise ValueError("Invalid final holdout audit path")
            report=json.loads((run/"comparison.json").read_text())
            previous=record.get("plan",report["plan"])
            previous_scope=tuple(previous[k] for k in ("market","commodity","variety","grade"))
            previous_horizon=(record.get("result") or {}).get("horizon")
            # A reserved incomplete run conservatively protects every horizon.
            previous_start=date.fromisoformat(previous["validation_end"])+timedelta(days=1)
            previous_end=date.fromisoformat(previous["holdout_end"])
        if previous_scope==scope and previous_horizon in (None,horizon) and max(start,previous_start)<=min(end,previous_end):
            raise ValueError("Final holdout already reserved/evaluated; overlapping date boundaries cannot grant another final test")
