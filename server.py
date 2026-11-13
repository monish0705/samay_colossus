"""Vercel entry point for the bundled SAMAY research demo."""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from starlette.middleware.gzip import GZipMiddleware

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))
os.chdir(ROOT)

from app.prepared_data import restore  # noqa: E402

runtime = TemporaryDirectory(prefix="samay-vercel-")
database = Path(runtime.name) / "samay.db"
bundle = ROOT / "data" / "prepared"
restore(bundle / "samay.db", bundle / "manifest.json", database)
if os.getenv('SAMAY_PERSISTENT_DATABASE_URL'):
    os.environ['SAMAY_DATABASE_URL'] = os.environ['SAMAY_PERSISTENT_DATABASE_URL']
else:
    os.environ["SAMAY_DATABASE_URL"] = f"sqlite:///{database.as_posix()}"
    # A per-instance temporary database cannot preserve bookings or user accounts.
    os.environ['SAMAY_MARKETPLACE_ENABLED'] = 'false'
os.environ["SAMAY_ENVIRONMENT"] = "production"

# Upgrade the writable runtime copy before importing services that use new fields.
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

command.upgrade(Config(str(ROOT / "backend" / "alembic.ini")), "head")

from app.db import engine  # noqa: E402
from app.db_migration import upgrade_database  # noqa: E402
from app.main import app as api  # noqa: E402

upgrade_database()


@asynccontextmanager
async def lifespan(application):
    try:
        async with api.router.lifespan_context(api):
            yield
    finally:
        engine.dispose()


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)


@app.middleware("http")
async def buffer_recommendation(request: Request, call_next):
    response = await call_next(request)
    if request.url.path != "/backend/api/v1/recommend":
        return response
    # The recommendation is one JSON document. Send its compressed bytes with a
    # known length so the client does not wait for a streamed response to close.
    content = b"".join([chunk async for chunk in response.body_iterator])
    headers = dict(response.headers)
    headers["content-length"] = str(len(content))
    return Response(content, status_code=response.status_code, headers=headers)


app.mount("/backend", api)


@app.get("/{page}", include_in_schema=False)
def farmer_page(page: str):
    if page in {"advisor", "forecast", "insights", "results", "explorer", "transparency"}:
        return FileResponse(ROOT / "frontend" / "dist" / "index.html", headers={"Cache-Control": "no-store"})
    from fastapi import HTTPException
    raise HTTPException(status_code=404)


app.frontend("/", directory=ROOT / "frontend" / "dist", fallback="index.html")
