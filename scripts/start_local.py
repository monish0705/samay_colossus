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
    parser.add_argument("--check", action="store_true", help="Migrate and verify existing listeners, then exit; do not launch or stop services")
    args = parser.parse_args()
    if not all(1024 <= p <= 65535 for p in (args.backend_port, args.frontend_port)) or args.backend_port == args.frontend_port:
        raise SystemExit("Choose distinct ports between 1024 and 65535")
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists() or not (ROOT / "frontend/node_modules/vite/bin/vite.js").exists():
        raise SystemExit("Dependencies are missing. Run python scripts/setup_local.py while online first.")
    env = os.environ.copy()
    env.update(PYTHONUTF8="1", VITE_API_BASE_URL="/backend", SAMAY_BACKEND_URL=f"http://127.0.0.1:{args.backend_port}")
    subprocess.run([str(python), "scripts/restore_prepared_data.py"], cwd=ROOT, env=env, check=True)
    subprocess.run([str(python), "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], cwd=ROOT, env=env, check=True)
    subprocess.run([str(python), "scripts/repair_data_provenance.py"], cwd=ROOT, env=env, check=True)
    backend = f"http://127.0.0.1:{args.backend_port}"
    frontend = f"http://127.0.0.1:{args.frontend_port}"
    owned = []
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
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
