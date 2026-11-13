"""Start or reuse local SAMAY services. No installation/network download at startup."""
import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def ready(url):
    try:
        with urlopen(url, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-port", type=int, default=8010)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--refresh-context", action="store_true", help="Collect public market-city weather/news/calendar now and hourly; unavailable sources never become fabricated data")
    parser.add_argument("--enable-research", action="store_true", help="Explicitly use bundled saved research forecasts with limited-evidence labels; never marks models validated")
    parser.add_argument('--bundled-research', action='store_true', help='Use a separate hash-verified bundled database and saved research models; preserve existing samay.db/.env; requires unused ports')
    parser.add_argument("--check", action="store_true", help="Migrate and verify existing listeners, then exit; do not launch or stop services")
    args = parser.parse_args()
    if not all(1024 <= p <= 65535 for p in (args.backend_port, args.frontend_port)) or args.backend_port == args.frontend_port:
        raise SystemExit("Choose distinct ports between 1024 and 65535")
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists() or not (ROOT / "frontend/node_modules/vite/bin/vite.js").exists():
        raise SystemExit("Dependencies are missing. Run python scripts/setup_local.py while online first.")
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", VITE_API_BASE_URL="/backend", SAMAY_BACKEND_URL=f"http://127.0.0.1:{args.backend_port}")
    profile_database = None
    if args.bundled_research:
        if not args.check and (ready(f'http://127.0.0.1:{args.backend_port}/api/health') or ready(f'http://127.0.0.1:{args.frontend_port}')):
            raise SystemExit('Bundled research needs unused ports. Stop the old launcher or choose different --backend-port and --frontend-port values; an old backend cannot receive new settings.')
        from app.prepared_data import bundled_environment
        env, profile_database, message = bundled_environment(ROOT, env)
        print(f'{message}\nBundled research profile; previous samay.db and .env are preserved. Forecasts remain limited-evidence research.',flush=True)
    if args.enable_research:
        env.update(SAMAY_ENABLE_RESEARCH_FORECASTS="true",SAMAY_RESEARCH_REGISTRY_PATH=str(ROOT/"research-registry.json"),SAMAY_RESEARCH_SERVING_REGISTRY_PATH=str(ROOT/"research-serving-registry.json"))
    subprocess.run([str(python), "scripts/restore_prepared_data.py"], cwd=ROOT, env=env, check=True)
    subprocess.run([str(python), "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], cwd=ROOT, env=env, check=True)
    repair_command = [str(python), "scripts/repair_data_provenance.py"]
    if profile_database is not None:
        repair_command += ['--database', str(profile_database)]
    subprocess.run(repair_command, cwd=ROOT, env=env, check=True)
    backend = f"http://127.0.0.1:{args.backend_port}"
    frontend = f"http://127.0.0.1:{args.frontend_port}"
    owned = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        if args.refresh_context and not args.check:
            owned.append(subprocess.Popen([str(python), "scripts/refresh_market_context.py", "--watch-minutes", "60"], cwd=ROOT, env=env, creationflags=flags))
        if not ready(backend + "/api/health") and not args.check:
            owned.append(subprocess.Popen([str(python), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(args.backend_port)], cwd=ROOT, env=env, creationflags=flags))
        if not ready(frontend) and not args.check:
            node = shutil.which("node")
            if not node:
                raise RuntimeError("Node.js is unavailable")
            owned.append(subprocess.Popen([node, str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", str(args.frontend_port), "--strictPort"], cwd=ROOT / "frontend", env=env, creationflags=flags))
        for _ in range(60):
            if ready(backend + "/api/health") and ready(frontend):
                break
            if args.check or any(p.poll() is not None for p in owned):
                raise RuntimeError("Services failed readiness; inspect the startup output")
            time.sleep(.5)
        else:
            raise RuntimeError("Startup timed out")
        with urlopen(backend + "/openapi.json", timeout=5) as response:
            schema = json.load(response)
        if "/api/v1/recommend" not in schema["paths"]:
            raise RuntimeError("The backend port belongs to an incompatible service")
        if args.bundled_research:
            with urlopen(backend+'/api/v1/models/status',timeout=15) as response:
                status = json.load(response)
            expected = json.loads((ROOT/'research-serving-registry.json').read_text(encoding='utf-8-sig'))
            if len(status.get('research_models',[])) != len(expected) or not expected:
                raise RuntimeError('Backend did not load the bundled research registry; stop the old server and retry on unused ports')
            with urlopen(backend+'/api/v1/data/status',timeout=15) as response:
                data = json.load(response)
            counts = json.loads((ROOT/'data/prepared/manifest.json').read_text(encoding='utf-8'))['observation_counts']
            if data['official_observations']<counts.get('official',0) or data.get('secondary_observations',0)<counts.get('secondary',0):
                raise RuntimeError('Backend does not contain the bundled observations; existing profile was preserved for inspection')
            print(f"Verified bundled profile: {data['official_observations']} official + {data.get('secondary_observations',0)} secondary observations; {len(expected)} research model artifacts",flush=True)
        print(f"SAMAY ready: {frontend}\nSwagger: {backend}/docs\nNo data or model is fabricated by startup.", flush=True)
        if args.check:
            return
        while True:
            if any(p.poll() is not None for p in owned):
                raise RuntimeError("An owned service stopped")
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping only services launched by this command.")
    finally:
        for process in owned:
            if process.poll() is None:
                process.terminate()
        for process in owned:
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
