# Forecast selection and one-shot evaluation (Prompt 4)

SAMAY selects horizon-specific models for Karnataka / Kolar / Kolar APMC / Tomato,
with an explicit variety and grade. Target units remain INR/quintal, with exact
1-, 3-, or 7-calendar-day targets. Wholesale modal prices are not guaranteed farmer
realization prices. No uncertainty interval is implemented in this stage.

## Current honest result

There is still no authenticated historical government dataset in the workspace.
The available fixture data is excluded. Each horizon has 0 effective training and
validation samples. The command produces a versioned insufficient-data comparison
report with empty candidate results, no champion and no final test evaluation.
There are no real-world MAE or accuracy numbers to report. It does not fabricate a
saved baseline when even a reliable last-known official price is unavailable.

## Windows workflow

From repository root:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,analysis,forecast]'
# Optional, only if evaluating LightGBM on sufficient data:
# .\.venv\Scripts\python.exe -m pip install -e './backend[ml]'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/build_market_features.py --start 2025-01-01 --train-end 2025-06-30 --validation-end 2025-09-30 --holdout-end 2025-12-31 --variety local --grade faq
# Use the ARTIFACTS path printed by the feature command:
.\.venv\Scripts\python.exe scripts/train_forecasts.py --feature-run reports/samay-features-v1-78a0e500308b86f0 --evaluate-final
$LASTEXITCODE
.\.venv\Scripts\python.exe -m pytest tests -q
```

The existing feature path above is valid for the previously created immutable run;
rebuilding with new code can print another path. Date boundaries are the existing
example plan, not a claim of real data availability. Do not shift a previously
inspected final holdout into development. A training exit code of 2 means insufficient
data, 1 means an operational/integrity failure, and 0 means development champions
were selected (inspect final sample status separately).

Use `--evaluate-final` on the initial training invocation when final reporting is
intended. Without it, only development selection is performed. Automatic evaluation
is refused on a later invocation of an already-frozen selection-only run; this
requires a separately reviewed evaluation operation, not retraining to probe test
outcomes. Do not change output roots or delete evaluation records to bypass this.

## Candidates and common comparisons

All candidates use the exact same per-fold examples, target vintages, units and
feature timing. Core baselines: last-known modal price, mean of the previous 14
available observations and median of those observations. No model is measured on
an easier subset. All predictions use the predeclared nonnegative-price constraint.

Ridge regression compares alpha 1, 10 and 100 with a StandardScaler fitted inside
each training fold. HistGradientBoosting uses 100 iterations, 15 leaf nodes,
learning rate .05, L2=1 and no internal randomized early-stopping validation.
Seed=42; CLI processes set OMP/BLAS/MKL thread counts to one before imports and
LightGBM uses one worker. On Windows the module avoids native thread-pool DLL
enumeration because it failed under this repository's non-ASCII directory path;
other platforms additionally use threadpoolctl. Embedded callers should configure
thread counts before importing NumPy for the same numerical runtime behavior.

The weekly seasonal candidate is considered only when each CV fold has at least
eight weeks of training samples and >=90% of validation origins have an exact
historically available matching-weekday report. It forecasts the latest weekly
counterpart of the target date strictly before origin; for a 7-day horizon that is
D-7, not D. If unavailable, its declared fallback is naive. The fallback applies
identically during validation, final evaluation and inference. Coverage only makes
this a candidate; actual out-of-sample skill must still support promotion.

LightGBM is optional and requires >=500 reliable training examples in **every**
CV fold. It uses 100 estimators, 15 leaves, learning rate .05, L2=1, deterministic
mode and seed 42. Otherwise it is explicitly skipped with a reason. Installing
LightGBM does not imply it is superior or even eligible.

## Rolling-origin tuning and selection

Prompt 3's sample/reliability gates apply independently to each horizon. A viable
horizon must also support three expanding-window training-period CV folds. Fold
validation starts at 50%, 67% and 84% of the training calendar window; the last
ends at train_end. Each fold needs >=60 train and >=14 validation examples after
causal-history, missing-target and horizon embargo checks.

Training labels are reconstructed as known strictly before each fold validation
start. Validation labels freeze strictly before the next fold. This avoids using
revisions that were available by the overall train_end but unknown at an earlier
CV origin. Fold features always use source vintages available at decision time.
Targets crossing partition boundaries are purged. No random train/test split or
full-dataset feature scaling is used.

Candidates are then fitted on train and compared on the separate chronological
validation partition. Validation MAE is the primary ranking. CV MAE variability
and validation p90 overprediction error break ties. Overprediction represents
optimistically overstating prices and is an additional downside diagnostic.

An ML or seasonal candidate may be promoted only if it beats **all three** core
baselines on MAE in at least two of three CV folds, has lower mean CV MAE than the
best validation baseline, and beats that baseline on validation MAE. Otherwise the
lowest-validation-MAE reliable core baseline wins. Exact baseline ties are resolved
deterministically by name after stability/downside criteria. This conservative rule
is recorded with each actual selection; it is not a statistical significance claim.

The selected fixed configuration is refitted on development examples whose labels
were available at final holdout start. Training-plus-validation boundary origins
may now be included when their labels are available, since tuning is finished.
No final outcome influences this refit. Validation comparisons are selection
statistics, not unbiased final performance claims.

## Metrics

Reports calculate actual per-fold and validation MAE, RMSE, sMAPE, WAPE, directional
accuracy, p90 absolute error and p90 overprediction. MAE/RMSE use INR/quintal.
sMAPE is `mean(200*abs(pred-y)/(abs(pred)+abs(y)))`; both-exactly-zero contributes
0, other combined denominators <=INR .01 are excluded with a count. WAPE is null
when total absolute target value <= .01 times sample count. Nonfinite vectors and
empty metric calls raise an error. Direction compares signs relative to the latest
known price, with changes <=INR .01 treated as ties. Ties count toward accuracy;
direction is not the selection objective. Percent errors are not accuracy claims.

## Frozen final holdout — once only

All horizon selections and model files are persisted **before** the final-data
loader executes. The final loader is a separate explicit path; normal feature
engineering and training exclude final report dates. For each selected horizon,
an exclusively created evaluation record under `models/forecasts/final_evaluation_registry`
reserves that series and chronological holdout before any final labels are read.
The record key deliberately excludes candidate/model/source version, preventing
new champions from repeatedly evaluating the same final period in this registry.

Only frozen champions are evaluated. At least 30 eligible holdout examples are
required for final metrics; otherwise the report says insufficient_final_samples
and no metric is invented. Final labels freeze strictly before holdout_end+1, and
targets beyond holdout_end are excluded. Models remain fixed while predictors
incorporate observations actually known at each successive final origin. Outcomes
are never used to choose another champion after final reporting.

Identical reruns return persisted results rather than re-opening final targets.
Failed/reserved/insufficient evaluations consume the reservation too; recovery
requires an audited human process. File-based audit records are an operational
guard, not a tamper-proof multi-host access-control system. Run one trainer at a
time, retain these files and backups, and never delete them to improve metrics.
In insufficient-data mode no final loader or reservation is executed.

## Saved artifacts and inference

`models/forecasts/samay-forecast-v1-<fingerprint>/comparison.json` contains full
computed comparisons, skips, fold windows/counts, source fingerprints and final
results. `comparison.md` provides the human-readable summary. For selected
horizons, `champion-Nd/` stores model.pkl and metadata.json with unique model version,
exact feature allowlist, runtime versions, seed, scope, training window/sample
count, data fingerprint, model SHA256 and selection metrics. A baseline is also
saved as an explicit named artifact (its estimator payload is None).

Fingerprints include source vintages, plan, provenance, algorithm code and runtime.
The feature-run artifacts and current source-vintage hash are checked before
training; changed sources require a new feature run. Generated models and reports
are ignored by Git. Do not load untrusted pickle files: only artifacts created by
this workflow are supported.

Public callable:

```python
from datetime import date
from pathlib import Path
from app.db import SessionLocal
from app.forecasting import forecast

