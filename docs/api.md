# Integrated SAMAY backend — Prompt 7

All nine required endpoints are implemented in one FastAPI app. HTTP handlers
delegate predictions/reliability to the existing saved-artifact services and
economic decisions to optimize_selling. They do not implement another forecast,
confidence score, spoilage model or optimization objective.

## Start and exercise the backend (Windows PowerShell)

From repository root:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,analysis,forecast]'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Swagger: http://127.0.0.1:8000/docs. OpenAPI: http://127.0.0.1:8000/openapi.json.
For the verification session a separate server uses port 8010, avoiding earlier
development servers on other ports. Restart an existing server after changes.

```powershell
$samayBase = 'http://127.0.0.1:8000'
Invoke-RestMethod "$samayBase/api/health"
Invoke-RestMethod "$samayBase/api/v1/markets"
Invoke-RestMethod "$samayBase/api/v1/commodities"
Invoke-RestMethod "$samayBase/api/v1/prices/history?market=Kolar%20APMC&commodity=Tomato&variety=local&grade=faq"
Invoke-RestMethod "$samayBase/api/v1/data/status"
Invoke-RestMethod "$samayBase/api/v1/models/status"
$samayExample = Get-Content docs/examples/api-recommend.example.json -Raw
Invoke-RestMethod "$samayBase/api/v1/recommend" -Method Post -ContentType 'application/json' -Body $samayExample | ConvertTo-Json -Depth 30
```

The example is explicitly illustrative. It uses a farmer-entered INR 1,000/quintal
quote, 20 quintals and INR 10,000 required cash, with disclosed example costs and
loss schedules. It does not claim real market prices or a trained forecast.
Unlike the standalone optimizer example, API inputs contain no future-price
triplet or user-set reliability status: those must come from the trusted service.

Prediction request (returns 503 when no actual saved model is deployed):

```powershell
$samayPredict = '{"market":"Kolar APMC","commodity":"Tomato","variety":"local","grade":"faq","horizon":3}'
Invoke-RestMethod "$samayBase/api/v1/predict" -Method Post -ContentType 'application/json' -Body $samayPredict
```

## Endpoint contracts

| Endpoint | Result |
| --- | --- |
| GET /api/health | Process liveness, unchanged 200 contract; not database readiness |
| GET /api/v1/markets | Markets with stored observations, official by default |
| GET /api/v1/commodities | Commodities with official observations |
| GET /api/v1/prices/history | Paginated dated wholesale observations, source, fetch time, market/commodity IDs, variety/grade and explicit units |
| GET /api/v1/prices/latest | Latest stored official observation for required variety/grade, with age/stale flag; not a live buyer quote |
| POST /api/v1/predict | Saved model + point-in-time official input + empirical reliability service |
| POST /api/v1/recommend | Saved prediction service per supported holding horizon, scenario bridge, optimizer, anonymous audit persistence |
| GET /api/v1/models/status | Deployed scope/horizon versions, training cutoff, source fingerprint and artifact/evidence configuration status |
| GET /api/v1/data/status | Separate official/fixture/demo counts, official report/fetch freshness and provenance limits |

PredictRequest includes market, commodity, variety, grade, integer horizon 1/3/7
and optional origin_date. Default origin is today in Asia/Kolkata; future origins
are rejected. Market aliases normalize using existing ingestion rules. Historical
requests still enforce artifact availability and source snapshot timing.

PredictionResponse includes model version, scope, exact target date, aware decision
timestamp, latest report/age, provenance, reliability flags/status and empirical
bands when supported. Prices are Decimal strings rounded to paise; interval lower
bounds round outward down and upper bounds outward up. Nominal interval levels
remain nominal empirical levels, not confidence promises.

RecommendRequest extends the pure optimizer request with server-controlled future
scenario handling. Each holding option supplies duration, daily loss/storage
schedule, future transaction costs, realization_multiplier, price_basis_assumption,
adverse_inr_per_quintal and adverse_assumption. It cannot submit trusted scenarios,
reliability flags, model versions or artifact paths. Unknown fields and non-null
scenarios are rejected. Scope must use canonical Kolar APMC / Tomato and normalized
variety/grade; decision_at must be aware and no later than server time. Supported
forecast horizons are 1/3/7; other holding dates receive unsupported-horizon warnings
and no fabricated forecast. Crop/horizon constraints still apply in the optimizer.

RecommendationResponse includes request ID, local history ID, as-of market freshness,
all successful prediction results, reliability warnings, selected plan and every
feasible compared alternative. The optimization object preserves immediate net
cash, four future price/proceeds scenarios, storage/deterioration, break-even
price, downside, sell-all-now comparison and all disclosed assumptions. INR values
use Decimal strings; quantities are quintals. No float conversion is introduced
into the optimizer. Mandi wholesale prices remain distinct from the user-entered
farmer quote and the explicit future realization mapping.

## Recommendation call chain and safe fallback

1. Validate economic inputs/scope/date and reconstruct official market freshness
   before the decision origin using the existing vintage loader.
2. Resolve the saved champion and reliability evidence from server configuration
   and call reliable_forecast for each supported holding duration.
