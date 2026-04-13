from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"


def run(cmd: list[str]) -> int:
    print(" ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean and run pipeline")
    parser.add_argument("--fetch", action="store_true", help="Allow network fetching")
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers when fetch is enabled")
    args = parser.parse_args()

    if not PYTHON_EXE.exists():
        print(f"ERROR: Python env not found: {PYTHON_EXE}")
        return 2

    cmd = [str(PYTHON_EXE), "pipeline.py"]
    if not args.fetch:
        cmd.extend(["--no-fetch", "--no-cleanup"])
    else:
        cmd.extend(["--no-cleanup", "--workers", str(args.workers)])

    rc = run(cmd)
    if rc != 0:
        return rc

    return run([str(PYTHON_EXE), str(ROOT / "tools" / "verify_dashboard_counts.py")])


if __name__ == "__main__":
    raise SystemExit(main())
