# Current APMC forecasting handoff — 5 November 2026

Four additional crop series now produce numeric, saved-artifact forecasts through
the same backend and frontend path as Tomato. These remain **limited-evidence
research forecasts**, not prospectively validated farmer advice. All original
Tomato and secondary-only frozen experiments remain intact.

## Newly obtained official history

The official [Variety-wise Daily Market Prices resource](https://www.data.gov.in/resource/variety-wise-daily-market-prices-data-commodity)
publishes a download URL for
`https://api.data.gov.in/resource/35985678-0d79-46b4-9ed6-6f13308a1d24`.
The adapter discovers that URL and its public download credential from the
publisher page. It neither guesses identifiers nor invents a key. An optional
`SAMAY_OGD_API_KEY` overrides the public download credential. Keys, complete
credential-bearing URLs and publisher HTML are never archived or logged.

The verified response exposes `State`, `District`, `Market`, `Commodity`,
`Variety`, `Grade`, `Arrival_Date`, `Min_Price`, `Max_Price`, `Modal_Price` and
`Commodity_Code`. Dates are day/month/year. Units are INR/quintal, verified from
the official AGMARKNET reports for these APMCs; no unit is inferred from price
magnitude. There is no arrivals field in these responses and none is invented.

The collector checks exact scope, fields, status, count, offset and stable total
across pages, with timeouts, bounded response sizes and retries. Original JSON
pages, credential-free query metadata, hashes, actual retrieval times, projected
CSV and importer manifests are under
`data/raw/ogd-history/20261105T083939Z/`.

| Official API market spelling / crop | Retrieved | Inserted | Duplicate rows | Quarantined | Latest report |
|---|---:|---:|---:|---:|---|
| Tiptur APMC / Copra | 361 | 299 | 62 | 0 | 3 Nov 2026 |
| Shimoga APMC / Arecanut | 1,393 | 1,182 | 210 | 1 | 3 Nov 2026 |
| APMC Hubballi / Onion | 163 | 162 | 0 | 1 | 4 Nov 2026 |
| Bengaluru APMC / Potato | 352 | 352 | 0 | 0 | 4 Nov 2026 |

Total: **2,269 raw rows, 1,995 inserted, 272 duplicates, 2 quarantines**. Invalid
or suspicious rows remain inspectable in the import quality reports. The portable
database contains 3,938 official and 5,834 secondary rows, plus isolated demos and
fixtures. Official/secondary counts overlap; their sum is not a unique-series count.

Legacy-spelling bulk acquisition was also attempted but returned HTTP 502 after
retries. Its failure log is retained in `reports/ogd-legacy-collection.log`.
It supplied no additional training records. Failed partial archive folders do not
have a completed catalog and are not treated as successful datasets.

## Exact forecasting scopes

| Crop | Canonical market | Variety | Grade |
|---|---|---|---|
| Copra | Tiptur APMC | other | local |
| Arecanut | Shivamogga Mandi | rashi | local |
| Onion | Hubballi APMC | puna | local |
| Potato | Bengaluru APMC | local | medium |

These identifiers are explicit in the UI. Copra `other` is the publisher's
variety name; it is not automatically Ball Copra or the separate `copra` variety.
Rashi is not Bette or Rashi Edi. Results must not be transferred to another grade.

The new plans explicitly opt into `source_kind=verified`: official history plus
the previously archived India Data Portal / ISB backfill for **identical** market,
commodity, variety and grade. Unspecified grades remain separate. Overlaps use
the latest actual fetched vintage; original source rows and hashes remain intact.
The selected scopes have 92 Copra, 103 Arecanut and 49 Potato overlapping dates:
all 244 modal values agree. Onion has no overlap; the secondary series ends in May
and the official current spelling begins in June. No calendar gaps are filled.

The default combined history API now resolves cross-source duplicates *before*
pagination using that same latest-fetch rule. Explicit `data_kind=official` or
`secondary` queries retain each source class for inspection.

## Frozen study and honest model selection

- Source window starts 27 October 2025. Training ends 31 July 2026 for Copra and
  Arecanut, 15 July for Onion and Potato; validation ends **15 September 2026**.
- The final chronological test is **16 September–4 November 2026**. Plans and
  selections were frozen before final prices were loaded by the experiment.
  Previously consumed tests were not reopened or used to improve these selections.
- Each horizon is exactly 1, 3 or 7 calendar days. Missing target dates are excluded.
  All six price lags and rolling statistics use observations strictly before the
  decision day. Labels crossing train/validation boundaries are purged.
- Three expanding CV folds each require at least 60 training and 14 validation
  examples. `recent_v3` chooses fold boundaries from development origin/availability
  counts, never price errors. Validation origins/targets do not repeat; training
  labels must settle before that fold's first validation decision.
- Stateless baseline comparisons require at least 90 training, 20 validation
  examples, 90 eligible calendar days and 50% observed-date coverage. This is an
  explicit short-history policy, not a claim that advanced ML is justified.
- Learned regression/boosting additionally require 120 training, 30 validation
  examples and 180 eligible calendar days. Copra and Arecanut are baseline-only.
  Onion and Potato compare regression and histogram boosting with causal return
  features. LightGBM requires larger folds and is skipped here.
- Validation MAE is primary, stability and overprediction downside secondary.
  Noncore candidates must beat all core baselines in at least two of three CV
  folds and beat the best validation baseline on validation and mean CV MAE.
- All champions remain baselines. These were fitted/refitted and saved as real
  versioned artifacts; no claim is made that LightGBM or another ML estimator won.

The [complete computed table](../reports/current-crop-models.md) includes training,
validation and final counts, candidate counts, validation MAE, final errors and
same-timestamp naive comparison. One-day final results are:

| Crop / scope above | Final n | MAE INR/quintal | WAPE error | Naive MAE |
|---|---:|---:|---:|---:|
| Copra | 39 | 689.74 | 3.83% | 974.36 |
| Arecanut | 28 | insufficient final evidence | unavailable | unavailable |
| Onion | 34 | 377.94 | 8.93% | 400.00 |
| Potato | 39 | 143.59 | 6.33% | 143.59 |

Arecanut's one-day validation MAE is 732.32 INR/quintal on 28 observations; that
is a selection-period score, **not** final accuracy. Current Onion/7d also has
fewer than 30 final examples. Potato/7d's final WAPE is 23.09%, worse than its
naive comparator. These outcomes are retained. WAPE is an error metric;
`100 - WAPE` is not reported as accuracy.

The serving refits use 175–245 eligible examples, depending on scope/horizon.
There are now **30 saved research serving artifacts**: 18 original plus 12 new.
Original publication/revision times remain unknown. Research feature availability
assumes next-day midnight; actual fetch times in SQLite are never backdated.
Current inference checks real fetch timestamps, artifact creation and freshness.
There are too few separated residuals for new calibrated empirical bands; the API
returns an empty interval list with a visible warning, rather than invented bands.
Limited evidence cannot enable confident automatic holding advice.

## Reproduce in Windows PowerShell

Run from `samay-sub2` after the existing setup:

```powershell
.\.venv\Scripts\python.exe scripts/collect_ogd_history.py --import
.\.venv\Scripts\python.exe scripts/train_current_crops.py --check
.\.venv\Scripts\python.exe scripts/train_current_crops.py --register
.\.venv\Scripts\python.exe scripts/prepare_research_service.py
.\.venv\Scripts\python.exe scripts/prepare_data_bundle.py
.\.venv\Scripts\python.exe scripts/report_current_crops.py
.\.venv\Scripts\python.exe scripts/report_model_readiness.py
.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8011 --frontend-port 5174
```

Training an identical completed study returns the hash-verified frozen report,
without retuning or consuming final outcomes again. New configurations require a
genuinely new untouched test. Source rows that have already been imported are
identified by hash. Installed dependencies are not bundled; the prepared data and
frozen artifacts support local inference without another internet download.

The running dashboard is `http://127.0.0.1:5174`; Swagger is
`http://127.0.0.1:8011/docs`. Tests through `/backend` on the frontend origin
returned **200 for all 12 forecasts**, fresh observations and history for all four
crops, and four feasible cash-aware recommendations. Every example cost, buyer
quote and deterioration assumption in these smoke requests is labeled EXAMPLE_ONLY.
Limited research forecasts retain safe advice fallbacks. Exact requests,
responses, units, dates, source hashes and model versions are in
`reports/current-live-smoke.json`.

No perfect, guaranteed or prospectively validated accuracy is claimed. These
are mandi modal-price forecasts, not guaranteed farmer transaction prices.

## Executed verification and delivery

| Command | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests -q` | **111 passed**, one upstream Starlette/httpx deprecation warning |
| `npm --prefix frontend test` | **20 passed**, including all four crop selections and Kannada warnings |
| `.\.venv\Scripts\python.exe scripts/run_e2e.py` | **3 HTTP integration tests passed** |
| `npm --prefix frontend run typecheck` | exit 0 |
| `npm --prefix frontend run build` | exit 0; bundle-size advisory above 500 kB remains |
| `npm --prefix frontend run lint` | exit 0 |
| `.\.venv\Scripts\python.exe -m ruff check backend scripts tests` | exit 0 |
| `.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8011 --frontend-port 5174 --check` | exit 0; existing database preserved and services ready |
| `.\.venv\Scripts\python.exe scripts/train_current_crops.py --register` (repeat) | four frozen reports reused; no retuning or second final evaluation |

New regression tests verify scope/response validation, rejection of incomplete
downloads, leakage-free CV labels, nonoverlapping CV targets, baseline-only gates,
cross-source history deduplication before pagination, all 12 real saved-artifact
predictions and stale fallbacks. The first full run exposed two obsolete assertions
that hardcoded 1,943 official rows; they now check manifest counts and exact
preservation of authentic rows. Initial failure output is retained alongside the
passing run. No data or model metric was changed to make a test pass.

`.gitattributes` preserves byte-for-byte data, model, report and registry files,
preventing Windows newline conversion from invalidating their SHA256 pins.
A temporary isolated Git index checked **688 hash-sensitive files with zero byte
mismatches**, without changing the user's staging area. When publishing this
attribute migration, explicitly renormalize the previously tracked evidence:

```powershell
git add --all
git add --renormalize -- data models reports research-registry.json research-serving-registry.json
```

Detailed logs are `reports/current-all-backend-tests.log`,
`reports/current-frontend-tests.log`, `reports/current-http-e2e.log`,
`reports/current-live-smoke.json`, `reports/current-packaging-verification.json`
and `reports/current-verification.json`. The source acquisition/training/API/UI
work in this update is included on branch `sub2` with the frozen source and model artifacts.
