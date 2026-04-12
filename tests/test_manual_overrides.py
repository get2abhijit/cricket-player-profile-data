from __future__ import annotations

import json

import manual_overrides
from dashboard_payload import build_dashboard_payload

from manual_overrides import (
    apply_manual_override,
    apply_manual_overrides_to_output,
    infer_is_wicketkeeper,
    load_manual_overrides,
    sync_manual_override_placeholders,
)


def _record() -> dict:
    return {
        "identifier": "player-1",
        "name": "Sample Player",
        "teams": ["Spain"],
        "external_ids": {"espn": "123", "cricbuzz": None},
        "batting": {"hand": None},
        "bowling": {"arm": None, "type": None, "subtype": None, "mechanism": None},
        "role": None,
        "is_wicketkeeper": None,
        "raw": {"batting_style": None, "bowling_style": None, "role": None},
        "source": "registry",
        "last_updated": "2026-03-30T00:00:00+00:00",
    }


class TestInferIsWicketkeeper:
    def test_true_for_wk_role(self):
        assert infer_is_wicketkeeper("WK-Batsman") is True

    def test_false_for_non_wk_role(self):
        assert infer_is_wicketkeeper("Bowler") is False

    def test_none_when_role_missing(self):
        assert infer_is_wicketkeeper(None) is None


class TestApplyManualOverride:
    def test_uses_raw_styles_when_present(self):
        record = _record()
        updated = apply_manual_override(
            record,
            {
                "batting_style": "Left Handed Bat",
                "bowling_style": "Right-arm offbreak",
                "role": "WK-Batsman",
                "notes": "Confirmed manually",
            },
        )

        assert updated["batting"]["hand"] == "LHB"
        assert updated["bowling"]["type"] == "Spin"
        assert updated["bowling"]["subtype"] == "Right Arm Off Spin"
        assert updated["role"] == "WK-Batsman"
        assert updated["is_wicketkeeper"] is True
        assert updated["manual_override"]["applied"] is True

    def test_explicit_fields_override_derived_values(self):
        record = _record()
        updated = apply_manual_override(
            record,
            {
                "batting_style": "Right Handed Bat",
                "batting_hand": "LHB",
                "bowling_style": "Right-arm medium",
                "bowling": {
                    "arm": "Left",
                    "type": "Spin",
                    "subtype": "Left Arm Orthodox",
                    "mechanism": "Finger",
                },
                "is_wicketkeeper": False,
            },
        )

        assert updated["batting"]["hand"] == "LHB"
        assert updated["bowling"]["arm"] == "Left"
        assert updated["bowling"]["type"] == "Spin"
        assert updated["is_wicketkeeper"] is False

    def test_default_placeholder_batting_is_not_actionable_override(self):
        record = _record()
        updated = apply_manual_override(
            record,
            {
                "batting_style": "RHB",
                "batting_hand": "Right",
            },
        )

        assert updated["batting"]["hand"] is None
        assert "manual_override" not in updated

    def test_clears_stale_default_placeholder_output(self):
        record = {
            **_record(),
            "batting": {"hand": "Right"},
            "raw": {"batting_style": "RHB", "bowling_style": None, "role": None},
            "manual_override": {"applied": True, "source": "manual", "notes": None},
        }

        updated = apply_manual_override(
            record,
            {
                "batting_style": "RHB",
                "batting_hand": "Right",
            },
        )

        assert updated["batting"]["hand"] is None
        assert updated["raw"]["batting_style"] is None
        assert "manual_override" not in updated

    def test_preserves_manual_override_enriched_flag(self):
        record = _record()
        updated = apply_manual_override(
            record,
            {
                "batting_style": "LHB",
                "enriched": True,
            },
        )

        assert updated["manual_override"]["applied"] is True
        assert updated["manual_override"]["enriched"] is True


