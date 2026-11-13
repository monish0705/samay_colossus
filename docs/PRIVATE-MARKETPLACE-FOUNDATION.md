# Private marketplace foundation — Prompt 1

Implemented locally on `sub1`, 13 November 2026. Existing APMC and farmer workflows
remain separate. No real business accounts, approvals, offers or transactions were seeded.
The foundation is included in the subsequent sub1 handoff commit. Deployment was not performed.

## Architecture and changed files

- `backend/app/business_models.py`: private registry, scoped memberships/roles, verification audit and workspace preferences.
- `backend/app/business_service.py`: current authorization, verified workspaces, ownership/management guards and future publishing guard.
- `backend/app/business_schemas.py`: strict registration, review, membership and workspace schemas; typed profile/access responses.
- `backend/app/business_routes.py`: authenticated business and administrator APIs.
- `backend/alembic/versions/d4e5f6a7b8c9_private_marketplace.py`: additive migration from `c3d4e5f6a7b8`.
- `backend/alembic/env.py`, `backend/app/main.py`: model/router registration and private no-store responses.
- `backend/app/sale_auth.py`, `sale_routes.py`, `sale_service.py`: effective authorized account roles; legacy APMC assignment checks remain mandatory.
- `backend/app/prepared_data.py`: public snapshot guard also rejects private business/account-role records.
- `scripts/sale_admin.py`: legitimate admin bootstrap includes role mapping.
- `frontend/src/business-context.tsx`: server-authorized workspace switch and refresh restoration.
- `frontend/src/BusinessPages.tsx`, `business.css`, `locales/business-kn.ts`: distinct onboarding, protected profiles, admin review and responsive workspaces.
- `frontend/src/App.tsx`, `i18n.tsx`, `SalePages.tsx`, `sale-api.ts`: route/navigation/auth integration.
- `frontend/openapi.json`, `frontend/src/generated/api-schema.ts`, `frontend/dist/`: generated API schema and production assets.
- `tests/test_private_business.py`, `frontend/src/BusinessPages.test.tsx`, `scripts/run_private_business_e2e.py`: isolated unit/integration/browser verification.
- `README.md`, `docs/STATUS.md`, this document: operational handoff.

Other existing uncommitted farmer-advisor/mandi changes were preserved.

## Database migration and preservation

Ten new tables: `account_roles`, `business_accounts`, `business_users`, `business_roles`,
`business_verifications`, `private_mandis`, `private_buyers`, `business_crop_preferences`,
`business_market_assignments`, `account_workspace_preferences`.

Existing `mandi_users` identities and commodity IDs are reused. Private mandis have their
own registry and assignment foreign keys; no private business is inserted into the
government APMC market registry. Foreign keys, unique keys, role/state constraints,
lookup indexes and optimistic verification versions are enforced. SQLite triggers
make verification decisions immutable. All stored timestamps use UTC-aware types.
Legacy primary roles are backfilled without changing password hashes or identities.

Upgrade/repeat-upgrade/downgrade are tested on disposable SQLite. The local runtime
was backed up under ignored `.local-data/backups/` before upgrade. Migration head is
`d4e5f6a7b8c9`; SHA-256 row fingerprints for all **26 existing tables** were identical
after migration (excluding the intentionally changed Alembic version table).
The private backup path and fingerprints are in ignored `.local-data/private-migration-snapshot.json`.

## APIs

All routes below start `/api/v1`. Login uses existing HttpOnly session cookies.
Write requests require `X-SAMAY-Action: 1`; registration also requires
`Idempotency-Key` (16–100 characters). All enforce durable database availability.

| Method | Path | Authorization |
| --- | --- | --- |
| POST | /business/register | Authenticated; application only, no role grant |
| GET | /business/profile | Own active memberships; optional business_id |
| GET | /business/roles | Current authorized roles/workspaces and saved selection |
| POST | /business/active-role | Exact current authorized business/role or permitted Farmer mode |
| GET | /business/verification-status?business_id=ID | Own active membership; audit history |
| GET | /business/workspace/{id} | Verified, active, scoped role and private market assignment |
| GET | /admin/businesses/pending | SYSTEM_ADMIN; paginated limit/offset |
| GET | /admin/businesses/{id} | SYSTEM_ADMIN |
| POST | /admin/businesses/{id}/verify | SYSTEM_ADMIN; version and evidence required |
| POST | /admin/businesses/{id}/members | SYSTEM_ADMIN; explicit compatible scoped membership |
| POST | /admin/businesses/{id}/market-assignment | SYSTEM_ADMIN; market must belong to that private business |

Error responses: 401 unauthenticated, 403 unauthorized/unverified, 404 inaccessible
or missing business, 409 stale review/invalid transition/idempotency conflict,
422 invalid inputs/evidence, 429 registration throttle. Existing durable-storage
write guard can return unavailable status. Swagger: `/docs`.

## Roles, verification and interface

One farmer account can apply for both types and later hold FARMER,
PRIVATE_MANDI_OWNER and PRIVATE_BUYER simultaneously. MANDI_STAFF has an explicit
business scope and management flag. SYSTEM_ADMIN approval is required; selecting
an interface or requesting a role in browser state grants nothing. Existing legacy
MANDI_OWNER continues to mean the existing APMC workflow, never PRIVATE_MANDI_OWNER.

