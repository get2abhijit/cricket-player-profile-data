from __future__ import annotations

import json

import pipeline
from registry_loader import PlayerRecord


class _FakeScraper:
    def fetch_profile(self, **kwargs):
        raise AssertionError("fetch_profile should not be called when cache exists in --no-fetch mode")

    @staticmethod
    def profile_url(espn_id: str, player_name: str | None = None) -> str:
        return f"https://example.test/player/{espn_id}"


def test_no_fetch_uses_cached_profiles(tmp_path, monkeypatch):
    cache_path = tmp_path / "profiles_raw.json"
    output_path = tmp_path / "player_profiles.json"
    dashboard_path = tmp_path / "dashboard_data.json"

    cache_path.write_text(
        json.dumps(
            {
                "player-1": {
                    "batting_style": "Right Handed Bat",
                    "bowling_style": "Right-arm offbreak",
                    "role": "WK-Batsman",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(pipeline, "CACHE_PATH", cache_path)
    monkeypatch.setattr(pipeline, "OUTPUT_PATH", output_path)
    monkeypatch.setattr(pipeline, "DASHBOARD_DATA_PATH", dashboard_path)
    monkeypatch.setattr(pipeline, "EspnScraper", _FakeScraper)
    monkeypatch.setattr(
        pipeline,
        "load_registry",
        lambda: [
            PlayerRecord(
                player_id="player-1",
                player_name="Sample Player",
                espn_id="123",
                cricbuzz_id=None,
                aliases=[],
            )
        ],
    )
    monkeypatch.setattr(
        pipeline,
        "load_teams_from_matches",
        lambda *args, **kwargs: ({"Spain": {"player-1"}}, {"player-1": "Sample Player"}),
    )
    monkeypatch.setattr(
        pipeline,
        "load_match_timestamps_from_readme",
        lambda *args, **kwargs: {"m1": "2025-01-01"},
    )
    monkeypatch.setattr(pipeline, "load_state", lambda: {})
    monkeypatch.setattr(pipeline, "save_state", lambda state: None)
    monkeypatch.setattr(pipeline, "generate_dashboard", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "build_dashboard_payload", lambda output: {"teams": [], "players": []})
    monkeypatch.setattr(pipeline, "load_manual_overrides", lambda: {})
    monkeypatch.setattr(pipeline, "sync_manual_override_placeholders", lambda output: None)

    output = pipeline.run_pipeline(no_fetch=True, cleanup=False)

    player = output["players"]["player-1"]
    assert player["batting"]["hand"] == "RHB"
    assert player["bowling"]["type"] == "Spin"
    assert player["role"] == "WK-Batsman"
    assert player["is_wicketkeeper"] is True