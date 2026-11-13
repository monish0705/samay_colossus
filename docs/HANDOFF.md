# Technical handoff · 2026-11-04

> Acquisition/model update: use MODEL-RESULTS.md, ACQUISITION.md and STATUS.md for
> the current state: 1,943 official records, six research-only baseline artifacts,
> actual final-period errors, 90 backend / 14 frontend / 3 HTTP tests passing.
> New implementation: app/research.py; scripts/archive_official_export.py,
> train_research_snapshot.py and report_research_results.py; research-registry.json;
> typed research evidence on models/status and the bilingual Transparency screen.
> Earlier zero-data statements below are superseded. Operational validated forecasts
> remain unavailable, and research models are explicitly rejected by that service.

Start with README, STATUS, RELEASE-VERIFICATION, EVALUATION and DEMO. Local
engineering checks pass; authentic data/model acceptance does not. Do not pitch
the isolated test baseline as an actually deployed agricultural model.

## Repository tree (source and operational artifacts)

```text
samay-agritech/
  .env.example  .gitignore  .dockerignore  README.md  ruff.toml  compose.yaml
  backend/
    pyproject.toml  requirements-lock.txt  alembic.ini  Dockerfile
    alembic/env.py
    alembic/versions/  # initial schema, source lineage/units, anonymous history
    app/
      main.py  config.py  db.py  models.py  readiness.py
      ingestion.py  prices.py
      features.py  analysis.py  forecasting.py  training.py
      reliability.py  backtesting.py  decision_backtesting.py  selling.py
      api_schemas.py  api_services.py  api_routes.py
  frontend/
    package.json  package-lock.json  vite.config.ts  vitest.e2e.config.ts
    eslint.config.js  tsconfig*.json  openapi.json  Dockerfile  nginx.conf
    src/
      App.tsx  MarketPages.tsx  AdvisorPage.tsx  Results.tsx  Demo.tsx
      Charts.tsx  ui.tsx  state.tsx  styles.css  main.tsx
      api.ts  config.ts  advisor.ts  explanations.ts  i18n.tsx  Speech.tsx
      locales/kn.ts  generated/api-schema.ts
      App.test.tsx  test/setup.ts  test/fixtures/*.json
    e2e/http.test.tsx
  scripts/
    setup_local.py  start_local.py  check_readiness.py  verify_release.py
    import_mandi_data.py  seed_demo.py  build_market_features.py
    train_forecasts.py  predict_price.py  backtest_forecasts.py
    backtest_decisions.py  optimize_selling.py  export_openapi.py
    run_e2e.py  container_start.py
  tests/
    test_backend.py  test_ingestion.py  test_features.py  test_forecasting.py
    test_reliability.py  test_selling.py  test_api_integration.py
    test_decision_backtesting.py  test_readiness.py  http_fixture_server.py
    fixtures/  # explicitly non-government CSV fixtures
  data/raw/  data/processed/  models/  reports/  # ignored operational outputs
  docs/
    STATUS.md  DEMO.md  JUDGES.md  DEPLOYMENT.md  EVALUATION.md
    RELEASE-VERIFICATION.md  HANDOFF.md  screenshots/*.jpg
    api.md  ingestion.md  features.md  forecasting.md  reliability.md  selling.md
    examples/  # labeled inputs and registry structure
```

## Final-integration changes

- Added startup/readiness service and historical replay configuration/date banner.
  Advisor and guided demo fetch configuration before submitting, fixing a race
  where a fast click could send today's date into a historical backend.
- Added realized decision backtest, source/code fingerprints, audit CSV/JSONL,
  cash/price mismatch reporting and deterministic settlement tests.
- Added real HTTP UI integration with imported temporary CSVs, frozen naive model
  and computed chronological interval calibration. Test files are explicitly
  synthetic and removed with their disposable database after the run.
- Added final naive/rolling-median comparison fields on identical holdout rows;
  no current authentic holdout was opened.
- Added Ruff and ESLint/accessibility lint; fixed unused imports and lint failures.
  Corrected a minimatch major override that broke ESLint's callable API usage.
- Added pinned backend environment, Windows setup/launch/verification scripts,
  Vite same-origin proxy, Docker/Nginx/Compose recipe and complete release docs.
- Reproduced Windows EPERM from reinstalling a loaded native CSS module; setup
  now detects repository Vite processes before installation. Clean reinstall and
  subsequent frontend/HTTP checks succeeded.
- Completed dashboard/Kannada components, deterministic explanations, risk
  previews, optional speech detection and browser verification from earlier stages.
- Preserved earlier foundation notes; no valuable code/data was discarded.

## Commands and tested outcomes

See RELEASE-VERIFICATION for exact commands/results and local JSON argv/log files.
82 backend tests, 13 frontend tests and 3 real-HTTP UI tests passed. Typecheck,
lint, migration/schema drift, package consistency and production build passed.
Authentic readiness failed as expected; the full development dependency audit
reported 14 moderate findings. Docker/cloud are untested.

## First next steps

1. Obtain a genuine official CSV and original source/unit evidence using
   ingestion.md. Preserve actual fetch times and original bytes. Confirm licensing.
2. Import into a separately backed-up operational SQLite database. Review quarantine,
   revision lineage, consistent variety/grade and actual availability times.
3. For historical decisions, obtain timestamped archived vintages. If these cannot
   be verified, start prospective collection and reserve later partitions. A new
   file's historical rows must not be assigned fabricated earlier fetch times.
4. Build a new versioned feature run and inspect effective sample/coverage gates.
   Keep the final chronological test untouched. Select on development/CV only.
5. Freeze champion, collect chronological calibration and assessment evidence,
   perform one final test, retain exclusive evaluation registry and compare baselines.
6. Configure actual paths in the explicit service registry. Run readiness, HTTP
   integration and authentic browser/offline demo. No placeholder registry is active.
7. Review Kannada/crop-storage assumptions with local farmers/agronomists, resolve
   development advisories, then test Docker/Linux and controlled deployment.

## Residual risks

Modal-price proxy is not farmer transaction realization. Cash is feasible against
entered quotes, not guaranteed market settlement. Spoilage/crop limits are explicit
assumptions, not agronomic measurements. No buyer, liquidity, disposal cost, grade
model or profit guarantee exists. Statistical regimes and interval coverage can
change. Local artifact hashes and one-shot locks rely on operational discipline.
SQLite and anonymous history need backup/retention policy before wider use.

The local git repository is initialized but has no commits or remote; no GitHub
repository was published. Review and make the initial commit before team transfer.
Raw/processed data, model binaries and generated reports are intentionally ignored;
transfer verified authentic artifacts separately. No authentic bundle exists here.
