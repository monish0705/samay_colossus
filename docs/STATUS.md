# Current acquisition/model update · 2026-11-04

**1,943 genuine official observations are now imported and six research-only
champion artifacts are saved.** See [MODEL-RESULTS](MODEL-RESULTS.md) for actual
held-out errors, baselines, sample sizes and limitations, and [ACQUISITION](ACQUISITION.md)
for source details. The earlier zero-data statements below are historical.

The source spans 2021-01-01–2026-10-31. Grades were not merged: older Tomato/FAQ
and newer Tomato/Local were studied separately. Research forecasts assume next-day
publication on the current snapshot; actual download times remain unchanged.
All six frozen champions are baselines. The Local 3d rolling-mean champion
underperformed naive on the final test; it was not swapped after seeing that result.

Current checks: **90 backend tests, 14 frontend tests, 3 real HTTP tests pass**;
production build, type checking, lint, migrations and package consistency pass.
Actual prediction CSV errors are independently checked. The UI defaults to the
actual Tomato/Local series and shows conditional research metrics on Transparency.
Validated live forecasting/holding recommendations remain unavailable. Docker,
public deployment, empirical interval deployment and farmer field validation are
not claimed. Research artifacts are rejected by the production predictor.

## Historical pre-acquisition release status

**Engineering integration works; authentic forecast demo is blocked.** No public
deployment or real market accuracy/coverage/profit claim is made.

Latest acquisition retry: **5 genuine modal-only observations downloaded**, with
2 unreported dates, from the verified government API. A full historical query is
prepared behind a CAPTCHA confirmation. These five records lack min/max/grade and
are not substituted into the full observation table. See ACQUISITION.md.

## Working and tested

- All nine FastAPI endpoints, Swagger, typed contracts, request IDs, safe logs,
  CORS, SQLite/Alembic initialization and anonymous recommendation persistence.
- CSV ingestion, normalization, invalid/suspicious quarantine, duplicate/revision
  lineage, hashes, cleaned exports and quality reports.
- Causal features, chronological CV/model selection, saved inference, protected
  final evaluation and empirical uncertainty machinery with isolated fixtures.
- Decimal cash/storage/lot optimization, costs, loss schedules, downside objectives,
  full sale, safe fallback and explicit infeasible outcomes.
- Historical decision replay, realized settlement and sell-all comparison reports.
- Seven responsive screens, API integration, honest loading/error/empty/disconnected
  states, five-step workflow, scenario previews and backend recalculation.
- English/Kannada core interface, exact deterministic explanations, numerical
  consistency, keyboard/mobile support and optional speech/text fallback.
- Windows setup/start, same-origin proxy, readiness checks, explicit offline
  historical clock/banner; production rejects historical replay.
- Automated React-to-real-HTTP CSV/model/uncertainty/optimizer integration and
  manual desktop/390px Kannada browser checks with screenshots.

## Partial / limitations

- **0 official rows**, 3 excluded fixture rows. Authentic government import is
  not demonstrated; official sites were inaccessible. CSV path is functional.
- **No deployed champion.** Real predict returns 503 `missing_model`; no fake price.
- Real sample counts are zero at 1/3/7d. All market metrics unavailable; holdout unopened.
- Offline historical replay is tested with isolated synthetic fixtures. Authentic
  offline demo needs genuine timestamped archives/frozen artifacts not bundled here.
- Kannada needs farmer/domain review. No Kannada voice was available in the manual
  browser; full text works. Raw notes/identifiers/export evidence retain source text.
- Accessibility lint/mobile checks are not formal WCAG or screen-reader certification.
- Runtime npm audit is clear; full development audit has 14 moderate findings
  associated with minimatch. See RELEASE-VERIFICATION.
- Dockerfiles/Compose are prepared; Docker is absent, so images/Linux/cloud are untested.
- Local git repo has no commits or remote. Ignored data/models/reports need separate transfer.

## Not implemented / not claimed

Verified official HTTP adapter, automatic live updates, authentic model deployment,
public hosting, authentication/rate limiting, multi-user tenancy, arrivals/weather
features, guaranteed buyer/price/profit, speech recognition, messaging integrations,
crop holding research, farmer transaction calibration, cumulative inventory
backtesting or offline service-worker installation.

## Acceptance gate

Local application, service communication, cash calculations, bilingual UI, tests
and production build pass. Authentic prices, validated real forecasts, real
out-of-sample metrics and authentic offline forecast demo remain **blocked by
missing authentic point-in-time data and artifacts**. Release verification returns
2 while these gates remain unmet.
