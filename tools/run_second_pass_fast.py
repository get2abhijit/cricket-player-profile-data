from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"


def run(cmd: list[str]) -> int:
    print(" ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    if not PYTHON_EXE.exists():
        print(f"ERROR: Python env not found: {PYTHON_EXE}")
        return 2

    rc = run([str(PYTHON_EXE), "second_pass.py"])
    if rc != 0:
        return rc

    rc = run([str(PYTHON_EXE), "pipeline.py", "--no-fetch", "--no-cleanup"])
    if rc != 0:
        return rc

    return run([str(PYTHON_EXE), str(ROOT / "tools" / "verify_dashboard_counts.py"), "--expected-players", "3445", "--expected-missing", "70"])


if __name__ == "__main__":
    raise SystemExit(main())
