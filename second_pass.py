"""
second_pass.py
--------------
Second-pass enrichment for players missing batting/bowling data after the
initial ESPN-only pipeline run.

Approach:
1. Collect missing players from the pipeline output.
2. Discover Cricbuzz profile IDs by crawling match scorecards.
3. For each missing player with a discovered Cricbuzz ID, fetch the profile.
4. Validate country/team match before accepting Cricbuzz data.
5. Update cache, output, dashboard, and registry.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from dashboard_payload import build_dashboard_payload
from manual_overrides import apply_manual_overrides_to_output, load_manual_overrides, sync_manual_override_placeholders
from normalizer import classify_bowling_style, normalize_batting_hand
from registry_loader import load_registry, PlayerRecord
from scraper_cricbuzz import CricbuzzScraper
from scraper_espn import EspnScraper
from generate_dashboard import generate_dashboard

CACHE_PATH = Path("data/cache/profiles_raw.json")
OUTPUT_PATH = Path("output/player_profiles.json")
DASHBOARD_DATA_PATH = Path("output/dashboard_data.json")


def _load_json(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _normalize_for_match(name: str) -> str:
    """Normalize name for comparison."""
    return re.sub(r"[^a-z\s]", "", name.strip().lower())


def _country_matches(cricbuzz_country: Optional[str], player_teams: List[str]) -> bool:
    """Check if the Cricbuzz country matches any of the player's teams."""
    if not cricbuzz_country:
        return True  # Can't validate, accept it
    cb = cricbuzz_country.lower().strip()
    for team in player_teams:
        t = team.lower().strip()
        if t in cb or cb in t:
            return True
        # Handle common variations
        if t == "isle of man" and cb in ("isle of man", "iom"):
            return True
        if t == "czech republic" and cb in ("czech republic", "czechia"):
            return True
        if t == "cayman islands" and "cayman" in cb:
            return True
    return False


def collect_missing_players(output: Dict) -> List[Dict]:
    """Extract players with no batting hand AND no bowling type from output."""
    missing = []
    for pid, record in output.get("players", {}).items():
        batting = (record.get("batting") or {}).get("hand")
        bowling = (record.get("bowling") or {}).get("type")
        if not batting and not bowling:
            missing.append(record)
    return missing


