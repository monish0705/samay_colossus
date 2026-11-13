# Current evaluation

The real-data retrospective studies are complete. See [MODEL-RESULTS](MODEL-RESULTS.md)
for all six horizon/grade combinations, actual MAE/RMSE/sMAPE/WAPE/direction metrics,
same-row naive comparisons, candidate tables, exact sample sizes, frozen split dates,
reproduction commands and important failures. Six baseline artifacts are saved.
See [ACQUISITION](ACQUISITION.md) for 1,943 original official observations and hashes.

These are conditional current-snapshot results, not verified original-vintage live
performance or farmer profit claims. Strict operational and uncertainty safeguards
remain in place. The previous no-data run below is historical and superseded.

## Historical pre-acquisition evaluation and decisions

Verified 2026-11-04: **0 official observations**, 3 excluded fixture observations,
0 deployed champions. Retrying the official OGD variety-wise page timed out;
AGMARKNET returned HTTP 403. No genuine CSV was obtained.

| Calendar horizon | Effective train | Validation | Champion | MAE / RMSE / sMAPE / WAPE |
| --- | ---: | ---: | --- | --- |
| 1 day | 0 | 0 | None | Unavailable |
| 3 days | 0 | 0 | None | Unavailable |
| 7 days | 0 | 0 | None | Unavailable |

No candidate comparisons were computed; final holdout remains unopened. This is
not a zero-error forecast. No LightGBM or other model superiority is claimed.
Uncertainty calibration n=0 and unseen pairs=0 at each horizon; coverage/width
are unavailable. Decision replay examined 153 dates (2025-05-01–2025-09-30), with
0 scored decisions. Mean/median gain, win rate, worst loss and cash success are
**null**, not zero or 100%. Fixture outcomes are not reported as market performance.

## Exact PowerShell reproduction

```powershell
.\.venv\Scripts\python.exe scripts/build_market_features.py --start 2025-01-01 --train-end 2025-06-30 --validation-end 2025-09-30 --holdout-end 2025-12-31 --variety local --grade faq
# Exit 2; 0 effective samples for 1/3/7d.
# ARTIFACTS: reports\samay-features-v1-68e87f1704aef7ad
.\.venv\Scripts\python.exe scripts/train_forecasts.py --feature-run reports/samay-features-v1-68e87f1704aef7ad --evaluate-final
# Exit 2; champion=NONE, comparisons=0; final unopened.
# models\forecasts\samay-forecast-v1-5b9586e0b4f9372e\comparison.md
.\.venv\Scripts\python.exe scripts/backtest_forecasts.py --feature-run reports/samay-features-v1-68e87f1704aef7ad --calibration-start 2025-01-01 --calibration-end 2025-04-30 --evaluation-end 2025-09-30
# Exit 2; calibration_n=0 unseen_pairs=0 metrics=None for all horizons.
# reports\backtests\samay-reliability-v1-7fc38a3e65acd7a7\summary.json
.\.venv\Scripts\python.exe scripts/backtest_decisions.py --feature-run reports/samay-features-v1-68e87f1704aef7ad --template docs/examples/selling-example.json --start 2025-05-01 --end 2025-09-30 --scoring-freeze 2025-10-01 --realization-multiplier 1
# Exit 2; 153 dates, 0 scored; aggregate outcomes null.
```

Use the new feature directory printed after any code/runtime/data change. Local
logs are `reports/release-features.log`, `release-training.log`,
`release-reliability.log`, `release-decisions.log`. Generated reports are ignored
by git; this document preserves their conclusion.

## Decision replay

`app.decision_backtesting.replay` freezes inputs at each origin's 00:00
Asia/Kolkata cutoff. Only earlier report dates available then enter the decision.
Today's quote is latest available modal price times the declared realization
factor: an explicit proxy, not a farmer transaction receipt. The template fixes
quantity, cash, fees, lot steps, crop limits, risk and daily storage/loss schedules.

Each option calls the existing reliability service, optionally with `--champions`
and `--evidence`. A champion must predate the decision; future calibration or
assessment cannot validate earlier plans. Inadequate evidence produces the actual
today-only fallback. The CLI predeclares a zero-price adverse stress, not a quantile.

Only after freezing decisions, scoring attaches exact decision/target observations
known at `--scoring-freeze`. Missing dates remain unscored. Settlement reuses
`sale` and stored-quantity calculations: compounded loss, opening-quantity storage
charges, market rounding, fixed/variable fees and payment timing. The benchmark
sells the full crop at the same actual decision-date proxy and costs.

Outputs: `decisions-vs-actual.csv`, full `decisions.jsonl`, summary, source row IDs,
source/code fingerprints, assumptions and file hashes. Cash success uses realized
immediate proceeds, not quoted feasibility. Its denominator is scored recommended
decisions; infeasible/unscored dates are reported separately. Decisions are
independent crop experiments, not a cumulative portfolio. Buyer availability,
disposal costs, actual grade realization and causal farmer-income gains are unverified.

## Leakage audit

- Observation lags and rolling statistics use strict prior availability; no target-day values.
- Exact 1/3/7-day targets, no filling or random splitting; crossing targets are purged.
- Fold labels must exist before the next partition. This creates horizon-dependent embargoes.
- Scaling/fitting occurs inside folds. Validation selects fixed configurations; only development data is refit before final testing.
- Separate final loader reserves an exclusive series/horizon/holdout audit lock before reading final values. These local operational locks can be circumvented by deleting/copying directories; retain the registry.
- Tests mutate future prices, late revisions, origin/target prices and holdout values and assert unchanged historical inputs/decisions.
- Final results include naive and rolling-median metrics on identical rows. The current real run does not invoke final evaluation because samples are absent.

Do not backdate a recent CSV to make old folds nonempty. Obtain genuine dated
archives or collect prospectively and reserve later chronological evaluation.
