# Ingestion verification — 2026-11-04

Changed implementation: backend/app/{models,main,ingestion,prices}.py,
backend/alembic/versions/549021dc3d31_ingestion_lineage_and_units.py,
scripts/import_mandi_data.py, tests/test_backend.py, tests/test_ingestion.py,
tests/fixtures/{mandi_fixture.csv,manifest.json}, README.md and ingestion docs.
No frontend implementation changes were needed.

## Exact executed commands and observed outputs

From repository root (PowerShell):

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini revision --autogenerate -m ingestion_lineage_and_units
```

Generated `549021dc3d31_ingestion_lineage_and_units.py`. The migration was then
reviewed and corrected to name/drop the old unique constraint, preserve both price
and arrivals CHECK constraints during SQLite batch recreation, and refuse a lossy
downgrade once import lineage exists.

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
```

Upgrade exited 0; check output: `No new upgrade operations detected.` During
development the empty ingestion schema was downgraded to `73bf51f6beac` and
upgraded again after migration review. Populated imports were not downgraded.

```powershell
.\.venv\Scripts\python.exe scripts/import_mandi_data.py --file tests/fixtures/mandi_fixture.csv --manifest tests/fixtures/manifest.json --market 'Kolar APMC' --commodity Tomato --start-date 2025-01-01 --end-date 2025-01-09
```

First import counts:

```json
{"batch_id":1,"counts":{"records":12,"inserted":3,"revised":0,"duplicates":1,"stale":0,"quarantined":7,"filtered":1},"data_kind":"fixture"}
```

The command prints the complete quality JSON followed by:
`COMMITTED batch 1: data\processed\imports\batch-1`.
Observed date range: 2025-01-01 through 2025-01-03. Seven unreported calendar dates
in the requested January 1–9 range; no observations fabricated. SHA256:
`90e43db81a1c0c8ee1ca5ca876f771f1f83e3197f1f20b2485f9ec042aa0b16c`.

The exact same command was run again after final report improvements:

```json
{"batch_id":2,"counts":{"records":12,"inserted":0,"revised":0,"duplicates":4,"stale":0,"quarantined":7,"filtered":1},"current_snapshot_records":3}
```

Output ended `COMMITTED batch 2: data\processed\imports\batch-2`.
The full latest report, quarantine and CSV files are in that ignored output folder.
Current snapshot modal-price distribution: count 3, min 1500, median 1500,
max 1600, mean 1533.3333333333333 INR/quintal. These are fixture statistics,
not claims about government data or model performance.

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Output included `Application startup complete.` and
`Uvicorn running on http://127.0.0.1:8001`. Port 8001 avoids the earlier foundation
server already running on 8000; restart the normal backend when adopting changes.

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/markets?data_kind=fixture' | ConvertTo-Json -Compress
```

```json
[{"id":1,"name":"Kolar APMC","district":"Kolar","state":"Karnataka"}]
```

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/prices/history?data_kind=fixture&limit=1' | ConvertTo-Json -Depth 5 -Compress
```

```json
{"items":[{"id":3,"market":"Kolar APMC","commodity":"Tomato","report_date":"2025-01-01","variety":"hybrid","grade":"faq","min_price_inr_per_quintal":"1200.00","modal_price_inr_per_quintal":"1600.00","max_price_inr_per_quintal":"2200.00","arrivals_quintals":null,"price_unit":"INR/quintal","source":"TEST_FIXTURE_NOT_GOVERNMENT_DATA","source_url":"fixture://mandi_fixture.csv","fetched_at":"2025-01-10T06:30:00Z","data_kind":"fixture"}],"limit":1,"offset":0,"next_offset":1,"note":"Wholesale observations, not guaranteed farmer realization prices. Observed min/max are not prediction intervals. Unreported dates are not imputed."}
```

```powershell
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/prices/history' | ConvertTo-Json -Depth 5 -Compress
```

```json
{"items":[],"limit":100,"offset":0,"next_offset":null,"note":"Wholesale observations, not guaranteed farmer realization prices. Observed min/max are not prediction intervals. Unreported dates are not imputed."}
```

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Final test run: `17 passed, 1 warning in 5.34s`. The warning is the existing
Starlette TestClient HTTPX deprecation. Coverage includes migration rollback/
upgrade, schema constraints, UTC, corrupt CSV values, explicit date formats,
unit conversion, duplicate/revised/stale handling and unchanged-fetch watermark,
raw-byte lineage, fixture exclusion, history filters/pagination and validation.

```powershell
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

Outputs: `No broken requirements found.` and no whitespace errors, respectively.

From frontend:

```powershell
npm.cmd test
npm.cmd run build
```

Outputs: `Tests 3 passed (3)` and successful TypeScript/Vite production build.

## Unresolved acceptance and handoff

No authenticated government CSV was downloaded. Official OGD HTML was HTTP 200
but contained a sandbox notice; AGMARKNET returned HTTP 403. A reproducible genuine
historical import and its authentic quality report remain unverified. The official
data API correctly remains empty. Follow ingestion.md to obtain and attest a real
CSV, then import it and inspect default official history before moving on.

No HTTP adapter was added because a usable official endpoint contract could not
be verified. No keys, endpoint identifiers, live data or ML metrics were invented.
Filesystem exports and SQLite commits require reconciliation after failures, as
documented in ingestion.md. Importers should run serially. Prompt 3 was not started.
