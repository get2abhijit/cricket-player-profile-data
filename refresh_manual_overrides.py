from __future__ import annotations

import json
from pathlib import Path

from dashboard_payload import build_dashboard_payload
from generate_dashboard import generate_dashboard
from manual_overrides import (
    apply_manual_overrides_to_output,
    load_manual_overrides,
    sync_manual_override_placeholders,
)

OUTPUT_PATH = Path("output/player_profiles.json")
DASHBOARD_DATA_PATH = Path("output/dashboard_data.json")


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
        return loaded if isinstance(loaded, dict) else {}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def refresh_manual_overrides() -> dict:
    output = _load_json(OUTPUT_PATH)
    overrides = load_manual_overrides()

    updated = apply_manual_overrides_to_output(output, overrides)
    sync_manual_override_placeholders(updated)
    _write_json(OUTPUT_PATH, updated)

    dashboard_data = build_dashboard_payload(updated)
    _write_json(DASHBOARD_DATA_PATH, dashboard_data)
    generate_dashboard()

    applied = sum(
        1
        for record in (updated.get("players") or {}).values()
        if (record.get("manual_override") or {}).get("applied")
    )

    print(f"Manual overrides refreshed: {applied} players marked with manual overrides")
    print(f"Updated: {OUTPUT_PATH}")
    print(f"Updated: {DASHBOARD_DATA_PATH}")
    return updated


if __name__ == "__main__":
    refresh_manual_overrides()