import json
import logging
import os
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api_routes import router as api_router
from app.api_services import ServiceProblem
from app.config import get_settings
from app.prices import router as prices_router
from app.sale_routes import router as sale_router
from app.business_routes import router as business_router
from app.purchase_routes import router as purchase_router


@asynccontextmanager
async def lifespan(application):
    if os.getenv("SAMAY_ENVIRONMENT", get_settings().environment) != "test":
        from pathlib import Path

        from sqlalchemy import inspect
        from sqlalchemy.engine import make_url

        from app.db import engine
        from app.provenance_repair import repair

        url = make_url(get_settings().database_url)
        if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:" and inspect(engine).has_table("import_batches"):
            corrected = repair(Path(url.database))
            if corrected["corrected_observations"]:
                logging.getLogger("samay.api").warning(json.dumps({"event":"legacy_synthetic_data_reclassified", **corrected}))
        from app.readiness import check
        result = check()
        application.state.readiness = result
        logging.getLogger("samay.api").warning(json.dumps({"event": "startup_readiness", "database": result["database"], "forecast_demo_ready": result["ready_for_authentic_forecast_demo"], "research_artifacts_configured":result.get('research_artifacts_configured',0), "issues": result["issues"]}))
    else:
        application.state.readiness = {"database": "test", "ready_for_authentic_forecast_demo": False, "issues": []}
    yield


app = FastAPI(title="SAMAY API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT"], allow_headers=["Content-Type", "X-Request-ID", "X-SAMAY-Action", "Idempotency-Key"], expose_headers=["X-Request-ID"])
logger = logging.getLogger("samay.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def error(request, status, code, message, details=None):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "request_id": request.state.request_id, "details": details or {}}})


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = time.monotonic()
    try:
        result = await call_next(request)
    except Exception as exc:
        logger.error(json.dumps({"event": "unhandled_error", "request_id": request.state.request_id, "exception_type": type(exc).__name__}))
        result = error(request, 500, "internal_error", "Unexpected server error")
        origin = request.headers.get("origin")
        if origin in get_settings().cors_origins:
            result.headers["Access-Control-Allow-Origin"] = origin
            result.headers["Access-Control-Expose-Headers"] = "X-Request-ID"
            result.headers["Vary"] = "Origin"
    result.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith(('/api/v1/auth', '/api/v1/sale-', '/api/v1/mandi/', '/api/v1/admin/', '/api/v1/notification')):
        result.headers['Cache-Control'] = 'private, no-store'
    if request.url.path.startswith(('/api/v1/business', '/api/v1/private-purchases')):
        result.headers['Cache-Control'] = 'private, no-store'
    logger.info(json.dumps({"event": "http_request", "request_id": request.state.request_id,
        "method": request.method, "route": getattr(request.scope.get("route"), "path", "unmatched"),
        "status": result.status_code, "duration_ms": round((time.monotonic() - start) * 1000, 2)}))
    return result


@app.exception_handler(ServiceProblem)
async def service_error(request, exc):
    return error(request, exc.status, exc.code, exc.message)


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    logger.warning(json.dumps({"event": "database_unavailable", "request_id": request.state.request_id}))
    return error(request, 503, "database_unavailable", "Database unavailable; verify configuration and migrations")


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    fields = []
    messages = []
    for e in exc.errors():
        field_parts = [str(x) for x in e["loc"] if x != "body"]
        field_name = ".".join(field_parts)
        msg = e.get("msg", "Invalid value")
        # Strip "Value error, " prefix if added by Pydantic
        if msg.startswith("Value error, "):
            msg = msg[len("Value error, "):]
        if field_name:
            messages.append(f"{field_name}: {msg}")
        else:
            messages.append(msg)
        fields.append({"field": field_name, "message": msg, "location": list(e["loc"]), "type": e["type"]})
    user_message = "; ".join(messages) if messages else "Request validation failed"
    return error(request, 422, "invalid_request", user_message, {"fields": fields})


@app.exception_handler(StarletteHTTPException)
async def http_error(request, exc):
    return error(request, exc.status_code, "invalid_request" if exc.status_code == 422 else "http_error", str(exc.detail))


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/api/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Process liveness; database migrations are an explicit deployment step."""
    return HealthResponse(status="ok", service="samay", version="0.1.0")


app.include_router(prices_router)
app.include_router(api_router)
app.include_router(sale_router)
app.include_router(business_router)
app.include_router(purchase_router)
