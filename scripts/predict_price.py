import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[variable] = "1"

from app.db import SessionLocal
from app.forecasting import forecast
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description="Point-in-time SAMAY prediction from a trusted local champion artifact")
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--origin", type=date.fromisoformat, required=True)
    parser.add_argument("--horizon", type=int, choices=[1, 3, 7], required=True)
    parser.add_argument("--market", default="Kolar APMC")
    parser.add_argument("--commodity", default="Tomato")
    parser.add_argument("--variety", required=True)
    parser.add_argument("--grade", required=True)
    args = parser.parse_args()
    try:
        with SessionLocal() as session:
            result = forecast(session, args.model, args.origin, args.horizon, args.market, args.commodity, args.variety, args.grade)
        print(json.dumps(result, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, SQLAlchemyError) as exc:
        print("PREDICTION UNAVAILABLE: " + ("Database unavailable" if isinstance(exc, SQLAlchemyError) else str(exc)), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
