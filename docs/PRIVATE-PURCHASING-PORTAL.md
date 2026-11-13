# Private purchasing portal — Prompt 2

Implemented locally on branch `sub1`, 13 November 2026. The attachment also contained
Prompts 3–4; this change stops after Prompt 2. No existing user, business, market data,
forecast model or APMC transaction was replaced. No real business account was seeded
or approved. Tests use disposable, explicitly labeled TEST_ONLY businesses and records.

## What works

Verified private mandi owners and private buyers have the same purchasing infrastructure
with distinct business type labels, registry entries and dashboards. Their own workspace
contains Overview, My Buying Offers, Create Buying Offer, Incoming Farmer Requests,
Accepted Requests, Appointments, Completed Purchases, Notifications, Business Profile
and Settings. The last two lifecycle sections explicitly explain what is not yet available;
confirmed arrival terms never appear as completed sales or booked appointments.

The five-step form captures crop/variety/grade/condition/quality, quantity limits and daily
intake, price type/bounds/basis/validity, location/coordinates/service area, transport/
charges/weighment/arrival dates, payment methods/timing/terms/deductions and instructions.
It reuses the commodity registry and registered business address. Unknown charges remain
null, distinct from a business-confirmed zero. All quantities are quintals and prices INR
per quintal; charge basis is explicitly per quintal or per trip. Optional images are protected
references only; uploads are not configured and protected references never enter farmer responses.

New offers save as DRAFT; publishing is a separate explicit action. Owners can edit, update
price/quantity requirement/validity, pause, resume and cancel. The server calculates remaining,
reserved and committed quantities; users cannot submit arbitrary counter values. A total
requirement may not be reduced below reservations and commitments. History and historical
prices are preserved; edits notify farmers with pending responses/requests. Cancelling publication
cancels unanswered requests, while preserving already issued response terms and commitments.

Businesses can inspect scoped incoming requests, accept, counteroffer or reject, specifying exact
quantity, price, arrival timestamp, response expiry and payment terms. The farmer must separately
confirm an acceptance/counteroffer. Confirmed terms are frozen snapshots and do not change when
a listing changes. Contact phone disclosure requires both explicit request consent and an actually
verified number; email is not returned. Physical quality, actual payment and final realization are
not asserted by a purchasing listing.

## Quantity integrity

Quantity arithmetic uses integer thousandths of a quintal, avoiding SQLite floating-point
accumulation for reservations. Monetary values use validated Decimal inputs and two-decimal
price storage. Remaining quantity = total requirement − unexpired reserved quantity − committed
quantity. Merely submitted requests reserve nothing and do not count as purchases.

A business response creates a HELD reservation with expiry. Farmer confirmation converts it to
COMMITTED atomically. Rejecting/replacing a response releases its old hold within the same
transaction. Expired holds are excluded immediately in reads and released in the next successful
write transaction. Failed writes roll back all intermediate changes. Offer expiry and stale response
status are computed against the current UTC-aware clock on reads; no scheduler is required for
safe capacity calculations. A future background maintenance task may materialize those transitions.

SQLite writes use BEGIN IMMEDIATE before reloading authorization, offer, request and counters.
This serializes read/validate/allocate within one database transaction. PostgreSQL row-lock hooks
exist, but **PostgreSQL is not tested**; this release's supported local concurrency evidence is
SQLite. Tests prove two simultaneous 60-quintal acceptances against a 100-quintal requirement
produce exactly one success and one 409, leaving 60 reserved. Per-offer, per-IST-arrival-date
capacity is independently enforced. Cross-offer shared physical capacity is not modeled.

All reads/writes validate current scoped membership, verification and exact server-persisted active
business workspace; mutations also require management permission. Pending, suspended, inactive,
foreign-business and farmer-only access is rejected. Private mandis require their private market
assignment; government APMC market/assignment records are not reused or impersonated.

## Database and changed files

Migration: `e5f6a7b8c9d0`, following `d4e5f6a7b8c9`.
Nine additive tables:

- purchase_offers
- purchase_offer_requirements
- purchase_offer_prices
- purchase_offer_history
- farmer_sale_requests
- business_responses
- purchase_offer_quantity_reservations
- private_purchase_request_history
- private_purchase_notifications

Foreign keys, indexes, quantity/state checks and unique idempotency constraints are included.
SQLite triggers forbid update/delete of price history, offer history, business responses and
request histories. Migration upgrade/repeat/downgrade preserves existing identities in tests.
The local runtime database was backed up under ignored `.local-data/backups/`; fingerprints
for **all 36 existing tables** matched after migration, excluding Alembic version tracking.
See `reports/private-purchasing-runtime-migration.json`. Private backup details are kept only
in ignored `.local-data/private-purchasing-migration-snapshot.json`.

