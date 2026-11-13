# Executed acquisition and model verification · 2026-11-04

- Six official browser exports were downloaded with per-query CAPTCHA authorization.
  Original/normalized CSV hashes and timestamps are in ACQUISITION.md and the local
  per-year provenance manifests. SQLite was backed up before import.
- 1,943 official records imported; zero quarantined/duplicate/revised rows. Three
  old fixture rows remain separate. API latest returns actual 2026-10-31 Tomato/Local
  modal ₹1,400/quintal, minimum ₹330, maximum ₹3,000 with government source URL and
  actual November 4 fetch timestamp. This is an observation, not a prediction.
- Two grade-specific research commands in MODEL-RESULTS.md exited 0 and saved six
  frozen baseline artifacts. FAQ compared nine candidates per horizon including
  LightGBM; Local compared seven. Grades/varieties were not merged.
- Identical command reruns returned the same frozen report directories, without
  retraining or reopening final evaluation. Source-code identity, registry report
  SHA256 and all six pickle hashes were checked. Independent CSV arithmetic checked
  MAE, RMSE, WAPE and naive MAE for every final prediction file.

## Checks actually executed

| Command | Observed result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest tests -q` | **90 passed**, 1 existing Starlette/httpx deprecation warning; 91.98s |
| `npm.cmd test` in frontend | **14 passed** |
| `.venv\Scripts\python.exe scripts/run_e2e.py` | **3 passed**, isolated real HTTP fixture |
| `npm.cmd run build` | TypeScript + production build passed; JS 485.74 kB / gzip 143.73 kB |
| `npm.cmd run typecheck` | Passed |
| `npm.cmd run lint` | Passed |
| `.venv\Scripts\python.exe -m ruff check backend scripts tests` | Passed |
| `.venv\Scripts\python.exe -m pip check` | No broken requirements |
| `.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check` | No schema drift |
| `.venv\Scripts\python.exe scripts/report_research_results.py` | All six frozen CSV metric checks passed; actual plots/report produced |

Logs: `reports/post-acquisition-backend-tests.log`,
`post-acquisition-frontend-tests.log`, `post-acquisition-frontend-build.log`,
`post-acquisition-http-e2e.log`, `train-research-faq.log`, `train-research-local.log`,
`research-faq-reproduction.log`, `research-local-reproduction.log`.

The initial research unit rerun overlapped optional LightGBM installation and
correctly detected a changed runtime identity. It was rerun after installation
stabilized and passed. A CAPTCHA transcription was rejected and corrected for the
same authorized 2023 query. No data/metric value was altered to resolve either issue.
An older backend listener hid new research fields; it was identified as this
repository's Uvicorn process and restarted. Actual HTTP now returns both studies.

## Browser checks

Current frontend/backend were started and actual data/metrics were verified through
the UI. Dashboard shows 371 Tomato/Local observations and ₹1,400 latest modal price.
Transparency shows 1,943 total official rows, both research studies, actual errors
and their limitations. Switching Kannada preserved ₹108.31, ₹138.79, ₹140.31 and
₹212.82; no recalculation or alternate financial values occurred.

Screenshots: `screenshots/official-data-dashboard.jpg`,
`actual-research-metrics-en.jpg`, `actual-research-metrics-kn.jpg`,
`official-history-downloaded.jpg`. Actual final prediction plots are under
`reports/research/research-snapshot-v1-*/final-predictions.png`.

Model results remain conditional on a next-day publication assumption applied only
to the research feature view. Original publication/revision histories were not
available. No validated live reliability, calibrated future interval or farmer
income gain is claimed. Operational prediction rejects research artifacts.
