# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-6dd9ea73854cc050
Train: 2021-01-01–2023-12-31; selection: 2024-01-01–2024-12-31; final: 2025-01-01–2025-06-30

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | naive | 1050 | 341 | 136 | 108.31 | 108.30882352941177 | 174.17 | 15.34 | 14.87 | 22.794117647058822 |
| 3d | naive | 1048 | 339 | 132 | 138.79 | 138.78787878787878 | 209.92 | 18.56 | 18.91 | 20.454545454545457 |
| 7d | naive | 1044 | 335 | 128 | 140.31 | 140.3125 | 235.94 | 18.13 | 18.98 | 21.09375 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.