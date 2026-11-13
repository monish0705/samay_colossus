"""Export the real backend contract for frontend type generation, without a running server."""
import json

from app.config import ROOT
from app.main import app

if __name__ == "__main__":
    path = ROOT / "frontend" / "openapi.json"
    path.write_text(json.dumps(app.openapi(), indent=2), encoding="utf-8", newline="\n")
    print(f"Exported {len(app.openapi()['paths'])} API paths")
