> Updated data/model status: see [SECONDARY-MODELS](SECONDARY-MODELS.md). The initial missing-history statements and earlier verification counts below are historical.

# Corrected SAMAY handoff — 5 November 2026

Branch: `sub2`. Changes are local; no push was performed for this repair task.

## Observed verification

All engineering checks passed. The complete release command exits 2 because validated production forecast readiness is still false. It does not treat limited research as validated advice.

| Check | Exit |
|---|---:|
| migrations | 0 |
| schema-drift | 0 |
| backend-lint | 0 |
| backend-tests | 0 |
| dependency-check | 0 |
| frontend-tests | 0 |
| frontend-typecheck | 0 |
| frontend-lint | 0 |
| production-build | 0 |
| http-e2e | 0 |
| runtime-npm-audit | 0 |
| full-npm-audit | 0 |
| authentic-demo-readiness | 2 |

Backend: **99 passed**. Frontend: **17 passed**. Real HTTP harness: **3 passed**. Both npm audits: **0 vulnerabilities**. One Starlette/httpx deprecation warning remains; Vite reports a nonblocking bundle-size warning.

The first fresh-environment HTTP run failed because research settings leaked from `.env` into the synthetic test server, and a research label took precedence over an operational artifact label. The fixture is now isolated and operational artifacts take precedence. The failing output and summary are preserved as `reports/release/http-e2e.initial-failure.log` and `verification.initial.json`; the final run passes.

## Real running service

Local UI: http://127.0.0.1:5174. Swagger: http://127.0.0.1:8011/docs. These alternate ports preserve the older application instance on 5173/8010.

Actual proxy smoke results are in `reports/corrected-live-smoke.json`: 1,943 official observations; 0 validated operational models; 6 separately listed research artifacts; Local/3d saved mean-14 prediction INR 1,255.71/quintal; limited evidence; latest source date 2026-10-31. The labeled example recommendation used the same model version and returned 20 quintals immediate sale with INR 18,700.00 net cash under its explicitly illustrative costs. It is not a farmer-specific recommendation.

## Main changed/new files

```text
backend/app/
  api_routes.py             # truthful endpoints; unsafe previews retired
  api_services.py           # one prediction path for forecast and advisor
  api_schemas.py config.py  # separate, opt-in research mode
  ingestion.py features.py research.py  # consistent market/district scope
  provenance_repair.py      # idempotent known synthetic-batch reclassification
  research_service.py       # hash-verified, limited-evidence saved inference
  selling.py               # compact source reference; full lineage retained in predictions
scripts/
  collect_official_data.py  # all five public recent reports; no inferred fields
  archive_official_export.py # configurable verified CSV scope
  prepare_research_service.py # frozen configuration refits, no retuning
  report_model_readiness.py # independently reproduce dated test errors
  repair_data_provenance.py # portable bundle/local database correction
  populate_multi_commodities.py # generator retired; no mutation
frontend/src/
  AdvisorPage.tsx Results.tsx MarketPages.tsx advisor.ts api.ts
  i18n.tsx locales/kn.ts generated/api-schema.ts App.test.tsx
data/raw/official-multi-recent/ # original government response captures + hashes
data/prepared/                # corrected database + hash manifest
models/research-serving/      # six saved research refits + metadata
research-serving-registry.json
reports/corrected-model-readiness.{md,json,log}
reports/corrected-live-smoke.json
reports/release/              # exact command arrays, exit codes and full logs
docs/CORRECTIONS.md DEMO.md STATUS.md
```

## Training and data limitations

See `reports/corrected-model-readiness.md` for all six original frozen final metrics, naive comparisons and current refit sample sizes. The Local/3d rolling mean underperformed naive on final observations; no post-holdout replacement was made. Current refits have no new independent final test. All research predictions remain limited evidence.

The four non-tomato markets have only a week of newly archived modal-only observations. Authentic multi-year daily CSV exports with actual variety/grade and full required fields are still needed. Browser automation stopped because it could not reliably determine the URL; public feed downloads succeeded. Do not train on the 7,304 reclassified synthetic rows.

## Run and reproduce

From this repository root in PowerShell:

```powershell
python scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8011 --frontend-port 5174
# In a second terminal:
.\.venv\Scripts\python.exe scripts/collect_official_data.py
.\.venv\Scripts\python.exe scripts/prepare_research_service.py
.\.venv\Scripts\python.exe scripts/report_model_readiness.py
.\.venv\Scripts\python.exe scripts/verify_release.py
```

The last command intentionally returns 2 until validated production readiness is established; individual engineering results and exact outputs are in `reports/release/verification.json`. See `CORRECTIONS.md` for official historical export/import instructions and existing `.env` settings.
