> **Current-grade update, 5 November 2026:** fresh official OGD history now enables 12 additional saved research forecasts for four crops. See [CURRENT-CROP-MODELS](CURRENT-CROP-MODELS.md). Earlier stale-series counts below describe the original secondary-only studies and remain preserved.

# Secondary acquisition update — 5 November 2026

An additional 5,834 usable variety-specific historical observations were imported from the India Data Portal / ISB AGMARKNET mirror. They are labeled **secondary**, separate from direct government downloads. All 5,837 retrieved source records and pagination responses are archived; 3 rows are quarantined. See [SECONDARY-MODELS](SECONDARY-MODELS.md) for exact publisher links, license attribution, dates, varieties, commands and limitations. The original 1,943 direct government observations below remain unchanged.

# Official data obtained · 2026-11-04

**The full historical acquisition has succeeded: 1,943 official records imported
from six annual CSV exports.** The initial five-point-only notes below are historical.
All annual queries were submitted through the official AGMARKNET report UI, with
user confirmation at each CAPTCHA. Actual fetch times were preserved. Source
coverage is 2021-01-01–2026-10-31; November 1–4 were requested but not supplied.

| Year | Original records | Original CSV SHA256 |
| --- | ---: | --- |
| 2021 | 362 | `37fdfa72368c59feb0afacd5635002d9ec8c213c177e020bdd999dcbe997ed17` |
| 2022 | 363 | `848e57a532c1104d996ecce5952549e8fcf2e33d769a2c574a7f49b8e26dc962` |
| 2023 | 358 | `d023df9708c8db2fb5d31d35136a090aabb4aeb52dd0cd26c80f35bb4f978b4a` |
| 2024 | 343 | `4824090fd75e8045985988af019df29d86c1a0e91272186415aa7ac8b418c1fd` |
| 2025 | 241 | `df98eee2a9c4c055d2932fb3f79cc4542c390b717db30e577a05462381265b65` |
| 2026 | 276 | `77d4aadb00cb6b9c0456821af2297b1a09d58936ac233ce0588467c21ed64f40` |

Archive directory: `data/raw/official-history/`. Each annual batch retains
`.original.csv`, importer `.csv`, `.manifest.json` and `.provenance.json`.
The latter records the actual download timestamp, original/import hashes and
header/prelude transformation. Values, grades and dates are unchanged. Import
logs: `reports/import-official-2021.log` through `import-official-2026.log`.
Cleaned exports/quality reports: `data/processed/imports/batch-3` through `batch-8`.
Across these imports: **0 duplicates, 0 revisions, 0 quarantines**.

Source groups: Tomato/FAQ 1,562; Tomato/Local 371; Tomato/Grade Range-1 5;
Hybrid/FAQ 3; Hybrid/Local 2. They were not merged. FAQ ends 2025-06-30;
Local starts 2025-07-03. That source metadata break required separate studies.
See [MODEL-RESULTS](MODEL-RESULTS.md) for frozen metrics and exact commands.

```powershell
.\.venv\Scripts\python.exe scripts/archive_official_export.py --file 'C:/Users/Suhan/Downloads/Daily Price Report-01-01-2021 to 31-12-2021 for Karnataka.csv' --year 2021
.\.venv\Scripts\python.exe scripts/import_mandi_data.py --file data/raw/official-history/kolar-tomato-2021.csv --manifest data/raw/official-history/kolar-tomato-2021.manifest.json
```

Repeat for each actual annual filename; 2026's filename ends `04-11-2026`.
The user authorized clearly labeled retrospective research. Original publication
and revision timestamps remain unverified. Only a temporary research view assumes
next-day publication; SQLite fetch times are not backdated. No research artifact
can enter the validated production forecasting service.

## Historical initial retry notes (superseded)

The official AGMARKNET 2.0 website and public API are now reachable. This supersedes
the earlier total acquisition failure, but does not establish a trained model.

## Genuine data obtained

Government SPA source inspected:
`https://agmarknet.gov.in/static/js/main.8c489c92.js`.
It explicitly identifies `https://api.agmarknet.gov.in/v1/`, the public filter
endpoint, last-week report route and its parameter names. Live official filters
resolved Karnataka=16, Kolar district=258, Kolar APMC=112, Tomato=65. IDs are
resolved by name on each scripted run rather than invented.

Executed from the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/fetch_official_recent.py
.\.venv\Scripts\python.exe -m pytest tests/test_official_recent.py -q
```

Observed: **5 official modal observations**, 2 not-reported dates; 4 validation
tests passed. Download timestamp `2026-11-04T09:23:39Z`. Archive:
`data/raw/official-recent/20261104T092339Z-3de6537e91e2/`.
Response SHA256:
`3de6537e91e29a64a161c9d735250aa3417fa775ef2b8e65fa6300bda9de561f`.
Original response, source filters and provenance manifest are retained there.

| Report date | Modal INR/quintal | Official market-variety label |
| --- | ---: | --- |
| 2026-10-27 | 1200 | Kolar APMC - Tomato |
| 2026-10-28 | 1330 | Kolar APMC - Tomato |
| 2026-10-29 | 1400 | Kolar APMC - Tomato |
| 2026-10-30 | 1400 | Kolar APMC - Tomato |
| 2026-10-31 | 1400 | Kolar APMC - Tomato |

November 1–2 are `NR` and remain absent. These are wholesale modal observations,
not buyer quotes. The official unit field is `Rs./Quintal`.

This report does not provide min/max or grade. Those fields are not inferred or
copied from modal price. Consequently it is not imported into the full observation
schema, which requires min/modal/max. The operational database still has 0 complete
official rows. Five points cannot support a trained/validated forecasting model.

## Historical query ready, user confirmation pending

Official UI: `https://agmarknet.gov.in/daily-price-and-arrival-report`.
Prepared filters: Price / Vegetables / Tomato / Karnataka / Kolar / Kolar APMC,
2025-11-05 through 2026-11-04, all source varieties and grades so their actual
coverage can be inspected without inventing a variety. The portal requires a CAPTCHA.
No CAPTCHA has been solved or bypassed. Confirmation was requested at this step.

Original publication/revision times may be absent from the eventual export. The
actual download time will be retained. A retrospective current-snapshot study
would need explicit authorization and limitations; it cannot be promoted as
verified point-in-time historical performance. No such assumption has yet been
applied, no model trained and no accuracy metric reported.
