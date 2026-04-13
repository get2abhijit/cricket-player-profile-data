import json
from pathlib import Path
import manual_overrides

out = json.loads(Path('output/player_profiles.json').read_text(encoding='utf-8'))
players = out.get('players', {})
ov = manual_overrides.load_manual_overrides()

def has_non_batting(r, o):
    if o.get('bowling_style'):
        return 'bowling_style'
    if o.get('role'):
        return 'role'
    if o.get('is_wicketkeeper') is not None:
        return 'is_wk'
    if o.get('source_url') and o.get('source_url') != r.get('source'):
        return 'source_diff'
    b = o.get('bowling')
    if isinstance(b, dict) and any(b.get(k) for k in ('arm', 'type', 'subtype', 'mechanism')):
        return 'bowling_obj'
    ext = o.get('external_ids')
    cur = r.get('external_ids') or {}
    if isinstance(ext, dict):
        for k in ('espn', 'cricbuzz'):
            if k in ext and ext.get(k) != cur.get(k):
                return 'ext_' + k
    return None

def is_default(o):
    has_fields = ('batting_style' in o or 'batting_hand' in o)
    if not has_fields:
        return False
    ns = o.get('batting_style') or 'RHB'
    nh = o.get('batting_hand') or 'Right'
    return ns == 'RHB' and nh == 'Right'

causes = {}
sample = None
count = 0
for pid, r in players.items():
    has_skill = bool((r.get('batting') or {}).get('hand') or (r.get('bowling') or {}).get('type'))
    if not ((r.get('manual_override') or {}).get('applied') and not has_skill):
        continue

    o = ov.get(pid, {})
    nb = has_non_batting(r, o)
    actionable = False
    if (o.get('batting_style') or o.get('batting_hand')) and (nb or not is_default(o)):
        actionable = True
    elif nb:
        actionable = True

    key = f"nb={nb}|default={is_default(o)}|bs={o.get('batting_style')}|bh={o.get('batting_hand')}|action={actionable}|in_ov={pid in ov}"
    causes[key] = causes.get(key, 0) + 1
    count += 1
    if sample is None:
        sample = (pid, r.get('source'), o)

print('manual_no_skill', count)
for k, v in sorted(causes.items(), key=lambda x: -x[1])[:10]:
    print(v, k)
print('sample_pid', sample[0])
print('sample_source', sample[1])
print('sample_override', sample[2])
