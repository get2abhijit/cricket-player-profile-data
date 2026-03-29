"""
tests/test_match_loader.py
--------------------------
Unit tests for match_loader.py  — team/player extraction from Cricsheet match JSON.
"""

import json
from pathlib import Path

import pytest

from match_loader import country_from_folder, load_teams_from_matches


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_MATCH_JSON = {
    "meta": {"data_version": "1.0.0", "created": "2020-10-16", "revision": 1},
    "info": {
        "players": {
            "Bulgaria": ["K Dasan", "Sulaiman Ali", "Bakhtiar Tahiri"],
            "Romania":  ["G Manan", "R Satheesan"],
        },
        "registry": {
            "people": {
                "K Dasan":        "1c014a94",
                "Sulaiman Ali":   "13bf1d91",
                "Bakhtiar Tahiri":"a9ee404e",
                "G Manan":        "d7265622",
                "R Satheesan":    "1125ebe4",
            }
        },
    },
}


@pytest.fixture()
def matches_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "bulgaria_male_json"
    folder.mkdir()
    (folder / "1235829.json").write_text(
        json.dumps(_MATCH_JSON), encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLoadTeamsFromMatches:
    def test_extracts_teams(self, matches_dir):
        teams, _ = load_teams_from_matches(matches_dir)
        assert "Bulgaria" in teams
        assert "Romania"  in teams

    def test_bulgaria_players(self, matches_dir):
        teams, _ = load_teams_from_matches(matches_dir)
        assert "1c014a94"  in teams["Bulgaria"]
        assert "13bf1d91"  in teams["Bulgaria"]
        assert "a9ee404e"  in teams["Bulgaria"]

    def test_id_names_mapping(self, matches_dir):
        _, id_names = load_teams_from_matches(matches_dir)
        assert id_names.get("1c014a94")     == "K Dasan"
        assert id_names.get("a9ee404e")     == "Bakhtiar Tahiri"

    def test_empty_directory(self, tmp_path):
        teams, id_names = load_teams_from_matches(tmp_path)
        assert teams    == {}
        assert id_names == {}

    def test_malformed_json_skipped(self, tmp_path):
        folder = tmp_path / "broken"
        folder.mkdir()
        (folder / "bad.json").write_text("{ not valid json", encoding="utf-8")
        teams, _ = load_teams_from_matches(tmp_path)
        assert teams == {}

    def test_player_without_registry_entry_skipped(self, tmp_path):
        data = {
            "info": {
                "players": {"TeamA": ["Unknown Player"]},
                "registry": {"people": {}},
            }
        }
        folder = tmp_path / "teama_json"
        folder.mkdir()
        (folder / "match.json").write_text(json.dumps(data), encoding="utf-8")
        teams, id_names = load_teams_from_matches(tmp_path)
        assert teams.get("TeamA", set()) == set()
        assert id_names == {}

    def test_multiple_matches_accumulate_players(self, tmp_path):
        folder = tmp_path / "czech_republic_male_json"
        folder.mkdir()
        match1 = {
            "info": {
                "players": {"Czech Republic": ["A Player"]},
                "registry": {"people": {"A Player": "id0001"}},
            }
        }
        match2 = {
            "info": {
                "players": {"Czech Republic": ["B Player"]},
                "registry": {"people": {"B Player": "id0002"}},
            }
        }
        (folder / "m1.json").write_text(json.dumps(match1), encoding="utf-8")
        (folder / "m2.json").write_text(json.dumps(match2), encoding="utf-8")
        teams, _ = load_teams_from_matches(tmp_path)
        assert "id0001" in teams["Czech Republic"]
        assert "id0002" in teams["Czech Republic"]


class TestCountryFromFolder:
    def test_bulgaria(self):
        assert country_from_folder("bulgaria_male_json") == "Bulgaria"

    def test_czech_republic(self):
        assert country_from_folder("czech_republic_male_json") == "Czech Republic"

    def test_isle_of_man(self):
        assert country_from_folder("isle_of_man_male_json") == "Isle Of Man"

    def test_no_suffix(self):
        # Folder with just a name
        assert "Spain" in country_from_folder("spain_male_json")
