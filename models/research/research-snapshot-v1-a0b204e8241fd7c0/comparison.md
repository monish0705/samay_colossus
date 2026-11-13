# SAMAY retrospective snapshot research

RETROSPECTIVE RESEARCH ONLY: current government snapshot, not verified historical vintages. Feature-view availability assumes next-day 00:00 Asia/Kolkata publication. Later source revisions may be present. Metrics are conditional on this assumption, not demonstrated live/as-of performance or farmer realized-price accuracy. Artifacts cannot be deployed as validated production forecasts.

Run: research-snapshot-v1-a0b204e8241fd7c0
Train: 2025-10-27–2026-07-31; selection: 2026-08-01–2026-09-15; final: 2026-09-16–2026-11-04

| Horizon | Selected | Train n | Validation n | Final n | Final MAE INR/qtl | Naive MAE INR/qtl | RMSE INR/qtl | sMAPE % | WAPE % | Direction % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1d | median_14 | 118 | 35 | 39 | 689.74 | 974.3589743589744 | 964.17 | 3.80 | 3.83 | 64.1025641025641 |
| 3d | median_14 | 116 | 34 | 37 | 720.27 | 994.5945945945946 | 1007.30 | 3.96 | 4.00 | 67.56756756756756 |
| 7d | median_14 | 113 | 30 | 34 | 717.65 | 1052.9411764705883 | 1028.71 | 3.95 | 3.99 | 61.76470588235294 |

Full candidate CV/validation and final baseline metrics: comparison.json. Final prediction rows: final-predictions-Nd.csv.
Directional accuracy is a direction classification measure; 100 minus WAPE/sMAPE is not reported as model accuracy.
No final result was used to retune the chosen model. Final labels may have current-snapshot revisions; no live performance claim.