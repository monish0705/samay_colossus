# Prompt 3 verification — 2026-11-04

Files added: backend/app/features.py, backend/app/analysis.py,
scripts/build_market_features.py, tests/test_features.py, reports/.gitkeep,
docs/features.md and this verification record. Updated backend/pyproject.toml
(optional matplotlib dependency), .gitignore (generated reports), and README.md.
No database schema or frontend implementation changed in this stage.

## Executed commands and outputs

PowerShell from repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e './backend[analysis]'
```

Installation exited 0 and installed matplotlib and its dependencies. Windows pip
produced legacy-console Unicode logging errors because the repository path contains
Chinese characters. Dependencies nevertheless installed successfully. The documented
setup sets `$env:PYTHONUTF8 = '1'` before pip to avoid these encoding errors.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_features.py -q
```

Initial feature tests: 11 passed. Further tests were added for holdout invariance
and training-only insights. Final full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

```text
30 passed, 1 warning in 14.93s
```

The warning is the existing Starlette TestClient HTTPX deprecation. Deterministic
analytical values are used only inside tests, never to populate production features.

```powershell
.\.venv\Scripts\python.exe scripts/build_market_features.py --start 2025-01-01 --train-end 2025-06-30 --validation-end 2025-09-30 --holdout-end 2025-12-31 --variety local --grade faq
Write-Output "Feature CLI exit code: $LASTEXITCODE"
```

```text
STATUS: insufficient_data
horizon_days | effective_train | effective_validation | status
           1 |               0 |                    0 | insufficient_data
           3 |               0 |                    0 | insufficient_data
           7 |               0 |                    0 | insufficient_data
ARTIFACTS: reports\samay-features-v1-78a0e500308b86f0
Final holdout: reserved; no values read for analysis/evaluation. No model trained.
Feature CLI exit code: 2
```

An identical rerun returned the same path and verified existing artifact hashes.
The preceding development run remains separately versioned under
samay-features-v1-3be85a10f4c129d4; use the 78a0e500308b86f0 run above.
All six PNGs and market_insights.json are saved under that final run directory.
The price-over-time PNG was visually inspected: title and explicit insufficient-data
message are legible, with no invented data series or price axis values.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
git diff --check
```

```text
No broken requirements found.
No new upgrade operations detected.
```

The whitespace check emitted no errors. The repository remains uncommitted, as it
was before this stage. No frontend changes were made or frontend tests rerun here.

## Unresolved prerequisite and handoff

There is no authenticated historical government dataset from Prompt 2 in the
workspace. Only fixture observations exist, and the feature loader excludes them.
Effective training samples are therefore 0/0/0 for the three requested horizons.
An actual price/seasonality/volatility analysis and viable feature dataset cannot
be honestly produced until authenticated, historically available official snapshots
are supplied and verified. A historical report downloaded after a decision is not
used as a predictor for that earlier decision.

Current example plan: train origins Jan–Jun 2025, validation Jul–Sep, reserved final
holdout Oct–Dec, with horizon-specific purging and availability-time checks. This is
an explicit example configuration, not a claim of data availability. The holdout
has no materialized values or evaluation metrics. No model trained, no final test
opened, and no Prompt 4 work started. See features.md for source integrity,
feature definitions, reliability thresholds and the frontend insights contract.