New backend files: `backend/app/purchase_models.py`, `purchase_schemas.py`,
`purchase_service.py`, `purchase_routes.py` and the Alembic migration.
Integration: `backend/alembic/env.py`, `backend/app/main.py` (router, private cache headers,
PUT CORS support), `sale_auth.py` (PUT write throttle), `prepared_data.py` (new private-table
snapshot exclusions), `business_routes.py`/`business_schemas.py` (publishing capability now exists).

New frontend files: `frontend/src/BusinessPurchasing.tsx`, `purchase-api.ts`,
`locales/purchase-kn.ts`, `BusinessPurchasing.test.tsx`.
Integration: `BusinessPages.tsx`, `business.css`, `i18n.tsx`, `sale-api.ts` (PUT support),
OpenAPI export/generated schema and production assets. Existing farmer routes remain intact.
New tests: `tests/test_private_purchasing.py`, `scripts/run_private_purchasing_e2e.py`.
The existing private foundation browser report now correctly records that offers are implemented.
Documentation: this file, README and STATUS. Earlier uncommitted farmer-flow work is preserved.

## APIs

All paths below have `/api/v1` prefix. Existing cookie login is reused. Writes require
`X-SAMAY-Action: 1`; create offer and submit request also require `Idempotency-Key`
(16–100 characters). Editing uses the current offer version; responding uses current request
version. Retrying a create with the same key/body returns the same row; changed bodies conflict.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | /business/offers | Create owned draft; business_id in body |
| GET | /business/offers?business_id=ID | Scoped offers, limit/offset |
| GET | /business/offers/{id} | Terms, prices and immutable revision history |
| PUT | /business/offers/{id} | Validate and save full revised terms |
| POST | /business/offers/{id}/publish | Publish draft or resume paused offer |
| POST | /business/offers/{id}/pause | Pause publication |
| POST | /business/offers/{id}/cancel | Cancel publication; frozen agreements remain |
| GET | /business/requests?business_id=ID | Scoped requests, limit/offset |
| GET | /business/requests/{id} | Request detail, responses and audit |
| POST | /business/requests/{id}/accept | Exact response and temporary reservation |
| POST | /business/requests/{id}/counteroffer | Counterproposal and temporary reservation |
| POST | /business/requests/{id}/reject | Release pending hold and record rejection |
| GET | /business/analytics?business_id=ID | Actual aggregate records and confirmed arrival terms |
| GET | /business/purchase-notifications?business_id=ID | Actual scoped notices/unread count, limit/offset |
| POST | /private-purchases/notifications/{id}/read | Recipient-only read acknowledgement |

Minimal authenticated farmer-side backend infrastructure is included to exercise incoming
requests and confirmation in Prompt 2. Full discovery/comparison/booking UI is not included:

- GET /private-purchases/offers/{id}: selected active verified listing, protected references removed.
- POST /private-purchases/offers/{id}/requests: exact offer/version, crop compatibility,
  quantity, future arrival availability, explicit quality/terms acknowledgement and idempotency.
- GET /private-purchases/requests: own records only, paginated.
- POST /private-purchases/requests/{id}/confirm: own current unexpired response only.
- GET /private-purchases/notifications: own request notices only.

401 unauthenticated; 403 wrong active role/insufficient permission/unverified; 404 missing or
foreign business resources; 409 changed versions/terminal state/insufficient capacity/duplicate
active request; 422 invalid fields/units/arrival/validity; 429 write throttle; 503 unavailable
storage/database. Responses contain request IDs through existing middleware. OpenAPI: `/docs`.

## Dashboard statistics and notifications

All quantities and counts are calculated from stored records. Requested quantity includes all
submitted historical requests. Confirmed quantity is committed reservations, never completed
purchases. Remaining quantity aggregates only currently open, price-valid offers. Average listed
price is the unweighted average of current prices across the business's offers, with an explicit
label; it is not a crop-normalized trade or realization metric. No observed price is overwritten.

A submitted request creates in-app notices only for active managing members of the exact
selected offer's business. Responses notify the corresponding farmer; farmer confirmation
notifies that same business. Listing changes notify farmers with pending requests. Notices are
stored transactionally with their source action and have recipient-specific unread/read state.

Private notices have a separate stream because the existing APMC notification schema requires
government-market foreign keys. Assigning private notifications to an APMC market would be
incorrect. The Business Mode panel reads actual private notices and unread counts. A unified
farmer discovery/notification surface and external private-message outbox integration are later
stages. External email/SMS/WhatsApp purchasing delivery is **not enabled or claimed**.
The Refresh purchasing records control retrieves new incoming requests and counts; automatic
polling/push is not implemented, avoiding form resets while a business writes its response.

## Actual validation and exact commands

