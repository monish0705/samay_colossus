"""Vercel entry point for the bundled SAMAY research demo."""

import logging
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from starlette.middleware.gzip import GZipMiddleware

logger = logging.getLogger("samay.server")

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)

from app.prepared_data import restore  # noqa: E402

bundle = ROOT / "data" / "prepared"
if os.getenv("SAMAY_PERSISTENT_DATABASE_URL"):
    os.environ["SAMAY_DATABASE_URL"] = os.environ["SAMAY_PERSISTENT_DATABASE_URL"]
    database = Path("samay.db")
else:
    tmp_base = Path("/tmp") if Path("/tmp").is_dir() else Path(TemporaryDirectory(prefix="samay-vercel-").name)
    database = tmp_base / "samay_runtime.db"
    if not database.exists():
        try:
            restore(bundle / "samay.db", bundle / "manifest.json", database)
        except Exception as e:
            logger.warning(f"Prepared database restoration skipped/failed: {e}")
    os.environ["SAMAY_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"

if "SAMAY_MARKETPLACE_ENABLED" not in os.environ:
    os.environ["SAMAY_MARKETPLACE_ENABLED"] = "true"
os.environ["SAMAY_ENVIRONMENT"] = "production"

# Invalidate any previously cached settings
try:
    from app.config import get_settings  # noqa: E402
    get_settings.cache_clear()
except Exception:
    pass

# Upgrade the writable runtime copy before importing services that use new fields.
try:
    from alembic import command  # noqa: E402
    from alembic.config import Config  # noqa: E402
    alembic_ini = ROOT / "backend" / "alembic.ini"
    if alembic_ini.exists():
        command.upgrade(Config(str(alembic_ini)), "head")
except Exception as e:
    logger.warning(f"Alembic upgrade warning: {e}")

try:
    from app.db import engine  # noqa: E402
    from app.db_migration import upgrade_database  # noqa: E402
    upgrade_database()
except Exception as e:
    logger.warning(f"Database upgrade warning: {e}")

from app.main import app as api  # noqa: E402

try:
    from scripts.seed_three_personas import run as seed_personas  # noqa: E402
    seed_personas(database.as_posix())
except Exception as e:
    logger.warning(f"Persona seeding skipped: {e}")


@asynccontextmanager
async def lifespan(application):
    try:
        async with api.router.lifespan_context(api):
            yield
    finally:
        try:
            from app.db import engine
            engine.dispose()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)


@app.middleware("http")
async def restore_vercel_path(request: Request, call_next):
    # When Vercel rewrites incoming traffic to /api/index.py, restore original URL path
    matched = request.headers.get("x-matched-path") or request.headers.get("x-forwarded-uri")
    if matched and request.url.path in ("/api/index.py", "/api/index", "/api"):
        request.scope["path"] = matched
    return await call_next(request)


@app.middleware("http")
async def buffer_recommendation(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != "/backend/api/v1/recommend":
        return response
    content = b"".join([chunk async for chunk in response.body_iterator])
    headers = dict(response.headers)
    headers["content-length"] = str(len(content))
    return Response(content, status_code=response.status_code, headers=headers)


app.mount("/backend", api)

dist_dir = ROOT / "frontend" / "dist"
if not dist_dir.is_dir():
    dist_dir = ROOT / "dist"

SPA_ROUTES = {
    "advisor", "forecast", "insights", "results", "explorer", "transparency",
    "business", "sale-requests", "private-rates", "mandi"
}


@app.get("/health", include_in_schema=False)
@app.get("/api/health", include_in_schema=False)
def health_status():
    return {"status": "ok", "environment": os.getenv("SAMAY_ENVIRONMENT", "production")}


@app.get("/", include_in_schema=False)
@app.get("/api/index.py", include_in_schema=False)
@app.get("/api/index", include_in_schema=False)
@app.get("/api", include_in_schema=False)
def root_index():
    index_file = dist_dir / "index.html"
    if index_file.is_file():
        return FileResponse(index_file, headers={"Cache-Control": "no-store"})
    return Response("<h1>SAMAY Agricultural Market Intelligence</h1>", media_type="text/html")


@app.get("/{page}", include_in_schema=False)
def farmer_page(page: str):
    file_path = dist_dir / page
    if file_path.is_file():
        return FileResponse(file_path)
    if page in SPA_ROUTES or "." not in page:
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file, headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404)


@app.get("/{first_part}/{rest_of_path:path}", include_in_schema=False)
def nested_spa_page(first_part: str, rest_of_path: str):
    full_path = f"{first_part}/{rest_of_path}"
    file_path = dist_dir / full_path
    if file_path.is_file():
        return FileResponse(file_path)
    if first_part in ("api", "backend") and rest_of_path.startswith("index"):
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file, headers={"Cache-Control": "no-store"})
    if first_part in SPA_ROUTES or "." not in rest_of_path.split("/")[-1]:
        index_file = dist_dir / "index.html"
        if index_file.is_file():
            return FileResponse(index_file, headers={"Cache-Control": "no-store"})
    raise HTTPException(status_code=404)


if dist_dir.is_dir():
    try:
        app.frontend("/", directory=dist_dir, fallback="index.html")
    except Exception as e:
        logger.warning(f"FastAPI app.frontend mounting notice: {e}")
