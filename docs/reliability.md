# Forecast reliability and empirical uncertainty — Prompt 5

## Current result

No authenticated historical government observations or market-trained champion
exist in this workspace. The real-data command therefore writes an insufficient-data
report with **0 calibration residuals and 0 unseen prediction/actual pairs at 1, 3
and 7 days**. Actual MAE/coverage/interval width are absent, not fabricated.
No sample market results sourced from genuine held-out observations can be shown
until that prerequisite is met. Deterministic test cases are not market evidence.

## Reproduce on Windows PowerShell

From repository root:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,analysis,forecast]'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/backtest_forecasts.py --feature-run reports/samay-features-v1-78a0e500308b86f0 --calibration-start 2025-01-01 --calibration-end 2025-06-30 --evaluation-end 2025-09-30
$LASTEXITCODE
.\.venv\Scripts\python.exe -m pytest tests -q
```

These dates use the existing example development plan; they do not claim authentic
data availability. For a new feature run substitute its printed ARTIFACTS directory.
Exit 2 means insufficient data, 1 means operational/configuration/integrity failure,
and 0 means at least one horizon has actual assessment pairs. Exit 0 alone is not
proof of interval calibration or validated reliability; inspect residual counts,
block counts, flags and coverage evidence.

Default is a **predeclared last-observed-price baseline**, not a newly promoted
champion or an untrained ML model. To backtest real saved models, add
`--champions models/forecasts/ACTUAL_EARLIER_RUN`. That directory must contain all
three horizon artifacts, match scope/schema, pass hash verification, and have been
trained/selected strictly no later than calibration_start. A champion selected using
the later assessment period is rejected. Missing champion artifacts fail rather
than silently substituting another algorithm. Use a feature plan with a subsequent
development assessment period if the existing champion was frozen later.

## Chronological protocol and final-test boundary

The command intentionally uses only the feature plan's **development** period.
Calibration ends before assessment begins; evaluation_end cannot exceed the frozen
validation_end. It refuses final-holdout dates, does not invoke the final-data loader,
and leaves Prompt 4's one-shot final-evaluation registry intact. This assessment
window is held out from calibration and, for a supplied champion, model selection.
It is not mislabeled as a new untouched final test if it has previously been used
for development decisions. Final uncertainty evaluation must be predeclared and
integrated with a future one-shot final-evaluation operation, never repeatedly
reopened to tune interval widths or policies after seeing test coverage.

At each calendar origin D, decision time is 00:00 Asia/Kolkata. Only report dates
strictly before D and source snapshots fetched by that timestamp can supply
features, latest prices or volatility flags. Fixed champion weights/configuration
are used; no retrospective retraining on assessment outcomes occurs. A predeclared
naive baseline has no fitted parameters. This is rolling-origin, fixed-model
assessment with expanding historically available input history, not random splitting.

Predictions are constructed without target values as inputs. Scoring attaches the
price for exactly D+h, frozen as known before partition_end+1. Missing targets and
target dates beyond that partition are marked, never filled from a nearby date.
Later revisions do not become available before their source capture times. A
historical CSV downloaded after a decision cannot be backdated into its features.
Source authenticity retains the operator-attestation limits documented in ingestion.md.

## Empirical interval method

For each horizon/model separately, collect chronological out-of-sample calibration
absolute errors. Require >=30 resolved errors and >=8 seven-calendar-day blocks.
Take the maximum error per block, then the empirical higher quantiles at .8 and
.9 of those block maxima. An interval is `[max(0, prediction − radius), prediction + radius]`.
It is ordered, nonnegative and nested across nominal levels. The block length,
sample gates and quantile method are fixed before assessment and recorded in policy.

Block maxima reduce optimism caused by nearby/overlapping forecast errors, but do
not prove residual independence, stationarity or exchangeability. The method can
be conservative and wide; it **does not guarantee 80% or 90% future coverage**.
Nominal levels are labels for empirical bands, not a probability that a particular
farmer will receive that price. The source mandi's observed min/max are never used
as prediction intervals. Sparse calibration returns no interval rather than a
fabricated uncertainty number.

Widths are frozen before assessment. Reports measure empirical coverage and mean
width only on later actual/prediction pairs. They report the evaluation sample count
even when small; small estimates must not be treated as reliable coverage evidence.
No nominal coverage claim is substituted for a measured coverage value.

## Reliability service contract

```python
from datetime import date
from pathlib import Path
from app.db import SessionLocal
from app.training import read_plan
from app.reliability import reliable_forecast

plan, _ = read_plan(Path('reports/samay-features-v1-78a0e500308b86f0'))
with SessionLocal() as session:
    response = reliable_forecast(
        session, plan, date(2026, 11, 4), 3,
        evidence_folder=None,  # use an actual matching saved backtest directory when present
        champion=None,         # explicit predeclared naive baseline; no claimed trained model
    )
    print(response.model_dump_json(indent=2))
