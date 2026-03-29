"""
tests/test_output_schema.py
----------------------------
Validates the structure of the generated output/player_profiles.json and
output/dashboard_data.json against the expected schemas.
"""

import json
from pathlib import Path

import pytest

OUTPUT_PATH        = Path("output/player_profiles.json")
DASHBOARD_PATH     = Path("output/dashboard_data.json")

PLAYER_REQUIRED_KEYS = {
    "identifier", "name", "known_as", "teams",
    "external_ids", "batting", "bowling", "role",
    "raw", "source", "last_updated",
}
BOWLING_KEYS = {"arm", "type", "subtype", "mechanism"}


@pytest.fixture(scope="module")
def profile_data():
    if not OUTPUT_PATH.exists():
        pytest.skip("output/player_profiles.json not generated yet")
    return json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dashboard_data():
    if not DASHBOARD_PATH.exists():
        pytest.skip("output/dashboard_data.json not generated yet")
    return json.loads(DASHBOARD_PATH.read_text(encoding="utf-8"))


class TestPlayerProfileSchema:
    def test_top_level_keys(self, profile_data):
        assert "meta"    in profile_data
        assert "teams"   in profile_data
        assert "players" in profile_data

    def test_meta_fields(self, profile_data):
        meta = profile_data["meta"]
        assert "data_version" in meta
        assert "created"      in meta
        assert "revision"     in meta

    def test_players_is_dict(self, profile_data):
        assert isinstance(profile_data["players"], dict)
        assert len(profile_data["players"]) > 0

    def test_teams_is_dict(self, profile_data):
        assert isinstance(profile_data["teams"], dict)

    def test_player_record_keys(self, profile_data):
        for pid, record in profile_data["players"].items():
            missing = PLAYER_REQUIRED_KEYS - set(record.keys())
            assert not missing, f"Player {pid} missing keys: {missing}"

    def test_player_identifier_matches_key(self, profile_data):
        for pid, record in profile_data["players"].items():
            assert record["identifier"] == pid

    def test_bowling_keys_present(self, profile_data):
        for pid, record in profile_data["players"].items():
            bowling = record.get("bowling") or {}
            missing = BOWLING_KEYS - set(bowling.keys())
            assert not missing, f"Player {pid} bowling missing keys: {missing}"

    def test_batting_key_present(self, profile_data):
        for pid, record in profile_data["players"].items():
            assert "hand" in (record.get("batting") or {}), (
                f"Player {pid} missing batting.hand"
            )

    def test_batting_hand_valid_when_present(self, profile_data):
        valid = {None, "RHB", "LHB"}
        for pid, record in profile_data["players"].items():
            hand = (record.get("batting") or {}).get("hand")
            assert hand in valid, f"Player {pid} unexpected batting hand: {hand!r}"

    def test_bowling_type_valid_when_present(self, profile_data):
        valid = {None, "Pace", "Spin"}
        for pid, record in profile_data["players"].items():
            btype = (record.get("bowling") or {}).get("type")
            assert btype in valid, f"Player {pid} unexpected bowling type: {btype!r}"

    def test_teams_block_references_valid_players(self, profile_data):
        player_ids = set(profile_data["players"].keys())
        for team, info in profile_data["teams"].items():
            for pid in info.get("player_ids", []):
                assert pid in player_ids, (
                    f"Team {team!r} references unknown player {pid!r}"
                )

    def test_some_players_have_batting_hand(self, profile_data):
        """At least some players should have enriched batting hand data."""
        enriched = [
            pid for pid, rec in profile_data["players"].items()
            if (rec.get("batting") or {}).get("hand")
        ]
        assert len(enriched) > 0, (
            "No players have batting hand data — enrichment pipeline may have failed"
        )

    def test_some_players_have_bowling_type(self, profile_data):
        """At least some players should have enriched bowling type data."""
        enriched = [
            pid for pid, rec in profile_data["players"].items()
            if (rec.get("bowling") or {}).get("type")
        ]
        assert len(enriched) > 0, (
            "No players have bowling type data — enrichment pipeline may have failed"
        )


class TestDashboardDataSchema:
    def test_top_level_keys(self, dashboard_data):
        assert "teams"   in dashboard_data
        assert "players" in dashboard_data

    def test_teams_is_list(self, dashboard_data):
        assert isinstance(dashboard_data["teams"], list)

    def test_players_is_list(self, dashboard_data):
        assert isinstance(dashboard_data["players"], list)

    def test_player_flat_keys(self, dashboard_data):
        required = {"id", "name", "teams", "batting_hand", "bowling_type",
                    "bowling_arm", "bowling_subtype", "bowling_mechanism",
                    "role", "espn_id", "raw_batting", "raw_bowling"}
        for p in dashboard_data["players"]:
            missing = required - set(p.keys())
            assert not missing, f"Dashboard player {p.get('id')} missing: {missing}"
