import json
import logging
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


@asynccontextmanager
async def lifespan(application):
    if get_settings().environment != "test":
        from app.readiness import check
        result = check()
        application.state.readiness = result
        logging.getLogger("samay.api").warning(json.dumps({"event": "startup_readiness", "database": result["database"], "forecast_demo_ready": result["ready_for_authentic_forecast_demo"], "issues": result["issues"]}))
    else:
        application.state.readiness = {"database": "test", "ready_for_authentic_forecast_demo": False, "issues": []}
    yield


app = FastAPI(title="SAMAY API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Request-ID"], expose_headers=["X-Request-ID"])
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
    fields = [{"location": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
    return error(request, 422, "invalid_request", "Request validation failed", {"fields": fields})


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
