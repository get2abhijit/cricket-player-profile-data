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
