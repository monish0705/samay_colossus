# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-35245f4e3dabb00e
Train: 2025-10-27–2026-07-15; selection: 2026-07-16–2026-09-15; final: 2026-09-16–2026-11-04

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | naive | 158 | 45 | 39 | 143.59 | 143.5897435897436 | 504.34 | 5.51 | 6.33 | 79.48717948717949 |
| 3d | naive | 156 | 43 | 37 | 302.70 | 302.7027027027027 | 732.27 | 11.62 | 13.27 | 56.75675675675676 |
| 7d | median_14 | 153 | 40 | 34 | 532.35 | 482.3529411764706 | 1006.01 | 19.80 | 23.09 | 38.23529411764706 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.