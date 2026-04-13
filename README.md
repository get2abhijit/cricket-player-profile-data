# Player Intelligence Engine

A standalone Python pipeline that reads Cricsheet registry files and builds a unified player profile dataset with batting/bowling classification.

## Features

- Loads player IDs and external IDs from Cricsheet registry files.
- Scrapes ESPN Cricinfo player profile pages using ESPN IDs.
- Normalizes batting hand to `RHB` / `LHB`.
- Classifies bowling into structured fields:
  - `arm`
  - `type`
  - `subtype`
  - `mechanism`
- Reuses cached raw profile responses to avoid duplicate scraping.
- Supports external manual overrides in `data/manual_overrides.json` so player data can be corrected without editing Python code.
- Continues processing on missing IDs, request failures, and missing fields.
- Writes final dataset to `output/player_profiles.json`.

## Project Structure

- `registry_loader.py`: Loads and maps player registry records.
- `scraper_espn.py`: Fetches and parses ESPN profile fields.
- `normalizer.py`: Batting and bowling normalization logic.
- `pipeline.py`: End-to-end orchestration, caching, and output writing.

Data paths used:

- Input registry: `data/people.csv` and `data/names.csv`
- Optional prompt-compatible path: `data/cricsheet/people.csv` and `data/cricsheet/names.csv`
- Raw cache: `data/cache/profiles_raw.json`
- Manual overrides: `data/manual_overrides.json`
- Output: `output/player_profiles.json`

## Setup (Workspace-local venv)

From repository root:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Usage

Run full pipeline:

```powershell
python pipeline.py
```

Run a smaller smoke test:

```powershell
python pipeline.py --limit 25
```

Manual overrides workflow:

```powershell
python pipeline.py
```

The pipeline auto-seeds `data/manual_overrides.json` with placeholder entries for players who are still missing batting and bowling data. Edit any player entry there to override scraped values.

Fast regeneration for manual edits (no network calls):

```powershell
python pipeline.py --no-fetch
```

This reuses existing cache plus `data/manual_overrides.json` and rebuilds:
- `output/player_profiles.json`
- `output/dashboard_data.json`
- `output/dashboard.html`

If you want the fastest manual-edit loop without rebuilding player records from cache at all, use:

```powershell
python refresh_manual_overrides.py
```

That keeps the current `output/player_profiles.json` intact, reapplies `data/manual_overrides.json`, and refreshes the dashboard artifacts only.

When you explicitly want to retry unresolved players that have empty cache rows, use:

```powershell
python pipeline.py --retry-empty-cache
```

## Utility Scripts (Easy Run)

These scripts are in `tools/` and are intended for everyday operations.

Clean rebuild from existing cache (no network):

```powershell
tools\run_clean_pipeline.bat
```

Clean rebuild with network fetch enabled:

```powershell
tools\run_clean_pipeline.bat --fetch --workers 6
```

Run Cricbuzz second pass, rebuild output, then verify snapshot counts:

```powershell
tools\run_second_pass_fast.bat
```

Verify dashboard regression snapshot explicitly:

```powershell
tools\verify_dashboard_counts.bat --expected-players 3445 --expected-missing 70
```

Supported override fields per player:

- `batting_style` and/or `batting_hand`
- `bowling_style` and/or `bowling.arm|type|subtype|mechanism`
- `role`
- `is_wicketkeeper`
- `external_ids.espn` and `external_ids.cricbuzz`
- `source_url` and `notes`

You can also add players manually by player ID under the top-level `players` object, even if they were not part of the seeded missing-player list.

## Output Schema

Each entry contains:

- `player_id`
- `player_name`
- `external_ids` (`espn`, `cricbuzz`)
- `batting.hand` (`RHB` or `LHB` when inferred)
- `bowling.arm`, `bowling.type`, `bowling.subtype`, `bowling.mechanism`
- `role`
- `raw.batting_style`, `raw.bowling_style`
- `source`
- `last_updated`

## Notes

- Scraper includes timeout, retry, and a 1-second polite delay.
- Cached profiles are reused automatically.
- The pipeline is designed for large runs (1000+ players) while remaining resilient to partial failures.
