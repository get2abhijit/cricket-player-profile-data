from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from normalizer import classify_bowling_style, normalize_batting_hand

MANUAL_OVERRIDES_PATH = Path("data/manual_overrides.json")

_BOWLING_KEYS = ("arm", "type", "subtype", "mechanism")


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


def load_manual_overrides(path: Path = MANUAL_OVERRIDES_PATH) -> Dict[str, Dict]:
    payload = _load_json_dict(path)
    players = payload.get("players")
    return players if isinstance(players, dict) else {}


def _empty_bowling() -> Dict[str, Optional[str]]:
    return {
        "arm": None,
        "type": None,
        "subtype": None,
        "mechanism": None,
    }


def _has_actionable_override(record: Dict, override: Dict) -> bool:
    if not isinstance(record, dict) or not isinstance(override, dict):
        return False

    if override.get("batting_style"):
        return True
    if override.get("batting_hand"):
        return True
    if override.get("bowling_style"):
        return True
    if override.get("role"):
        return True
    if override.get("is_wicketkeeper") is not None:
        return True
    if override.get("source_url") and override.get("source_url") != record.get("source"):
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


def apply_manual_override(record: Dict, override: Dict) -> Dict:
    if not _has_actionable_override(record, override):
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
        batting["hand"] = override.get("batting_hand")
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
        "notes": override.get("notes"),
    }
    record["last_updated"] = datetime.now(timezone.utc).isoformat()
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
        if player_id not in players or player_id not in actionable_ids:
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
        "batting_style": None,
        "batting_hand": None,
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
        "notes": None,
    }


def sync_manual_override_placeholders(
    output: Dict,
    path: Path = MANUAL_OVERRIDES_PATH,
) -> Path:
    payload = _load_json_dict(path)
    players = payload.get("players")
    if not isinstance(players, dict):
        players = {}

    changed = not path.exists()

    for pid, record in output.get("players", {}).items():
        batting = (record.get("batting") or {}).get("hand")
        bowling = (record.get("bowling") or {}).get("type")
        if batting or bowling:
            continue
        if pid in players:
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

    return path