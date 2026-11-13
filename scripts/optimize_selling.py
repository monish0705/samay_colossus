"""Evaluate an explicit scenario file; this does not fetch prices or create forecasts."""
import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from app.selling import optimize_selling


def decimal_json(value):
    if isinstance(value, Decimal):
        return str(value)
    raise TypeError(f"Not serializable: {type(value).__name__}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = optimize_selling(json.loads(args.input.read_text(encoding="utf-8-sig"), parse_float=Decimal))
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, default=decimal_json), encoding="utf-8")
        selected = result["recommended_plan"]
        summary = {"status": result["status"], "recommendation_basis": result["recommendation_basis"],
                   "cash_requirement_achievable_on_grid": result["cash_requirement_achievable_on_grid"],
                   "sell_today_quintals": selected["sell_today_quintals"] if selected else None,
                   "hold_quintals": selected["hold_initial_quintals"] if selected else None,
                   "cash_today_inr": selected["cash_today_inr"] if selected else None,
                   "feasible_grid_plans": len(result["feasible_plans"])}
        print(json.dumps(summary, indent=2, default=decimal_json))
        return 0 if selected else 2
    except (ValueError, OSError) as exc:
        print(f"SELLING PLAN FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
