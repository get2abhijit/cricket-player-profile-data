"""
tests/test_normalizer.py
------------------------
Unit tests for normalizer.py — batting hand normalisation and bowling style
classification.
"""

import pytest

from normalizer import normalize_batting_hand, classify_bowling_style


# ────────────────────────────────────────────────────────────────────────────
# normalize_batting_hand
# ────────────────────────────────────────────────────────────────────────────

class TestNormalizeBattingHand:
    def test_right_hand_bat(self):
        assert normalize_batting_hand("Right-hand bat") == "RHB"

    def test_right_handed_bat_cricbuzz(self):
        assert normalize_batting_hand("Right Handed Bat") == "RHB"

    def test_left_hand_bat(self):
        assert normalize_batting_hand("Left-hand bat") == "LHB"

    def test_left_handed_bat_cricbuzz(self):
        assert normalize_batting_hand("Left Handed Bat") == "LHB"

    def test_case_insensitive(self):
        assert normalize_batting_hand("RIGHT HAND BAT") == "RHB"
        assert normalize_batting_hand("left hand bat")  == "LHB"

    def test_none_returns_none(self):
        assert normalize_batting_hand(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_batting_hand("") is None
        assert normalize_batting_hand("  ") is None

    def test_ambiguous_returns_none(self):
        assert normalize_batting_hand("Unknown") is None


# ────────────────────────────────────────────────────────────────────────────
# classify_bowling_style — arm, type, subtype, mechanism
# ────────────────────────────────────────────────────────────────────────────

class TestClassifyBowlingStyle:
    # ── Pace variants ──────────────────────────────────────────────────────

    def test_fast(self):
        r = classify_bowling_style("Right-arm fast")
        assert r["type"]      == "Pace"
        assert r["subtype"]   == "Seam"
        assert r["arm"]       == "Right"
        assert r["mechanism"] == "None"

    def test_medium(self):
        r = classify_bowling_style("Left-arm medium")
        assert r["type"]    == "Pace"
        assert r["subtype"] == "Seam"
        assert r["arm"]     == "Left"

    def test_seam(self):
        r = classify_bowling_style("Right-arm medium seam")
        assert r["type"]    == "Pace"
        assert r["subtype"] == "Seam"

    # ── Spin variants ──────────────────────────────────────────────────────

    def test_off_break(self):
        r = classify_bowling_style("Right-arm offbreak")
        assert r["type"]      == "Spin"
        assert r["subtype"]   == "Right Arm Off Spin"
        assert r["arm"]       == "Right"
        assert r["mechanism"] == "Finger"

    def test_off_spin(self):
        r = classify_bowling_style("Off spin")
        assert r["type"]    == "Spin"
        assert r["subtype"] == "Right Arm Off Spin"

    def test_leg_break(self):
        r = classify_bowling_style("Right-arm legbreak")
        assert r["type"]      == "Spin"
        assert r["subtype"]   == "Right Arm Leg Spin"
        assert r["arm"]       == "Right"
        assert r["mechanism"] == "Wrist"

    def test_leg_spin(self):
        r = classify_bowling_style("Leg spin")
        assert r["type"]    == "Spin"
        assert r["subtype"] == "Right Arm Leg Spin"

    def test_left_arm_orthodox(self):
        r = classify_bowling_style("Slow left-arm orthodox")
        assert r["type"]      == "Spin"
        assert r["subtype"]   == "Left Arm Orthodox"
        assert r["arm"]       == "Left"
        assert r["mechanism"] == "Finger"

    def test_chinaman(self):
        r = classify_bowling_style("Left-arm chinaman")
        assert r["type"]      == "Spin"
        assert r["subtype"]   == "Left Arm Chinaman"
        assert r["arm"]       == "Left"
        assert r["mechanism"] == "Wrist"

    def test_left_arm_wrist_spin(self):
        r = classify_bowling_style("Left-arm wrist spin")
        assert r["type"]      == "Spin"
        assert r["subtype"]   == "Left Arm Chinaman"

    # ── Null / edge cases ──────────────────────────────────────────────────

    def test_none(self):
        r = classify_bowling_style(None)
        assert all(v is None for v in r.values())

    def test_empty_string(self):
        r = classify_bowling_style("")
        assert all(v is None for v in r.values())

    def test_unknown_style(self):
        r = classify_bowling_style("Unknown style")
        assert r["type"] is None

    # ── Real-world ESPN/Cricbuzz strings ────────────────────────────────────

    @pytest.mark.parametrize("raw,expected_type,expected_subtype", [
        ("Right-arm fast", "Pace", "Seam"),
        ("Right-arm fast-medium", "Pace", "Seam"),
        ("Right-arm medium-fast", "Pace", "Seam"),
        ("Right-arm medium", "Pace", "Seam"),
        ("Left-arm medium-fast", "Pace", "Seam"),
        ("Right-arm offbreak", "Spin", "Right Arm Off Spin"),
        ("Off break", "Spin", "Right Arm Off Spin"),
        ("Right-arm legbreak", "Spin", "Right Arm Leg Spin"),
        ("Leg break", "Spin", "Right Arm Leg Spin"),
        ("Slow left-arm orthodox", "Spin", "Left Arm Orthodox"),
        ("Left-arm orthodox", "Spin", "Left Arm Orthodox"),
        ("Left-arm Chinaman", "Spin", "Left Arm Chinaman"),
    ])
    def test_parametrized_real_world(self, raw, expected_type, expected_subtype):
        r = classify_bowling_style(raw)
        assert r["type"]    == expected_type,    f"type mismatch for {raw!r}"
        assert r["subtype"] == expected_subtype, f"subtype mismatch for {raw!r}"

    def test_returns_dict_with_all_keys(self):
        r = classify_bowling_style("Right-arm fast")
        assert set(r.keys()) == {"arm", "type", "subtype", "mechanism"}
