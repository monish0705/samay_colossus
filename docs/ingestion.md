# Mandi ingestion — scope, provenance and operations

This stage implements file ingestion for Karnataka / Kolar / Kolar APMC / Tomato.
Wholesale modal prices are market observations, not guaranteed farmer realization
prices. Observed minimum and maximum prices are not prediction intervals.
No arrivals are inferred, no daily frequency is assumed, and missing calendar dates
remain missing. No training or recommendation logic is implemented.

## Official sources checked on 2026-11-04

- [OGD catalog](https://data.gov.in/catalog/current-daily-price-various-commodities-various-markets-mandi)
- [OGD current daily resource](https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi)
- [OGD variety-wise resource](https://data.gov.in/resource/variety-wise-daily-market-prices-data-commodity)
- [AGMARKNET](https://agmarknet.gov.in)

The catalog describes wholesale min/max/modal prices generated through AGMARKNET.
The current resource is a current snapshot; it is not evidence of complete history.
During implementation the OGD page returned HTTP 200 HTML with a sandbox notice,
without a usable verified download/API contract. AGMARKNET returned HTTP 403.
No genuine CSV could be obtained and authenticated in this session. All imported
example observations are labeled TEST_FIXTURE_NOT_GOVERNMENT_DATA.

No HTTP adapter, endpoint UUID, API key, response field mapping, or history query
has been guessed. HTTP retry/timeout/key/pagination behavior is intentionally not
implemented without a verified official contract. This file importer makes no
network calls. A future adapter must pin the verified official endpoint and docs,
use bounded timeouts and exponential retries for transport/429/5xx only, validate
the response schema, paginate exactly as documented, detect repeated pages, retain
raw responses and manifests, and read a real API key from environment variables.
It must not log keys, retry authorization failures, or reinterpret current snapshots
as a historical API. API history responses already support local limit/offset paging.

## Obtain authentic data

1. Open the official catalog/resource above in a browser. Confirm publisher DMI /
   Ministry of Agriculture, resource title, license and reporting period.
2. Use the portal's available Download/export controls. For history, use the
   variety-wise resource or AGMARKNET's official historical reports if available;
   select Karnataka, Kolar, Kolar, Tomato and the requested dates where controls
   support this. Do not manufacture a download URL or assume a date-range API.
3. Save the original CSV unchanged to `data/raw/kolar-tomato.csv`. Keep source URL,
   actual download timestamp, and official unit evidence. If the portal offers
   only Excel, do not rename it CSV: export CSV separately and retain the original
   and transformation notes. HTML/login/error pages are rejected as CSV input.
4. Create a JSON manifest. Values below are a structure to fill from the download,
   not evidence that a download happened. Confirm units explicitly: bare `Rs`,
   `quintal`, missing units, USD, or undocumented assumptions are rejected.

```json
{
  "source_label": "AGMARKNET via OGD",
  "source_url": "https://data.gov.in/resource/variety-wise-daily-market-prices-data-commodity",
  "data_kind": "official",
  "fetched_at": "REPLACE_WITH_ACTUAL_DOWNLOAD_TIMESTAMP_WITH_OFFSET",
  "price_unit": "REPLACE_WITH_VERIFIED_CURRENCY_AND_WEIGHT_UNIT",
  "unit_evidence": "REPLACE_WITH_OFFICIAL_REPORT_HEADER_OR_DOCUMENTATION_AND_URL",
  "date_format": "%d/%m/%Y",
  "sha256": "REPLACE_WITH_FILE_HASH"
}
```

Use the URL of the resource actually downloaded, without API keys or query secrets.
The official-host allowlist is intentionally narrow: `data.gov.in`, `www.data.gov.in`,
`agmarknet.gov.in`, `www.agmarknet.gov.in`. Extend it only after verifying another
government host. Host checking does not independently authenticate a local file;
the operator attests provenance through this manifest. Its hash binds the import
to exact bytes; it does not certify their publisher.

PowerShell from repository root, after saving the download and manifest:

```powershell
Get-FileHash data/raw/kolar-tomato.csv -Algorithm SHA256
# Put the hash in data/raw/kolar-tomato.manifest.json, along with verified metadata.
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/import_mandi_data.py --file data/raw/kolar-tomato.csv --manifest data/raw/kolar-tomato.manifest.json --market 'Kolar APMC' --commodity Tomato --start-date 2025-01-01 --end-date 2025-12-31
```

The dates above are requested filters, not a claim of available data. Use dates
appropriate to the actual source. CSV fields accepted (case-insensitive): State,
District, Market, Commodity, Variety, optional Grade, Arrival_Date (or Report_Date /
Date), Min_Price, Max_Price, Modal_Price, optional Price_Unit. Spaces in place of
underscores are supported for dates/prices. Unexpected source headers require an
explicit reviewed alias; duplicate aliases or missing required fields fail early.
Extra columns remain in the raw row ledger. UTF-8/BOM and quoted grouped prices
are supported. Malformed row widths are quarantined; structurally invalid CSV
fails the transaction. No undocumented response fields are assumed.

## Reproduce with fixtures — not authentic observations

```powershell
.\.venv\Scripts\python.exe scripts/import_mandi_data.py --file tests/fixtures/mandi_fixture.csv --manifest tests/fixtures/manifest.json --market 'Kolar APMC' --commodity Tomato --start-date 2025-01-01 --end-date 2025-01-09
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8001
# In another terminal:
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/markets?data_kind=fixture' | ConvertTo-Json -Compress
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/prices/history?data_kind=fixture&limit=1' | ConvertTo-Json -Depth 5 -Compress
Invoke-RestMethod 'http://127.0.0.1:8001/api/v1/prices/history' | ConvertTo-Json -Depth 5 -Compress
```

On an empty development database the first command inserts 3 observations from
12 rows: 1 duplicate, 7 quarantined, 1 filtered. Repeating creates a new lineage
batch, with zero inserts and 4 duplicates; rejected rows remain auditable.
Default API queries return only official observations; select `fixture` or `demo`
explicitly to inspect development data. Fixture observations never enter the
official default export/API result set. All fixtures are hand-authored test data.

## Validation, revision and audit contract

Business key: **state/district/canonical market + canonical commodity + report date
+ normalized variety + normalized grade + data kind**. Market/commodity IDs resolve
the location/name part. `Kolar`, `Kolar APMC`, `Kolar (APMC)` and `Kolar A.P.M.C.` map
to `Kolar APMC`; name case/whitespace are normalized. Variety/grade retain semantic
distinctions and normalize only whitespace/case; omitted grade becomes unspecified.

Dates use one explicit manifest format (`%d/%m/%Y`, `%d-%m-%Y`, `%Y-%m-%d`), never
ambiguous automatic inference. Impossible/future dates, negative/nonfinite/malformed
prices, unknown units, missing variety and invalid min <= modal <= max order are
quarantined. Zero modal or a maximum above the configurable review threshold
(default INR 100,000/quintal) is suspicious and quarantined, not silently corrected.
These are review rules, not learned anomaly scores. Supported unit conversions:
INR/quintal (including documented Rs spelling), INR/100kg, INR/kg ×100, INR/tonne ×0.1.
Normalized prices must fit two decimal places and database precision. Missing
arrivals remain NULL even if the source contains price data every day.

Exact equal-price duplicates retain an ImportRow lineage entry without duplicating
observations. A later fetched_at confirms freshness even when prices are unchanged.
Changed prices with a strictly newer fetched_at revise the current observation;
older/equal-time conflicts are retained as stale conflicts for inspection. Within
one file, conflicting same-key rows do not silently overwrite one another. fetched_at
is an operator-supplied retrieval timestamp, not a source-issued revision timestamp;
this is a documented last-newer-fetch policy, not proof of source revision order.

Each ImportBatch stores file SHA256, manifest, fetch/import timestamps, provenance,
archive path and report. ImportRow preserves original row values, physical record
ordinal (header=1; multiline quoted records use record ordinals, not physical lines),
normalized values, outcome/reason and observation ID. Earlier normalized ledger
entries survive current-value revisions. Raw file bytes are archived by SHA256.
All timestamps are timezone-aware UTC in Python; report dates are calendar dates.

Each successful batch exports under `data/processed/imports/batch-N/`:

- `quality.json`: disposition counts, date range, unreported calendar dates,
  source/hash/fetch freshness, input price distribution and deduplicated current
  snapshot distribution/count. Missing-date checks are a union across varieties/
  grades and are not a completeness claim per series. Input distribution explicitly
  includes duplicate/stale rows; use current-snapshot statistics for analysis.
- `quarantine.json`: rejected and stale records with raw values and reasons.
- `validated_input.csv`: normalized accepted input including duplicate/stale
  dispositions, raw price-unit declaration, hash and row ordinal.
- `prices.csv`: deduplicated current observations for this data kind/scope and
  requested dates, with explicit price units in column names, source and freshness.

CSV snapshots are deterministic in date/variety/grade order. Decimal API prices are
JSON strings to preserve currency precision. `/api/v1/prices/history` supports
market, commodity, start_date/end_date, variety, grade, data_kind, bounded limit
(1–1000) and offset. Invalid query values return 422; empty data returns 200 with
an empty items array. A next_offset is provided when another page exists.

Database writes commit as one transaction per file. Header/hash/manifest failures
exit nonzero before ingestion. Row-level validation failures quarantine individual
rows; inspect counts even when the CLI succeeds. SQLite serializes writers; run
one importer at a time. This is not a distributed ingestion service. File outputs
and SQLite are not one atomic filesystem transaction: a failed write/commit can
leave orphaned archives/output folders. Trust only batches present in import_batches
and a CLI COMMITTED message; reconcile/remove orphan batch folders before retrying
if their IDs would collide. Keep source files and database backups. Downgrade is
refused once lineage exists because it would discard audit history.

## Remaining acceptance boundary

The CSV path, nonempty fixture API, exports, migrations and tests are reproducible.
An authentic historical import remains pending a genuine official download. Do
not relabel a fixture manifest as official to satisfy acceptance. After obtaining
one, retain its hash/source/unit evidence and rerun the commands above; inspect
the official quality report and default history response before any ML work.
This implementation stops before Prompt 3.
