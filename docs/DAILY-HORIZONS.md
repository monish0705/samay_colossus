# Crop-specific daily forecasting — 5 November 2026

The saved service now accepts an exact integer calendar horizon, with a separate
artifact for every supported day. It does not extrapolate a three-day forecast
to a year or recursively feed predicted prices into future lag features.

| Current series | Saved days, inclusive | Application planning ceiling |
|---|---|---:|
| Tomato / Kolar APMC / tomato / local | Every day 1–7 | 7 |
| Copra / Tiptur APMC / other / local | Every day 1–60 | 365 |
| Arecanut / Shivamogga Mandi / rashi / local | Every day 1–73 | 730 |
| Onion / Hubballi APMC / puna / local | Every day 1–83 | 120 |
| Potato / Bengaluru APMC / local / medium | Every day 1–84 | 180 |

Planning ceilings are software limits, not verified shelf lives or forecast
availability. Longer dates failed the declared evidence policy. They remain
available only as explicitly entered scenario assumptions. There is no credible
model for every future date; more consistent, authenticated history is needed.
Older unspecified grades are not silently merged with the current graded series.

## What was saved

292 new daily artifacts join the existing 30 serving artifacts: **322 registered**.
Of the additions, 274 use the predeclared last-observed-price rule because
separated selection evidence is inadequate. Eighteen underwent development
selection: seventeen selected rolling baselines and one selected regularized
return regression for Onion at 11 days. This is development evidence, not proof
that ML improved final test performance. No LightGBM superiority is claimed.

A fixed last-price rule may give the same number at several horizons. That is
the declared baseline behavior, not a fabricated upward price trend.

## Evidence and leakage controls

- Each market, commodity, variety and grade stays separate. Raw archives,
  actual download timestamps and SHA256 pins are retained.
- These are retrospective research snapshots. Historical publication and revision
  times are unverified; next-day availability is an explicit research assumption.
- New model selection opens only development observations through **15 September
  2026**. The previously consumed final period is excluded. There is **no new
  untouched final accuracy claim** for these additions.
- Features use only reports strictly earlier than each decision date. Labels
  match exactly decision date + horizon; missing dates are excluded, not filled.
- Training labels settle before validation begins. Three chronological CV folds
  have disjoint validation targets and horizon-specific purging of training labels.
- Learned candidates require 120 training and 30 selection validation examples,
  at least 180 training calendar days, and three eligible folds. Promotion must
  beat all core baselines in at least two folds and the best validation baseline.
- Where selection is impossible, the fixed persistence rule requires at least
  60 exact development pairs, a 90-day origin span and three nonoverlapping cases.
  Three cases are a minimal research fallback gate, **not strong validation**.
- Ordinary daily errors overlap and are dependent. Reports expose nonoverlapping
  counts. New empirical intervals are unavailable; user stress bounds are not
  prediction intervals or confidence percentages.
- Runtime refitting occurs only after configurations and evaluation rows freeze.
  A saved artifact cannot be used before its actual creation time. Stale inputs
  still fail; a longer horizon does not excuse stale market prices.

## Computed errors

[Full computed report](../reports/daily-horizon-results.md) includes MAE, RMSE,
WAPE, sample counts, reasons for unavailable dates and model identities.
Thirty-day fixed-rule retrospective benchmarks are:

| Crop | MAE INR/quintal | WAPE error | Dated pairs | Nonoverlapping cases |
|---|---:|---:|---:|---:|
| Copra | 1,337.40 | 7.13% | 131 | 5 |
| Arecanut | 1,922.10 | 3.67% | 130 | 7 |
| Onion | 325.61 | 16.51% | 164 | 8 |
| Potato | 316.30 | 21.38% | 184 | 8 |

These are **research baseline errors, not new final-test accuracy**. Selection
validation errors elsewhere participated in model choice and are optimistic as
performance estimates. WAPE is error; 100 minus WAPE is not an accuracy score.
Original short-horizon final evaluations remain unchanged in
[CURRENT-CROP-MODELS](CURRENT-CROP-MODELS.md).

## Reproduce and run on Windows PowerShell

From the repository root, after `python scripts/setup_local.py`:

```powershell
.\.venv\Scripts\python.exe scripts/train_crop_horizons.py --register
.\.venv\Scripts\python.exe scripts/report_crop_horizons.py
.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8011 --frontend-port 5174 --enable-research --refresh-context
```

