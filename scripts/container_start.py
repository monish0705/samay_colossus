"""Apply migrations before serving; fail startup if migrations fail."""
import os
import subprocess
import sys

subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "upgrade", "head"], check=True)
os.execvp(sys.executable, [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--root-path", "/backend"])
