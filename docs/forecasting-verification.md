# Prompt 4 verification — 2026-11-04

## Files changed

Added backend/app/forecasting.py (models, metrics, comparison, saved prediction),
backend/app/training.py (versioned workflow and one-shot evaluation),
scripts/train_forecasts.py, scripts/predict_price.py, tests/test_forecasting.py,
docs/forecasting.md and this record. Updated backend/app/features.py with a
separate explicit final-evaluation loader mode; normal loading still excludes
final holdout dates. Updated backend/pyproject.toml with a scikit-learn-only
forecast extra and README.md with the workflow link. Frontend unchanged.

## Commands and actual outputs

PowerShell, repository root:

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install --quiet 'scikit-learn>=1.5,<2'
```

Dependency installation completed with exit 0. Tests initially ran before the
installation had completed and failed to import sklearn; they were rerun after
installation. A subsequent test run exposed Windows threadpoolctl DLL-path
enumeration failing under the non-ASCII workspace directory. This was corrected
by setting thread-count environment variables before CLI imports and avoiding
explicit native DLL enumeration on Windows. Numerical libraries still retain
their normal model computation; the candidate models were not bypassed.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_forecasting.py -q
```

```text
5 passed in 93.72s (0:01:33)
```

The deterministic test-only cases exercise guarded metrics, expanding folds and
purging, fold-time label revisions, actual ridge/boosting/baseline comparisons,
baseline promotion, artifact save/load, causal predictions, unsupported requests,
freezing before final-label loading, persisted reruns and refusal to re-test a
new model/source version on the same holdout. These test scores are not SAMAY
market performance and no test-only model was promoted into production folders.

```powershell
.\.venv\Scripts\python.exe scripts/train_forecasts.py --feature-run reports/samay-features-v1-78a0e500308b86f0 --evaluate-final
Write-Output "Training CLI exit code: $LASTEXITCODE"
```

```text
STATUS: insufficient_data
horizon=1d train=0 validation=0 champion=NONE comparisons=0
horizon=3d train=0 validation=0 champion=NONE comparisons=0
horizon=7d train=0 validation=0 champion=NONE comparisons=0
FINAL HOLDOUT: unopened / not evaluated
REPORT: models\forecasts\samay-forecast-v1-c674aa8f870f2ba2\comparison.md
Training CLI exit code: 2
```

An identical command returned the same saved report without opening the final
holdout or creating a final-evaluation reservation. Earlier development report
versions remain in ignored model directories; use c674aa8f870f2ba2 for this run.

```powershell
.\.venv\Scripts\python.exe scripts/predict_price.py --model models/forecasts/samay-forecast-v1-c674aa8f870f2ba2/champion-1d --origin 2026-11-04 --horizon 1 --variety local --grade faq
Write-Output "Prediction CLI exit code: $LASTEXITCODE"
```

```text
PREDICTION UNAVAILABLE: Unsupported or untrained series/horizon; no champion artifact
Prediction CLI exit code: 2
```

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
git diff --check
```

```text
No broken requirements found.
No new upgrade operations detected.
```

The whitespace check emitted no errors. LightGBM was not installed or trained:
there are no real samples that justify it.

Final complete-suite rerun after the Windows fix:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```text
35 passed, 1 warning in 111.87s (0:01:51)
```

The remaining warning is the pre-existing Starlette TestClient HTTPX deprecation.
No frontend code changed and frontend tests were not rerun for this stage.

## Real-data acceptance boundary

Prompt 2 never obtained authenticated government history; only fixtures exist.
Consequently no real comparison metric, saved champion or final holdout result
can be honestly produced now. The functioning production path is the explicit
insufficient-data mode, with empty comparisons and no invented baseline price.
The implemented full path is verified using isolated deterministic test cases.
Final evaluation is reserved exactly once only when actual development champions
exist, and refuses to score fewer than 30 valid final examples.

Next handoff: obtain authenticated, historically available official snapshots,
rebuild features for the frozen plan, then execute the documented training command.
Keep the final evaluation registry and report artifacts, and never use final
metrics to reselect a champion. No Prompt 5 work was started.
