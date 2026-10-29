from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = ROOT / ".venv" / "Scripts" / "python.exe"


def _run(cmd: list[str]) -> int:
    print(" ".join(cmd))
    return subprocess.run(cmd, cwd=ROOT).returncode


def _ensure_python() -> int:
    if PYTHON_EXE.exists():
        return 0
    print(f"ERROR: Python environment not found at {PYTHON_EXE}")
    print("Create it first: py -m venv .venv && .\\.venv\\Scripts\\pip install -r requirements.txt")
    return 2


def _clean_all_runtime_files() -> None:
    removed = 0
    for path in [
        ROOT / "output" / "player_profiles.json",
        ROOT / "output" / "dashboard_data.json",
        ROOT / "output" / "dashboard.html",
        ROOT / "output" / "registry_enriched.json",
        ROOT / "data" / "cache" / "profiles_raw.json",
        ROOT / "data" / "enrichment_state.json",
        ROOT / "data" / "matches_json" / "README.txt",
    ]:
        if path.exists():
            path.unlink()
            removed += 1

    matches_dir = ROOT / "data" / "matches_json"
    if matches_dir.exists():
        for match_file in matches_dir.glob("*.json"):
            match_file.unlink()
            removed += 1

    print(f"Full clean complete: removed {removed} file(s)")


def _update_inputs(window_days: int | None, full_archive: bool) -> int:
    cmd = [str(PYTHON_EXE), "tools/update_cricsheet_inputs.py"]
    if full_archive:
        cmd.append("--full-archive")
    elif window_days is not None:
        cmd.extend(["--window-days", str(window_days)])
    return _run(cmd)


def _run_pipeline(workers: int, no_fetch: bool) -> int:
    cmd = [str(PYTHON_EXE), "pipeline.py", "--no-cleanup"]
    if no_fetch:
        cmd.append("--no-fetch")
    else:
        cmd.extend(["--workers", str(workers), "--retry-empty-cache"])
    return _run(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="One-click automation runner for local workflows")
    parser.add_argument(
        "mode",
        choices=(
            "run-2d",
            "run-7d",
            "run-complete",
            "update-only-2d",
            "update-only-7d",
            "full-clean",
        ),
        help="Automation mode",
    )
    parser.add_argument("--workers", type=int, default=6, help="Parallel workers for pipeline fetch")
    parser.add_argument("--no-fetch", action="store_true", help="Run pipeline in --no-fetch mode")
    args = parser.parse_args()

    rc = _ensure_python()
    if rc != 0:
        return rc

    if args.mode == "full-clean":
        _clean_all_runtime_files()
        rc = _update_inputs(window_days=None, full_archive=True)
        if rc != 0:
            return rc
        return _run_pipeline(workers=args.workers, no_fetch=args.no_fetch)

    if args.mode == "run-complete":
        rc = _update_inputs(window_days=None, full_archive=True)
        if rc != 0:
            return rc
        return _run_pipeline(workers=args.workers, no_fetch=args.no_fetch)

    if args.mode == "run-2d":
        rc = _update_inputs(window_days=2, full_archive=False)
        if rc != 0:
            return rc
        return _run_pipeline(workers=args.workers, no_fetch=args.no_fetch)

    if args.mode == "run-7d":
        rc = _update_inputs(window_days=7, full_archive=False)
        if rc != 0:
            return rc
        return _run_pipeline(workers=args.workers, no_fetch=args.no_fetch)

    if args.mode == "update-only-2d":
        return _update_inputs(window_days=2, full_archive=False)

    if args.mode == "update-only-7d":
        return _update_inputs(window_days=7, full_archive=False)

    print(f"Unknown mode: {args.mode}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
