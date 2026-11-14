"""Vercel Serverless Function entry point."""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

backend_path = ROOT / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

try:
    from server import app  # noqa: E402, F401
except Exception as exc:
    import traceback
    error_trace = traceback.format_exc()
    logging.error(f"Critical error loading server.app: {error_trace}")

    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI(title="SAMAY Recovery")

    @app.api_route("/{rest_of_path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
    async def startup_error(rest_of_path: str = ""):
        return HTMLResponse(
            f"""<!DOCTYPE html>
            <html>
            <head><title>SAMAY - Startup Diagnostic</title></head>
            <body style="font-family:system-ui,-apple-system,sans-serif;padding:2rem;background:#f8fafc;color:#1e293b;line-height:1.6;">
              <h2 style="color:#0f766e;">SAMAY Server Diagnostic</h2>
              <p>A startup exception occurred during serverless function initialization:</p>
              <pre style="background:#f1f5f9;padding:1rem;border-radius:8px;overflow-x:auto;border:1px solid #cbd5e1;font-size:13px;color:#334155;">{error_trace}</pre>
            </body>
            </html>""",
            status_code=500
        )
