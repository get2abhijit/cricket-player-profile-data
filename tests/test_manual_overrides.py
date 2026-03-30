from __future__ import annotations

import json

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


class TestOverrideFileHelpers:
    def test_load_manual_overrides_reads_players_block(self, tmp_path):
        path = tmp_path / "manual_overrides.json"
        path.write_text(json.dumps({"players": {"abc": {"role": "Bowler"}}}), encoding="utf-8")

        overrides = load_manual_overrides(path)

        assert overrides == {"abc": {"role": "Bowler"}}

    def test_sync_manual_override_placeholders_seeds_missing_players(self, tmp_path):
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

        sync_manual_override_placeholders(output, path)

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert "missing-1" in payload["players"]
        assert "enriched-1" not in payload["players"]


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
