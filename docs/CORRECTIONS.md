> Updated data/model status: see [SECONDARY-MODELS](SECONDARY-MODELS.md). The initial missing-history statements and earlier verification counts below are historical.

# Corrected data and forecasting workflow — 5 November 2026

Work is on `sub2`. The farmer/judge layout and commodity selectors are retained.
Generated prices, unsupported model claims, hardcoded weather/festival adjustments,
unverified warehouse listings and locally calculated storage recommendations were removed
from operational flows. Both prediction and recommendation now use the same service.

## Data obtained and preserved

- 1,943 complete government observations from the six original Kolar/Tomato annual
  exports, 2021–2026. Original bytes, hashes, grades and actual fetch times are retained.
- 67 current modal-only observations from the official public AGMARKNET last-week
  endpoint: Tomato 5, Arecanut 30, Copra 8, Onion 12, Potato 12, across reported varieties.
  Original JSON, filters and SHA256 manifests are under `data/raw/official-multi-recent/`.
  These may overlap existing history; they are not 67 newly imported complete records.
- 7,304 legacy random observations were reclassified as `demo`, with their original
  provenance claims retained only for audit. No authentic prices were removed.
- Non-tomato historical daily exports are still missing. A week of modal observations
  without grade/min/max does not establish historical training viability. No missing
  fields, calendar dates, arrivals or historical publication times were invented.

Browser automation was stopped because it could not identify the current browser URL
reliably. Direct public downloads succeeded. The data.gov.in resource pages retrieved
during this attempt did not expose a usable historical CSV link. No CAPTCHA or browser
safety barrier was bypassed.

## Windows setup and run

Run from this repository root:

```powershell
python scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/start_local.py
```

The sample `.env` explicitly enables limited-evidence research inference and points to
`research-serving-registry.json`. For an existing `.env`, set these entries manually:

```dotenv
SAMAY_ENABLE_RESEARCH_FORECASTS=true
SAMAY_RESEARCH_REGISTRY_PATH=research-registry.json
SAMAY_RESEARCH_SERVING_REGISTRY_PATH=research-serving-registry.json
```

This does not enable validated advice. Missing artifacts, stale data, unknown
variety/grade and unsupported forecast horizons still fail clearly.
Startup also repairs the identified legacy synthetic batch in existing local SQLite
databases. It preserves authentic data and recommendation history.

## Collect, import, refit and reproduce metrics

```powershell
.\.venv\Scripts\python.exe scripts/collect_official_data.py
.\.venv\Scripts\python.exe scripts/repair_data_provenance.py
.\.venv\Scripts\python.exe scripts/prepare_research_service.py
.\.venv\Scripts\python.exe scripts/report_model_readiness.py
```

`prepare_research_service.py` verifies frozen selection reports, refits only their
previously selected configurations on the available authentic series, and saves
six hash-pinned research artifacts. It does not retune against consumed final tests.
Naive and rolling baselines have no learned coefficient arrays; `model.pkl` can
legitimately contain `None`. The algorithm, feature schema, sample count, training
window, source fingerprint and original evaluation reference are saved in metadata.

Measured errors and sample sizes are in `reports/corrected-model-readiness.md` and
its JSON companion. Those metrics reproduce the original consumed chronological
holdouts. They are not a new independent evaluation of the refits. In particular,
the selected Local/3d rolling mean had higher final MAE than naive. No model was
swapped after inspecting that final outcome.

Empirical interval diagnostics use an earlier calibration subset, seven-day block
maximum residuals, a horizon embargo, and a later diagnostic subset of the already
reported retrospective predictions. This secondary analysis is explicitly labeled;
it is not a new untouched test, a probability of farmer profit or guaranteed coverage.
Learned models do not receive transferred calibration after refitting.

## Obtain the remaining authentic history

Use `https://agmarknet.gov.in/daily-price-and-arrival-report`. Select Karnataka and
the exact official market/crop, request annual exports for 2021 onward, and retain
all original varieties and grades for inspection:

| Crop | Official market selector | Normalized importer market |
|---|---|---|
| Arecanut(Betelnut/Supari) | Shimoga APMC | Shivamogga Mandi |
| Copra | Tiptur APMC | Tiptur APMC |
| Onion | APMC Hubballi | Hubballi APMC |
| Potato | Bengaluru APMC | Bengaluru APMC |

MAMCOS is not silently merged with the government Shimoga APMC series.
For each downloaded file, use `scripts/archive_official_export.py --file` with
its real local filename and `--year`, `--market`, `--commodity`. Then pass the
resulting CSV and manifest to `scripts/import_mandi_data.py`. Scope, district,
dates, min/modal/max ordering and units are checked, suspicious rows quarantined,
and hashes/fetch times preserved. `train_research_snapshot.py` now accepts
`--market` and `--commodity`; use an explicitly observed consistent variety/grade,
development/validation dates and a genuinely new untouched final interval.
It refuses to reuse a consumed final holdout for new model selection.

Do not run the retired population generator. It now exits without changing data.

## Forecasts and recommendations

- `POST /api/v1/predict`: validated saved deployment first; explicitly enabled saved
  research artifact second. Research status remains `limited evidence` with source
  and calibration limitations. No price is returned from empty/missing inputs.
- `GET /api/v1/models/status`: actual deployments and research artifacts are separate.
  Research artifacts do not set `reliability_evidence_configured=true`.
- `POST /api/v1/recommend`: same prediction service; Decimal costs, mandatory cash,
  storage and market-lot constraints remain enforced. Limited research cannot qualify
  a confident hold recommendation. The best feasible scenario-only plan is shown
  separately from the operational safe fallback.
- An explicit `scenario_price_inr_per_quintal` supports user-assumption analysis for
  storage durations up to the configured crop limit, including 60/730 days. It is
  never presented as a supported long-horizon model forecast. Adverse must be no
  greater than the central scenario. Zero-loss assumptions remain zero.
- The fabricated multi-factor and warehouse GET routes now return 410; negative
  durations return 422. Use the validated request schemas and real quoted costs.

## Verification

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
.\.venv\Scripts\python.exe -m ruff check backend scripts tests
.\.venv\Scripts\python.exe -m pytest -q
npm --prefix frontend test
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run build
.\.venv\Scripts\python.exe scripts/run_e2e.py
```

The HTTP harness uses explicitly synthetic, isolated test data to test wiring.
An additional integration test imports actual archived government CSVs and exercises
the real saved research artifact, interval output and optimizer together. No test
fixture is used as a genuine market observation or performance claim.
