# Additional data and model handoff — 5 November 2026

The missing multi-year historical acquisition and research training have now been
completed for Copra, Arecanut, Onion and Potato. There are **7,777 usable stored
observations**: 1,943 direct government observations and **5,834 separately labeled
secondary observations**. The 7,304 legacy generated records remain demo data and
are excluded from both source classes and all training.

There are **six frozen studies and 18 saved research horizon artifacts**. This
does not mean 18 validated live models: Potato/3d and /7d lack 30 final examples,
and the additional series are stale for current-day forecasting. No perfect
accuracy, guaranteed interval coverage or confident holding advice is claimed.

## Publisher and evidence

Publisher: [India Data Portal / Indian School of Business](https://indiadataportal.com/p/agriculture-marketing).
The [published CKAN collection](https://ckandev.indiadataportal.com/dataset/agriculture-marketing)
links both CSV resources, their data dictionaries, the DataStore API documentation
and **Open Data Commons Attribution License**. Upstream source is AGMARKNET / DMI,
Ministry of Agriculture and Farmers Welfare. These are secondary mirror downloads,
not files claimed to have been downloaded directly from the government.

The adapter discovers actual resource identifiers from those published links.
It uses the linked public DataStore API with explicit state/market/commodity
filters, pagination and unique row-ID checks. Exact responses, query bodies,
SHA256 hashes, actual fetch timestamps, publisher pages, import CSVs and manifests
are retained under `data/raw/idp-history/20261104T193424Z/`.

| Scope | Old-source rows | New-source rows | Coverage represented |
|---|---:|---:|---|
| Tiptur / Copra | 1,259 | 121 | Jan 2021–May 2026 |
| Shimoga / Arecanut | 1,064 | 598 | Jan 2021–May 2026 |
| Hubli/Hubballi / Onion | 1,299 | 203 | Jan 2021–May 2026 |
| Bangalore/Bengaluru / Potato | 993 | 300 | Jan 2021–May 2026, with a source gap |

Of 5,837 retrieved rows, **5,834 were accepted and 3 quarantined**. Two Onion rows
have impossible min/modal/max orderings. One Arecanut/Saraku row has maximum
100,340 INR/quintal, above the configured 100,000 review threshold. It is held for
review, not asserted to be false or silently corrected. Original rows are retained.

The older source has no grade column. Its grade is explicitly `unspecified`, never
assigned FAQ or combined with newer Local/Medium grades. Selected high-coverage
historical varieties are Copra=`copra`, Arecanut=`bette`, Onion=`local`, Potato=`local`.
The Arecanut model is **Bette**, not Rashi/Rashi Edi. Those source variants do not
have enough consistent history for the same reliable study and are not relabeled.

CEDA was also checked: its documented API requires a token. Other published
market-day aggregates do not preserve a complete variety ledger. They were not
substituted for these variety-specific training observations.

## Frozen study design

All four studies use training **2021–2023**, development validation **2024**, and
one final chronological test starting **1 January 2025**, ending at the last actual
observation of the selected series. No missing dates or grades are filled.

| Crop / variety | Final end | 1d / 3d / 7d training examples | 1d / 3d / 7d validation examples |
|---|---|---|---|
| Copra / copra | 19 Jun 2025 | 799 / 794 / 783 | 239 / 237 / 235 |
| Arecanut / bette | 17 Oct 2025 | 533 / 530 / 524 | 226 / 226 / 224 |
| Onion / local | 25 Oct 2025 | 436 / 432 / 425 | 190 / 187 / 182 |
| Potato / local | 21 Feb 2025 | 706 / 701 / 700 | 186 / 182 / 182 |

Selection uses three chronological rolling-origin folds and the separate validation
period, with exact calendar targets and split-crossing label embargoes. Candidate
families include naive, rolling mean/median, seasonal naive when supported, fixed
naive/mean blends, regularized regression, histogram boosting and eligible LightGBM.
The added `relative_v2` models predict returns from prices relative to the latest
known price and known cyclic calendars. No weather/festival values are invented.
All candidates share dates and targets. ML must consistently beat core baselines
before promotion. **The selected champions remain baselines.**

The Onion study predeclares a 35% observed-calendar-date coverage floor for irregular
reporting; other series retain 50%. Minimum samples, span, three folds, label timing
and age checks remain enforced. Coverage is reported, not treated as a constant
daily trading frequency.

Final tests were consumed only after selections were frozen. An additional audit
guard now rejects **overlapping** final-date intervals: changing an end date cannot
turn previously seen targets into a fresh test. Existing metrics are never used to
swap a selected champion after testing.

## Actual final errors

WAPE is a percentage **error**, not an accuracy percentage. MAE/RMSE are INR/quintal.
Full candidate comparisons and naive errors are in each study's `comparison.json`
and in [the reproduced consolidated report](../reports/corrected-model-readiness.md).

| Crop / variety | Horizon | Selected | Final n | MAE INR/quintal | WAPE % |
|---|---:|---|---:|---:|---:|
| Copra / copra | 1d | naive | 39 | 491.08 | 2.85 |
| Copra / copra | 3d | 75% naive + 25% mean-14 | 38 | 696.70 | 4.05 |
| Copra / copra | 7d | 75% naive + 25% mean-14 | 36 | 1,042.10 | 5.99 |
| Arecanut / bette | 1d | median-14 | 163 | 1,689.72 | 2.88 |
| Arecanut / bette | 3d | median-14 | 161 | 1,725.79 | 2.94 |
| Arecanut / bette | 7d | median-14 | 158 | 1,834.50 | 3.12 |
| Onion / local | 1d | 75% naive + 25% mean-14 | 68 | 236.59 | 22.32 |
| Onion / local | 3d | median-14 | 65 | 259.23 | 24.24 |
| Onion / local | 7d | median-14 | 59 | 265.85 | 24.75 |
| Potato / local | 1d | naive | 31 | 161.29 | 7.47 |
| Potato / local | 3d | naive | 29 | insufficient final evidence | unavailable |
| Potato / local | 7d | naive | 26 | insufficient final evidence | unavailable |

Some selections lose to naive on final observations. Those outcomes are retained.
This is not evidence of a universally superior ML system. The original tomato
study results are unchanged; its consumed final data was not used to perfect a
new model. All serving refits reference their frozen studies and have no newly
claimed independent final evaluation.

## UI and API behavior

- Market Insights and the Dashboard use actual observations with explicit source
  labels. The `secondary` class is separate from `official`, `fixture` and `demo`.
- Price Forecast includes a **Historical evaluation: actual versus predicted**
  panel with dated plots, original metrics, naive comparisons and inspectable rows.
  It uses `GET /api/v1/models/evaluation`, verifying report and prediction CSV hashes.
- The selected old series use `grade=unspecified`. Freshness is checked per series.
  Current prediction requests for stale series return **503 `stale_market_data`**.
  A successful historical panel is not presented as a current prediction.
- Runtime research inputs can use only downloads available by the actual aware
  decision timestamp, while report dates remain strictly before the origin date.
  Historical training/evaluation retains its explicit midnight publication assumption.
  Original publication/revision timestamps remain unverified.
- Operational validated models remain separate from the 18 research artifacts.
  Limited evidence never silently enables confident hold recommendations.
- A stale historical observation is never prefilled as today's selling quote.
  The advisor requires a current price entered by the farmer in that case.
  The dashboard counts saved research artifacts separately from live validation.

## Reproduce on Windows PowerShell

From this repository root, after the existing setup:

```powershell
.\.venv\Scripts\python.exe scripts/collect_idp_history.py
.\.venv\Scripts\python.exe scripts/import_idp_history.py
foreach ($crop in @('Copra', 'Arecanut', 'Onion', 'Potato')) {
    .\.venv\Scripts\python.exe scripts/train_secondary_markets.py --commodity $crop --register
    if ($LASTEXITCODE -ne 0) { throw "Study failed: $crop" }
}
.\.venv\Scripts\python.exe scripts/prepare_research_service.py
.\.venv\Scripts\python.exe scripts/prepare_data_bundle.py
.\.venv\Scripts\python.exe scripts/report_model_readiness.py
.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8011 --frontend-port 5174
```

Identical captures are not imported again. Repeating a completed study returns its
hash-verified frozen report; it does not retune or consume the final period again.
To fit a genuinely changed configuration, reserve a genuinely new untouched test.
The portable database has no recommendation history and verifies all eligible raw
archives before replacement. Existing user databases are preserved by startup;
run the importer explicitly to add the new captures there.

Source acquisition/import logs, study commands, all candidate metrics, dated final
predictions, metadata, fingerprints and unit/integration outputs are saved under
`reports/`, `data/raw/idp-history/`, `data/processed/imports/` and `models/research/`.
`reports/secondary-live-smoke.json` captures real proxy requests: historical
evaluations succeed for all four crops; stale current forecasts fail clearly.

## Final verification actually executed

| Command (repository root) | Observed result |
|---|---|
| `.\.venv\Scripts\python.exe -m pytest tests -q` | 105 passed; one upstream Starlette/httpx deprecation warning |
| `npm --prefix frontend test` | 19 passed, including stale-quote rejection and language consistency |
| `.\.venv\Scripts\python.exe scripts/run_e2e.py` | 3 HTTP integration tests passed |
| `npm --prefix frontend run typecheck` | exit 0 |
| `npm --prefix frontend run lint` | exit 0 |
| `npm --prefix frontend run build` | exit 0; production bundle produced |
| `.\.venv\Scripts\python.exe -m ruff check backend scripts tests` | exit 0 |
| `.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head` | exit 0 |
| `.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check` | exit 0; no schema drift |
| `.\.venv\Scripts\python.exe -m pip check` | exit 0 |
| `npm --prefix frontend audit --json` | 0 reported vulnerabilities |
| `.\.venv\Scripts\python.exe scripts/verify_release.py` | exit 2: engineering checks pass; validated-live readiness remains false |

The readiness failure is retained deliberately: secondary series are stale,
publication vintages are unverified, and saved research artifacts do not establish
prospective farmer-facing validation. It must not be interpreted as a deployment
approval. HTTP integration fixtures test wiring, not market performance; actual
historical errors above come from the archived secondary observations.

Detailed outputs: `reports/release/verification.json`,
`reports/release/backend-tests.log`, `reports/secondary-frontend-final.log`,
`reports/secondary-http-e2e-final.log` and `reports/secondary-live-smoke.json`.
Code, raw captures and trained artifacts are included in branch `sub2`.
Credentials, runtime databases and installed dependencies remain excluded.
