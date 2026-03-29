"""Quick inspection of empty cache entries and their ESPN IDs."""
import json
from registry_loader import load_registry

players = load_registry()
reg = {p.player_id: p for p in players}
cache = json.load(open("data/cache/profiles_raw.json"))

empty = {k: v for k, v in cache.items() if not any(v.get(f) for f in ("batting_style", "bowling_style", "role"))}

print(f"Total cached: {len(cache)}")
print(f"With data: {len(cache) - len(empty)}")
print(f"Empty: {len(empty)}")
print()

no_espn = 0
has_espn = 0
has_cricbuzz = 0
for pid in empty:
    p = reg.get(pid)
    if not p:
        continue
    if p.espn_id:
        has_espn += 1
    else:
        no_espn += 1
    if p.cricbuzz_id:
        has_cricbuzz += 1

print(f"Empty with ESPN ID: {has_espn}")
print(f"Empty without ESPN ID: {no_espn}")
print(f"Empty with Cricbuzz ID: {has_cricbuzz}")
print()

# Show all empty entries with ESPN IDs
print("--- Empty entries with ESPN ID (could retry Site API) ---")
espn_empties = []
for pid in sorted(empty.keys()):
    p = reg.get(pid)
    if p and p.espn_id:
        espn_empties.append((pid, p.player_name, p.espn_id, p.cricbuzz_id))
        print(f"  {p.player_name:30s}  espn={p.espn_id:10s}  cb={p.cricbuzz_id or '-':10s}  id={pid}")

print()
print(f"Total with ESPN to retry: {len(espn_empties)}")

# Check: for the first 3, what does the Site API URL look like?
print()
print("--- Sample Site API URLs ---")
for _, name, espn_id, _ in espn_empties[:5]:
    print(f"  https://site.api.espn.com/apis/common/v3/sports/cricket/athletes/{espn_id}")

# Also show entries with NO ESPN ID at all
print()
print("--- Empty entries without ESPN ID ---")
for pid in sorted(empty.keys()):
    p = reg.get(pid)
    if p and not p.espn_id:
        print(f"  {p.player_name:30s}  cb={p.cricbuzz_id or '-':10s}  id={pid}")
