"""
pipeline.py
-----------
Orchestrates the Player Intelligence Engine end-to-end.

Output format (output/player_profiles.json) is structured similarly to
Cricsheet match JSON files:

{
  "meta": { "data_version": "1.1.0", "created": "...", "revision": 1 },
  "teams": {
    "Bulgaria": { "player_ids": [...], "gender": "male" }
  },
  "players": {
    "<cricsheet_id>": { ...player record... }
  }
}
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from dashboard_payload import build_dashboard_payload
from generate_dashboard import generate_dashboard
from manual_overrides import (
    apply_manual_overrides_to_output,
    infer_is_wicketkeeper,
    load_manual_overrides,
    sync_manual_override_placeholders,
)
from match_loader import load_teams_from_matches
from normalizer import classify_bowling_style, normalize_batting_hand
from registry_loader import PlayerRecord, load_registry
from scraper_espn import EspnScraper
from enrichment_state import load_state, save_state, mark_enriched, is_enriched

CACHE_PATH = Path("data/cache/profiles_raw.json")
OUTPUT_PATH = Path("output/player_profiles.json")
DASHBOARD_DATA_PATH = Path("output/dashboard_data.json")

_DATA_VERSION = "1.1.0"


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _load_json_dict(path: Path) -> Dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
            return loaded if isinstance(loaded, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Record builder
# ---------------------------------------------------------------------------

def _build_player_record(
    player: PlayerRecord,
    raw_profile: Optional[Dict],
    teams: Optional[List[str]] = None,
    display_name: Optional[str] = None,
) -> Dict:
    raw = raw_profile or {}
    batting_style = raw.get("batting_style")
    bowling_style = raw.get("bowling_style")
    role = raw.get("role")
    # Use ESPN's display name if available, then provided display_name, then registry
    best_name = raw.get("espn_display_name") or display_name or player.player_name

    # Always compute a proper ESPN URL from the ID + name (not the API URL from cache)
    source_url = "registry"
    if player.espn_id:
        source_url = EspnScraper.profile_url(player.espn_id, best_name)

    return {
        "identifier": player.player_id,
        "name": best_name,
        "registry_name": player.player_name,
        "known_as": player.aliases or [player.player_name],
        "teams": teams or [],
        "external_ids": {
            "espn": player.espn_id,
            "cricbuzz": player.cricbuzz_id,
        },
        "batting": {
            "hand": normalize_batting_hand(batting_style),
        },
        "bowling": classify_bowling_style(bowling_style),
        "role": role,
        "is_wicketkeeper": infer_is_wicketkeeper(role),
        "raw": {
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "role": role,
        },
        "source": source_url,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Team gender inference
# ---------------------------------------------------------------------------

def _infer_gender(team_name: str, all_match_files_text: str = "") -> str:
    if "female" in all_match_files_text.lower() or "women" in team_name.lower():
        return "female"
    return "male"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    limit: Optional[int] = None,
    match_players_only: bool = True,
    skip_espn: bool = False,
    no_fetch: bool = False,
    retry_empty_cache: bool = False,
) -> Dict:
    """
    Build the player intelligence dataset.

    Parameters
    ----------
    limit:               If set, cap the number of players processed.
    match_players_only:  When True (default), only enrich players who appear
                         in match JSON files.  False processes full registry.
    """
    # 1. Load registry
    registry_players = load_registry()
    registry_by_id: Dict[str, PlayerRecord] = {p.player_id: p for p in registry_players}

    # 2. Load team→player mappings from match files
    teams_ids, id_display_names = load_teams_from_matches()

    # 3. Compute the ordered list of players to process
    if match_players_only and teams_ids:
        all_match_ids: Set[str] = set()
        for pid_set in teams_ids.values():
            all_match_ids.update(pid_set)
        # Preserve stable ordering using registry order
        players_to_process = [
            registry_by_id[pid]
            for pid in (p.player_id for p in registry_players)
            if pid in all_match_ids and pid in registry_by_id
        ]
        print(f"Mode: match_players_only — {len(players_to_process)} players from match files")
    else:
        players_to_process = registry_players
        print(f"Mode: full registry — {len(players_to_process)} players")

    if limit is not None:
        players_to_process = players_to_process[:limit]

    # 4. Build per-player team list
    player_teams: Dict[str, List[str]] = {}
    for team_name, pid_set in teams_ids.items():
        for pid in pid_set:
            player_teams.setdefault(pid, []).append(team_name)

    # 5. Scraping loop
    scraper = EspnScraper()
    cache: Dict = _load_json_dict(CACHE_PATH)
    enrichment_state: Dict = load_state()
    manual_overrides = load_manual_overrides()

    # Optionally purge empty cache entries so they get re-fetched.
    # Keep them by default for fast regeneration workflows.
    if retry_empty_cache:
        stale_keys = [
            k for k, v in cache.items()
            if not any(v.get(f) for f in ("batting_style", "bowling_style", "role"))
        ]
        if stale_keys:
            for k in stale_keys:
                del cache[k]
            print(f"Purged {len(stale_keys)} stale empty cache entries for retry")

    processed = 0
    skipped = 0
    failed = 0
    already_enriched = 0
    total = len(players_to_process)

    player_records: Dict[str, Dict] = {}

    def _best_display_name(player: PlayerRecord) -> str:
        """Pick the best full name: longest alias > match display name > people.csv name."""
        candidates = list(player.aliases)
        match_name = id_display_names.get(player.player_id)
        if match_name:
            candidates.append(match_name)
        candidates.append(player.player_name)
        # Prefer the longest name that has at least two parts (likely a real full name)
        full_names = [n for n in candidates if len(n.split()) >= 2]
        if full_names:
            return max(full_names, key=len)
        return player.player_name

    for index, player in enumerate(players_to_process, start=1):
        display_name = _best_display_name(player)
        print(f"[{index}/{total}] {display_name} ({player.player_id})")

        raw_profile: Optional[Dict] = None

        # Check if already enriched (has_data=True in state)
        if is_enriched(enrichment_state, player.player_id):
            already_enriched += 1
            print(f"  -> Already enriched (cached from prior run)")
            raw_profile = cache.get(player.player_id)
        elif not player.espn_id and not player.cricbuzz_id:
            skipped += 1
            print(f"  -> Skipped: no external IDs")
        else:
            cache_key = player.player_id
            if cache_key in cache:
                raw_profile = cache[cache_key]
                print(f"  -> Cache hit")
            elif no_fetch:
                skipped += 1
                print("  -> Skipped fetch: --no-fetch mode")
            else:
                try:
                    raw_profile = scraper.fetch_profile(
                        espn_id=player.espn_id or "",
                        cricbuzz_id=player.cricbuzz_id,
                        skip_espn=skip_espn,
                        player_name=display_name,
                    )
                    cache[cache_key] = raw_profile
                    _write_json(CACHE_PATH, cache)

                    had_data = any(
                        raw_profile.get(k)
                        for k in ("batting_style", "bowling_style", "role")
                    )
                    if had_data:
                        print(
                            f"  -> Fetched: "
                            f"bat={raw_profile.get('batting_style')} "
                            f"bowl={raw_profile.get('bowling_style')}"
                        )
                        mark_enriched(enrichment_state, player.player_id, has_data=True)
                    else:
                        print("  -> Fetched but no style data found")
                        mark_enriched(enrichment_state, player.player_id, has_data=False)

                except Exception as exc:  # noqa: BLE001
                    failed += 1
                    print(f"  -> Failed: {exc}")
                    mark_enriched(enrichment_state, player.player_id, has_data=False, error=str(exc))

        record = _build_player_record(
            player,
            raw_profile,
            teams=player_teams.get(player.player_id, []),
            display_name=display_name,
        )
        player_records[player.player_id] = record
        processed += 1

    # 6. Build teams block
    teams_block: Dict = {}
    for team_name, pid_set in teams_ids.items():
        in_output = [pid for pid in pid_set if pid in player_records]
        if in_output:
            teams_block[team_name] = {
                "player_ids": sorted(in_output),
                "gender": "male",
            }

    # 7. Assemble final output (match-JSON-style structure)
    today = datetime.now(timezone.utc).date().isoformat()
    output: Dict = {
        "meta": {
            "data_version": _DATA_VERSION,
            "created": today,
            "revision": 1,
            "description": (
                "Player Intelligence Dataset — "
                "built from Cricsheet registry + ESPN Cricinfo"
            ),
        },
        "teams": teams_block,
        "players": player_records,
    }

    output = apply_manual_overrides_to_output(output, manual_overrides)
    _write_json(OUTPUT_PATH, output)
    sync_manual_override_placeholders(output)
    # Also write a flat list for the dashboard (easier to consume client-side)
    _write_json(DASHBOARD_DATA_PATH, build_dashboard_payload(output))
    _write_json(CACHE_PATH, cache)
    save_state(enrichment_state)  # Save enrichment tracking state
    generate_dashboard()

    print("\nPipeline complete")
    print(f"  Processed      : {processed}")
    print(f"  Already enriched: {already_enriched}")
    print(f"  Skipped        : {skipped}")
    print(f"  Failed         : {failed}")
    print(f"  Output         : {OUTPUT_PATH}")

    return output


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build player intelligence dataset from Cricsheet + ESPN"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of players processed (useful for testing).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process full registry instead of only match players.",
    )
    parser.add_argument(
        "--skip-espn",
        action="store_true",
        help="Skip ESPN HTTP attempts (use when Akamai is blocking). Only Cricbuzz IDs will be fetched.",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help=(
            "Do not make any HTTP requests. Rebuild outputs from registry + cache + manual overrides only. "
            "Useful for fast manual-edit iteration."
        ),
    )
    parser.add_argument(
        "--retry-empty-cache",
        action="store_true",
        help=(
            "Re-fetch players whose cached profiles have no batting_style/bowling_style/role. "
            "Disabled by default for faster reruns."
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_pipeline(
        limit=args.limit,
        match_players_only=not args.all,
        skip_espn=args.skip_espn,
        no_fetch=args.no_fetch,
        retry_empty_cache=args.retry_empty_cache,
    )
