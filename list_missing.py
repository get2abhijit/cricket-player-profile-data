import json

data = json.load(open('output/player_profiles.json'))
players = data['players']
missing = []
for pid, p in players.items():
    bat = p.get('batting', {})
    bowl = p.get('bowling', {})
    has_bat = bool(bat.get('hand'))
    has_bowl = bool(bowl.get('type'))
    if not has_bat and not has_bowl:
        teams = p.get('teams', [])
        country = teams[0] if teams else ''
        missing.append({
            'id': pid,
            'name': p.get('name', ''),
            'country': country,
            'espn_id': p.get('external_ids', {}).get('espn', ''),
        })

print(f'Total missing: {len(missing)}')
for m in sorted(missing, key=lambda x: (x['country'], x['name'])):
    print(f"{m['country']:20s} | {m['name']:35s} | espn={m['espn_id']}")
