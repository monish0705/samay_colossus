# Point-in-time market analysis and features (Prompt 3)

## Current result and data prerequisite

Prompt 2 did **not** obtain an authenticated historical government CSV. The local
database contains only fixture observations; these are excluded by the production
feature loader. Therefore the actual effective training and validation sample
counts are **zero for each of 1, 3 and 7 calendar days**. No model has been fitted,
no forecasts are available, and no seasonality conclusions are claimed.

This stage implements reproducible algorithms and insufficient-data artifacts,
not a successful analysis of an unavailable government history. Follow ingestion.md
to obtain real data. A recent download of old report dates is not evidence of what
was known at historical decision times. Meaningful leakage-safe backtests additionally
need original timestamped source snapshots, captured before each decision, or an
independently verified publication/version archive. The pipeline does not backdate
`fetched_at` to `report_date` to manufacture training availability.

## Reproduce on Windows PowerShell

From the repository root:

```powershell
# UTF-8 avoids pip logging failures under Windows legacy console encoding.
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pip install -e './backend[dev,analysis]'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/build_market_features.py --start 2025-01-01 --train-end 2025-06-30 --validation-end 2025-09-30 --holdout-end 2025-12-31 --market 'Kolar APMC' --commodity Tomato --variety local --grade faq
$LASTEXITCODE
.\.venv\Scripts\python.exe -m pytest tests -q
```

The dates and local/faq series above define an explicit example analysis plan;
they do not assert those authentic observations exist. Choose and freeze a plan
appropriate to a real source **before** inspecting analysis results. CLI requires
explicit boundaries and a variety and grade; it never automatically chooses the
best-performing variety or split from outcomes. Exit codes: 0 = at least one
horizon passes development viability checks, 2 = all horizons insufficient, 1 =
invalid configuration, unavailable dependencies/database, or integrity error.

Output from the current data:

```text
STATUS: insufficient_data
horizon_days | effective_train | effective_validation | status
           1 |               0 |                    0 | insufficient_data
           3 |               0 |                    0 | insufficient_data
           7 |               0 |                    0 | insufficient_data
Final holdout: reserved; no values read for analysis/evaluation. No model trained.
```

## Selection and source integrity

The selected series is Karnataka / Kolar / Kolar APMC / Tomato / one normalized
variety / one normalized grade. Distinct varieties and grades are never averaged
together. Input is the cleaned ImportRow/ImportBatch ledger, not current-value
`prices.csv`: current-value exports cannot reconstruct historical revisions.

Only official batches with valid SourceManifest metadata and matching local raw
archive SHA256 are admitted. Manifest/source-label/hash consistency and normalized
scope/units/price ordering are checked. A local archive hash proves byte integrity,
not independent publisher authentication. Operator download attestations remain
explicitly identified as such in metadata; the pipeline cannot certify a publisher
or timestamp it did not independently witness. No fixture/demo override exists in
the CLI. Deterministic analytical sequences exist only in unit tests and are never
written to actual production feature datasets.

The loader selects only report dates through validation_end and snapshots fetched
strictly before holdout_start. Final holdout price rows are not selected into the
analysis frame. Hashing an archived file for integrity can touch its bytes, including
holdout bytes when a source download spans multiple partitions; these are not
parsed into holdout statistics or labels by this feature workflow. Source-wide
quality counts are not treated as training-period statistics.

## Decision timing and feature definitions

An origin is **00:00 Asia/Kolkata on calendar date D**. Target is the selected
series' modal wholesale price in **INR/quintal on exactly D+h**, separately for
h=1, 3 and 7 calendar days. This definition does not guarantee farmer realization.
Missing exact target dates are marked `missing_target_at_label_freeze`; nearest
observation, forward-fill and interpolation are never substituted.

At each origin, predictors use only report dates strictly before D and versions
whose source snapshot `fetched_at <= origin_timestamp`. For each report date, the
latest eligible snapshot is selected. Future revisions are unavailable until their
actual fetch timestamp. Accepted inserted/revised/duplicate ledger rows are used;
stale or quarantined conflicting imports are excluded. Conflicting simultaneous
vintages raise a clear error rather than silently selecting a price. This conservative
policy can omit an older snapshot that the importer marked stale; it never treats
the latest database observation as historical truth.

Predictors are explicitly allowlisted in metadata:

- Lags 1, 2, 3, 7, 14, 30: Nth most recent **available observation**, not N calendar
  days ago. No unreported dates are inserted into this observation sequence.
- Rolling mean, median and sample standard deviation (ddof=1) over the preceding
  7, 14, 30 available observations; each requires the full N observations. This is
  a causal shift before rolling, implemented by an explicit as-of history slice.
- Known origin/target weekday (Monday=0) and month.
- Days since latest available report and calendar span of the last 30 observations.

