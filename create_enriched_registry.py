"""
create_enriched_registry.py
---------------------------
Creates a state-aware player registry with best-available full names.
Reads from pipeline output + cache to resolve ESPN display names.
Generates output/registry_enriched.json
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

CACHE_PATH = Path("data/cache/profiles_raw.json")
NAMES_CSV = Path("data/names.csv")
OUTPUT_PATH = Path("output/player_profiles.json")
STATE_PATH = Path("data/enrichment_state.json")
REGISTRY_OUTPUT = Path("output/registry_enriched.json")


def _best_full_name(
    registry_name: str,
    aliases: list,
    match_display_name: Optional[str],
    espn_display_name: Optional[str],
) -> str:
    """Pick the best full name available for a player."""
    # ESPN display name is the gold standard (e.g., "Alister Gajic" not "AA Gajic")
    if espn_display_name and len(espn_display_name.split()) >= 2:
        return espn_display_name
    # Then try longest alias from names.csv
    full_aliases = [a for a in aliases if len(a.split()) >= 2]
    if full_aliases:
        return max(full_aliases, key=len)
    # Then match display name
    if match_display_name and len(match_display_name.split()) >= 2:
        return match_display_name
    # Fallback to whatever we have
    return espn_display_name or match_display_name or registry_name


def _make_slug(name: str) -> str:
    """firstname_lastname slug for registry keying."""
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9\s]", "", slug)
    slug = re.sub(r"\s+", "_", slug)
    return slug.strip("_")


def generate_enriched_registry():
    """Generate enriched registry from pipeline output, cache, and state."""
    # Load pipeline output
    if not OUTPUT_PATH.exists():
        print("Error: Run pipeline first to generate player_profiles.json")
        return

    with OUTPUT_PATH.open("r", encoding="utf-8") as f:
        output = json.load(f)

    # Load cache for ESPN display names
    cache = {}
    if CACHE_PATH.exists():
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            cache = json.load(f)

    # Load names.csv for aliases
    aliases_map: Dict[str, list] = {}
    if NAMES_CSV.exists():
        with NAMES_CSV.open("r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                pid = (row.get("identifier") or "").strip()
                name = (row.get("name") or "").strip()
                if pid and name:
                    aliases_map.setdefault(pid, []).append(name)

    # Load state
    state = {}
    if STATE_PATH.exists():
        with STATE_PATH.open("r", encoding="utf-8") as f:
            state = json.load(f)

    # Build registry from pipeline output players
    players_out = output.get("players", {})
    teams_out = output.get("teams", {})

    registry_entries = {}
    enriched_count = 0

    for pid, record in players_out.items():
        registry_name = record.get("registry_name") or record.get("name", "")
        aliases = aliases_map.get(pid, [])
        espn_display_name = cache.get(pid, {}).get("espn_display_name")
        # Also check record name if it came from ESPN
        record_name = record.get("name", "")

        best_name = _best_full_name(registry_name, aliases, record_name, espn_display_name)
        slug = _make_slug(best_name)

        has_data = bool(
            record.get("batting", {}).get("hand")
            or record.get("bowling", {}).get("type")
        )
        if has_data:
            enriched_count += 1

        # Collect teams
        player_teams = record.get("teams", [])

        registry_entries[pid] = {
            "player_id": pid,
            "full_name": best_name,
            "registry_name": registry_name,
            "slug": slug,
            "espn_id": (record.get("external_ids") or {}).get("espn"),
            "cricbuzz_id": (record.get("external_ids") or {}).get("cricbuzz"),
            "teams": player_teams,
            "enriched": has_data,
            "batting_hand": record.get("batting", {}).get("hand"),
            "bowling_type": record.get("bowling", {}).get("type"),
            "is_wicketkeeper": record.get("is_wicketkeeper"),
            "source_url": record.get("source"),
            "last_attempted": state.get(pid, {}).get("last_attempted"),
        }

    # Assemble final registry
    registry = {
        "metadata": {
            "format": "firstname_lastname",
            "created": datetime.now(timezone.utc).isoformat(),
            "description": "Player registry with best-available full names and enrichment state",
            "total_players": len(registry_entries),
            "enriched": enriched_count,
            "missing": len(registry_entries) - enriched_count,
        },
        "teams": {
            team: {
                "player_count": len(info.get("player_ids", [])),
                "gender": info.get("gender", "male"),
            }
            for team, info in teams_out.items()
        },
        "players": registry_entries,
    }

    REGISTRY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_OUTPUT.open("w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)

    print(f"Registry written to {REGISTRY_OUTPUT}")
    print(f"  Total players : {len(registry_entries)}")
    print(f"  Enriched      : {enriched_count}")
    print(f"  Missing data  : {len(registry_entries) - enriched_count}")

    return registry


if __name__ == "__main__":
    generate_enriched_registry()
