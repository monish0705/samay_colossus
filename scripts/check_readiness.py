"""Offline read-only release readiness command."""
import json
import sys

from app.readiness import check

if __name__ == "__main__":
    result = check()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["ready_for_authentic_forecast_demo"] else 2)
