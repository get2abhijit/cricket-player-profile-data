"""Check registry output quality."""
import json

r = json.load(open("output/registry_enriched.json"))
print("Metadata:", json.dumps(r["metadata"], indent=2))
print()

# Show sample entries
print("--- Sample registry entries ---")
for pid, entry in list(r["players"].items())[:8]:
    slug = entry["slug"]
    name = entry["full_name"]
    reg = entry["registry_name"]
    espn = entry.get("espn_id", "?")
    bat = entry.get("batting_hand", "-")
    bowl = entry.get("bowling_type", "-")
    enriched = entry.get("enriched", False)
    src = entry.get("source_url", "")[:60]
    print(f"  {slug:30s}  {name:30s}  (reg: {reg:15s})  bat={bat}  bowl={bowl}  espn={espn}")

print()
# Count name improvements
improved = 0
for entry in r["players"].values():
    if entry["full_name"] != entry["registry_name"]:
        improved += 1
print(f"Players with improved names: {improved}")
print(f"Players with original names: {len(r['players']) - improved}")
