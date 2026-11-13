# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-ace0b738d62a1d97
Train: 2021-01-01–2023-12-31; selection: 2024-01-01–2024-12-31; final: 2025-01-01–2025-06-19

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | naive | 799 | 239 | 39 | 491.08 | 491.0769230769231 | 699.07 | 2.74 | 2.85 | 2.564102564102564 |
| 3d | blend_naive_mean14_25 | 794 | 237 | 38 | 696.70 | 618.0263157894736 | 1053.45 | 3.91 | 4.05 | 44.73684210526316 |
| 7d | blend_naive_mean14_25 | 783 | 235 | 36 | 1042.10 | 900.1111111111111 | 1504.35 | 5.70 | 5.99 | 33.33333333333333 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.