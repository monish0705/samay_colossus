# Foundation verification — 2026-11-04

Verified on Windows, Python 3.12.10, Node 24.20.0.

Commands executed from repository root, except npm commands from frontend:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e './backend[dev]'
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini revision --autogenerate -m initial_schema
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
.\.venv\Scripts\python.exe -m pytest tests -v
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

```powershell
npm.cmd install
npm.cmd install --save-dev vitest@latest vite@latest @vitejs/plugin-react@latest
npm.cmd run build
npm.cmd test
npm.cmd audit
npm.cmd run dev -- --port 5173 --strictPort
```

Results: pytest 3 passed; Vitest 3 passed; TypeScript and Vite production build
passed; npm audit 0 vulnerabilities; pip check no broken requirements; Alembic
check no new operations. Both HTTP servers started and returned 200. Health JSON:
`{"status":"ok","service":"samay","version":"0.1.0"}`.

The database integration test verifies all six entity tables plus alembic_version,
repeat upgrades, downgrade/upgrade, foreign-key rejection, UTC round-trip, naive
timestamp rejection, repeatable DEMO_DATA seed, and production seed rejection.
Tests use a temporary database; the development database remains unseeded.

One non-blocking upstream Starlette deprecation warning remains: its HTTPX-based
TestClient recommends migration to HTTPX2. No tests fail. Browser visual review
was not performed; frontend verification covers DOM behavior, build, and HTTP.

No Prompt 2 work was started. Next owner should follow docs/architecture.md:
validate real data provenance and ingestion first, then chronological baselines,
uncertainty evaluation and cash/storage-aware decision contracts.
