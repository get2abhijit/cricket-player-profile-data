"""
tests/test_registry_loader.py
------------------------------
Unit tests for registry_loader.py.  Uses the real data/people.csv and
data/names.csv files from the workspace so results are consistent with
live data.
"""

import csv
import io
from pathlib import Path

import pytest

from registry_loader import (
    RegistryPaths,
    RegistryLoaderError,
    load_registry,
    resolve_registry_paths,
)

# ---------------------------------------------------------------------------
# Fixtures: tiny in-memory CSV stubs
# ---------------------------------------------------------------------------

_PEOPLE_CSV = """\
identifier,name,unique_name,key_bcci,key_bcci_2,key_bigbash,key_cricbuzz,key_cricheroes,key_crichq,key_cricinfo,key_cricinfo_2,key_cricinfo_3,key_cricingif,key_cricketarchive,key_cricketarchive_2,key_cricketworld,key_nvplay,key_nvplay_2,key_opta,key_opta_2,key_pulse,key_pulse_2
aabb0001,Test Player One,Test Player One,,,,,,,111111,,,,,,,,,,,,
aabb0002,Test Player Two,Test Player Two,,,,,,,222222,,,,,,,,,,,,
aabb0003,No ID Player,No ID Player,,,,,,,,,,,,,,,,,,,
"""

_NAMES_CSV = """\
identifier,name
aabb0001,T Player One
aabb0001,Test P One
aabb0002,Player Two
"""


def _make_paths(tmp_path: Path) -> RegistryPaths:
    (tmp_path / "people.csv").write_text(_PEOPLE_CSV, encoding="utf-8")
    (tmp_path / "names.csv").write_text(_NAMES_CSV, encoding="utf-8")
    return RegistryPaths(
        people_csv=tmp_path / "people.csv",
        names_csv=tmp_path / "names.csv",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRegistryLoader:
    def test_loads_players(self, tmp_path):
        paths = _make_paths(tmp_path)
        players = load_registry(paths)
        assert len(players) == 3

    def test_player_fields(self, tmp_path):
        paths = _make_paths(tmp_path)
        by_id = {p.player_id: p for p in load_registry(paths)}

        p1 = by_id["aabb0001"]
        assert p1.player_name  == "Test Player One"
        assert p1.espn_id      == "111111"
        assert p1.cricbuzz_id  is None

        p3 = by_id["aabb0003"]
        assert p3.espn_id     is None
        assert p3.cricbuzz_id is None

    def test_aliases_populated(self, tmp_path):
        paths = _make_paths(tmp_path)
        by_id = {p.player_id: p for p in load_registry(paths)}

        p1 = by_id["aabb0001"]
        assert "T Player One" in p1.aliases
        assert "Test P One"   in p1.aliases

    def test_player_with_no_aliases(self, tmp_path):
        paths = _make_paths(tmp_path)
        by_id = {p.player_id: p for p in load_registry(paths)}
        assert by_id["aabb0003"].aliases == []

    def test_espn_id_from_key_cricinfo(self, tmp_path):
        paths = _make_paths(tmp_path)
        by_id = {p.player_id: p for p in load_registry(paths)}
        assert by_id["aabb0002"].espn_id == "222222"


class TestResolveRegistryPaths:
    def test_finds_data_subdir(self, tmp_path):
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "people.csv").write_text("identifier,name\n", encoding="utf-8")
        (tmp_path / "data" / "names.csv").write_text("identifier,name\n", encoding="utf-8")
        paths = resolve_registry_paths(tmp_path)
        assert paths.people_csv.exists()

    def test_raises_when_files_missing(self, tmp_path):
        with pytest.raises(RegistryLoaderError):
            resolve_registry_paths(tmp_path)


class TestLoadRegistryLive:
    """Tests against actual workspace data/people.csv + data/names.csv."""

    @pytest.fixture(autouse=True)
    def check_data_present(self):
        data_dir = Path("data")
        if not (data_dir / "people.csv").exists():
            pytest.skip("data/ directory not available")

    def test_loads_without_error(self):
        players = load_registry()
        assert len(players) > 0, "Expected at least one player from live data"

    def test_all_records_have_id_and_name(self):
        players = load_registry()
        for p in players:
            assert p.player_id, "player_id must not be empty"
            assert p.player_name, "player_name must not be empty"

    def test_espn_id_is_numeric_when_present(self):
        players = load_registry()
        for p in players:
            if p.espn_id:
                assert p.espn_id.isdigit(), f"Expected numeric ESPN ID, got {p.espn_id!r}"

    def test_unique_player_ids(self):
        players = load_registry()
        ids = [p.player_id for p in players]
        assert len(ids) == len(set(ids)), "Duplicate player_ids found"
