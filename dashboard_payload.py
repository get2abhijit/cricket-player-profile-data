"""
dashboard_payload.py
--------------------
Builds output/dashboard_data.json payloads from output/player_profiles.json.

Rules:
- Include enriched players in `players`.
- Split non-enriched players into:
  - `unfound_players`: actionable missing players.
  - `ignored_players`: skipped from enrichment workflow with a reason.
"""

from __future__ import annotations

from datetime import date
from typing import Dict, List

from match_loader import load_player_latest_match_dates, load_t20i_player_team_counts

IGNORE_REASON_NO_T20 = "No T20 appearance"
IGNORE_REASON_NO_RECENT = "No match since 2020-01-01"
IGNORE_REASON_NO_PROFILE = "No profile available"
RECENT_MATCH_CUTOFF = date(2020, 1, 1)

# Manual overrides for known mismatches where the linked public profile does not
# represent a T20 player in scope for this dashboard.
IGNORE_REASON_OVERRIDES = {
    "20ccbb4c": IGNORE_REASON_NO_T20,
}


def _bucket_append(target: Dict[str, List[Dict]], teams: List[str], player_flat: Dict) -> None:
    bucket_teams = teams or ["Unassigned"]
    for team in bucket_teams:
        target.setdefault(team, []).append(player_flat)


def _has_public_profile(record: Dict) -> bool:
    ext_ids = record.get("external_ids") or {}
    source_url = record.get("source")
    return bool(
        ext_ids.get("espn")
        or ext_ids.get("cricbuzz")
        or (source_url and source_url != "registry")
    )


def _t20i_matches_for_player(player_id: str, teams: List[str], t20i_counts: Dict[str, Dict[str, int]]) -> int:
    by_team = t20i_counts.get(player_id, {})
    if not by_team:
        return 0

    total = sum(by_team.get(team, 0) for team in teams)
    # Fallback to any known team count if team names don't align exactly.
    if total == 0:
        total = sum(by_team.values())
    return total


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_dashboard_payload(output: Dict) -> Dict:
    """
    Flatten into a dashboard-friendly form:
    {
      teams: [...],
      players: [...enriched...],
      unfound_players: {team: [...actionable missing...]},
      ignored_players: {team: [...ignored with reason...]}
    }
    """
    flat_players: List[Dict] = []
    unfound_by_team: Dict[str, List[Dict]] = {}
    ignored_by_team: Dict[str, List[Dict]] = {}
    t20i_counts = load_t20i_player_team_counts()
    latest_match_dates = load_player_latest_match_dates()

    for pid, record in output.get("players", {}).items():
        bowling = record.get("bowling") or {}
        batting = record.get("batting") or {}
        teams = record.get("teams", [])
        t20i_matches = _t20i_matches_for_player(pid, teams, t20i_counts)
        latest_match_date = latest_match_dates.get(pid)
        is_enriched = bool(batting.get("hand") or bowling.get("type"))

        player_flat = {
            "id": pid,
            "name": record.get("name"),
            "teams": teams,
            "batting_hand": batting.get("hand"),
            "bowling_arm": bowling.get("arm"),
            "bowling_type": bowling.get("type"),
            "bowling_subtype": bowling.get("subtype"),
            "bowling_mechanism": bowling.get("mechanism"),
            "role": record.get("role"),
            "is_wicketkeeper": record.get("is_wicketkeeper"),
            "manual_override": bool((record.get("manual_override") or {}).get("applied")),
            "manual_override_notes": (record.get("manual_override") or {}).get("notes"),
            "espn_id": (record.get("external_ids") or {}).get("espn"),
            "cricbuzz_id": (record.get("external_ids") or {}).get("cricbuzz"),
            "source_url": record.get("source"),
            "raw_batting": (record.get("raw") or {}).get("batting_style"),
            "raw_bowling": (record.get("raw") or {}).get("bowling_style"),
            "t20i_matches": t20i_matches,
            "latest_match_date": latest_match_date,
        }

        if is_enriched:
            flat_players.append(player_flat)
            continue

        ignore_reason = IGNORE_REASON_OVERRIDES.get(pid)
        if ignore_reason is None and t20i_matches < 1:
            ignore_reason = IGNORE_REASON_NO_T20
        elif ignore_reason is None:
            latest_match = _parse_iso_date(latest_match_date)
            if latest_match is None or latest_match < RECENT_MATCH_CUTOFF:
                ignore_reason = IGNORE_REASON_NO_RECENT
        elif ignore_reason is None and not _has_public_profile(record):
            ignore_reason = IGNORE_REASON_NO_PROFILE

        if ignore_reason is None and not _has_public_profile(record):
            ignore_reason = IGNORE_REASON_NO_PROFILE

        if ignore_reason:
            ignored = dict(player_flat)
            ignored["ignore_reason"] = ignore_reason
            _bucket_append(ignored_by_team, teams, ignored)
        else:
            _bucket_append(unfound_by_team, teams, player_flat)

    team_names = sorted(output.get("teams", {}).keys())
    return {
        "teams": team_names,
        "players": flat_players,
        "unfound_players": unfound_by_team,
        "ignored_players": ignored_by_team,
    }