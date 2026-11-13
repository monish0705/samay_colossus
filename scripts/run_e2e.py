"""Run React → actual HTTP → SQLite/saved baseline/reliability/optimizer in a disposable fixture."""
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="samay-TEST_ONLY-") as temporary:
        with (Path(temporary) / "server.log").open("w+", encoding="utf-8") as log:
            process = subprocess.Popen([sys.executable, "tests/http_fixture_server.py", "--folder", temporary, "--port", str(port)], cwd=ROOT, stdout=log, stderr=log)
            try:
                for _ in range(240):
                    try:
                        with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=1):
                            break
                    except (OSError, URLError):
                        if process.poll() is not None:
                            raise RuntimeError("Fixture server failed") from None
                        time.sleep(.25)
                else:
                    raise RuntimeError("Fixture server timed out")
                env = {**os.environ, "VITE_API_BASE_URL": f"http://127.0.0.1:{port}", "SAMAY_E2E_URL": f"http://127.0.0.1:{port}"}
                result = subprocess.run([shutil.which("npm.cmd" if os.name == "nt" else "npm"), "run", "test:e2e"], cwd=ROOT / "frontend", env=env, check=False)
                if result.returncode:
                    log.seek(0)
                    print("\nFixture server diagnostic log:\n" + log.read()[-12000:])
                return result.returncode
            except RuntimeError:
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                process.wait(timeout=15)


if __name__ == "__main__":
    sys.exit(main())