with SessionLocal() as session:
    prediction = forecast(
        session, Path("models/forecasts/ACTUAL_RUN/champion-1d"),
        date(2026, 11, 4), 1,
        market="Kolar APMC", commodity="Tomato", variety="local", grade="faq",
    )
```

Use an actual saved champion directory, not the placeholder ACTUAL_RUN. Equivalent
CLI after a champion actually exists:

```powershell
.\.venv\Scripts\python.exe scripts/predict_price.py --model models/forecasts/ACTUAL_RUN/champion-1d --origin 2026-11-04 --horizon 1 --variety local --grade faq
```

The public function reads scoped official ledger inputs, builds causal features
and returns a numeric INR/quintal prediction, unique version, horizon, target/origin,
scope and observation freshness. Unsupported combinations, missing models, requests
before model-training availability, incomplete/stale history and corrupted model
payloads fail explicitly. It never fills an unavailable forecast with a made-up
price. The private frame-based helper exists for deterministic tests only.

## Remaining handoff

Obtain authenticated historical official snapshots with credible original capture
times, rebuild features without changing the reserved holdout, and run selection.
Until then the production report remains insufficient_data with no real metrics,
champion or final evaluation. Test-only constant sequences verify model selection
and final-evaluation mechanics; their computed scores are never published as SAMAY
market performance. No Prompt 5 work is included.
