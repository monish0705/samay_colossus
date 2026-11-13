# Current APMC crop model results — 5 November 2026

Frozen chronological study; retrospective snapshot research, not prospectively validated accuracy.

| Crop / variety / grade | Days | Selected | Train / validation / final n | Candidate count | Validation MAE | Final MAE | Final naive MAE | Final WAPE error % |
|---|---:|---|---|---:|---:|---:|---:|---:|
| Copra / other / local | 1 | median_14 | 118 / 35 / 39 | 6 | 740.00 | 689.74 | 974.36 | 3.83 |
| Copra / other / local | 3 | median_14 | 116 / 34 / 37 | 6 | 776.47 | 720.27 | 994.59 | 4.00 |
| Copra / other / local | 7 | median_14 | 113 / 30 / 34 | 6 | 663.33 | 717.65 | 1052.94 | 3.99 |
| Arecanut / rashi / local | 1 | naive | 120 / 28 / 28 | 5 | 732.32 | insufficient final evidence | insufficient final evidence | insufficient final evidence |
| Arecanut / rashi / local | 3 | naive | 120 / 27 / 26 | 6 | 911.48 | insufficient final evidence | insufficient final evidence | insufficient final evidence |
| Arecanut / rashi / local | 7 | mean_14 | 116 / 23 / 24 | 6 | 1426.31 | insufficient final evidence | insufficient final evidence | insufficient final evidence |
| Onion / puna / local | 1 | blend_naive_mean14_25 | 142 / 42 / 34 | 12 | 221.81 | 377.94 | 400.00 | 8.93 |
| Onion / puna / local | 3 | naive | 141 / 40 / 32 | 12 | 337.50 | 559.38 | 559.38 | 13.11 |
| Onion / puna / local | 7 | blend_naive_mean14_50 | 137 / 37 / 29 | 12 | 360.62 | insufficient final evidence | insufficient final evidence | insufficient final evidence |
| Potato / local / medium | 1 | naive | 158 / 45 / 39 | 13 | 40.00 | 143.59 | 143.59 | 6.33 |
| Potato / local / medium | 3 | naive | 156 / 43 / 37 | 13 | 83.72 | 302.70 | 302.70 | 13.27 |
| Potato / local / medium | 7 | median_14 | 153 / 40 / 34 | 13 | 115.00 | 532.35 | 482.35 | 23.09 |

MAE and RMSE use INR/quintal. WAPE is error, not an accuracy score. Final metrics require >=30 examples; sparse final sets retain their counts without a reliable final score.

All selected configurations remain baselines. Some final errors exceed naive; frozen selections were not changed after testing.

Current-grade source overlap checks (identical variety and grade only):
- Copra: 92 overlapping dates, 92 matching modal prices, 0 differences retained in JSON.
- Arecanut: 103 overlapping dates, 103 matching modal prices, 0 differences retained in JSON.
- Onion: 0 overlapping dates, 0 matching modal prices, 0 differences retained in JSON.
- Potato: 49 overlapping dates, 49 matching modal prices, 0 differences retained in JSON.
