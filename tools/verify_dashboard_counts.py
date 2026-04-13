from __future__ import annotations

import argparse
import json
from pathlib import Path

DASHBOARD_DATA = Path("output/dashboard_data.json")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify dashboard count regression guard")
    parser.add_argument("--expected-players", type=int, default=3442)
    parser.add_argument("--expected-missing", type=int, default=75)
    args = parser.parse_args()

    if not DASHBOARD_DATA.exists():
        print(f"ERROR: {DASHBOARD_DATA} not found")
        return 2

    payload = json.loads(DASHBOARD_DATA.read_text(encoding="utf-8"))
    players = len(payload.get("players", []))
    missing = sum(len(v) for v in payload.get("unfound_players", {}).values())
    ignored = sum(len(v) for v in payload.get("ignored_players", {}).values())

    print(f"players={players} missing={missing} ignored={ignored}")

    if players != args.expected_players or missing != args.expected_missing:
        print("REGRESSION DETECTED")
        print(f"Expected players={args.expected_players}, missing={args.expected_missing}")
        return 1

    print("Counts match expected snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
