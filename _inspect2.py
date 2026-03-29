"""Quick: find Gajic, check 503 retries, check source_url formats in cache."""
import json, requests
from registry_loader import load_registry

players = load_registry()
cache = json.load(open("data/cache/profiles_raw.json"))

# Find alister gajic
print("=== Looking for Gajic ===")
for p in players:
    if "gajic" in p.player_name.lower() or p.espn_id == "1323426":
        ck = p.player_id
        print(f"Name: {p.player_name}  ID: {p.player_id}  ESPN: {p.espn_id}  CB: {p.cricbuzz_id}")
        if ck in cache:
            c = cache[ck]
            print(f"  Cache: bat={c.get('batting_style')} bowl={c.get('bowling_style')} role={c.get('role')}")
            print(f"  Source: {c.get('source_url')}")
        else:
            print("  Not in cache")
        print()

# Check current source_url patterns in cache
print("=== Source URL patterns ===")
patterns = {}
for k, v in cache.items():
    url = v.get("source_url", "")
    if "site.api.espn.com" in url:
        patterns["site_api"] = patterns.get("site_api", 0) + 1
    elif "/cricketers/_/id/" in url:
        patterns["id_only"] = patterns.get("id_only", 0) + 1
    elif "/cricketers/" in url:
        patterns["slug"] = patterns.get("slug", 0) + 1
    elif "cricbuzz" in url:
        patterns["cricbuzz"] = patterns.get("cricbuzz", 0) + 1
    else:
        patterns[url[:50] if url else "empty"] = patterns.get(url[:50] if url else "empty", 0) + 1
for p, c in sorted(patterns.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# Check output source field
print()
print("=== Output source field patterns ===")
output = json.load(open("output/player_profiles.json"))
src_patterns = {}
for pid, rec in output.get("players", {}).items():
    src = rec.get("source", "")
    if "site.api.espn.com" in src:
        src_patterns["site_api"] = src_patterns.get("site_api", 0) + 1
    elif "/cricketers/_/id/" in src:
        src_patterns["id_only"] = src_patterns.get("id_only", 0) + 1
    elif "/cricketers/" in src:
        src_patterns["slug"] = src_patterns.get("slug", 0) + 1
    elif "cricbuzz" in src:
        src_patterns["cricbuzz"] = src_patterns.get("cricbuzz", 0) + 1
    elif src == "registry":
        src_patterns["registry"] = src_patterns.get("registry", 0) + 1
    else:
        src_patterns[src[:50] if src else "empty"] = src_patterns.get(src[:50] if src else "empty", 0) + 1
for p, c in sorted(src_patterns.items(), key=lambda x: -x[1]):
    print(f"  {p}: {c}")

# Retry 503s
print()
print("=== Retrying 503 IDs ===")
ids_503 = ["25490", "56161", "302700"]
for eid in ids_503:
    url = f"https://site.api.espn.com/apis/common/v3/sports/cricket/athletes/{eid}"
    r = requests.get(url, headers={"Accept": "application/json"}, timeout=10)
    print(f"  ESPN {eid}: status={r.status_code}")
