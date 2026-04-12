from __future__ import annotations

import json
from datetime import date

import pipeline
from match_loader import load_match_timestamps_from_readme, load_teams_from_matches
from registry_loader import PlayerRecord


def _write_match(path, match_date: str, players: dict, registry: dict, match_type: str = "T20"):
    payload = {
        "info": {
            "dates": [match_date],
            "match_type": match_type,
            "players": players,
            "registry": {"people": registry},
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_match_filtering_excludes_pre_2021(tmp_path):
    _write_match(
        tmp_path / "old.json",
        "2020-12-31",
        {"TeamA": ["Old Player"]},
        {"Old Player": "old-id"},
    )
    _write_match(
        tmp_path / "new.json",
        "2021-01-01",
        {"TeamA": ["New Player"]},
        {"New Player": "new-id"},
    )

    teams, id_names = load_teams_from_matches(tmp_path, min_date=date(2021, 1, 1))

    assert "new-id" in teams["TeamA"]
    assert "old-id" not in teams["TeamA"]
    assert id_names["new-id"] == "New Player"


def test_readme_timestamp_filtering_uses_cutoff_and_t20_only(tmp_path):
    readme = tmp_path / "README.txt"
    readme.write_text(
        "\n".join(
            [
                "2020-12-31 - international - T20 - male - 100 - A vs B",
                "2021-01-01 - international - T20 - male - 101 - A vs B",
                "2024-01-01 - international - ODI - male - 102 - A vs B",
            ]
        ),
        encoding="utf-8",
    )

    timestamps = load_match_timestamps_from_readme(tmp_path, min_date=date(2021, 1, 1))

    assert timestamps == {"101": "2021-01-01"}


def test_pipeline_player_eligibility_and_manual_override_precedence(tmp_path, monkeypatch):
    cache_path = tmp_path / "profiles_raw.json"
    output_path = tmp_path / "player_profiles.json"
    dashboard_path = tmp_path / "dashboard_data.json"

    cache_path.write_text(
        json.dumps(
            {
                "p1": {
                    "batting_style": "Right Handed Bat",
                    "bowling_style": "Right-arm medium",
                    "role": "Allrounder",
                },
                "p2": {
                    "batting_style": "Left Handed Bat",
                    "bowling_style": "Left-arm orthodox",
                    "role": "Bowler",
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pipeline, "OUTPUT_PATH", output_path)
    monkeypatch.setattr(pipeline, "DASHBOARD_DATA_PATH", dashboard_path)
    monkeypatch.setattr(
        pipeline,
        "load_registry",
        lambda: [
            PlayerRecord("p1", "Player One", "1", None, ["P One"]),
            PlayerRecord("p2", "Player Two", "2", None, ["P Two"]),
            PlayerRecord("p3", "Player Three", "3", None, ["P Three"]),
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "load_match_timestamps_from_readme",
        lambda *args, **kwargs: {"m1": "2024-05-01"},
    )
    monkeypatch.setattr(
        pipeline,
        "load_teams_from_matches",
        lambda *args, **kwargs: (
            {"TeamX": {"p1", "p2"}},
            {"p1": "Player One", "p2": "Player Two"},
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "load_manual_overrides",
        lambda: {"p1": {"role": "WK-Batsman", "notes": "manual value"}},
    )
    monkeypatch.setattr(pipeline, "load_state", lambda: {})
    monkeypatch.setattr(pipeline, "save_state", lambda state: None)
    monkeypatch.setattr(pipeline, "generate_dashboard", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "build_dashboard_payload", lambda output: {"teams": [], "players": []})
    monkeypatch.setattr(pipeline, "sync_manual_override_placeholders", lambda output: None)

    output = pipeline.run_pipeline(no_fetch=True, cleanup=False)

    assert set(output["players"].keys()) == {"p1", "p2"}
    assert output["players"]["p1"]["role"] == "WK-Batsman"
    assert output["players"]["p1"]["manual_override"]["applied"] is True

    for player_id, record in output["players"].items():
        assert player_id
        assert record["name"]
        assert record["teams"]


def test_pipeline_idempotent_same_inputs(tmp_path, monkeypatch):
    cache_path = tmp_path / "profiles_raw.json"
    output_path = tmp_path / "player_profiles.json"
    dashboard_path = tmp_path / "dashboard_data.json"

    cache_path.write_text(
        json.dumps(
            {
                "p1": {
                    "batting_style": "Right Handed Bat",
                    "bowling_style": "Right-arm medium",
                    "role": "Batter",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pipeline, "OUTPUT_PATH", output_path)
    monkeypatch.setattr(pipeline, "DASHBOARD_DATA_PATH", dashboard_path)
    monkeypatch.setattr(
        pipeline,
        "load_registry",
        lambda: [PlayerRecord("p1", "Player One", "1", None, ["P One", "Player One"])],
    )
    monkeypatch.setattr(
        pipeline,
        "load_match_timestamps_from_readme",
        lambda *args, **kwargs: {"m1": "2024-05-01"},
    )
    monkeypatch.setattr(
        pipeline,
        "load_teams_from_matches",
        lambda *args, **kwargs: ({"TeamX": {"p1"}}, {"p1": "Player One"}),
    )
    monkeypatch.setattr(pipeline, "load_manual_overrides", lambda: {})
    monkeypatch.setattr(pipeline, "load_state", lambda: {})
    monkeypatch.setattr(pipeline, "save_state", lambda state: None)
    monkeypatch.setattr(pipeline, "generate_dashboard", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "build_dashboard_payload", lambda output: {"teams": [], "players": []})
    monkeypatch.setattr(pipeline, "sync_manual_override_placeholders", lambda output: None)

    first = pipeline.run_pipeline(no_fetch=True, cleanup=False)
    second = pipeline.run_pipeline(no_fetch=True, cleanup=False)

    assert first == second


def test_incremental_update_detection_uses_readme_timestamps():
    state = {
        "__match_state__": {
            "timestamps": {
                "100": "2024-01-01",
                "101": "2024-01-02",
            }
        }
    }
    incoming = {
        "100": "2024-01-01",
        "101": "2024-01-03",
        "102": "2024-01-04",
    }

    matches = pipeline._compute_matches_to_process(incoming, state, incremental=True)

    assert matches == {"101", "102"}


def test_cleanup_preserves_cache_and_state_for_no_fetch_runs(tmp_path, monkeypatch):
    cache_path = tmp_path / "profiles_raw.json"
    output_path = tmp_path / "player_profiles.json"
    dashboard_path = tmp_path / "dashboard_data.json"
    state_path = tmp_path / "enrichment_state.json"

    cache_path.write_text(
        json.dumps(
            {
                "p1": {
                    "batting_style": "Right Handed Bat",
                    "bowling_style": "Right-arm medium",
                    "role": "Batter",
                }
            }
        ),
        encoding="utf-8",
    )
    state_path.write_text(json.dumps({"p1": {"has_data": True}}), encoding="utf-8")

    monkeypatch.setattr(pipeline, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pipeline, "OUTPUT_PATH", output_path)
    monkeypatch.setattr(pipeline, "DASHBOARD_DATA_PATH", dashboard_path)
    monkeypatch.setattr(pipeline, "ENRICHMENT_STATE_PATH", state_path)
    monkeypatch.setattr(
        pipeline,
        "_CLEANUP_PATHS",
        (
            output_path,
            dashboard_path,
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "load_registry",
        lambda: [PlayerRecord("p1", "Player One", "1", None, ["P One"])],
    )
    monkeypatch.setattr(
        pipeline,
        "load_match_timestamps_from_readme",
        lambda *args, **kwargs: {"m1": "2024-05-01"},
    )
    monkeypatch.setattr(
        pipeline,
        "load_teams_from_matches",
        lambda *args, **kwargs: ({"TeamX": {"p1"}}, {"p1": "Player One"}),
    )
    monkeypatch.setattr(pipeline, "load_state", lambda: {"p1": {"has_data": True}})
    monkeypatch.setattr(pipeline, "save_state", lambda state: None)
    monkeypatch.setattr(pipeline, "load_manual_overrides", lambda: {})
    monkeypatch.setattr(pipeline, "generate_dashboard", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "build_dashboard_payload", lambda output: {"teams": [], "players": []})
    monkeypatch.setattr(pipeline, "sync_manual_override_placeholders", lambda output: None)

    output = pipeline.run_pipeline(no_fetch=True, cleanup=True)

    assert cache_path.exists()
    assert state_path.exists()
    assert output["players"]["p1"]["batting"]["hand"] == "RHB"
