"""Capture exact release commands, exit codes and output; data-readiness failure stays visible."""
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise SystemExit("npm is missing")
    python = sys.executable
    tasks = [
        ("migrations", [python, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], ROOT),
        ("schema-drift", [python, "-m", "alembic", "-c", "backend/alembic.ini", "check"], ROOT),
        ("backend-lint", [python, "-m", "ruff", "check", "backend", "scripts", "tests"], ROOT),
        ("backend-tests", [python, "-m", "pytest", "tests", "-q"], ROOT),
        ("dependency-check", [python, "-m", "pip", "check"], ROOT),
        ("frontend-tests", [npm, "test"], ROOT / "frontend"),
        ("frontend-typecheck", [npm, "run", "typecheck"], ROOT / "frontend"),
        ("frontend-lint", [npm, "run", "lint"], ROOT / "frontend"),
        ("production-build", [npm, "run", "build"], ROOT / "frontend"),
        ("http-e2e", [python, "scripts/run_e2e.py"], ROOT),
        ("runtime-npm-audit", [npm, "audit", "--omit=dev"], ROOT / "frontend"),
        ("full-npm-audit", [npm, "audit", "--json"], ROOT / "frontend"),
        ("authentic-demo-readiness", [python, "scripts/check_readiness.py"], ROOT),
    ]
    folder = ROOT / "reports/release"
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    for name, command, cwd in tasks:
        start = time.monotonic()
        process = subprocess.run(command, cwd=cwd, env={**os.environ, "PYTHONUTF8": "1", "DEBUG_PRINT_LIMIT": "1800"}, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        log = folder / f"{name}.log"
        log.write_text(process.stdout, encoding="utf-8")
        row = {"check": name, "command": command, "cwd": str(cwd), "exit_code": process.returncode, "seconds": round(time.monotonic() - start, 2), "log": str(log.relative_to(ROOT))}
        results.append(row)
        print(f"{name}: exit={process.returncode} ({row['seconds']}s) — {row['log']}", flush=True)
    summary = {"verified_at": datetime.now(UTC).isoformat(), "results": results,
        "engineering_checks_pass": all(r["exit_code"] == 0 for r in results if r["check"] not in {"authentic-demo-readiness", "full-npm-audit"}),
        "authentic_demo_ready": results[-1]["exit_code"] == 0,
        "note": "Synthetic HTTP fixtures verify service wiring only. They are not authentic market performance. Full development audit and readiness failures are retained."}
    (folder / "verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0 if summary["engineering_checks_pass"] and summary["authentic_demo_ready"] and all(r["exit_code"] == 0 for r in results) else 2


if __name__ == "__main__":
    sys.exit(main())
