"""Application entry point — always use the project virtualenv."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
RUN_SCRIPT = ROOT / "run.py"


def _use_venv_python():
    """Re-launch with venv Python (handles paths with spaces on Windows)."""
    if not VENV_PYTHON.exists():
        return False
    if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
        return False
    cmd = [str(VENV_PYTHON), str(RUN_SCRIPT), *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd))


_use_venv_python()

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"Starting Myntra Dashboard at http://127.0.0.1:{port}")
    app.run(debug=False, host="127.0.0.1", port=port, threaded=True, use_reloader=False)