class TestOverrideFileHelpers:
    def test_load_manual_overrides_reads_players_block(self, tmp_path):
        path = tmp_path / "manual_overrides.json"
        path.write_text(json.dumps({"players": {"abc": {"role": "Bowler"}}}), encoding="utf-8")
        enriched_path = tmp_path / "manual_overrides_enriched.json"
        enriched_path.write_text(json.dumps({"players": {"old": {"role": "Keeper"}}}), encoding="utf-8")

        overrides = load_manual_overrides(path, enriched_path)

        assert overrides == {"old": {"role": "Keeper"}, "abc": {"role": "Bowler"}}

    def test_sync_moves_enriched_true_entries_to_separate_file(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        enriched_path = tmp_path / "manual_overrides_enriched.json"
        path.write_text(
            json.dumps(
                {
                    "players": {
                        "player-1": {
                            "name": "Done Player",
                            "teams": ["Spain"],
                            "batting_style": "RHB",
                            "batting_hand": "RHB",
                            "bowling_style": "Right-arm medium",
                            "bowling": {
                                "arm": "Right",
                                "type": "Pace",
                                "subtype": "Fast Medium",
                                "mechanism": "Seam",
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "123", "cricbuzz": None},
                            "source_url": None,
                            "source": "manual",
                            "enriched": True,
                            "notes": None,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {"unfound_players": {}, "ignored_players": {}},
        )

        sync_manual_override_placeholders({"players": {}}, path, enriched_path)

        active_payload = json.loads(path.read_text(encoding="utf-8"))
        enriched_payload = json.loads(enriched_path.read_text(encoding="utf-8"))
        assert "player-1" not in active_payload["players"]
        assert enriched_payload["players"]["player-1"]["enriched"] is True

    def test_sync_moves_ignored_entries_to_separate_file(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        enriched_path = tmp_path / "manual_overrides_enriched.json"
        ignored_path = tmp_path / "manual_overrides_ignored.json"
        path.write_text(
            json.dumps(
                {
                    "players": {
                        "ignored-1": {
                            "name": "Ignored Player",
                            "teams": ["Spain"],
                            "batting_style": None,
                            "batting_hand": None,
                            "bowling_style": None,
                            "bowling": {
                                "arm": None,
                                "type": None,
                                "subtype": None,
                                "mechanism": None,
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "123", "cricbuzz": None},
                            "source_url": "https://www.espncricinfo.com/player/ignored-1",
                            "source": "manual",
                            "enriched": False,
                            "notes": None,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {
                "unfound_players": {},
                "ignored_players": {
                    "Spain": [
                        {
                            "id": "ignored-1",
                            "name": "Ignored Player",
                            "teams": ["Spain"],
                            "ignore_reason": "No T20 appearance",
                            "t20i_matches": 0,
                            "latest_match_date": None,
                        }
                    ]
                },
            },
        )

        sync_manual_override_placeholders({"players": {"ignored-1": _record()}}, path, enriched_path, ignored_path)

        active_payload = json.loads(path.read_text(encoding="utf-8"))
        ignored_payload = json.loads(ignored_path.read_text(encoding="utf-8"))
        assert "ignored-1" not in active_payload["players"]
        assert ignored_payload["players"]["ignored-1"]["ignore_reason"] == "No T20 appearance"

    def test_sync_manual_override_placeholders_seeds_missing_players(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        output = {
            "players": {
                "missing-1": _record(),
                "enriched-1": {
                    **_record(),
                    "batting": {"hand": "RHB"},
                },
            }
        }

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {
                "unfound_players": {"Spain": [{"id": "missing-1"}]},
                "ignored_players": {},
            },
        )

        sync_manual_override_placeholders(output, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "missing-1" in payload["players"]
        assert "enriched-1" not in payload["players"]
        assert payload["players"]["missing-1"]["batting_style"] == "RHB"
        assert payload["players"]["missing-1"]["batting_hand"] == "Right"
        assert payload["players"]["missing-1"]["enriched"] is False


class TestDashboardPayloadManualOverrides:
    def test_manual_override_players_are_not_missing(self, monkeypatch):
        output = {
            "teams": {"Spain": {"player_ids": ["p1"]}},
            "players": {
                "p1": {
                    "identifier": "p1",
                    "name": "Override Player",
                    "teams": ["Spain"],
                    "external_ids": {"espn": "123", "cricbuzz": None},
                    "batting": {"hand": None},
                    "bowling": {"arm": None, "type": None, "subtype": None, "mechanism": None},
                    "role": None,
                    "is_wicketkeeper": None,
                    "raw": {"batting_style": None, "bowling_style": None, "role": None},
                    "source": "registry",
                    "manual_override": {"applied": True, "enriched": False, "notes": "manual"},
                }
            },
        }

        monkeypatch.setattr(manual_overrides, "build_dashboard_payload", build_dashboard_payload)
        monkeypatch.setattr(
            "dashboard_payload.load_t20i_player_team_counts",
            lambda: {},
        )
        monkeypatch.setattr(
            "dashboard_payload.load_player_latest_match_dates",
            lambda: {},
        )

        payload = build_dashboard_payload(output)

        assert len(payload["players"]) == 1
        assert payload["players"][0]["id"] == "p1"
        assert payload["unfound_players"] == {}

    def test_payload_no_validation_needed_bucket(self, monkeypatch):
        output = {
            "teams": {},
            "players": {},
        }

        monkeypatch.setattr(
            "dashboard_payload.load_t20i_player_team_counts",
            lambda: {},
        )
        monkeypatch.setattr(
            "dashboard_payload.load_player_latest_match_dates",
            lambda: {},
        )

        payload = build_dashboard_payload(output)
        assert "validation_needed" not in payload

    def test_sync_manual_override_placeholders_excludes_registry_enriched_players(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        registry_enriched_path = tmp_path / "registry_enriched.json"

        path.write_text(
            json.dumps(
                {
                    "players": {
                        "missing-1": {
                            "name": "Missing Player",
                            "teams": ["Spain"],
                            "batting_style": "RHB",
                            "batting_hand": "Right",
                            "bowling_style": None,
                            "bowling": {
                                "arm": None,
                                "type": None,
                                "subtype": None,
                                "mechanism": None,
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "111", "cricbuzz": None},
                            "source_url": None,
                            "source": "manual",
                            "enriched": False,
                            "notes": None,
                        },
                        "enriched-1": {
                            "name": "Already Enriched",
                            "teams": ["Spain"],
                            "batting_style": "RHB",
                            "batting_hand": "Right",
                            "bowling_style": None,
                            "bowling": {
                                "arm": None,
                                "type": None,
                                "subtype": None,
                                "mechanism": None,
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "222", "cricbuzz": None},
                            "source_url": None,
                            "source": "manual",
                            "enriched": False,
                            "notes": None,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )

        registry_enriched_path.write_text(
            json.dumps(
                {
                    "players": {
                        "enriched-1": {"enriched": True},
                        "missing-1": {"enriched": False},
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {
                "unfound_players": {"Spain": [{"id": "missing-1"}, {"id": "enriched-1"}]},
                "ignored_players": {},
            },
        )

        sync_manual_override_placeholders(
            {"players": {"missing-1": _record(), "enriched-1": _record()}},
            path,
            registry_enriched_path=registry_enriched_path,
        )

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "missing-1" in payload["players"]
        assert "enriched-1" not in payload["players"]

    def test_sync_manual_override_placeholders_backfills_null_batting_defaults(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        path.write_text(
            json.dumps(
                {
                    "players": {
                        "missing-1": {
                            "name": "Sample Player",
                            "teams": ["Spain"],
                            "batting_style": None,
                            "batting_hand": None,
                            "bowling_style": None,
                            "bowling": {
                                "arm": None,
                                "type": None,
                                "subtype": None,
                                "mechanism": None,
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "123", "cricbuzz": None},
                            "source_url": None,
                            "source": "manual",
                            "notes": None,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        output = {"players": {"missing-1": _record()}}

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {
                "unfound_players": {"Spain": [{"id": "missing-1"}]},
                "ignored_players": {},
            },
        )

        sync_manual_override_placeholders(output, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["players"]["missing-1"]["batting_style"] == "RHB"
        assert payload["players"]["missing-1"]["batting_hand"] == "Right"
        assert payload["players"]["missing-1"]["enriched"] is False

    def test_sync_manual_override_placeholders_backfills_enriched_flag(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        path.write_text(
            json.dumps(
                {
                    "players": {
                        "missing-1": {
                            "name": "Sample Player",
                            "teams": ["Spain"],
                            "batting_style": None,
                            "batting_hand": None,
                            "bowling_style": None,
                            "bowling": {
                                "arm": None,
                                "type": None,
                                "subtype": None,
                                "mechanism": None,
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "123", "cricbuzz": None},
                            "source_url": None,
                            "source": "manual",
                            "notes": None,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {
                "unfound_players": {"Spain": [{"id": "missing-1"}]},
                "ignored_players": {},
            },
        )

        sync_manual_override_placeholders({"players": {"missing-1": _record()}}, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["players"]["missing-1"]["enriched"] is False

    def test_sync_manual_override_placeholders_clears_defaults_for_ignored_placeholders(self, tmp_path, monkeypatch):
        path = tmp_path / "manual_overrides.json"
        ignored_path = tmp_path / "manual_overrides_ignored.json"
        path.write_text(
            json.dumps(
                {
                    "players": {
                        "ignored-1": {
                            "name": "Ignored Player",
                            "teams": ["Spain"],
                            "batting_style": "RHB",
                            "batting_hand": "Right",
                            "bowling_style": None,
                            "bowling": {
                                "arm": None,
                                "type": None,
                                "subtype": None,
                                "mechanism": None,
                            },
                            "role": None,
                            "is_wicketkeeper": None,
                            "external_ids": {"espn": "123", "cricbuzz": None},
                            "source_url": None,
                            "source": "manual",
                            "notes": None,
                        }
                    }
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr(
            manual_overrides,
            "build_dashboard_payload",
            lambda _output: {
                "unfound_players": {},
                "ignored_players": {"Spain": [{"id": "ignored-1"}]},
            },
        )

        sync_manual_override_placeholders({"players": {}}, path, ignored_path=ignored_path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        ignored_payload = json.loads(ignored_path.read_text(encoding="utf-8"))
        assert "ignored-1" not in payload["players"]
        assert ignored_payload["players"]["ignored-1"]["ignore_reason"] is None


class TestApplyManualOverridesToOutput:
    def test_updates_only_matching_players(self):
        output = {
            "players": {
                "player-1": _record(),
                "player-2": _record(),
            }
        }

        updated = apply_manual_overrides_to_output(
            output,
            {"player-1": {"role": "WK-Batsman"}, "missing": {"role": "Bowler"}},
        )

        assert updated["players"]["player-1"]["role"] == "WK-Batsman"
        assert updated["players"]["player-1"]["is_wicketkeeper"] is True
        assert updated["players"]["player-2"]["role"] is None


class TestDashboardPayloadManualOverrideResolution:
    def test_resolved_manual_overrides_are_in_enriched_only(self):
        output = {
            "players": {
                "player-1": {
                    **_record(),
                    "batting": {"hand": "RHB"},
                    "manual_override": {
                        "applied": True,
                        "enriched": True,
                        "source": "manual",
                        "notes": None,
                    },
                }
            },
            "teams": {"Spain": {"player_ids": ["player-1"]}},
        }

        payload = build_dashboard_payload(output)

        assert "validation_needed" not in payload
        assert payload["unfound_players"] == {}
        assert payload["players"][0]["manual_override"] is True
        assert payload["players"][0]["manual_override_enriched"] is True