def run_second_pass() -> Dict:
    """
    Execute the second-pass enrichment for missing players.
    Returns the updated output dict.
    """
    print("=" * 60)
    print("SECOND PASS: Cricbuzz enrichment for missing players")
    print("=" * 60)

    # 1. Load current output and cache
    output = _load_json(OUTPUT_PATH)
    cache = _load_json(CACHE_PATH)
    manual_overrides = load_manual_overrides()

    if not output.get("players"):
        print("ERROR: No player output found. Run the main pipeline first.")
        return output

    # 2. Collect missing players
    missing = collect_missing_players(output)
    print(f"\nMissing players: {len(missing)}")
    if not missing:
        print("No missing players. Nothing to do.")
        return output

    # Group by team for reporting
    by_team: Dict[str, List[Dict]] = {}
    for p in missing:
        for team in p.get("teams", []):
            by_team.setdefault(team, []).append(p)
    print(f"Across {len(by_team)} teams:")
    for team in sorted(by_team):
        print(f"  {team}: {len(by_team[team])}")

    # 3. Build registry lookup for names.csv aliases and cricbuzz_ids
    registry_players = load_registry()
    registry_by_id = {p.player_id: p for p in registry_players}

    # 4. Discover Cricbuzz IDs from match scorecards
    print("\n--- Phase 1: Discovering Cricbuzz player IDs ---")
    cb_scraper = CricbuzzScraper()

    # Discover from all known European series scorecards
    cb_scraper.discover_from_series()

    # 5. Match missing players against discovered Cricbuzz profiles
    print(f"\n--- Phase 2: Matching missing players to Cricbuzz profiles ---")
    matched = 0
    unmatched = 0
    match_results: Dict[str, str] = {}  # player_id -> cricbuzz_id

    for player in missing:
        pid = player["identifier"]
        name = player.get("name", "")
        # Also try aliases
        names_to_try = [name]
        known_as = player.get("known_as", [])
        if known_as:
            names_to_try.extend(known_as)

        cb_id = None
        for n in names_to_try:
            cb_id = cb_scraper.find_cricbuzz_id(n)
            if cb_id:
                break

        if cb_id:
            match_results[pid] = cb_id
            matched += 1
        else:
            unmatched += 1

    print(f"  Matched: {matched}, Unmatched: {unmatched}")

    # 6. Fetch Cricbuzz profiles for matched players
    print(f"\n--- Phase 3: Fetching Cricbuzz profiles ---")
    enriched_count = 0
    failed_count = 0

    workers = 8
    print(f"Using {workers} workers for Cricbuzz profile fetches")

    def _fetch_one(item: Tuple[str, str]) -> Tuple[str, str, Optional[Dict], Optional[str]]:
        pid, cb_id = item
        profile = cb_scraper.fetch_profile(cb_id)
        if not profile:
            return pid, cb_id, None, "fetch_failed"
        return pid, cb_id, profile, None

    completed = 0
    total_matches = len(match_results)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(_fetch_one, item): item
            for item in match_results.items()
        }
        for future in as_completed(futures):
            pid, cb_id, profile, err = future.result()
            completed += 1
            record = output["players"][pid]
            name = record.get("name", "")
            teams = record.get("teams", [])
            print(f"  [{completed}/{total_matches}] {name} (cb:{cb_id})")

            if err or not profile:
                print("    -> Failed to fetch profile")
                failed_count += 1
                continue

            # Validate country match
            if not _country_matches(profile.get("country"), teams):
                print(f"    -> Country mismatch: {profile.get('country')} vs {teams}")
                failed_count += 1
                continue

            batting_style = profile.get("batting_style")
            bowling_style = profile.get("bowling_style")
            role = profile.get("role")

            has_data = bool(batting_style or bowling_style or role)
            if not has_data:
                print("    -> Profile found but no style data")
                failed_count += 1
                continue

            # Update the player record
            batting_hand = normalize_batting_hand(batting_style)
            bowling = classify_bowling_style(bowling_style)

            record["batting"]["hand"] = batting_hand or record["batting"].get("hand")
            if bowling.get("type"):
                record["bowling"] = bowling
            if role:
                record["role"] = role
            record["raw"]["batting_style"] = batting_style or record["raw"].get("batting_style")
            record["raw"]["bowling_style"] = bowling_style or record["raw"].get("bowling_style")

            # Update external IDs and source URL
            ext_ids = record.get("external_ids", {})
            ext_ids["cricbuzz"] = cb_id
            record["external_ids"] = ext_ids

            # Set source URL to Cricbuzz profile if we got data from there
            cb_url = CricbuzzScraper.profile_url(cb_id, name)
            record["source"] = cb_url
            record["last_updated"] = datetime.now(timezone.utc).isoformat()

            # Update cache
            cache_key = pid
            if cache_key in cache:
                cache[cache_key]["batting_style"] = batting_style or cache[cache_key].get("batting_style")
                cache[cache_key]["bowling_style"] = bowling_style or cache[cache_key].get("bowling_style")
                cache[cache_key]["role"] = role or cache[cache_key].get("role")
                cache[cache_key]["cricbuzz_id"] = cb_id
                cache[cache_key]["cricbuzz_url"] = cb_url

            output["players"][pid] = record
            enriched_count += 1
            print(f"    -> Enriched: bat={batting_style}, bowl={bowling_style}, role={role}")

    output = apply_manual_overrides_to_output(output, manual_overrides)

    # 7. Write updated output
    print(f"\n--- Phase 4: Writing updated outputs ---")
    _write_json(OUTPUT_PATH, output)
    _write_json(CACHE_PATH, cache)
    sync_manual_override_placeholders(output)

    # Rebuild dashboard data with actionable missing vs ignored split
    dashboard_data = build_dashboard_payload(output)
    _write_json(DASHBOARD_DATA_PATH, dashboard_data)
    generate_dashboard()

    # 8. Summary
    total = len(output["players"])
    now_enriched = sum(
        1 for p in output["players"].values()
        if (p.get("batting") or {}).get("hand") or (p.get("bowling") or {}).get("type")
    )
    still_missing = total - now_enriched

    print(f"\n{'=' * 60}")
    print(f"SECOND PASS COMPLETE")
    print(f"  New enrichments from Cricbuzz: {enriched_count}")
    print(f"  Failed/unmatched: {failed_count + unmatched}")
    print(f"  Total enriched: {now_enriched}/{total}")
    print(f"  Still missing: {still_missing}")
    print(f"{'=' * 60}")

    return output


if __name__ == "__main__":
    run_second_pass()
