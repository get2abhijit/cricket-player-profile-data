"""
enrichment_state.py
-------------------
Manages state tracking for player enrichment.
Tracks which players have been processed, when, and what data was found.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

STATE_PATH = Path("data/enrichment_state.json")


def load_state() -> Dict[str, Dict[str, Any]]:
    """Load enrichment state. Returns empty dict if file doesn't exist."""
    if not STATE_PATH.exists():
        return {}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: Dict[str, Dict[str, Any]]) -> None:
    """Write enrichment state to disk."""
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def mark_enriched(
    state: Dict[str, Dict[str, Any]],
    player_id: str,
    has_data: bool,
    error: Optional[str] = None,
) -> None:
    """Mark a player as attempted enrichment."""
    state[player_id] = {
        "enriched": has_data,
        "last_attempted": datetime.now(timezone.utc).isoformat(),
        "has_data": has_data,
        "error": error,
    }


def is_enriched(state: Dict[str, Dict[str, Any]], player_id: str) -> bool:
    """Check if a player has been enriched (has_data=True)."""
    return state.get(player_id, {}).get("has_data", False)


def get_unenriched_players(
    state: Dict[str, Dict[str, Any]],
    all_player_ids: set,
    include_failed: bool = False,
) -> set:
    """
    Get the set of players that have not been successfully enriched.
    
    If include_failed=True, also include players that were attempted but failed.
    """
    unenriched = set()
    for player_id in all_player_ids:
        if player_id not in state:
            # Never attempted
            unenriched.add(player_id)
        elif not state[player_id].get("has_data", False):
            # Attempted but no data
            if include_failed or state[player_id].get("error"):
                unenriched.add(player_id)
    return unenriched
