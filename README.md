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

- Input registry: `data/registry_csv/people.csv` and `data/registry_csv/names.csv`
- Optional compatibility paths: `data/cricsheet/people.csv` + `data/cricsheet/names.csv`, or `data/people.csv` + `data/names.csv`
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
tools\verify_dashboard_counts.bat --expected-players 3653 --expected-missing 106
```

## Automated Data Refresh

This is the automation path for both local one-click runs and GitHub scheduled runs.

### Expected inputs

- Register files from Cricsheet:
  - `https://cricsheet.org/register/people.csv`
  - `https://cricsheet.org/register/names.csv`
- Match update zips from Cricsheet downloads:
  - 2-day: `recently_added_2_male_json.zip`
  - 7-day: `recently_added_7_male_json.zip`
- Optional full bootstrap archive:
  - `t20s_male_json.zip`

### Expected outputs

- Updated register files:
  - `data/registry_csv/people.csv`
  - `data/registry_csv/names.csv`
- Updated match index/cache:
  - `data/matches_json/*.json` (male `T20`/`IT20` only)
  - `data/matches_json/README.txt` (compact merged index)
- Enriched artifacts:
  - `output/player_profiles.json`
  - `output/dashboard_data.json`
  - `output/dashboard.html`

### One-click local scripts

All scripts are in `tools/` and can be double-clicked from Explorer or run in terminal.

- `tools\run_auto_2d.bat`: refresh 2-day feed + run pipeline
- `tools\run_auto_7d.bat`: refresh 7-day feed + run pipeline
- `tools\run_auto_complete.bat`: full archive refresh + run pipeline
- `tools\run_auto_update_only_2d.bat`: refresh 2-day feed only (no pipeline)
- `tools\run_auto_update_only_7d.bat`: refresh 7-day feed only (no pipeline)
- `tools\run_auto_full_clean.bat`: delete runtime artifacts, rebuild from full archive, run pipeline

Advanced flags can be passed through each script (for example `--workers 8` or `--no-fetch`).

### Core updater behavior

`tools/update_cricsheet_inputs.py` does the following:

1. Downloads register CSVs.
2. Downloads requested zip (`2-day`, `7-day`, or `full-archive`).
3. Parses zip `README.txt`.
4. Selects only male `T20`/`IT20` match IDs.
5. Extracts only selected JSON files.
6. Merges/updates compact `data/matches_json/README.txt`.
7. Produces optional machine-readable delta summary (`--summary-json`).

If `data/matches_json` is empty, it automatically bootstraps from `t20s_male_json.zip` unless `--no-bootstrap` is used.

### GitHub automation (2-step schedule)

Workflow: `.github/workflows/enrich-players.yml`

- Step 1 schedule: every 2 days -> downloads 2-day feed.
- Step 2 schedule: weekly consolidation -> downloads 7-day feed.

Manual trigger supports:

- `window_days`: `2` or `7`
- `no_fetch`: pipeline cache-only mode
- `workers`: pipeline fetch parallelism
- `force_pipeline`: run enrichment even if inputs are unchanged

Important runtime rule:

- If updater detects no registry or match delta, pipeline/dashboard regeneration is skipped.
- This avoids unnecessary dashboard churn when both 2-day and 7-day downloads carry no new data.

### Keep dashboard always online (GitHub Pages)

The workflow publishes dashboard artifacts to GitHub Pages every run.

One-time repository setup:

1. `Settings -> Actions -> General`: set workflow permissions to `Read and write`.
2. `Settings -> Pages`: set source to `GitHub Actions`.
3. If branch protection is enabled, allow workflow commits or switch to bot-PR flow.

After setup, your dashboard is always accessible from the Pages URL even when a run skips regeneration due to no data changes.

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
