# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-a18c6b2407216a5a
Train: 2025-10-27–2026-07-31; selection: 2026-08-01–2026-09-15; final: 2026-09-16–2026-11-04

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | naive | 120 | 28 | 28 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| 3d | naive | 120 | 27 | 26 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |
| 7d | mean_14 | 116 | 23 | 24 | unavailable | unavailable | unavailable | unavailable | unavailable | unavailable |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.