From repository root in PowerShell, with dependencies already installed:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 201 passed, one existing deprecation warning in 144.80s
.\.venv\Scripts\python.exe -m pytest tests/test_private_purchasing.py tests/test_private_business.py -q
# 18 passed; one existing Starlette/httpx deprecation warning
npm.cmd --prefix frontend test
# 4 files, 45 tests passed, no unhandled errors
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run types
npm.cmd --prefix frontend run build
# Passed; existing >500 kB production JavaScript chunk warning remains
.\.venv\Scripts\ruff.exe check backend/app/purchase_models.py backend/app/purchase_routes.py backend/app/purchase_service.py backend/app/purchase_schemas.py tests/test_private_purchasing.py scripts/run_private_purchasing_e2e.py backend/alembic/versions/e5f6a7b8c9d0_private_purchasing.py
# All checks passed
.\.venv\Scripts\python.exe scripts/run_e2e.py
# 3 real HTTP integration tests passed
$env:SAMAY_E2E_CHROMIUM = "$env:LOCALAPPDATA\ms-playwright\chromium-1254\chrome-win64\chrome.exe"
.\.venv\Scripts\python.exe scripts/run_private_purchasing_e2e.py
# Passed for PRIVATE_BUYER and PRIVATE_MANDI, zero page errors
.\.venv\Scripts\python.exe scripts/run_sale_e2e.py
# Existing complete APMC browser lifecycle passed, zero browser errors
```

The browser executable path above is this machine's installation. Install Playwright Chromium
or set the variable to your own installed executable on another computer. Browser tests use the
production Vite preview and real FastAPI/SQLite; business actions use the actual forms. Test
setup/verification and farmer request/confirmation use real APIs on disposable databases.
They do not imply a farmer discovery UI already exists.

Coverage: both business types, pending/suspended/foreign/incorrect active roles, offer drafts/
publication/edits/price revisions/pause/resume/cancel/expiry, reservation expiry, daily capacity,
concurrent acceptance, exact 0.001-quintal boundary, idempotency and duplicate active requests,
contact consent, protected references, immutable audit triggers and migration preservation.
Revised grade/variety incompatibility is rejected before allocation. Protected image references
are removed from all request response payloads, including business copies, avoiding any
revoked-membership disclosure path. Frontend tests cover backend statistics, real registry loading, disconnected/retry states,
authorized active workspace and identical Kannada/English numbers. Chromium verifies draft,
publish, request receipt, counteroffer, farmer API confirmation, revision without agreement
mutation, history and Kannada mobile layout for both business types. Existing forecast/optimizer
HTTP and APMC full sale lifecycle tests pass.

Initial checks found: a missing test-mock Promise, lint formatting issues and an asynchronous
crop-selector default-value bug on editing. These were fixed; the final runs pass. The form
also validates quantity/price/date relationships before submission, with backend checks remaining
authoritative. No test fixture, dataset or model metric was changed to improve reported results.

Reports: `reports/private-purchasing-*.log`, `private-purchasing-browser.json`,
`private-purchasing-runtime-migration.json`. Screenshots: `private-purchasing-private_buyer.png`,
`private-purchasing-private_mandi.png` and their `-mobile-kn.png` counterparts under reports/.

## Running and user journey

The local app is running at http://127.0.0.1:5175/business/register and API at
http://127.0.0.1:8012. Health returned `{"status":"ok","service":"samay","version":"0.1.0"}`;
registration route returned HTTP 200. Current migration is `e5f6a7b8c9d0`.

```powershell
# When these ports are unused:
.\.venv\Scripts\python.exe scripts/start_local.py --bundled-research --backend-port 8012 --frontend-port 5175
# For a separately configured durable DB, back it up first, then:
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

Register a real private business using an existing authenticated account. An authorized real
administrator independently reviews it. After approval, select its Business Mode workspace,
create a buying-offer draft, review the five sections and publish. Incoming requests then appear
on Refresh; inspect the exact request, enter a response and send it. Pending capacity is reserved;
farmer API confirmation commits it. Revisions remain visible and do not rewrite prior agreements.

## Remaining scope / deployment requirements

- Stop after Prompt 2. Prompt 3 still owns farmer discovery/filter/comparison UI, farmer-facing
  private request/response journey, booking, arrival/weighment/payment and optimizer integration.
  Prompt 4's unified navigation/notifications and full end-to-end private physical sale audit are
  not claimed complete. Existing APMC booking/completion remains operational.
- Appointments currently show confirmed arrival terms only, explicitly not booked appointments.
  Actual private purchase completion records are not available. No invented records fill empty tabs.
- Secure image/document uploads and external identity verification remain unimplemented.
  Private message external delivery/push updates are not enabled.
- Production deployment was not performed. Use a durable SQLite volume for a single-instance
  deployment; temporary Vercel database writes remain disabled. Multi-host/PostgreSQL operation,
  native Kannada review, load testing, audit retention/backup policy and smaller frontend chunks
  need separate production work. No real payment, quality certification or guaranteed realization
  is promised. Existing saved models retain their existing research limitations.

Source, tests, reports and production assets are included in the sub1 handoff commit.
Private runtime databases, credentials and backups remain local. Earlier source work is retained.
