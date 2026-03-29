"""
_generate_enrichment_report.py
------------------------------
Generates a detailed enrichment report showing which players are missing data
and what sources have been tried.
"""

import json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

CACHE_PATH = Path("data/cache/profiles_raw.json")
STATE_PATH = Path("data/enrichment_state.json")
OUTPUT_PATH = Path("output/player_profiles.json")
REPORT_PATH = Path("data/enrichment_report.json")


def generate_report():
    """Generate enrichment report with statistics and missing player details."""
    
    report = {
        "generated_at": datetime.utcnow().isoformat(),
        "summary": {},
        "missing_by_team": {},
        "missing_details": [],
        "enrichment_errors": [],
    }
    
    # Load data
    cache = json.load(open(CACHE_PATH)) if CACHE_PATH.exists() else {}
    state = json.load(open(STATE_PATH)) if STATE_PATH.exists() else {}
    output = json.load(open(OUTPUT_PATH)) if OUTPUT_PATH.exists() else {}
    
    players = output.get("players", {})
    teams = output.get("teams", {})
    
    # Count statistics
    total = len(players)
    enriched = sum(1 for p in players.values() if p.get("batting", {}).get("hand") or p.get("bowling", {}).get("type"))
    missing = total - enriched
    
    report["summary"] = {
        "total_players": total,
        "enriched": enriched,
        "missing": missing,
        "enrichment_rate": f"{100 * enriched / total:.1f}%" if total else "0%",
    }
    
    # Track missing by team
    missing_by_team = defaultdict(list)
    for pid, player in players.items():
        has_data = bool(player.get("batting", {}).get("hand") or player.get("bowling", {}).get("type"))
        if not has_data:
            for team in player.get("teams", []):
                missing_by_team[team].append({
                    "id": pid,
                    "name": player.get("name"),
                    "espn_id": player.get("external_ids", {}).get("espn"),
                    "cricbuzz_id": player.get("external_ids", {}).get("cricbuzz"),
                })
    
    report["missing_by_team"] = {team: players for team, players in sorted(missing_by_team.items())}
    report["summary"]["teams_with_missing"] = len(missing_by_team)
    
    # Find players with errors
    for pid, s in state.items():
        if s.get("error"):
            if pid in players:
                report["enrichment_errors"].append({
                    "player_id": pid,
                    "name": players[pid].get("name"),
                    "error": s.get("error"),
                    "last_attempted": s.get("last_attempted"),
                })
    
    # Write report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"Enrichment Report Generated: {REPORT_PATH}")
    print(f"  Total Players: {report['summary']['total_players']}")
    print(f"  Enriched: {report['summary']['enriched']} ({report['summary']['enrichment_rate']})")
    print(f"  Missing: {report['summary']['missing']}")
    print(f"  Teams with missing data: {report['summary']['teams_with_missing']}")
    
    if report["enrichment_errors"]:
        print(f"  Errors encountered: {len(report['enrichment_errors'])}")
    
    return report


if __name__ == "__main__":
    generate_report()
