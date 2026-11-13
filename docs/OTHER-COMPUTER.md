# Missing data or models on another computer

The files are committed to `sub2`; checking the default branch does not guarantee
you have that branch's data or artifacts. Confirm with `git branch --show-current`
and `git log -1 --oneline`.

A freshly cloned `sub2` was installed in a separate directory with its own
virtualenv and npm dependencies. Startup restored **3,938 official** and **5,834
secondary** observations. `/api/v1/models/status` listed **322 artifacts** and a
real 30-day Copra request returned **INR 18,500/quintal**, research baseline version
`daec5736ea5fc9b2-champion-30d`. This establishes checkout portability on a fresh
Windows installation directory on the test computer; it does not claim testing
on the user's inaccessible second computer or every operating system.

Older installations intentionally preserve their own database and environment
files. Therefore pulling newer code alone can leave an empty/older `samay.db`,
`SAMAY_ENABLE_RESEARCH_FORECASTS=false`, an outdated registry path, or an old replay
date in effect. A running backend also keeps its original environment until it
is restarted. These are possible causes, not a diagnosis made remotely.

From the repository root in PowerShell:

```powershell
git switch sub2
git pull --ff-only origin sub2
.\.venv\Scripts\python.exe scripts/start_local.py --bundled-research --backend-port 8012 --frontend-port 5175
```

If setup was never completed, first stop any repository Vite process and run
`python scripts/setup_local.py` with Python 3.12 and Node.js 22.12+ installed.
Do not copy a virtualenv or `node_modules` from another computer. Open
**http://127.0.0.1:5175 on the computer running these commands** and refresh the page.

The opt-in profile uses a hash-verified copy of the authentic prepared database
in `.local-data/`, enables bundled research models, clears legacy replay mode for
this profile, and checks the API's observation/model counts before claiming ready.
Your original database and `.env` remain untouched. Anonymous recommendations
for this profile are stored in its separate database and retained on repeat runs.
It does not run in production mode. Forecasts are still labeled research only.

If ports are occupied, stop the old launcher or choose another pair, for example
`--backend-port 8013 --frontend-port 5176`, then open that frontend port. The
profile refuses to silently reuse an old backend because new command-line
environment settings cannot reconfigure an already running process.

Check the running instance:

```powershell
$data = Invoke-RestMethod http://127.0.0.1:8012/api/v1/data/status
$data | Select-Object official_observations, secondary_observations
$models = Invoke-RestMethod http://127.0.0.1:8012/api/v1/models/status
$models.status
$models.research_models.Count
```

Expected counts: `3938`, `5834`, `research_only_configured`, `322`.
Genuine data can still become stale; the profile does not change source dates,
fabricate fresh prices or bypass the forecast service's freshness checks.
