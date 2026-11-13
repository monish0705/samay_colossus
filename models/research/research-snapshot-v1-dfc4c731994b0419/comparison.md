# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-dfc4c731994b0419
Train: 2025-10-27–2026-07-15; selection: 2026-07-16–2026-09-15; final: 2026-09-16–2026-11-04

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | blend_naive_mean14_25 | 142 | 42 | 34 | 377.94 | 400.0 | 479.01 | 9.16 | 8.93 | 55.88235294117647 |
| 3d | naive | 141 | 40 | 32 | 559.38 | 559.375 | 740.14 | 13.55 | 13.11 | 6.25 |
| 7d | blend_naive_mean14_50 | 137 | 37 | 29 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.