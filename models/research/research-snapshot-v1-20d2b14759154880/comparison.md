# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-20d2b14759154880
Train: 2021-01-01–2023-12-31; selection: 2024-01-01–2024-12-31; final: 2025-01-01–2025-10-25

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | blend_naive_mean14_25 | 436 | 190 | 68 | 236.59 | 253.38235294117646 | 322.88 | 22.63 | 22.32 | 66.17647058823529 |
| 3d | median_14 | 432 | 187 | 65 | 259.23 | 225.3846153846154 | 342.21 | 24.63 | 24.24 | 53.84615384615385 |
| 7d | median_14 | 425 | 182 | 59 | 265.85 | 277.1186440677966 | 353.50 | 24.94 | 24.75 | 54.23728813559322 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.