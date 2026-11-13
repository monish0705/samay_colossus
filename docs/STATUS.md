# SAMAY status — 13 November 2026

## Private purchasing portal — Prompt 2

Implemented separate private-buyer/private-mandi purchasing dashboards, five-step draft
forms, publication/edit/price revisions/pause/resume/cancellation, scoped incoming requests,
accept/counteroffer/reject responses, frozen agreement snapshots, transactional quantity
reservations and farmer API confirmation, real analytics and private in-app notifications.
Migration `e5f6a7b8c9d0` adds nine tables; all 36 existing runtime tables were preserved.

Validation reports and exact commands: [purchasing handoff](PRIVATE-PURCHASING-PORTAL.md).
Backend 201 tests, frontend 45 tests, 3 actual HTTP tests, both private business browser
flows and the existing APMC browser lifecycle pass. Lint, type checking and production
build pass, with one existing backend deprecation warning and the bundle-size warning.

Prompt 3 discovery/comparison UI, private bookings and actual sale/payment recording remain
unimplemented and explicitly labeled in the portal. No real businesses or sales seeded;
no external delivery, real identity verification or production deployment is claimed.

## Private marketplace foundation — Prompt 1

Implemented separate private mandi/buyer applications, manual administrator verification,
scoped multi-role permissions, private market assignment, persistent authorized workspace
switching, and English/Kannada onboarding/dashboard foundations. Ten additive tables;
existing 26 runtime tables verified unchanged after migration. No fake business accounts.

Verification: 191 backend tests, 40 frontend tests, 3 HTTP integration tests, private
marketplace Chromium flow and existing complete APMC Chromium flow pass. Frontend lint,
type checking and production build pass. See [full handoff](PRIVATE-MARKETPLACE-FOUNDATION.md).

Not implemented in this prompt: purchase offers/private trading, secure document upload,
automatic external verification and deployment. Manual approval requires an authorized
administrator and independent contact/registration checks.

## Farmer-to-mandi workflow update

Implemented and tested locally on branch `sub1`: authenticated farmer accounts,
administrator-approved mandi invitations/assignments, the separate `/mandi` portal,
sale request previews and idempotent submission, immutable request/offer histories,
counteroffers, farmer confirmation, arrival bookings, arrival/weighment/completion,
manual payment records, discrepancy reporting, scoped in-app notifications and outbox.
Core workflow labels are available in English and Kannada. Existing market/forecast/
optimizer functionality is preserved.

Final verification: **178 backend tests and 32 frontend tests pass**. Production build,
frontend lint/typecheck and lint for changed feature Python files pass. Actual Chromium
through production React, HTTP API and disposable SQLite passed the complete lifecycle,
including mobile English/Kannada numerical consistency. Screenshots and exact results
are in reports/ and [SALE-VERIFICATION.md](SALE-VERIFICATION.md).

Operational requirements remain: approve real mandi operators, verify contacts, configure
and test external providers, and deploy on durable storage. No real operator accounts or
marketplace transactions were seeded. The five authentic local mandi entries correctly
show online requests unavailable until activated and assigned. SMTP/Twilio adapters have
failure-path tests, but **no real external delivery has been tested**. Native Kannada
review and production load/security review remain. Repository-wide backend lint reports
25 existing issues in untouched files; the feature-specific lint check passes.

The temporary-database Vercel deployment fails closed for marketplace routes. It needs a
shared durable database and worker scheduling. This feature has not been deployed.
See [onboarding, APIs and configuration](SALE-WORKFLOW.md).

## Earlier platform status — 5 November 2026

## Working

- Five crops have genuine historical records: 3,938 direct government observations and 5,834 separately labeled secondary India Data Portal / ISB AGMARKNET records. Raw responses, actual timestamps, units, hashes and publisher attribution are retained.
- CSV ingestion, quarantines, deduplication, source separation, portable SQLite bundle and idempotent imports. Three secondary rows are quarantined; no observations were fabricated.
- Ten frozen short-horizon studies and 322 registered serving artifacts. Current-grade daily ranges: Tomato 1–7, Copra 1–60, Arecanut/Rashi 1–73, Onion 1–83 and Potato 1–84. Of 292 daily additions, 274 are explicit fixed persistence baselines. Eighteen underwent development selection; one selected a regression. No new final-test superiority is claimed.
- Historical actual-versus-predicted API and charts, original final errors and naive comparisons, English/Kannada labels, source and grade limitations.
- One prediction path for API/advisor, explicit missing/stale failures, Decimal cash-aware optimization and separate user-scenario holding analysis.
- Conditional plans are displayed consistently with exact ledgers; the safe sell-now fallback remains separate. Actual monthly artifact-to-optimizer integration passes.
- Dated, hash-verified market-city weather, official holiday calendar and publisher RSS context. Explicit outdoor rain constraints; no fabricated news/weather price coefficients.
- Exact horizon availability API, responsive English/Kannada forms, manual inputs and optional speech fallback. No hardcoded crop prices or seasonal profit claims.
- Tests protect source integrity, exact targets, future availability, unseen holdouts, overlapping interval reuse and financial constraints.

## Limited evidence

- Research only: original publication/revision histories are unverified. No validated operational holding advice.
- Old mirror records often do not report grade. Unspecified grades are not combined with current graded series. Current Arecanut/Rashi and older Bette studies remain separate.
- Sparse final samples have no reliable final score; some frozen models underperform naive. New daily extensions use development-only evidence or predeclared-rule benchmarks and do not reopen final testing.
- Some selected baselines underperform naive on final data. Results are preserved without reselection from test feedback.
- Current refits have no new independent final test. Empirical intervals are retrospective diagnostics, not guaranteed coverage.

## Still unavailable

- Forecasts beyond the supported daily ranges, including current-grade 90/180/365/730-day trained forecasts. They fail evidence checks rather than inventing prices. Explicit user scenarios remain possible within crop/storage constraints.
- Verified live/as-of original vintages, guaranteed farmer realization, real buyer quotes, verified warehouse bookings and public production deployment.
- Historically timestamped weather/news predictors, prospectively validated long-horizon skill, new calibrated long-horizon intervals, automatic mandi refresh and 2027 verified calendars.

Latest checks: **134 backend tests, 24 frontend tests, 3 actual HTTP integration tests and 9 live API decision cases pass**. Typecheck, lint and production build pass. An initial concurrent HTTP timeout is preserved; the isolated rerun passed. Starlette/httpx deprecation and Vite bundle-size warnings remain.

See [DAILY-HORIZONS](DAILY-HORIZONS.md), [SELL-HOLD-ADVISOR](SELL-HOLD-ADVISOR.md), [CURRENT-CROP-MODELS](CURRENT-CROP-MODELS.md) and [computed daily errors](../reports/daily-horizon-results.md). Changes and saved artifacts are included on branch `sub2`.
