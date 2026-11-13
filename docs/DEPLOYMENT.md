# Operation and deployment preparation

> Current research bundle: 1,943 official records and six research-only baseline
> artifacts exist locally. Transfer data/raw/official-history, data/processed/imports,
> SQLite, models/research and research-registry.json with hashes. Set
> SAMAY_RESEARCH_REGISTRY_PATH=research-registry.json to show research results on
> Transparency. This setting never deploys operational forecasts. See MODEL-RESULTS.md.

Local Windows startup has been exercised. Docker and external deployment have
**not** been tested: Docker is not installed on this machine. No deployment URL
or completed cloud release is claimed.

## Local Windows

From the repository root, Python 3.12 and Node.js 22.12+ available:

```powershell
python scripts/setup_local.py
.\.venv\Scripts\python.exe scripts/start_local.py
```

Setup creates `.venv`, installs `backend/requirements-lock.txt` plus the local
package, runs `npm ci`, and copies examples only when target `.env` files do not
exist. It is an online preparation step. Direct `.venv` invocation avoids
PowerShell activation policy. `npm.cmd` avoids blocked `npm.ps1` execution.
Stop repository Vite previews before rerunning setup on Windows. Its native CSS
modules cannot be replaced while loaded. Setup detects repository Vite processes
and exits before touching dependencies. If an earlier install was interrupted,
stop that preview and rerun setup; administrator privileges are not normally needed.

Startup migrates before serving and has bounded readiness polling. Defaults:
backend 8010, frontend 5173. It reuses compatible running services and terminates
only children it created. An existing listener does not automatically reload
changed configuration. Restart it deliberately or select fresh ports.

```powershell
.\.venv\Scripts\python.exe scripts/start_local.py --backend-port 8012 --frontend-port 5175
.\.venv\Scripts\python.exe scripts/start_local.py --check
```

## Environment

| Variable | Purpose |
| --- | --- |
| `SAMAY_DATABASE_URL` | SQLite path; default repository `samay.db`. Relative example URL requires repository working directory. |
| `SAMAY_ENVIRONMENT` | development, test or production; gates development fixture access and replay. |
| `SAMAY_CORS_ORIGINS` | JSON array of explicit frontend origins. No credentials/wildcard required. |
| `SAMAY_SERVICE_REGISTRY_PATH` | Explicit trusted feature/champion/evidence deployment registry. Unset means unavailable forecast. |
| `SAMAY_HISTORICAL_DEMO_DATE` | Optional past date, development/test only; clearly labeled historical replay. See DEMO. |
| `VITE_API_BASE_URL` | Build-time public frontend URL/path, preferably `/backend`. Never a secret. |
| `SAMAY_BACKEND_URL` | Vite development proxy target, default `http://127.0.0.1:8010`. |

Startup checks database tables, actual official row counts, deployed artifacts and
prediction reliability. Warnings do not turn process liveness into a false forecast
readiness claim. `scripts/check_readiness.py` exits 2 when the authentic forecast
demonstration is not ready. `/api/health` remains a stable liveness endpoint.

## Offline bundle

Prepare dependencies while online, preserve the matching Python/NumPy/sklearn
runtime, SQLite database, original timestamped CSV archives, registry, feature
metadata, model pickle/metadata and empirical evidence. Verify hashes and service
readiness before travel. Do not copy a Windows absolute-path registry unchanged
to Linux. Reimport/relocate archives deliberately and verify lineage. Never
accept an untrusted pickle: these are server-owned artifacts, not upload inputs.

The farmer UI and inference/recommendation services make no external API calls.
No remote fonts or chart/image assets are needed. The app is not a PWA and has no
service-worker install path. Swagger's CDN assets are separate from the farmer UI.
Missing data, stale observations or invalid artifacts still disable confident
holding. There is no authentic offline bundle in this repository today.

## Docker recipe — prepared, untested

```powershell
docker compose config
docker compose build
docker compose up -d
Invoke-RestMethod http://127.0.0.1:8080/backend/api/health
```

Backend: Python 3.12, pinned dependencies, non-root user, migrations before
Uvicorn, SQLite in persistent named volume `/app/runtime`. Frontend: Node 24
multi-stage build and Nginx SPA fallback, same-origin `/backend` proxy. Uvicorn
root path supports proxied Swagger. Compose binds only localhost:8080. Its health
check is liveness, not authentic forecast readiness. Builds do not include secrets,
data, model binaries or development `.env` files.

To add an authentic prepared deployment, mount a verified bundle at a fixed path,
set `SAMAY_SERVICE_REGISTRY_PATH`, and preserve the paths referenced by archived
source batches. Verify directory permissions for the non-root backend. Do not
assume a host database's absolute Windows archive paths work in the container.
Do not run `docker compose down -v` unless intentionally deleting the database.

## Public deployment checklist

Build frontend with the actual public API base URL or same-origin proxy. Configure
SPA routing for all seven routes. Backend requires persistent writable storage,
migrations, trusted artifacts, explicit origins, TLS termination and backup/restore.
Use one SQLite writer deployment; scaling needs a planned database migration.

Before public access, add authentication/authorization where needed, request-rate
and body limits, operational monitoring, retention controls and dependency patch
review. CORS alone is not access control. Never expose fixture endpoints or
historical replay as live data. Existing safe logs exclude raw input notes and
credentials; preserve that policy. Current product is a local hackathon system,
not an audited multi-tenant financial service.

The runtime npm audit reports 0 vulnerabilities. The full development toolchain
reports 14 moderate findings associated with minimatch. A global forced upgrade
to minimatch 11 broke legacy callable imports in ESLint plugins; the compatible
version is retained with the findings disclosed. Review upstream compatible fixes
before a public build service accepts untrusted repositories/patterns.
