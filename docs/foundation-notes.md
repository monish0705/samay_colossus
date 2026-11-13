# Historical implementation notes

These notes describe earlier stages. Use README.md and STATUS.md for the release state.

# SAMAY

[Integrated API](api.md) documents all nine FastAPI endpoints, saved-model
deployment configuration, trusted recommendation orchestration, anonymous local
history, error codes and reproducible request examples. Swagger remains at `/docs`.
Current official data/model availability is reported explicitly; fixture data is
never substituted into production forecasts.

[Selling optimization](selling.md) now provides pure Decimal-based cash/risk
planning, crop-specific loss schedules, transaction/storage costs, feasible-grid
comparisons and safe fallbacks for unavailable forecasts. The bundled 20-quintal
example is explicitly illustrative, with scenario-only future prices.

[Reliability and backtesting](reliability.md) now provides chronological
assessment, frozen empirical interval calibration, naive benchmarks and a stable
reliability service. Current official-data counts remain zero; no real coverage
or held-out market examples are claimed.

The forecasting workflow is documented in [forecasting.md](forecasting.md):
rolling-origin comparisons, conservative baseline/ML selection, guarded metrics,
saved champion inference and one-shot final evaluation. With the current absent
official history it explicitly reports insufficient_data and leaves holdout unopened.

The point-in-time analysis/feature pipeline is documented in [features.md](features.md).
It provides 1/3/7-calendar-day targets, causal features, chronological partitions,
sealed final-holdout plans, six chart artifacts and frontend-ready insight JSON.
Current effective training samples are zero because authenticated historical data
was not obtained; fixture observations are excluded.

The CSV mandi ingestion layer is now available. See [ingestion operations and provenance](ingestion.md)
for official download instructions, validation rules, revision lineage, fixture
reproduction, quality reports and `/api/v1/markets` / `/api/v1/prices/history`.
An authentic government historical download remains pending; current examples are
explicit fixtures. The original foundation notes below describe the initial stage.

Agricultural market decision support for **Team Resonance · COLOSSUS 3.0**.
The planned system will help Indian farmers compare selling harvested produce
now versus holding it, understand price uncertainty, and meet immediate cash needs.
This repository implements the engineering foundation. **No ML model is trained,
no live market data is connected, and no accuracy claims are made.**

## Requirements

Windows PowerShell, Git, Python 3.11+ (verified with Python 3.12), and Node.js
22.12+ with npm. All commands below start at the repository root unless stated.
Use `npm.cmd` to avoid PowerShell script execution-policy issues. Python activation
is unnecessary because commands invoke the virtual environment directly.

## First-time setup

```powershell
Set-Location 'C:\Users\Suhan\OneDrive\文件\ChatGPT\agritech\samay-agritech'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
Set-Location frontend
npm.cmd ci
Set-Location ..
```

If installed elsewhere, change only the first `Set-Location` path. Run setup from
the root so the example relative SQLite URL creates `samay.db` there. Without an
`.env`, the default database path is anchored to the repository root. For custom
locations use `SAMAY_DATABASE_URL=sqlite:///C:/absolute/path/samay.db`.

## Run locally

Backend, terminal 1, repository root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, terminal 2, repository root:

```powershell
Set-Location frontend
npm.cmd run dev -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs.
The UI displays loading, connection success, or an error with retry.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

Expected HTTP 200: `{"status":"ok","service":"samay","version":"0.1.0"}`.
This is process liveness, not a database readiness check. `/api/v1` is reserved
in the API router for future endpoints; no forecast endpoint exists yet.

## Tests and production build

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -v
Set-Location frontend
npm.cmd test
npm.cmd run build
npm.cmd audit
Set-Location ..
```

Backend tests apply real Alembic migrations to an isolated temporary SQLite file,
verify all six entity tables, repeat upgrade, exercise downgrade/upgrade, enforce
foreign keys and reject naive timestamps. They also check health and CORS.
Frontend tests cover initial render/loading, successful connection, error/retry,
and unknown routing. The build type-checks TypeScript and bundles to `frontend/dist`.

## Configuration

| Variable | Purpose |
| --- | --- |
| `SAMAY_ENVIRONMENT` | `development`, `test`, or `production` |
| `SAMAY_DATABASE_URL` | SQLAlchemy SQLite URL |
| `SAMAY_CORS_ORIGINS` | JSON array of allowed browser origins |
| `VITE_API_BASE_URL` | Frontend backend origin; restart Vite after changes |

Backend settings are validated by Pydantic and read from root `.env`; environment
variables take precedence. Frontend variables are public build configuration:
never place credentials in a `VITE_` variable. CORS permits only configured origins
and currently GET requests. Extend methods deliberately when adding write APIs.

## Database and optional demo seed

Schema changes are explicit Alembic migrations, never automatic startup DDL.
Tables: `markets`, `commodities`, `mandi_observations`, `model_versions`,
`predictions`, `recommendations`, plus Alembic's version table.

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini current
# Optional synthetic development fixture; safe to repeat:
.\.venv\Scripts\python.exe scripts/seed_demo.py
# After editing entities, generate and review a new migration:
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini revision --autogenerate -m 'describe schema change'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

The seed refuses non-development environments. Its market, commodity, variety,
and provenance are explicitly labeled **DEMO_DATA**. It contains one synthetic
observation and no predictions or recommendations. Never train or evaluate on it.
Alembic downgrade removes data; use only against disposable development databases.

Money fields explicitly use INR, prices INR per quintal, and quantities quintals
(100 kg). Timestamp inputs must be timezone-aware and are returned as aware UTC;
observation and target dates are calendar dates. See [architecture](architecture.md)
for relationships, constraints, SQLite limitations and the next implementation boundary.

## Layout

```text
backend/          FastAPI, typed settings, SQLAlchemy entities, Alembic migrations
frontend/         React, TypeScript, Vite, Tailwind, routing and Vitest
data/raw/         ignored input datasets
data/processed/   ignored derived datasets
models/           ignored model artifacts (none trained)
tests/            pytest integration checks
docs/             architecture and handoff
scripts/          explicit development utilities
```

Datasets, SQLite databases, environment secrets, build products, and large model
artifacts are ignored. The frontend npm lockfile is committed for repeatable
installs. Optional future ML dependencies: `pip install -e './backend[ml]'` using
the virtual environment Python; installing them does not train a model.

Next handoff: define and validate real ingestion contracts, establish chronological
baselines and uncertainty evaluation, then implement versioned decision APIs and
the farmer input workflow. This foundation stops before Prompt 2.
