from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass(frozen=True)
class PlayerRecord:
    """Single player record assembled from Cricsheet registry data."""

    player_id: str
    player_name: str
    espn_id: Optional[str]
    cricbuzz_id: Optional[str]
    aliases: List[str]


@dataclass(frozen=True)
class RegistryPaths:
    """Resolved paths for people and names registry CSVs."""

    people_csv: Path
    names_csv: Path


class RegistryLoaderError(RuntimeError):
    """Raised when registry files cannot be located or parsed."""


def resolve_registry_paths(base_dir: Optional[Path] = None) -> RegistryPaths:
    """
    Resolve registry files from data/registry_csv/, data/cricsheet/, or data/.

    This keeps compatibility with both the prompt's desired folder structure and
    the current repository layout.
    """
    root = (base_dir or Path(__file__).resolve().parent).resolve()
    candidate_roots = [
        root / "data" / "registry_csv",
        root / "data" / "cricsheet",
        root / "data",
    ]

    for candidate in candidate_roots:
        people_csv = candidate / "people.csv"
        names_csv = candidate / "names.csv"
        if people_csv.exists() and names_csv.exists():
            return RegistryPaths(people_csv=people_csv, names_csv=names_csv)

    searched = "\n".join(str(path) for path in candidate_roots)
    raise RegistryLoaderError(f"Could not find people.csv and names.csv. Searched:\n{searched}")


def _clean_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def load_registry(paths: Optional[RegistryPaths] = None) -> List[PlayerRecord]:
    """Load players from Cricsheet registry CSV files."""
    resolved_paths = paths or resolve_registry_paths()

    aliases_map: Dict[str, List[str]] = {}
    with resolved_paths.names_csv.open("r", encoding="utf-8", newline="") as names_file:
        reader = csv.DictReader(names_file)
        for row in reader:
            player_id = _clean_value(row.get("identifier"))
            alias = _clean_value(row.get("name"))
            if not player_id or not alias:
                continue
            aliases = aliases_map.setdefault(player_id, [])
            if alias not in aliases:
                aliases.append(alias)

    players: List[PlayerRecord] = []
    with resolved_paths.people_csv.open("r", encoding="utf-8", newline="") as people_file:
        reader = csv.DictReader(people_file)
        for row in reader:
            player_id = _clean_value(row.get("identifier"))
            player_name = _clean_value(row.get("name"))
            if not player_id or not player_name:
                continue

            players.append(
                PlayerRecord(
                    player_id=player_id,
                    player_name=player_name,
                    espn_id=_clean_value(row.get("key_cricinfo")),
                    cricbuzz_id=_clean_value(row.get("key_cricbuzz")),
                    aliases=aliases_map.get(player_id, []),
                )
            )

    return players
