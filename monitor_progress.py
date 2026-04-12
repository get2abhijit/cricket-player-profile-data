"""Quick progress monitor for the running pipeline fetch job.

Usage:
    python monitor_progress.py          # print current snapshot and exit
    python monitor_progress.py --watch  # refresh every 10 s until complete
"""

import json
import sys
import time
from pathlib import Path

CACHE_PATH = Path("data/cache/profiles_raw.json")
STATE_PATH = Path("data/enrichment_state.json")
TOTAL_PLAYERS = 3516
WATCH_INTERVAL = 10  # seconds


def snapshot():
    cache = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    fetched = len(cache)
    no_style = sum(
        1 for v in cache.values()
        if not v.get("batting_style") and not v.get("bowling_style")
    )
    has_bat = sum(1 for v in cache.values() if v.get("batting_style"))
    has_bowl = sum(1 for v in cache.values() if v.get("bowling_style"))

    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    attempted = sum(1 for k, v in state.items() if k != "__match_state__" and isinstance(v, dict))

    pct = fetched / TOTAL_PLAYERS * 100
    remaining = TOTAL_PLAYERS - fetched
    size_kb = CACHE_PATH.stat().st_size / 1024 if CACHE_PATH.exists() else 0

    print(f"Cache entries : {fetched:>5} / {TOTAL_PLAYERS}  ({pct:.1f}%)")
    print(f"  With bat    : {has_bat:>5}")
    print(f"  With bowl   : {has_bowl:>5}")
    print(f"  No style    : {no_style:>5}")
    print(f"State attempts: {attempted:>5}")
    print(f"Remaining est.: {remaining:>5}")
    print(f"Cache file size: {size_kb:.1f} KB")
    return fetched


def main():
    watch = "--watch" in sys.argv

    if not watch:
        snapshot()
        return

    print("Watching progress (Ctrl-C to stop)...\n")
    prev = -1
    while True:
        now = snapshot()
        if now != prev:
            from datetime import datetime
            print(f"[{datetime.now().strftime('%H:%M:%S')}]\n")
        prev = now
        if now >= TOTAL_PLAYERS:
            print("Done — all players fetched.")
            break
        time.sleep(WATCH_INTERVAL)


if __name__ == "__main__":
    main()