There is no target-day price, observed min/max, arrivals, weather or other external
predictor. No full-dataset scaler, imputer or feature selection is fitted. All future
preprocessing must fit on training data only. Metadata/audit fields and `*_y.csv`
must never be automatically included as predictors; only `feature_columns` are X.

## Chronological partitions and embargo

| Partition in executed example | Origin dates | Permitted purpose |
| --- | --- | --- |
| Train | 2025-01-01 through 2025-06-30 | Fit and training-period EDA |
| Validation | 2025-07-01 through 2025-09-30 | Tune choices/hyperparameters |
| Final holdout | 2025-10-01 through 2025-12-31 | Reserved, unopened final evaluation |

For each horizon purge every training origin whose D+h target crosses train_end,
and every validation origin whose target crosses validation_end. This removes the
last h origin days from each development partition. In addition, training labels
must actually be available strictly before validation_start; validation labels
must be available strictly before holdout_start. Delayed reporting can therefore
remove more samples than a simple h-day embargo. Labels are fixed at those freeze
times and do not adopt later revisions. Audit records retain target dates, label
availability/source row, origin timestamp and feature source-row IDs.

Final holdout materialization is intentionally absent: only its origin and exact
target dates and a target-boundary eligibility flag are saved. No final X, y,
counts of observed holdout prices, charts, tuning or evaluation are produced.
`reports/holdout_registry.json` freezes boundaries per selected series; a rerun
with different boundaries in the same output root is refused. This is a local
operational guard, not an access-control or tamper-proof service. Preserve the
registry and predeclare boundaries; changing output directories must not be used
to reclassify a previously inspected holdout as validation. Run one report writer
at a time. A future final-evaluation step requires an explicit separate workflow.

## Reliability and effective sample size

Candidates are all calendar origins in each partition. Effective samples require
an exact available label, 30 causal observations to satisfy the complete feature
set, and latest report no older than 7 calendar days. All exclusions are counted
by partition/reason and written to development_audit.csv, including purged rows.

Default development viability policy requires >=120 effective training samples,
>=30 validation samples, >=180 calendar days spanned by eligible training origins,
and >=50% training-date reporting coverage. These are transparent engineering
screening thresholds, not a statistical guarantee, model accuracy claim or proof
of annual seasonality. Thresholds are recorded in the plan; short/irregular series
must be judged for the intended evaluation. Defaults are not relaxed by the CLI
to create apparent viability. Each horizon reports its own status and counts.

## Versioned artifacts and frontend handoff

`reports/samay-features-v1-<fingerprint>/` contains:

- `metadata.json`: source hashes/URLs/evidence, date plan, series, horizon sample
  sizes/exclusions, definitions, runtime versions, code hashes and artifact hashes.
- `horizon-{1,3,7}d/`: train/validation X and y CSVs, development audit, and final
  holdout date plan without values. Missing-data runs write empty feature/label
  datasets with stable headers; they never fabricate examples.
- Six PNGs: price-over-time, weekday means/counts, month means/counts, consecutive
  observed-price returns, missing-date availability, and reporting quality.
- `market_insights.json`: chart-ready series, mean/median, observed return standard
  deviation, weekday/month means with group counts, missing-date list, scope and
  honest status/caveats. The frontend should show an insufficient-data state when
  indicated and keep absent statistics null. It must not turn these into forecasts.

EDA uses training-period observations as known before validation_start only;
neither validation nor holdout prices influence these summaries. Consecutive
observation returns can span unequal calendar gaps: the plot is not daily or
annualized volatility, and not prediction uncertainty. Missing calendar dates
are reporting gaps, not proof of market closure or data loss. Seasonality groups
are descriptive associations with visible sample counts, not causal effects.
Where no authenticated observations exist, PNGs explicitly display insufficient
data instead of charting fixtures. No frontend page was wired to filesystem paths;
these artifacts form the contract for a later Market Insights endpoint/screen.

The fingerprint includes algorithm version, source metadata/data hashes, code
hashes, configuration and runtime versions. An identical rerun reuses immutable
outputs and verifies their hashes. Changed artifacts fail instead of silently
overwriting the prior run. New code/data creates a separate version. Temporary
directories are renamed into place only after all outputs finish. Generated
datasets/charts and registry are ignored by Git; preserve them in controlled
artifact storage along with raw provenance and database backups.

## Tests and next handoff

Automated tests check exact lag/rolling values; future/origin/target mutations;
late-original availability; delayed revisions; missing targets; per-horizon purge;
label freeze times; holdout invariance; train-only EDA; insufficiency thresholds;
fixture exclusion; immutable outputs and holdout-boundary freeze.

Obtain authenticated versioned official snapshots and verify their historical
availability before claiming effective training samples. Re-run the frozen plan
and inspect all horizon counts and exclusions. Keep final holdout untouched.
No Prompt 4 work, model training, tuning or final evaluation was started.
