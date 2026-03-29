import json

# Check output
d = json.load(open('output/player_profiles.json'))
p = list(d['players'].values())[0]
print('Sample player:')
print(f"  Name: {p['name']}")
print(f"  Source: {p['source']}")
print(f"  Batting: {p['batting']}")
print(f"  Bowling type: {p['bowling'].get('type')}")

# Check dashboard data
dd = json.load(open('output/dashboard_data.json'))
print(f"\nDashboard data keys: {list(dd.keys())}")
print(f"Enriched players: {len(dd['players'])}")
print(f"Unfound players: {len(dd.get('unfound_players', {}))}")
if dd.get('unfound_players'):
    for team, players in list(dd['unfound_players'].items())[:2]:
        print(f"  {team}: {len(players)} unfound")
