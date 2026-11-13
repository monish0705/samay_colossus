# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-52875c5dff4eac15
Train: 2021-01-01–2023-12-31; selection: 2024-01-01–2024-12-31; final: 2025-01-01–2025-10-17

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | median_14 | 533 | 226 | 163 | 1689.72 | 1471.2576687116564 | 2239.16 | 2.85 | 2.88 | 60.73619631901841 |
| 3d | median_14 | 530 | 226 | 161 | 1725.79 | 1731.0062111801242 | 2317.91 | 2.90 | 2.94 | 60.86956521739131 |
| 7d | median_14 | 524 | 224 | 158 | 1834.50 | 1728.2974683544303 | 2475.28 | 3.07 | 3.12 | 57.59493670886076 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.