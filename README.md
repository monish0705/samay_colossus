# SAMAY · Team Resonance · COLOSSUS 3.0

Cash-aware market decision support for five Karnataka crop/market series.
FastAPI + SQLite/Alembic, causal forecasting and empirical uncertainty, Decimal
sale optimization, and a responsive English/Kannada React dashboard.

**Current state, 5 November 2026:** fresh official OGD histories were obtained for
Copra, Arecanut, Onion and Potato, with reports through 3–4 November 2026. All four
now return saved research forecasts at 1/3/7 calendar days through the browser UI.
The database stores 3,938 official and 5,834 separately labeled secondary rows;
source overlaps are deduplicated for training/history, and demo data is excluded.
There are ten frozen short-horizon studies and 322 registered research serving
artifacts, including 292 new daily-horizon artifacts. Current series cover every
calendar day through Tomato 7, Copra 60, Arecanut 73, Onion 83 and Potato 84 days.
Most additions are explicitly predeclared last-price baselines; longer unsupported
dates stay unavailable. The new extension has no new untouched final test.

See [daily horizons and measured errors](docs/DAILY-HORIZONS.md) and
[cash-aware decisions with dated weather/news context](docs/SELL-HOLD-ADVISOR.md).
The advisor compares conditional hold plans with an immediate-sale fallback,
preserving cash, costs, storage loss and downside. Weather/news are reviewable
context, not unvalidated numeric price adjustments.

See [current crop training and measured errors](docs/CURRENT-CROP-MODELS.md) and
[the computed report](reports/current-crop-models.md). All champions remain
baselines in those frozen short-horizon final studies; advanced ML did not
consistently beat them. Sparse final sets have no
claimed reliable final score, calibrated intervals are unavailable for the new
series, and all models remain research-only with no guaranteed selling price.

See [additional data/model handoff](docs/SECONDARY-MODELS.md),
[actual errors and sample sizes](reports/corrected-model-readiness.md),
[original tomato comparisons](docs/MODEL-RESULTS.md), and
[initial engineering corrections](docs/CORRECTIONS.md).

## Windows two-command setup and launch

Prerequisites: Python 3.12 recommended (3.11+ source requirement), Node.js 22.12+
and Git. Tested Python 3.12.10, Node 24.20.0, npm 11.19.0. Open PowerShell at the
repository root; no activation or execution-policy change is required.

```powershell
python scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/start_local.py --enable-research
```

Setup installs pinned Python packages and `npm ci`; it needs internet and preserves
existing `.env` files. Stop repository Vite previews before repeating setup on
Windows; an early check prevents locked native-module installation failures.
Startup needs no downloads, applies migrations, starts/reuses
backend `http://127.0.0.1:8010` and frontend `http://127.0.0.1:5173`, and checks
the API contract. Ctrl+C stops only children it launched. Swagger: backend `/docs`.
Health is process liveness, not forecast readiness. Restart existing listeners
after code/configuration changes.

For fresh ports and optional hourly internet context refresh:

```powershell
.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8011 --frontend-port 5174 --enable-research --refresh-context
```

Omit `--refresh-context` for offline operation with prepared authentic history
and saved models. Cached context expires visibly; this flag does not update mandi
price observations. No live market-price feed is implied.

The launcher uses a same-origin `/backend` Vite proxy. Independent terminals:

```powershell
# Terminal 1, repository root
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010
# Terminal 2, repository root
Set-Location frontend
$env:VITE_API_BASE_URL = '/backend'
$env:SAMAY_BACKEND_URL = 'http://127.0.0.1:8010'
npm.cmd run dev
```

Use `scripts/start_local.py --backend-port 8012 --frontend-port 5175` for fresh
ports. `--check` verifies existing services without launching/stopping them.
`SAMAY_CORS_ORIGINS` accepts a JSON origin array for direct cross-origin clients.

## Release verification

```powershell
.\.venv\Scripts\python.exe scripts/verify_release.py
```

Runs migrations/schema drift, backend lint/tests, dependency consistency, frontend
tests/types/accessibility lint/build, real HTTP integration, npm audits and
authentic data/model readiness. Exact argv, directories, exit codes and logs go to
`reports/release/verification.json`. Exit 2 means a release gate remains open.
Currently engineering checks pass; authentic readiness fails and the full
development audit reports moderate advisories. See [verification](docs/RELEASE-VERIFICATION.md).

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m ruff check backend scripts tests
.\.venv\Scripts\python.exe scripts/run_e2e.py
.\.venv\Scripts\python.exe scripts/check_readiness.py
Set-Location frontend
npm.cmd test
npm.cmd run typecheck
npm.cmd run lint
npm.cmd run build
npm.cmd audit --omit=dev
```

HTTP integration uses a disposable SQLite database, explicitly synthetic TEST_ONLY
CSV imports, a saved baseline, computed chronological calibration residuals and
the real optimizer. It never seeds the workspace with those observations and
provides no evidence of real market performance.

## Data and honest interpretation

[Ingestion](docs/ingestion.md) explains official CSV download, provenance, units,
quarantine and revisions. No HTTP endpoint/key is guessed. Never relabel fixtures
or backdate fetch timestamps. A newly downloaded historical file does not establish
earlier availability: defensible replay requires timestamped source vintages.

[Features](docs/features.md), [forecasting](docs/forecasting.md),
[reliability](docs/reliability.md) and [evaluation](docs/EVALUATION.md) document
causal targets, chronological partitions/CV, one-shot holdout safeguards, actual
metrics availability and decision backtesting. [Selling](docs/selling.md) explains
net settlement, mandatory cash/storage/lot constraints and downside objectives.

Money is INR, prices INR/quintal, quantity quintals. Mandi modal prices are wholesale
observations, not guaranteed farmer realization. Observed min/max are not prediction
intervals. Future prices are uncertain; the farmer makes the final decision.

## Handoff

- [DEMO](docs/DEMO.md): guided bilingual flow, storage/adverse/infeasible scenarios, offline preparation.
- [JUDGES](docs/JUDGES.md): architecture, differentiation, provenance and hard questions.
- [DEPLOYMENT](docs/DEPLOYMENT.md): local/offline operation and untested Docker recipe.
- [HANDOFF](docs/HANDOFF.md): file tree, changes, remaining work and acceptance gates.
- [API](docs/api.md): all nine endpoints, schemas, error codes and model registry.

Official datasets, six research model artifacts, generated evaluation reports and
a portable database are included in this repository. Startup restores
`data/prepared/samay.db` only when the default local database does not exist; it
checks the bundled hash and never overwrites an existing database. The prepared
copy has empty recommendation history and repository-relative source paths.
`.env.example` enables the bundled research registry for the Transparency screen.
These remain explicitly retrospective research artifacts, not validated live models.

Secrets, dependency folders, caches, local database backups and credential-bearing
website/debug downloads stay excluded. The repository is published at
https://github.com/monish0705/prototype; no hosted application deployment is claimed.
Earlier foundation notes are preserved in [foundation-notes](docs/foundation-notes.md).
