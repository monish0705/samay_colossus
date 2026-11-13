# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-bf5682f4a2bfbde9
Train: 2025-07-03–2026-06-30; selection: 2026-07-01–2026-08-31; final: 2026-09-01–2026-10-31

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | naive | 212 | 60 | 59 | 134.75 | 134.74576271186442 | 184.25 | 11.89 | 11.44 | 27.11864406779661 |
| 3d | mean_14 | 210 | 58 | 57 | 212.82 | 174.73684210526315 | 256.50 | 18.29 | 18.03 | 47.368421052631575 |
| 7d | mean_14 | 212 | 54 | 53 | 240.32 | 240.56603773584905 | 287.23 | 20.45 | 20.21 | 58.490566037735846 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.