```

The stable Pydantic response includes schema version, numeric prediction or null,
80%/90% nominal empirical bounds when supported, horizon, aware decision timestamp,
target date, model version, scope, freshness, flags, source metadata and disclaimer.
The public service loads scoped official ledger observations itself. It accepts no
arbitrary caller-supplied training prices. Optional champion artifacts must satisfy
their historical availability and exact series/horizon checks.

`evidence_folder` must match scope, model version, horizon and current policy and
pass artifact hashes. Calibration cannot be used before its freeze time. Only
assessment errors with actual availability strictly before the requested origin
can establish historical reliability/drift; later scoring rows are not consulted
for those diagnostics. File integrity/policy failures return unavailable with an
invalid-evidence flag and no prediction/interval. Database/source-integrity failures
remain explicit exceptions; callers must not replace them with a fake forecast.

Status policy, applied in priority order:

| Status | Meaning |
| --- | --- |
| unavailable | Unsupported horizon/series, no usable observations, fewer than two prior observations, unavailable champion, or invalid reliability artifacts. Prediction and bands are null/empty. |
| stale data | Latest known report is more than 7 calendar days old. Prediction and bands are suppressed. |
| limited evidence | Point forecast can be computed, but any evidence/sample/diagnostic requirement below fails. Missing calibration yields no bands. |
| validated | All checks pass: >=60 unseen resolved errors spanning >=60 origin days; empirical coverage at both levels is no more than 10 percentage points below nominal; no adverse flags. This is a documented empirical status, not certification or guaranteed future performance. |

Flags include:

- `sparse_history`: fewer than 30 prior available report dates. With >=2 fresh
  dates the explicit naive baseline can still return a limited-evidence point
  forecast; insufficient champion feature history abstains instead.
- `stale_data`, `unsupported_horizon`, `unsupported_series`, no official observations,
  champion unavailable at decision, and invalid reliability evidence.
- `excessive_volatility`: sample std of the last up to 29 consecutive observed
  returns >20%, requiring >=7 returns. Gaps are unequal; this is not daily volatility.
- `model_drift`: mean of last 20 resolved assessment absolute errors exceeds twice
  calibration MAE plus INR 1/quintal. This is a heuristic diagnostic, not a formal
  distribution-shift hypothesis test.
- `large_recent_forecast_errors`: last-five mean absolute error exceeds both 20%
  of the current forecast price and calibration p90 absolute error (once >=20
  assessment errors exist).
- `stale_calibration`: calibration freeze more than 180 days old;
  `stale_error_evidence`: most recent resolved error more than 30 days old;
  `wide_empirical_interval`: a full band width exceeds the point price.
- `insufficient_calibration` / `limited_unseen_interval_evidence` as applicable.
- Backtest-only `missing_target_observation` and `target_crosses_partition`:
  a live forecast must not assert that its future target observation is missing.

Thresholds are engineering safeguards, not universal statistical guarantees or
agronomic truths. They are persisted with artifacts. Very wide intervals, adverse
drift or volatility downgrade status; bands may still be displayed with warnings
as empirical bands, never as validated promises. Data source freshness and actual
calibration/evaluation counts should be visible to the user.

## Auditable reports and frontend charts

`reports/backtests/samay-reliability-v1-<fingerprint>/` contains:

- `calibration-{1,3,7}d.csv`: dated forecasts, actuals, residuals, absolute errors,
  availability/source row IDs, decision timestamps, model versions and flags.
- `evaluation-{1,3,7}d.csv`: the same fields plus supported frozen band bounds.
  All price, prediction, error and interval columns use **INR/quintal**, declared
  in summary metadata. Predictor row IDs allow ledger reconstruction.
- `summary.json`: per-horizon paired sample sizes, actual MAE/RMSE/sMAPE/WAPE,
  directional accuracy, naive benchmark on the **identical timestamps**, empirical
  coverage/width, calibration method/counts, source provenance, policy and hashes.
- `predicted_vs_actual.png`, `residuals_over_time.png`, `error_by_horizon.png`,
  `error_by_season.png`. Seasonality is explicitly target-calendar month with
  per-group sample counts, not an invented local cropping-season classification.

Empty real-data runs retain dated audit rows with missing values/flags, write no
fake errors or intervals, and render explicit unavailable charts. Run fingerprints
bind code, source, scope, time windows, model hashes and policy. Identical reruns
verify hashes and reuse saved artifacts. Generated outputs are ignored by Git.
Do not tune repeatedly on the same assessment period and call it untouched.

## What farmers must not infer

An empirical mandi modal-price band is **not** a guaranteed realized selling price,
minimum support price, insurance payout, profit guarantee or recommendation to
borrow/hold stock. It describes uncertainty in a wholesale market statistic for
one series, horizon and reporting convention. A farmer's variety/grade, ripeness,
quality, sorting, lot size, spoilage, commission, transport, credit terms and
bargaining can cause different transaction prices and net proceeds. These sources
of farmer-level uncertainty are not measured by this module. Missing reports do
not mean a mandi was closed. Past coverage and the word validated do not promise
future coverage in a changed market regime.

## Acceptance boundary and next handoff

The backtest command, service, empirical calibration, safety flags, reports, charts
and leakage tests are implemented. **Actual held-out market examples and real
coverage/error measurements remain unavailable** because authenticated history
has not been obtained. No synthetic test result is presented as real performance.
Supply historically captured official snapshots, freeze model and window choices,
then rerun and inspect actual paired counts/coverage before enabling farmer-facing
reliability claims. No Prompt 6 work was started.