3. Use scenarios_from_reliability to map the returned wholesale band and central
   price to the supplied farmer realization basis, with a separately disclosed
   adverse stress price. An invalid adverse/mapping assumption is 422.
4. Pass those trusted scenarios (or None when absent) to optimize_selling.
   Unvalidated/stale/unavailable predictions never become confident hold decisions.
5. Persist only a minimal anonymous outcome; return the typed comparison response.

Missing forecasts do not prevent a quote-based immediate-sale comparison. A 200
today_only_safe_fallback explicitly reports model/data warnings, no invented
forecast and a user-supplied today quote. If even the mandatory cash/physical plan
is infeasible, return 409 **with the full RecommendationResponse**, no selected
plan and an explanation. A scenario-only outcome without a validated hold action
is labeled as such. Storage, cash and lot constraints are never relaxed by API code.

The current workspace has 3 fixture observations, 0 official observations and no
deployed model. Default market/commodity/history endpoints return empty results;
latest returns 404, predict 503, and the example recommend call returns a clear
today-only fallback. There is no claim that fixture values are live prices.
Explicit fixture/demo queries for markets/history are permitted only in development/
test and retain data-kind/source labels; production configuration rejects them.

## Deploy actual saved artifacts

No artifacts are auto-selected by scanning for the most favorable test metrics.
Set an explicit registry after producing genuine source/model/calibration runs:

```powershell
Copy-Item docs/examples/service-registry.example.json service-registry.json
# Replace every ACTUAL_* placeholder with real artifact directories first.
$env:SAMAY_SERVICE_REGISTRY_PATH = 'service-registry.json'
# Restart Uvicorn after configuration changes.
```

The registry is a list of feature_run, champions and optional evidence directories.
Paths are trusted server configuration and resolve relative to repository root
unless absolute. Each entry's feature metadata defines one market/commodity/variety/
grade; duplicates are rejected. Champions are loaded per horizon from champion-Nd.
Evidence must match scope, version, policy, source timing and integrity checks in
the existing reliability module. No evidence means limited evidence, not validated.
Missing/corrupt registry or service artifacts fail explicitly; no fixture or arbitrary
untrained estimator is loaded as a fallback. Saved pickle artifacts must be trusted.

models/status presence is explicitly **not** a reliability validation claim. Actual
prediction calls check historic availability, integrity, sparse/stale inputs and
calibration evidence. Models trained after a requested origin cannot be used there.

## Error codes, request IDs and logging

| HTTP | Machine codes / meaning |
| --- | --- |
| 200 | Available forecast or fully explained recommendation/fallback; inspect reliability/status |
| 404 | no_official_observation for latest; empty list/history responses otherwise remain 200 |
| 409 | No feasible cash/physical recommendation; full typed comparison response |
| 422 | invalid_request, unsupported_series, future_decision, scenario_assumptions_invalid, economic_assumptions_invalid |
| 503 | missing_model, forecast_unavailable, stale_market_data, registry_unavailable, prediction_service_unavailable, market_source_unavailable, database_unavailable |
| 500 | internal_error with a generic safe message |

Errors other than the documented 409 use `{error: {code,message,request_id,details}}`.
Validation details include field locations and error types, never echoed raw bodies.
SQL, credentials, exception messages and artifact paths are not returned in unexpected
errors. Every request receives a new server-generated UUID in X-Request-ID; prediction/
recommendation/error bodies repeat it. Client-provided IDs are not used as unique
history keys. Structured JSON logs include request ID, method, route template,
status and duration, without query strings, body, farmer notes or IP. CORS allows
configured origins and GET/POST, exposes X-Request-ID, and handles error responses.

## Local recommendation history and data minimization

Alembic migration cee3e9392b8d adds recommendation_history, leaving existing domain
entities intact. It stores an aware creation/decision time, request UUID, scope,
outcome status, sold/held quantities, net cash, source report date, model versions
and reliability warnings. It stores no farmer name, phone, location, IP, free-text
cost/source assumptions, full request body or full response. No unauthenticated
history-list endpoint is added. Persistence failure returns 503 instead of claiming
an audit record was saved. This is a local single-user backend; configure access
controls and retention before sharing financial histories between users.

## Integration verification and limits

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_integration.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
Set-Location frontend
npm.cmd test
npm.cmd run build
```

Integration tests use two deterministic captured-CSV fixtures in a **temporary
database**, the real importer, causal examples, a real ridge fit and saved artifact,
the actual reliability service and actual optimizer. No forecasting/optimization
response is hardcoded or mocked for that flow. Small fixture sample counts correctly
produce limited evidence and block confident holding; changing today's quote changes
computed net cash. Separate tests cover stale data, missing horizon/model, service
failure, invalid user-supplied trust assertions, privacy/logging, CORS, Swagger and
cash/persistence failures.

The isolated fixture metadata simulates the official schema for wiring tests and
is explicitly labeled INTEGRATION_TEST_ONLY_NOT_LIVE. It is never imported into
the workspace database, never presented as government evidence, and never used
to claim a statistically validated champion. A genuine calibrated-model deployment
remains blocked by the missing authenticated historical data from earlier stages.
No Prompt 8 work was started.
