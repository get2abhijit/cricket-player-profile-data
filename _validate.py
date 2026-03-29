"""Validate pipeline output results."""
import json

# Check output
output = json.load(open("output/player_profiles.json"))
players = output.get("players", {})
teams = output.get("teams", {})
print(f"Total players: {len(players)}")
print(f"Total teams: {len(teams)}")

# Count enriched
enriched = sum(1 for p in players.values() if p.get("batting", {}).get("hand") or p.get("bowling", {}).get("type"))
print(f"Enriched (bat or bowl): {enriched}")
print(f"Missing data: {len(players) - enriched}")

# Sample a few names to verify display name resolution
print("\n--- Sample players (name vs registry_name) ---")
count = 0
for pid, p in players.items():
    name = p.get("name", "?")
    reg_name = p.get("registry_name", "?")
    if name != reg_name:
        print(f"  {reg_name:30s} -> {name}")
        count += 1
        if count >= 10:
            break

# Check source URLs
print("\n--- Source URL patterns ---")
url_patterns = {}
for p in players.values():
    src = p.get("source", "")
    if "espncricinfo.com/cricketers/" in src and "/_/id/" not in src:
        url_patterns["slug_url"] = url_patterns.get("slug_url", 0) + 1
    elif "/_/id/" in src:
        url_patterns["id_only"] = url_patterns.get("id_only", 0) + 1
    elif "site.api.espn.com" in src:
        url_patterns["api_url"] = url_patterns.get("api_url", 0) + 1
    elif "cricbuzz" in src:
        url_patterns["cricbuzz"] = url_patterns.get("cricbuzz", 0) + 1
    elif src == "registry":
        url_patterns["registry"] = url_patterns.get("registry", 0) + 1
    else:
        url_patterns["other"] = url_patterns.get("other", 0) + 1
for p, c in sorted(url_patterns.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# Check dashboard data
dash = json.load(open("output/dashboard_data.json"))
print(f"\nDashboard enriched players: {len(dash.get('players', []))}")
unfound = dash.get("unfound_players", {})
total_unfound = sum(len(v) for v in unfound.values())
print(f"Dashboard unfound players: {total_unfound}")
for team, plist in sorted(unfound.items()):
    print(f"  {team}: {len(plist)} missing")

# Check state
state = json.load(open("data/enrichment_state.json"))
print(f"\nState entries: {len(state)}")
has_data = sum(1 for v in state.values() if v.get("has_data"))
no_data = sum(1 for v in state.values() if not v.get("has_data"))
print(f"State has_data=True: {has_data}")
print(f"State has_data=False: {no_data}")

# Check Gajic specifically
gajic = players.get("a768a762", {})
print(f"\n--- Gajic check ---")
print(f"Name: {gajic.get('name')}")
print(f"Registry name: {gajic.get('registry_name')}")
print(f"Source: {gajic.get('source')}")
print(f"Batting: {gajic.get('batting')}")
print(f"Bowling: {gajic.get('bowling')}")

# Sample a source_url
print("\n--- Sample source URLs ---")
for pid, p in list(players.items())[:5]:
    print(f"  {p.get('name', '?')}: {p.get('source', '?')}")
