"""
match_loader.py
---------------
Scans all Cricsheet match JSON files under data/matches_json/ and builds a
mapping of { team_name: set(cricsheet_player_ids) } plus a
{ cricsheet_id: canonical_name } lookup.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

MATCHES_BASE = Path("data/matches_json")
_T20_MATCH_TYPES = {"T20", "IT20"}


class MatchLoaderError(RuntimeError):
    pass


def _iter_match_files(base_dir: Optional[Path] = None) -> List[Path]:
    root = (base_dir or MATCHES_BASE).resolve()
    if not root.exists():
        return []
    return sorted(root.rglob("*.json"))


def load_teams_from_matches(
    base_dir: Optional[Path] = None,
) -> Tuple[Dict[str, Set[str]], Dict[str, str]]:
    """
    Read every match JSON and return two dicts:

    teams:    { team_name -> set of cricsheet player_ids }
    id_names: { cricsheet_id -> most-recently-seen display name }
    """
    teams: Dict[str, Set[str]] = defaultdict(set)
    id_names: Dict[str, str] = {}

    for match_file in _iter_match_files(base_dir):
        try:
            with match_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        info = data.get("info", {})
        players_by_team: Dict[str, List[str]] = info.get("players", {})
        registry: Dict[str, str] = info.get("registry", {}).get("people", {})

        for team_name, player_names in players_by_team.items():
            for display_name in player_names:
                cricsheet_id = registry.get(display_name)
                if cricsheet_id:
                    teams[team_name].add(cricsheet_id)
                    id_names[cricsheet_id] = display_name

    return dict(teams), id_names


def country_from_folder(folder_name: str) -> str:
    """Convert folder name like 'bulgaria_male_json' → 'Bulgaria'."""
    parts = folder_name.replace("_json", "").replace("_male", "").replace("_female", "")
    return " ".join(p.capitalize() for p in parts.split("_"))


def load_t20i_player_team_counts(
    base_dir: Optional[Path] = None,
) -> Dict[str, Dict[str, int]]:
    """
    Return per-player T20 international appearance counts grouped by team.

    Result shape:
    {
      "<player_id>": {"Team Name": <count>, ...},
      ...
    }
    """
    counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for match_file in _iter_match_files(base_dir):
        try:
            with match_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        info = data.get("info", {})
        match_type = str(info.get("match_type") or "").upper()
        team_type = str(info.get("team_type") or "").lower()

        if match_type not in _T20_MATCH_TYPES or team_type != "international":
            continue

        players_by_team: Dict[str, List[str]] = info.get("players", {})
        registry: Dict[str, str] = info.get("registry", {}).get("people", {})

        for team_name, player_names in players_by_team.items():
            for display_name in player_names:
                player_id = registry.get(display_name)
                if player_id:
                    counts[player_id][team_name] += 1

    return {pid: dict(team_counts) for pid, team_counts in counts.items()}


def load_player_latest_match_dates(
    base_dir: Optional[Path] = None,
) -> Dict[str, str]:
    """Return the latest match date seen for each player as YYYY-MM-DD."""
    latest_dates: Dict[str, date] = {}

    for match_file in _iter_match_files(base_dir):
        try:
            with match_file.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            continue

        info = data.get("info", {})
        match_dates = info.get("dates") or []
        if not match_dates:
            continue

        try:
            latest_in_file = max(date.fromisoformat(d) for d in match_dates)
        except ValueError:
            continue

        players_by_team: Dict[str, List[str]] = info.get("players", {})
        registry: Dict[str, str] = info.get("registry", {}).get("people", {})

        for player_names in players_by_team.values():
            for display_name in player_names:
                player_id = registry.get(display_name)
                if not player_id:
                    continue
                previous = latest_dates.get(player_id)
                if previous is None or latest_in_file > previous:
                    latest_dates[player_id] = latest_in_file

    return {pid: match_date.isoformat() for pid, match_date in latest_dates.items()}