Pending -> Verified/Rejected; Verified -> Suspended; Rejected -> Pending;
Suspended -> Pending/Verified. Approval records reviewer, evidence and contact/
registration attestations, then grants scoped permissions and private market assignment.
Suspension/inactive membership removes effective powers immediately on backend requests.
The browser restores only the server-persisted authorized selection; invalid selections
fall back to the farmer interface. Persistence uses the authenticated account, not
browser role claims. Protected profiles/doc references have no public listing endpoint.

Pages: `/business/register`, `/business/admin`, `/business/mandi/{id}`,
`/business/buyer/{id}`. Top navigation exposes authorized Farmer/Business modes;
a farmer-only account cannot enter Business Mode. Existing `/mandi` remains separate.
Administrator UI can review pending applications or find an existing business by ID.
Staff membership/private assignment management currently use administrator APIs.

## Exact tested PowerShell commands and observed results

Run from repository root with prepared dependencies:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
# 191 passed, 1 deprecation warning in 136.50s
npm.cmd --prefix frontend test
# 3 files, 40 tests passed
npm.cmd --prefix frontend run lint
# exit 0
npm.cmd --prefix frontend run typecheck
# exit 0
npm.cmd --prefix frontend run types
# generated src/generated/api-schema.ts
npm.cmd --prefix frontend run build
# exit 0; existing >500 kB JavaScript chunk warning
.\.venv\Scripts\ruff.exe check backend/app/business_models.py backend/app/business_routes.py backend/app/business_schemas.py backend/app/business_service.py tests/test_private_business.py scripts/run_private_business_e2e.py
# All checks passed!
.\.venv\Scripts\python.exe scripts/run_e2e.py
# 3 actual HTTP integration tests passed
$env:SAMAY_E2E_CHROMIUM = "$env:LOCALAPPDATA\ms-playwright\chromium-1254\chrome-win64\chrome.exe"
.\.venv\Scripts\python.exe scripts/run_private_business_e2e.py
# status: passed; no browser page errors
.\.venv\Scripts\python.exe scripts/run_sale_e2e.py
# status: passed; no browser errors
```

Chromium executable path above is this machine's installed browser; on other machines
install Playwright Chromium or point SAMAY_E2E_CHROMIUM at an available executable.
Tests use disposable TEST_ONLY accounts/documents and make no external verification claims.
Private browser test covers both registrations, admin approval, saved selection on reload,
multiple roles, forged scope rejection, suspension and Kannada mobile layout without
overflow. Existing sale browser test exercises onboarding, waiting-request release,
counteroffer, farmer acceptance, arrival, weighing and completion with English/Kannada
numerical consistency. HTTP tests retain market/forecast/optimizer wiring.

Reports: `reports/private-business-backend-all.log`, `private-business-frontend-tests.log`,
`private-business-build.log`, `private-business-http-e2e.log`,
`private-business-browser.json`, `private-business-legacy-browser.log`.
Screenshots: `reports/private-buyer-dashboard.png`, `reports/private-mandi-mobile-kn.png`.
Initial browser runs exposed missing exact accessible labels and an overly strict text
selector; labels/selectors were corrected and the final browser flow passed.
A Windows console encoding error occurred while printing an already-created backup path;
UTF-8 output and subsequent fingerprint verification confirmed backup/migration success.

## Running locally

```powershell
.\.venv\Scripts\python.exe scripts/start_local.py --bundled-research --backend-port 8012 --frontend-port 5175
```

This runs migrations and uses an isolated hash-verified prepared database, preserving
existing `.env` and `samay.db`. Requires unused ports and installed dependencies.
Current local launcher is running; do not start another on the same ports.
Frontend: http://127.0.0.1:5175/business/register
API health: http://127.0.0.1:8012/api/health returned
`{"status":"ok","service":"samay","version":"0.1.0"}`.
Registration page returned HTTP 200. Existing saved forecasts retain research limitations.

For an existing configured durable database, back it up, then apply:

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
```

## Unresolved limitations and next handoff

- Prompt 1 only: public purchase offers/private transactions and business notifications
  are not implemented; dashboards say so. `can_publish` is a permission capability,
  not a claim that publishing exists; `public_offers_implemented` is false.
- Verification is manual administrator attestation, not automated government/license,
  contact, email or phone verification. No real business has been approved by tests.
- Documents are protected references only. Secure uploads/storage/scanning, retention
  controls and external document access verification remain future work.
- No real external message delivery or production deployment tested. SQLite requires
  durable storage; the existing temporary Vercel database write guard stays fail-closed.
- Native Kannada review, production security/load review and frontend chunk splitting
  remain. Backend emits one existing Starlette/httpx deprecation warning.
- Admin pending API is paginated; UI shows its first page and supports ID lookup.
  Advanced business administration and membership editors are API-only foundations.

Future purchase-offer services must call the scoped `may_publish` guard, maintain private
business identifiers, and never reuse APMC assignment privileges. Stop here for Prompt 1.
