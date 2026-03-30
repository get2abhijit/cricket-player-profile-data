"""
Apply Cricbuzz profile data to missing players in player_profiles.json.
Found via brute-force DuckDuckGo search for each player name on Cricbuzz.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from dashboard_payload import build_dashboard_payload
from generate_dashboard import generate_dashboard
from normalizer import normalize_batting_hand, classify_bowling_style

# Cricbuzz profile data extracted from profile pages
# Key: (registry_name_substring, team) -> profile data
CRICBUZZ_PROFILES = [
    {
        "match": {"name": "Fanyan Mughal", "team": "Malta"},
        "cricbuzz_id": "43349",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "WK-Batsman",
    },
    {
        "match": {"name": "Abdul Majid Abbasi", "team": "Bahrain"},
        "cricbuzz_id": "41725",
        "batting_style": "Left Handed Bat",
        "bowling_style": "Left-arm orthodox",
        "role": "Bowler",
    },
    {
        "match": {"name": "Svilicic", "team": "Croatia"},
        "cricbuzz_id": "1466309",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Bowler",
    },
    {
        "match": {"name": "AA Senn", "team": "Cyprus"},
        "cricbuzz_id": "1460871",
        "batting_style": "Right Handed Bat",
        "bowling_style": "Right-arm offbreak",
        "role": "Batting Allrounder",
    },
    {
        "match": {"name": "Kyriacou", "team": "Cyprus"},
        "cricbuzz_id": "1424804",
        "batting_style": "Left Handed Bat",
        "bowling_style": None,
        "role": None,
    },
    {
        "match": {"name": "Kristensen", "team": "Denmark"},
        "cricbuzz_id": "44399",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Batsman",
    },
    {
        "match": {"name": "Sumit Singh", "team": "Finland"},
        "cricbuzz_id": "44469",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Batsman",
    },
    {
        "match": {"name": "Amith Sarma", "team": "Germany"},
        "cricbuzz_id": "14834",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Batsman",
    },
    {
        "match": {"name": "Orfila", "team": "Gibraltar"},
        "cricbuzz_id": "15680",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Bowler",
    },
    {
        "match": {"name": "Collado", "team": "Gibraltar"},
        "cricbuzz_id": "15679",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "WK-Batsman",
    },
    {
        "match": {"name": "Manousis", "team": "Greece"},
        "cricbuzz_id": "28353",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "WK-Batsman",
    },
    {
        "match": {"name": "Bogdos", "team": "Greece"},
        "cricbuzz_id": "28327",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "WK-Batsman",
    },
    {
        "match": {"name": "Gasteratos", "team": "Greece"},
        "cricbuzz_id": "1427702",
        "batting_style": "Left Handed Bat",
        "bowling_style": None,
        "role": None,
    },
    {
        "match": {"name": "Kahamker", "team": "Israel"},
        "cricbuzz_id": "27732",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Batsman",
    },
    {
        "match": {"name": "Ali Naqi", "team": "Portugal"},
        "cricbuzz_id": "15695",
        "batting_style": "Right Handed Bat",
        "bowling_style": "Right-arm medium",
        "role": "Bowler",
    },
    {
        "match": {"name": "Fakhrul Mohon", "team": "Portugal"},
        "cricbuzz_id": "27669",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Batsman",
    },
    {
        "match": {"name": "Imran Khan", "team": "Portugal"},
        "cricbuzz_id": "15690",
        "batting_style": "Left Handed Bat",
        "bowling_style": "Right-arm fast-medium",
        "role": "Bowling Allrounder",
    },
    {
        "match": {"name": "Najjam Shahzad", "team": "Portugal"},
        "cricbuzz_id": "15686",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Batsman",
    },
    {
        "match": {"name": "Dharmendra Manani", "team": "Romania"},
        "cricbuzz_id": "48235",
        "batting_style": "Right Handed Bat",
        "bowling_style": "Right-arm fast-medium",
        "role": "Batsman",
    },
    {
        "match": {"name": "Ravinder Gill", "team": "Romania"},
        "cricbuzz_id": "1461869",
        "batting_style": "Right Handed Bat",
        "bowling_style": "Right-arm fast-medium",
        "role": "Batting Allrounder",
    },
    {
        "match": {"name": "Azam Khalil", "team": "Sweden"},
        "cricbuzz_id": "26395",
        "batting_style": "Right Handed Bat",
        "bowling_style": "Right-arm medium",
        "role": "Bowler",
    },
    {
        "match": {"name": "Shahzeb Choudhry", "team": "Sweden"},
        "cricbuzz_id": "44515",
        "batting_style": "Right Handed Bat",
        "bowling_style": None,
        "role": "Bowler",
    },
    {
        "match": {"name": "Rahel Khan", "team": "Sweden"},
        "cricbuzz_id": "1425821",
        "batting_style": "Left Handed Bat",
        "bowling_style": None,
        "role": None,
    },
]


def find_player(players, match_name, match_team):
    """Find a player in the profiles dict by name substring and team."""
    candidates = []
    for pid, p in players.items():
        name = p.get("name", "")
        teams = p.get("teams", [])
        if match_name.lower() in name.lower() and match_team in teams:
            # Also check that batting/bowling are not already enriched
            bat = p.get("batting", {}).get("hand")
            bowl = p.get("bowling", {}).get("type")
            if not bat and not bowl:
                candidates.append((pid, p))
    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        # Try exact match
        for pid, p in candidates:
            if p.get("name", "").lower() == match_name.lower():
                return (pid, p)
        print(f"  WARNING: Multiple matches for {match_name} ({match_team}): {[c[1]['name'] for c in candidates]}")
        return candidates[0]  # Take first
    return None


def main():
    with open("output/player_profiles.json") as f:
        data = json.load(f)

    players = data["players"]
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    failed = 0

    for profile in CRICBUZZ_PROFILES:
        match_name = profile["match"]["name"]
        match_team = profile["match"]["team"]

        result = find_player(players, match_name, match_team)
        if not result:
            print(f"  SKIP: Could not find {match_name} ({match_team}) in profiles")
            failed += 1
            continue

        pid, player = result

        # Normalize batting
        bat_hand = normalize_batting_hand(profile["batting_style"])
        # Normalize bowling
        bowl = classify_bowling_style(profile["bowling_style"])

        # Update player
        player["batting"]["hand"] = bat_hand
        if bowl["type"]:
            player["bowling"] = bowl
        player["role"] = profile["role"]
        player["raw"] = {
            "batting_style": profile["batting_style"],
            "bowling_style": profile["bowling_style"],
        }
        player["external_ids"]["cricbuzz"] = profile["cricbuzz_id"]
        player["source"] = f"https://www.cricbuzz.com/profiles/{profile['cricbuzz_id']}"
        player["last_updated"] = now

        print(f"  OK: {player['name']} ({match_team}) -> CB {profile['cricbuzz_id']}, bat={bat_hand}, bowl={bowl.get('type')}")
        updated += 1

    # Update meta
    data["meta"]["last_updated"] = now

    with open("output/player_profiles.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    dashboard_payload = build_dashboard_payload(data)
    dashboard_data_path = Path("output/dashboard_data.json")
    with dashboard_data_path.open("w", encoding="utf-8") as f:
        json.dump(dashboard_payload, f, indent=2, ensure_ascii=False)

    generate_dashboard()

    print(f"\nDone: {updated} updated, {failed} failed")
    print("Dashboard artifacts refreshed: output/dashboard_data.json, output/dashboard.html")


if __name__ == "__main__":
    main()
