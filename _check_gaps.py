import json
d = json.load(open('output/player_profiles.json'))
players = d['players']

# Find players with no bowling data
no_bowl = [(pid, p) for pid, p in players.items() if not (p.get('bowling', {}).get('type'))]
print(f'Players without bowling type: {len(no_bowl)}')
print('First 5:')
for pid, p in no_bowl[:5]:
    espn = p.get('external_ids', {}).get('espn')
    teams = p.get('teams')
    name = p['name']
    print(f"  {name} ({pid}): espn={espn}, teams={teams}")

# Check a player with ESPN data to see URL format
Registry = []
from registry_loader import load_registry, resolve_registry_paths
paths = resolve_registry_paths()
registry_players = load_registry(paths)

# Find an example with no bowl but has ESPN ID
for pid, p in no_bowl[:3]:
    for rp in registry_players:
        if rp.player_id == pid:
            print(f"\nExample: {rp.player_name} (ESPN {rp.espn_id})")
            print(f"  Current source URL: {p.get('source')}")
            break
