from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from dashboard_payload import build_dashboard_payload
from normalizer import classify_bowling_style, normalize_batting_hand

MANUAL_OVERRIDES_PATH = Path("data/manual_overrides.json")
ENRICHED_OVERRIDES_PATH = Path("data/manual_overrides_enriched.json")
IGNORED_OVERRIDES_PATH = Path("data/manual_overrides_ignored.json")
REGISTRY_ENRICHED_PATH = Path("output/registry_enriched.json")

_BOWLING_KEYS = ("arm", "type", "subtype", "mechanism")
_DEFAULT_BATTING_STYLE = "RHB"
_DEFAULT_BATTING_HAND = "Right"
_ESPN_ID_PATTERNS = (
    r"(?:cricketers|player)/[^/?#]*-(\d+)(?:[/?#]|$)",
    r"/player/(\d+)(?:[/?#]|$)",
    r"[?&]player(?:id)?=(\d+)",
)


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


def infer_is_wicketkeeper(role: Optional[str]) -> Optional[bool]:
    if not role:
        return None

    normalized = role.strip().lower()
    if "wk" in normalized or "wicket" in normalized:
        return True
    return False


def _load_players_block(path: Path) -> Dict[str, Dict]:
    payload = _load_json_dict(path)
    players = payload.get("players")
    return players if isinstance(players, dict) else {}


def load_manual_overrides(
    path: Path = MANUAL_OVERRIDES_PATH,
    enriched_path: Path = ENRICHED_OVERRIDES_PATH,
) -> Dict[str, Dict]:
    enriched_players = _load_players_block(enriched_path)
    active_players = _load_players_block(path)
    merged = dict(enriched_players)
    merged.update(active_players)
    return merged


def _empty_bowling() -> Dict[str, Optional[str]]:
    return {
        "arm": None,
        "type": None,
        "subtype": None,
        "mechanism": None,
    }


def _has_non_batting_override(record: Dict, override: Dict) -> bool:
    if override.get("bowling_style"):
        return True
    if override.get("role"):
        return True
    if override.get("is_wicketkeeper") is not None:
        return True

    source_url = override.get("source_url")
    record_source = record.get("source")
    if source_url and source_url != record_source:
        override_external_ids = override.get("external_ids")
        record_external_ids = record.get("external_ids")
        override_espn_id = _extract_espn_id(source_url)
        if not override_espn_id and isinstance(override_external_ids, dict):
            override_espn_id = _extract_espn_id(override_external_ids.get("espn"))

        record_espn_id = _extract_espn_id(record_source)
        if not record_espn_id and isinstance(record_external_ids, dict):
            record_espn_id = _extract_espn_id(record_external_ids.get("espn"))

        # Treat URL slug changes as equivalent when both refer to the same ESPN id.
        if not (override_espn_id and record_espn_id and override_espn_id == record_espn_id):
            return True

    bowling = override.get("bowling")
    if isinstance(bowling, dict) and any(bowling.get(key) for key in _BOWLING_KEYS):
        return True

    external_ids = override.get("external_ids")
    current_external_ids = record.get("external_ids") or {}
    if isinstance(external_ids, dict):
        for key in ("espn", "cricbuzz"):
            if key in external_ids and external_ids.get(key) != current_external_ids.get(key):
                return True

    return False