Repeated training reuses the frozen run when source, code and policy fingerprints
match. It does not reopen final tests. Stop this repository's existing launcher
before starting updated code. The optional context collector uses internet; omit
`--refresh-context` for offline operation with prepared data/models. Cached
external evidence ages visibly. Context refresh does not update mandi prices.

```powershell
$body = @{market='Tiptur APMC'; commodity='Copra'; variety='other'; grade='local'; horizon=30} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:8011/api/v1/predict -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod 'http://127.0.0.1:8011/api/v1/models/horizons?market=Tiptur%20APMC&commodity=Copra&variety=other&grade=local&horizon=365'
.\.venv\Scripts\python.exe scripts/verify_sell_hold.py
```

Observed browser result on 5 November: Copra 30-day baseline **INR 18,500/quintal**,
target **5 December 2026**, latest report **3 November 2026**. This is an uncertain
wholesale point forecast, not a current buyer quote or a promised selling price.
The same value appeared in English and Kannada. A 365-day request displayed an
unavailable state and no invented forecast.

## Checks actually executed

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 134 passed; Starlette/httpx deprecation warning |
| `npm.cmd --prefix frontend test` | 24 passed |
| `npm.cmd --prefix frontend run typecheck` | exit 0 |
| `npm.cmd --prefix frontend run lint` | exit 0 |
| `npm.cmd --prefix frontend run build` | exit 0; bundle-size advisory above 500 kB |
| `.\.venv\Scripts\python.exe -m ruff check backend scripts tests` | exit 0 |
| `.\.venv\Scripts\python.exe scripts/run_e2e.py` | 3 passed on isolated rerun |
| `.\.venv\Scripts\python.exe scripts/verify_sell_hold.py` | 9 actual HTTP cases passed |
| `.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check` | No new upgrade operations detected |
| `.\.venv\Scripts\python.exe -m pip check` | No broken requirements found |

The first concurrent HTTP test run timed out under load. Its output is preserved
in `reports/daily-http-e2e.initial-timeout.log`; the isolated rerun passed without
changing the timeout or substituting fake responses. Exact outputs are in the
`reports/daily-*.log` files and `reports/sell-hold-live-verification.json`.

The final actual HTTP smoke test checked imported history and the maximum saved
horizon for all five crops: every request returned 200 with numeric prices and
real source dates. Copra at 365 days returned 503 `insufficient_horizon_evidence`.
See `reports/daily-live-smoke.json`. Models status now distinguishes configured
research artifacts from absent models and validated production models.

A temporary isolated Git index verified **2,039 hash-sensitive files with zero
byte mismatches**, preserving the user's staging area. The attribute migration
requires the following when publishing; do not normalize raw evidence bytes:

```powershell
git add --all
git add --renormalize -- data models reports research-registry.json research-serving-registry.json
```

These changes and their saved model/data artifacts are included on branch `sub2`.

Main files: `backend/app/crop_horizons.py`, `scripts/train_crop_horizons.py`,
`scripts/report_crop_horizons.py`, API schemas/services/routes, research inference,
forecast/advisor UI, bilingual copy and `tests/test_crop_horizons.py`.

```text
backend/app/
  crop_horizons.py       causal daily horizon construction and model comparison
  decision_support.py    conditional risk/cash decision summaries
  market_context.py      dated weather/calendar/news integrity and availability
  research_service.py    saved hash-pinned research inference
scripts/
  train_crop_horizons.py
  report_crop_horizons.py
  refresh_market_context.py
  verify_sell_hold.py
frontend/src/
  DecisionPanel.tsx
  AdvisorPage.tsx
  MarketPages.tsx
  Results.tsx
  locales/kn.ts
models/crop-horizons/<frozen-run>/
  comparison.json
  development-predictions.csv
  champion-<horizon>d/{model.pkl,metadata.json}
data/context/<capture>/
  snapshot.json
  source-*.dat
reports/
  daily-horizon-results.{md,json}
  daily-live-smoke.{log,json}
  daily-*.log
  sell-hold-live-verification.{log,json}
  screenshots/
tests/test_crop_horizons.py
docs/{DAILY-HORIZONS,SELL-HOLD-ADVISOR,STATUS,DEMO}.md
```

Next: collect more same-grade history and prospective source vintages, reserve
a genuinely future evaluation period, assess each longer horizon prospectively,
then calibrate intervals. Weather/festival/news effects require historically
timestamped features and independent ablation tests before entering price models.
