# Sale workflow verification — 13 November 2026

Branch: `sub1`, in the existing `samay-sub2` worktree. No production deployment or real
operator onboarding was performed. No test accounts or transactions were added to the
running local database. Tests isolate generated identities/data in temporary SQLite files.

## Commands actually executed

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q --tb=short
.\.venv\Scripts\python.exe -m pytest tests/test_sale_workflow.py tests/test_prepared_bundle.py tests/test_bundled_profile.py -q --tb=short
.\.venv\Scripts\python.exe -m ruff check backend/app/sale*.py backend/app/main.py backend/app/config.py backend/alembic/env.py backend/app/prepared_data.py scripts/sale*.py scripts/prepare_data_bundle.py scripts/run_sale_e2e.py tests/test_sale_workflow.py tests/http_fixture_server.py tests/test_backend.py tests/test_bundled_profile.py tests/test_prepared_bundle.py tests/test_current_crops.py tests/test_crop_horizons.py
.\.venv\Scripts\python.exe -m ruff check backend scripts tests
```

Final full backend result: **178 passed**, one existing Starlette/httpx deprecation warning,
106.98 seconds. The targeted workflow/bundle group passed **30 tests**. The full suite includes
24 new workflow tests, schema upgrade/repeat-upgrade/downgrade and immutable audit protection,
true concurrent owner responses, idempotency, ownership isolation, staff restrictions,
expired/superseded offers, Decimal settlement, rollback when notification creation fails,
unconfigured channels, simulated email/SMS/WhatsApp failures, verification/consent and the
private-data bundle guard.

Changed-feature Python lint: passed. Whole repository Python lint: **25 existing errors in
untouched files**, retained in `reports/sale-backend-lint.log`. They concern imports/unused
symbols and module import ordering in prior market-data modules/tests. Do not interpret
feature lint success as a clean repository-wide lint result.

Frontend commands, from `frontend`:

```powershell
npm.cmd run types
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
```

OpenAPI types regenerated. Lint/typecheck/build passed. Final Vitest result:
**2 files passed, 32 tests passed**. Seven new UI tests cover unavailable mandi submission,
correct crop selection with asynchronously loaded multi-crop catalogues, failed login,
role separation, language switching, channel verification/availability and empty history.
Vite retains the existing large-bundle warning; this is not a build failure.

## Actual browser integration

Installed the optional Playwright Python package. The test used the installed local
Chromium executable through this override:

```powershell
$env:SAMAY_E2E_CHROMIUM = "$env:LOCALAPPDATA\ms-playwright\chromium-1254\chrome-win64\chrome.exe"
.\.venv\Scripts\python.exe scripts/run_sale_e2e.py
```

For a clean machine, install the documented browser extra and run
`python -m playwright install chromium`; omit the override to use Playwright's default.

Result: **passed**, zero browser page errors. The test launched the production React bundle
through Vite preview, actual FastAPI HTTP endpoints, migrated temporary SQLite, a saved
fixture baseline, actual recommendation service, and the real marketplace services.

Verified sequence:

1. Administrator approves an existing test mandi and invites an owner.
2. Owner redeems the invitation through `/mandi`.
3. Farmer calculates a real backend recommendation and opens Sell to This Mandi.
4. Farmer registers, edits to a partial quantity and explicitly confirms submission.
5. Owner inbox/list updates automatically through polling.
6. Owner offers a different price and accepts only part of the requested quantity.
7. Farmer opens the notification and confirms the exact offer/slot.
8. Booking is created; owner records arrival, weighment and completion.
9. Farmer sees the completed record, with identical amounts after switching to Kannada.
10. Mobile page has no horizontal overflow.

The financial TEST_ONLY case records 9.725 quintals at INR 1,049.95/quintal:
gross INR 10,210.76 after ROUND_HALF_UP settlement; deductions INR 250.75;
net INR 9,960.01. This is deterministic test evidence, not a real transaction or profit claim.

Evidence:

- `reports/sale-browser-e2e.json`
- `reports/sale-browser-command.log`
- `reports/sale-e2e-server.log`
- `reports/sale-owner-incoming.png`
- `reports/sale-farmer-completed-en.png`
- `reports/sale-farmer-completed-kn.png`
- `reports/sale-backend-tests.log`
- `reports/sale-workflow-tests.log`

## Local running application

Restarted the existing local launcher after migration/code updates:

```powershell
.\.venv\Scripts\python.exe scripts/start_local.py --bundled-research --backend-port 8012 --frontend-port 5175
```

Verified frontend `/mandi` HTTP 200, backend `/api/health` healthy, and unauthenticated
`/api/v1/sale-requests` HTTP 401. Five authentic mandi entries are present; zero are activated
for online requests, because no real owner was supplied or approved. This is the intended
safe state. Market history/model startup still verifies 3,988 official observations,
5,834 separately labeled secondary observations and 322 research artifacts.
See `reports/sale-local-smoke.json`.

Local farmer URL: http://127.0.0.1:5175/sale-requests

Local owner URL: http://127.0.0.1:5175/mandi

Swagger: http://127.0.0.1:8012/docs

## Failures found and resolved

- Initial untyped JSON serialization converted Decimals to floats. Sale responses now preserve
  decimal strings and expose Pydantic response schemas.
- Corrected a test's arithmetic expectation: the exact product rounds to 10,210.76.
- Updated an old migration test that assumed the original table set.
- Existing stale-data tests assumed the snapshot ended in early November; they now test a
  date beyond the actual latest imported report. No freshness threshold or metric was altered.
- Bundle tests used arbitrary byte strings; they now use real temporary SQLite files so
  privacy validation can inspect the schema. Invalid SQLite remains rejected.
- Fixed asynchronous crop selection and added a regression test with a different first crop.
- Removed prior speech-input TypeScript `any`/unused-label lint errors with explicit types.

## Outstanding requirements

No SMTP, SMS or WhatsApp message has been sent or claimed delivered. Provider errors and
unknown delivery outcomes were tested with local mocks. Real delivery requires credentials,
verified contacts, explicit consent, approved WhatsApp templates and provider testing.

Mandi registration/identity evidence, owner invitations and contact verification need real
operators. A trusted local administrator bootstrap is documented in SALE-WORKFLOW.md.

The current Vercel temporary-database setup cannot safely retain accounts/bookings and now
refuses marketplace requests unless durable storage is provisioned. Production deployment,
account-recovery tooling, native Kannada review, organization-specific capacity/cancellation
policies and production load testing remain operational work. Payment transfer and multi-request
inventory reservations are not implemented.
