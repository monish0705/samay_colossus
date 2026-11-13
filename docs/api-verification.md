# Prompt 7 verification — 2026-11-04

## Files changed

Added backend/app/api_schemas.py, api_services.py and api_routes.py;
backend/alembic/versions/cee3e9392b8d_anonymous_recommendation_history.py;
tests/test_api_integration.py; docs/api.md; docs/examples/api-recommend.example.json;
docs/examples/service-registry.example.json and this verification record.
Updated backend/app/main.py, prices.py, models.py and config.py; .env.example;
tests/test_backend.py and README.md. No frontend implementation changed.

## Executed commands and outputs

PowerShell from repository root:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini revision --autogenerate -m anonymous_recommendation_history
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Generated and reviewed migration cee3e9392b8d. Upgrade exited 0. Schema check:
`No new upgrade operations detected.` Existing tables were preserved.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_integration.py -q
```

```text
5 passed, 1 warning in 4.12s
```

The integration flow imports two captured CSV snapshots into isolated temporary
SQLite, reconstructs causal examples and fits a real ridge estimator with the
existing training primitives, saves/loads its artifact through the configured
registry, calls the actual reliability service, calls the actual optimizer and
persists anonymous recommendation outcomes. The fixture is deliberately too small
for a production validation claim; reliability stays limited and confident holding
is blocked. Its metadata is labeled INTEGRATION_TEST_ONLY_NOT_LIVE and never enters
the workspace database or reported real-world forecasting metrics.

Changing the input today quote from INR 1,000 to 1,200 changes net cash from INR
18,700 to 22,500. Raising required cash to INR 50,000 returns 409 with no selected
plan. Other tests cover missing model/horizon, no official data, stale observations,
service failures, invalid client trust assertions, CORS, safe errors, request IDs,
Swagger and persistence failure. A dropped history table produces 503 rather than
a false saved-history claim.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```text
71 passed, 1 warning in 43.77s
```

After final logging/OpenAPI/error-envelope refinements, targeted regression checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_integration.py tests/test_backend.py tests/test_ingestion.py -q
```

```text
22 passed, 1 warning in 6.96s
```

The remaining warning is the existing Starlette TestClient HTTPX deprecation.

From frontend:

```powershell
npm.cmd test
npm.cmd run build
```

Outputs: `Tests 3 passed (3)` and successful TypeScript/Vite production build.

## Actual workspace HTTP smoke checks

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Output: `Application startup complete.` and server listening at 127.0.0.1:8010.
An httpx client exercised all nine required endpoints and Swagger/OpenAPI:

| Request | Actual status and result |
| --- | --- |
| GET /api/health | 200; status ok, service samay, version 0.1.0 |
| GET /api/v1/markets | 200; [] |
| GET /api/v1/commodities | 200; [] |
| GET /api/v1/prices/history | 200; items [], limit 100, offset 0 |
| GET /api/v1/prices/latest?variety=local&grade=faq | 404; no_official_observation |
| POST /api/v1/predict, local/faq horizon 3 | 503; missing_model |
| GET /api/v1/models/status | 200; no_models_deployed |
| GET /api/v1/data/status | 200; unavailable, official 0, fixture 3, demo 0 |
| POST /api/v1/recommend with docs/examples/api-recommend.example.json | 200; persisted today-only fallback |
| GET /docs and /openapi.json | both 200 |

The complete actual recommendation response is saved to
reports/api-recommendation-example.json. Its compact result was:

```json
{
  "history_id": 1,
  "request_id": "f0b7324a-e634-4c99-9126-8851c7a2decb",
  "status": "sell_all_now",
  "cash_today_inr": "18700.00",
  "warnings": [
    "3d:missing_model",
    "no_official_market_observations; today's quote is user supplied"
  ]
}
```

This request used **example economic inputs**, not actual farmer data or live
prices. The returned model list is empty, source report date is null, and the
optimizer labels today_only_safe_fallback. The audit record contains only scope,
decision/request identifiers, numeric outcome, source date/version and warnings.

Equivalent PowerShell request:

```powershell
$samayRequest = Get-Content docs/examples/api-recommend.example.json -Raw
Invoke-RestMethod http://127.0.0.1:8010/api/v1/recommend -Method Post -ContentType 'application/json' -Body $samayRequest | ConvertTo-Json -Depth 30
```

Requests create a new audit ID each time; the ID above records the actual first
smoke invocation, not a hardcoded API response. Final restart smoke checks confirmed
health, Swagger and OpenAPI return 200 with distinct X-Request-ID headers.

```powershell
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Outputs: `No broken requirements found.` and no whitespace errors.

## Acceptance boundary and next handoff

The complete backend request flow is implemented, tested and traceable. An actual
workspace recommendation succeeds through the honest quote-only fallback; isolated
tests demonstrate the imported-history → fitted saved model → reliability → optimizer
path without stubbing domain outputs. No fixture values are returned as default
live market data.

A genuinely calibrated model deployment and validated real-data hold recommendation
remain unavailable because authenticated historical snapshots were never obtained
in earlier stages. No simulated test fit is represented as production validation.
Obtain those sources, run the existing feature/training/backtest workflows, populate
the trusted server registry, and rerun the documented API examples. Client JSON
cannot set validated status or artifact paths. No Prompt 8 work was started.
