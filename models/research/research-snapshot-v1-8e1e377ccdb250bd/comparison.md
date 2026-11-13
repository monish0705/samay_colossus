# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-8e1e377ccdb250bd
Train: 2021-01-01–2023-12-31; selection: 2024-01-01–2024-12-31; final: 2025-01-01–2025-02-21

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | naive | 706 | 186 | 31 | 161.29 | 161.29032258064515 | 246.26 | 7.09 | 7.47 | 41.935483870967744 |
| 3d | naive | 701 | 182 | 29 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| 7d | naive | 700 | 182 | 26 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.