def _extract_espn_id(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return text

    for pattern in _ESPN_ID_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def _is_default_batting_override(override: Dict) -> bool:
    batting_style = override.get("batting_style")
    batting_hand = override.get("batting_hand")
    has_batting_fields = "batting_style" in override or "batting_hand" in override
    if not has_batting_fields:
        return False

    normalized_style = batting_style or _DEFAULT_BATTING_STYLE
    normalized_hand = batting_hand or _DEFAULT_BATTING_HAND
    return normalized_style == _DEFAULT_BATTING_STYLE and normalized_hand == _DEFAULT_BATTING_HAND


def _is_placeholder_entry(entry: Dict) -> bool:
    if not isinstance(entry, dict):
        return False
    if entry.get("role") is not None or entry.get("is_wicketkeeper") is not None:
        return False
    if entry.get("bowling_style") is not None:
        return False

    bowling = entry.get("bowling")
    if isinstance(bowling, dict) and any(bowling.get(key) for key in _BOWLING_KEYS):
        return False

    batting_style = entry.get("batting_style")
    batting_hand = entry.get("batting_hand")
    return batting_style in {None, _DEFAULT_BATTING_STYLE} and batting_hand in {None, _DEFAULT_BATTING_HAND}


def _clear_stale_placeholder_override(record: Dict, override: Dict) -> None:
    if not _is_default_batting_override(override):
        return

    batting = dict(record.get("batting") or {})
    raw = dict(record.get("raw") or {})
    if batting.get("hand") == "Right" or raw.get("batting_style") == _DEFAULT_BATTING_STYLE:
        batting["hand"] = None
    if raw.get("batting_style") == _DEFAULT_BATTING_STYLE:
        raw["batting_style"] = None
    record["batting"] = batting
    record["raw"] = raw


def _override_enriched_flag(override: Dict) -> bool:
    return bool(override.get("enriched", False))


def _has_actionable_override(record: Dict, override: Dict) -> bool:
    if not isinstance(record, dict) or not isinstance(override, dict):
        return False

    has_non_batting_override = _has_non_batting_override(record, override)

    if (override.get("batting_style") or override.get("batting_hand")) and (
        has_non_batting_override or not _is_default_batting_override(override)
    ):
        return True

    return has_non_batting_override


def apply_manual_override(record: Dict, override: Dict) -> Dict:
    if not _has_actionable_override(record, override):
        _clear_stale_placeholder_override(record, override)
        record.pop("manual_override", None)
        return record

    batting = dict(record.get("batting") or {"hand": None})
    bowling = _empty_bowling()
    bowling.update(record.get("bowling") or {})
    raw = dict(record.get("raw") or {})
    external_ids = dict(record.get("external_ids") or {})

    if "batting_style" in override:
        raw["batting_style"] = override.get("batting_style")

    if "bowling_style" in override:
        raw["bowling_style"] = override.get("bowling_style")
        bowling = classify_bowling_style(override.get("bowling_style"))

    manual_bowling = override.get("bowling")
    if isinstance(manual_bowling, dict):
        if "bowling_style" not in override:
            bowling = _empty_bowling()
        for key in _BOWLING_KEYS:
            if key in manual_bowling:
                bowling[key] = manual_bowling.get(key)

    if "batting_hand" in override:
        batting["hand"] = normalize_batting_hand(override.get("batting_hand")) or override.get("batting_hand")
    elif "batting_style" in override:
        batting["hand"] = normalize_batting_hand(override.get("batting_style"))

    if "role" in override:
        record["role"] = override.get("role")
        raw["role"] = override.get("role")

    if "is_wicketkeeper" in override:
        record["is_wicketkeeper"] = override.get("is_wicketkeeper")
    elif "role" in override:
        record["is_wicketkeeper"] = infer_is_wicketkeeper(override.get("role"))

    manual_external_ids = override.get("external_ids")
    if isinstance(manual_external_ids, dict):
        for key in ("espn", "cricbuzz"):
            if key in manual_external_ids:
                external_ids[key] = manual_external_ids.get(key)

    source_url = override.get("source_url")
    if source_url:
        record["source"] = source_url

    record["batting"] = batting
    record["bowling"] = bowling
    record["raw"] = raw
    record["external_ids"] = external_ids
    record["manual_override"] = {
        "applied": True,
        "source": override.get("source") or "manual",
        "enriched": _override_enriched_flag(override),
        "notes": override.get("notes"),
    }
    record["last_updated"] = datetime.now(timezone.utc).date().isoformat()
    return record


def apply_manual_overrides_to_output(output: Dict, overrides: Dict[str, Dict]) -> Dict:
    players = output.get("players")
    if not isinstance(players, dict):
        return output

    actionable_ids = {
        player_id
        for player_id, override in overrides.items()
        if player_id in players and _has_actionable_override(players[player_id], override)
    }

    for player_id, record in players.items():
        if player_id not in actionable_ids:
            record.pop("manual_override", None)

    for player_id, override in overrides.items():
        if player_id not in players:
            continue
        players[player_id] = apply_manual_override(players[player_id], override)

    output["players"] = players
    return output


def _placeholder_entry(record: Dict) -> Dict:
    external_ids = record.get("external_ids") or {}
    source_url = record.get("source")
    return {
        "name": record.get("name"),
        "teams": record.get("teams", []),
        "batting_style": _DEFAULT_BATTING_STYLE,
        "batting_hand": _DEFAULT_BATTING_HAND,
        "bowling_style": None,
        "bowling": _empty_bowling(),
        "role": None,
        "is_wicketkeeper": None,
        "external_ids": {
            "espn": external_ids.get("espn"),
            "cricbuzz": external_ids.get("cricbuzz"),
        },
        "source_url": source_url if source_url and source_url != "registry" else None,
        "source": "manual",
        "enriched": False,
        "notes": None,
    }


def _ignored_entry(record: Dict, ignored_flat: Optional[Dict] = None, existing: Optional[Dict] = None) -> Dict:
    external_ids = record.get("external_ids") or {}
    source_url = record.get("source")
    if isinstance(existing, dict):
        entry = dict(existing)
    else:
        entry = {
            "name": record.get("name"),
            "teams": record.get("teams", []),
            "external_ids": {
                "espn": external_ids.get("espn"),
                "cricbuzz": external_ids.get("cricbuzz"),
            },
            "source_url": source_url if source_url and source_url != "registry" else None,
            "source": "system",
            "notes": None,
        }

    if isinstance(ignored_flat, dict):
        entry["ignore_reason"] = ignored_flat.get("ignore_reason")
        entry["t20i_matches"] = ignored_flat.get("t20i_matches")
        entry["latest_match_date"] = ignored_flat.get("latest_match_date")
    return entry


def _backfill_default_batting_fields(entry: Dict) -> bool:
    changed = False
    if entry.get("batting_style") is None:
        entry["batting_style"] = _DEFAULT_BATTING_STYLE
        changed = True
    if entry.get("batting_hand") is None:
        entry["batting_hand"] = _DEFAULT_BATTING_HAND
        changed = True
    return changed


def _backfill_enriched_flag(entry: Dict) -> bool:
    if "enriched" in entry:
        return False
    entry["enriched"] = False
    return True


def sync_manual_override_placeholders(
    output: Dict,
    path: Path = MANUAL_OVERRIDES_PATH,
    enriched_path: Path = ENRICHED_OVERRIDES_PATH,
    ignored_path: Path = IGNORED_OVERRIDES_PATH,
    registry_enriched_path: Path = REGISTRY_ENRICHED_PATH,
) -> Path:
    payload = _load_json_dict(path)
    players = payload.get("players")
    if not isinstance(players, dict):
        players = {}

    enriched_payload = _load_json_dict(enriched_path)
    enriched_players = enriched_payload.get("players")
    if not isinstance(enriched_players, dict):
        enriched_players = {}

    ignored_payload = _load_json_dict(ignored_path)
    ignored_players = ignored_payload.get("players")
    if not isinstance(ignored_players, dict):
        ignored_players = {}

    registry_enriched = _load_json_dict(registry_enriched_path)
    registry_players = registry_enriched.get("players")
    if not isinstance(registry_players, dict):
        registry_players = {}
    registry_enriched_ids = {
        pid
        for pid, value in registry_players.items()
        if isinstance(value, dict) and bool(value.get("enriched", False))
    }

    changed = not path.exists()
    enriched_changed = not enriched_path.exists()
    ignored_changed = not ignored_path.exists()

    dashboard_payload = build_dashboard_payload(output)
    actionable_missing_ids = {
        player.get("id")
        for players_by_team in (dashboard_payload.get("unfound_players") or {}).values()
        for player in players_by_team
        if isinstance(player, dict) and player.get("id")
    }
    actionable_missing_ids -= registry_enriched_ids
    ignored_flat_by_id = {
        player.get("id"): player
        for players_by_team in (dashboard_payload.get("ignored_players") or {}).values()
        for player in players_by_team
        if isinstance(player, dict) and player.get("id")
    }

    enriched_ids = [
        pid
        for pid, existing in players.items()
        if isinstance(existing, dict) and bool(existing.get("enriched", False))
    ]
    for pid in enriched_ids:
        enriched_players[pid] = players.pop(pid)
        enriched_changed = True
        changed = True

    for pid in list(players.keys()):
        if pid in registry_enriched_ids:
            players.pop(pid)
            changed = True
            continue
        if pid not in ignored_flat_by_id:
            continue
        existing = players.pop(pid)
        record = (output.get("players") or {}).get(pid) or {}
        ignored_players[pid] = _ignored_entry(record, ignored_flat_by_id.get(pid), existing)
        ignored_changed = True
        changed = True

    for pid, existing in players.items():
        if not isinstance(existing, dict):
            continue

        if _backfill_enriched_flag(existing):
            changed = True

        if not _is_placeholder_entry(existing):
            continue
        if pid in actionable_missing_ids:
            if _backfill_default_batting_fields(existing):
                changed = True
            continue

        cleared = False
        if existing.get("batting_style") == _DEFAULT_BATTING_STYLE:
            existing["batting_style"] = None
            cleared = True
        if existing.get("batting_hand") == _DEFAULT_BATTING_HAND:
            existing["batting_hand"] = None
            cleared = True
        if cleared:
            changed = True

    for pid, record in output.get("players", {}).items():
        if pid not in actionable_missing_ids:
            continue
        batting = (record.get("batting") or {}).get("hand")
        bowling = (record.get("bowling") or {}).get("type")
        if batting or bowling:
            continue
        existing = players.get(pid)
        if isinstance(existing, dict):
            continue
        players[pid] = _placeholder_entry(record)
        changed = True

    payload["meta"] = {
        "description": "Optional manual overrides. Edit players here instead of changing Python code.",
        "editable_scope": "Any player may be added under players by player id.",
        "seeded_with": "Players currently missing batting and bowling data are auto-added as placeholders.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    payload["players"] = players

    if changed:
        _write_json(path, payload)

    enriched_payload["meta"] = {
        "description": "Resolved manual overrides retained for enrichment and excluded from manual review queue.",
        "editable_scope": "Players moved here automatically when enriched is set to true.",
        "seeded_with": "Entries are migrated from data/manual_overrides.json during refresh.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    enriched_payload["players"] = enriched_players
    if enriched_changed:
        _write_json(enriched_path, enriched_payload)

    # Keep ignored list independent from editable manual overrides.
    stale_ignored_ids = [pid for pid in ignored_players if pid not in ignored_flat_by_id]
    for pid in stale_ignored_ids:
        ignored_players.pop(pid, None)
        ignored_changed = True

    for pid, ignored_flat in ignored_flat_by_id.items():
        record = (output.get("players") or {}).get(pid) or {}
        candidate_existing = ignored_players.get(pid)
        entry = _ignored_entry(record, ignored_flat, candidate_existing)
        if ignored_players.get(pid) != entry:
            ignored_players[pid] = entry
            ignored_changed = True

    ignored_payload["meta"] = {
        "description": "Ignored players are tracked separately and excluded from manual override workflow.",
        "editable_scope": "Reference only; these players are ignored based on dashboard classification rules.",
        "seeded_with": "Entries are refreshed from output/dashboard classification during refresh.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    ignored_payload["players"] = ignored_players
    if ignored_changed:
        _write_json(ignored_path, ignored_payload)

    return path