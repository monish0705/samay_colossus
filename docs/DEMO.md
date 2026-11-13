> Updated data/model status: see [SECONDARY-MODELS](SECONDARY-MODELS.md). The initial missing-history statements and earlier verification counts below are historical.

# Current research demo — 5 November 2026

Use `python scripts/setup_local.py`, then `.\.venv\Scripts\python.exe scripts/start_local.py`.
The sample environment explicitly enables the saved research registry. Follow
`docs/CORRECTIONS.md` if an existing `.env` needs the new entries.

1. Open Dashboard: verify official source/report dates, not fabricated live prices.
2. Select Kolar APMC / Tomato / tomato / local. On Forecast request 3 days.
   The saved mean-14 baseline currently returns limited-evidence research output,
   with dated source lineage and a retrospective empirical band. A stale/missing
   dataset must produce an explicit error. No guaranteed farmer realization is implied.
3. Open Advisor and load the labeled 20-quintal, INR 10,000-cash example. This is
   illustrative farmer input. Calculate with zero storage: the real backend selects
   a feasible immediate sale and exposes its cost ledger.
4. Enable holding, enter an actual or explicitly illustrative storage quote/loss
   assumption and future-price scenario. Examine the separate scenario-best plan,
   its immediate cash and adverse outcome. Limited research does not authorize
   confident operational holding advice.
5. Lower the future scenario price or increase costs and recalculate; compare the
   resulting backend figures. Turn storage off and verify held quantity is zero.
6. Switch Kannada/English: amounts must stay identical. Inspect Transparency and
   `reports/corrected-model-readiness.md`; explain the source-vintage limitations.

This flow works offline with prepared data/artifacts and installed dependencies.
The last complete source date is 31 October 2026; forecasts must reject stale inputs
once the freshness limit is exceeded. Do not freeze the clock silently. Any later
historical replay must be explicitly configured and visibly labeled.

The following original guide is retained as historical context; current availability
and errors are governed by the status above.

# SAMAY demonstration

> Update: 1,943 official records are now imported and six research-only champions
> are saved. Dashboard shows actual Tomato/Local history; Transparency shows the
> computed retrospective results. See MODEL-RESULTS.md and STATUS.md. The earlier
> zero-data walkthrough below describes the pre-acquisition release. Validated live
> forecasts remain unavailable; research errors do not enable confident holding.

Current workspace has 0 official observations and no model. The interactive
fallback walkthrough calls the backend; it is not an authentic-price forecast demo.

## Prepare

```powershell
python scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/start_local.py
# In another PowerShell, repository root:
.\.venv\Scripts\python.exe scripts/check_readiness.py
```

Open `http://127.0.0.1:5173`. Readiness currently exits 2. Do not hide this.
Local farmer UI assets have no CDN requirement. Swagger's default CDN assets may
need internet. Keep authentic archives, SQLite, registry and artifacts on-machine
if a real offline bundle has separately been prepared.

## 90-second flow

Click **90-sec demo**; actions make actual API requests.

| Time | Action | Explain |
| --- | --- | --- |
| 0–15s | Dashboard / refresh | Connection, official count and source date. Current count: 0. |
| 15–30s | Insights / retrieve history | Real observations when present; current honest empty state. |
| 30–45s | Forecast / check 3d service | Prepared model: dated prediction/version/interval. Currently `missing_model`, no number substituted. |
| 45–60s | Advisor / labeled example | 20 qtl, ₹1,000/qtl buyer quote, ₹10,000 cash; illustrative assumptions. |
| 60–75s | Calculate | Actual immediate sale 20 qtl, hold 0, net ₹18,700; ledger and source warning. |
| 75–90s | ಕನ್ನಡ / transparency | Same values; expand “Why this recommendation?”, show limitations. |

Example math: ₹20,000 gross − ₹1,000 commission − ₹300 transport (₹100 trip +
₹10 × 20 qtl) = ₹18,700. This is example-quote arithmetic, not real market income
or a fixed recommendation for all farmers.

## Edge scenarios

1. Explorer → labeled example → capacity 0 → **Recalculate with backend**. Hold is 0.
2. Required cash ₹50,000 → recalculate. Show explained infeasibility; no constraint relaxation.
3. Restore ₹10,000; adjust buyer quote/costs, recalculate and inspect the actual ledger.

With a prepared forecast, enter nonzero storage, verified crop limit, daily loss
and storage charges, horizon, realization factor and adverse price at/below the
forecast lower bound. Recalculate. In Results toggle **Conservative**, **Central**
and **Adverse** scenario: only backend amounts are displayed. A preview toggle does
not change the selected plan. Change risk/assumptions in Explorer and recalculate.
Currently missing forecasts prevent confident holding; show the safe fallback
instead of inventing an adverse forecast. Rising/falling/flat test scenarios are
unit tests, not authentic market outcomes.

## Prepared authentic offline replay

First obtain real timestamped vintages, frozen champions and earlier empirical
evidence per HANDOFF/EVALUATION. Never backdate a new download. Registry paths and
archive/model hashes must resolve locally.

```powershell
$env:SAMAY_ENVIRONMENT = 'development'
$env:SAMAY_SERVICE_REGISTRY_PATH = 'service-registry.json'
$env:SAMAY_HISTORICAL_DEMO_DATE = Read-Host 'Verified archived decision date (YYYY-MM-DD)'
.\.venv\Scripts\python.exe scripts/check_readiness.py
.\.venv\Scripts\python.exe scripts/start_local.py
```

Restart services after changing configuration. The UI shows **HISTORICAL REPLAY —
not live market data**, also translated, with the archived date. Prediction and
advisor requests use that historical clock. Production rejects replay. Once
dependencies/artifacts are prepared, disconnect internet and repeat the flow.
Missing/stale evidence remains visible. This authentic offline demo has not been
completed in the present workspace.

## Captured evidence

`screenshots/results-en.jpg`, `results-kn-mobile.jpg`, `results-kn-cash.jpg` show
actual backend example output, source warning and identical ₹18,700 amounts.
These are no-forecast, user-quote results. Disposable HTTP reproduction:
`.\.venv\Scripts\python.exe scripts/run_e2e.py`.
