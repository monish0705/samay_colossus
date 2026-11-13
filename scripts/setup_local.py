"""One-time Windows-compatible dependency setup; never overwrite existing environment files."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_windows_preview():
    """Fail before npm ci can partially remove loaded Windows native modules."""
    if os.name != "nt":
        return
    result = subprocess.run(["powershell.exe", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
    processes = json.loads(result.stdout)
    lookup = {p["ProcessId"]: p for p in processes}
    root = str(ROOT).replace("\\", "/").casefold()
    for process in processes:
        command = (process.get("CommandLine") or "").replace("\\", "/").casefold()
        parent = lookup.get(process.get("ParentProcessId"), {})
        parent_command = (parent.get("CommandLine") or "").replace("\\", "/").casefold()
        if process["Name"].casefold() == "node.exe" and "vite" in command and (root in command or root in parent_command):
            raise SystemExit(f"Stop this repository's Vite preview (PID {process['ProcessId']}) before setup. Windows locks its loaded native modules. No dependencies were changed.")


def main():
    check_windows_preview()
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
    lock = ROOT / "backend" / "requirements-lock.txt"
    if lock.exists():
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(lock)], cwd=ROOT, env=environment, check=True)
    subprocess.run([str(python), "-m", "pip", "install", "-e", "./backend[dev,analysis,forecast]"], cwd=ROOT, env=environment, check=True)
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise SystemExit("Node.js 22.12+ and npm are required")
    try:
        subprocess.run([npm, "ci"], cwd=ROOT / "frontend", env=environment, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit("Frontend install failed. Stop repository Vite/build processes, check the npm error above, then rerun setup; no administrator access is normally needed.") from exc
    for example, target in [(ROOT / ".env.example", ROOT / ".env"), (ROOT / "frontend/.env.example", ROOT / "frontend/.env")]:
        if not target.exists():
            shutil.copyfile(example, target)
    print("Setup complete. Run: .venv\\Scripts\\python.exe scripts/start_local.py")


if __name__ == "__main__":
    main()
