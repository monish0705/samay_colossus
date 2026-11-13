# Prompt 5 verification — 2026-11-04

Files added: backend/app/reliability.py, backend/app/backtesting.py,
scripts/backtest_forecasts.py, tests/test_reliability.py, docs/reliability.md and
this verification record. README.md links to the new workflow. No database schema,
frontend code, candidate selection algorithm or final-evaluation registry changed.

## Commands and observed results

PowerShell from repository root:

```powershell
.\.venv\Scripts\python.exe scripts/backtest_forecasts.py --feature-run reports/samay-features-v1-78a0e500308b86f0 --calibration-start 2025-01-01 --calibration-end 2025-06-30 --evaluation-end 2025-09-30
Write-Output "Backtest CLI exit code: $LASTEXITCODE"
```

Final artifact-producing run:

```text
STATUS: insufficient_data
horizon=1d calibration_n=0 unseen_pairs=0 metrics=None
horizon=3d calibration_n=0 unseen_pairs=0 metrics=None
horizon=7d calibration_n=0 unseen_pairs=0 metrics=None
REPORT: reports\backtests\samay-reliability-v1-bed1a8a92afac35e\summary.json
Final holdout: unopened. Nominal interval levels are not confidence guarantees.
Backtest CLI exit code: 2
```

The versioned directory contains six calibration/evaluation CSV files, four PNGs
and summary.json. CSV rows retain decision dates and unavailable/missing-target
flags; no null outcome is converted into a zero error. All price/error columns
are INR/quintal. Older development report versions remain separately archived;
use bed1a8a92afac35e for the final code. The predicted-vs-actual PNG was visually
inspected: it explicitly reports unavailable authenticated pairs, with no invented
points, price values or performance curves.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_reliability.py -q
```

Latest targeted result: `6 passed in 6.78s`. Tests cover future observations and
late revisions, missing/delayed actuals, sparse/stale/unsupported requests, volatility,
nested ordered intervals, naive benchmarking on identical dates, calibration/assessment
separation, retrospective reliability gating, drift/large-error downgrades, artifact
tamper rejection, final-holdout refusal and reproducible insufficient-data outputs.
Test observations are deterministic, local and explicitly test-only; their computed
coverage or prices are never reported as SAMAY market performance.

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```text
41 passed, 1 warning in 84.76s (0:01:24)
```

The warning is the existing Starlette TestClient HTTPX deprecation. The latest
audit-column additions were also exercised by the targeted six-test rerun above.

The public reliable_forecast function was called using the documented example
plan, real SQLite session, origin 2026-11-04 and horizon 3. Its actual response:

```json
{
  "schema_version": "samay-reliability-v1",
  "prediction_inr_per_quintal": null,
  "intervals": [],
  "horizon_calendar_days": 3,
  "timestamp": "2026-11-03T18:30:00+00:00",
  "target_date": "2026-11-07",
  "model_version": null,
  "reliability_status": "unavailable",
  "flags": ["sparse_history", "no_official_observations"],
  "market": "Kolar APMC",
  "commodity": "Tomato",
  "variety": "local",
  "grade": "faq",
  "latest_report_date": null,
  "observation_age_calendar_days": null,
  "data_source": {
    "sources": [],
    "development_ledger_dispositions": {},
    "provenance": "Official operator-attested manifests and SHA256-verified local archives; independent publisher authentication not established by this pipeline"
  },
  "disclaimer": "Empirical uncertainty for mandi modal wholesale prices only. Coverage is not guaranteed. This does not capture individual farmer grade, quality, sorting, fees, transport, bargaining or transaction-price uncertainty, and is not a guaranteed realized selling price or advice to hold produce."
}
```

Timestamp is 00:00 Asia/Kolkata on the requested origin, expressed as aware UTC.
This is an actual unavailable response, not a fabricated held-out forecast example.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
git diff --check
```

```text
No broken requirements found.
No new upgrade operations detected.
```

Whitespace check emitted no errors. No new dependencies were needed; matplotlib
and the prior forecasting stack are reused. Frontend tests were not rerun because
no frontend implementation changed.

## Unresolved acceptance and handoff

Real held-out example forecasts, error statistics, coverage and widths cannot be
shown because authenticated historical official data remains absent from Prompt 2.
The module functions and tests pass, but this real-data acceptance requirement
remains unverified. Current official-data output is intentionally insufficient_data.

Obtain authenticated point-in-time source snapshots. Predeclare a fixed baseline
or champion selected before calibration, chronological calibration and a later
assessment window. Rerun, inspect actual pairs and empirical interval diagnostics,
and retain audit artifacts. The existing final holdout remains unopened; this
development assessment is not a second final test. No Prompt 6 work was started.
