# Project Guidelines

## Code Style
- Use Python for all implementation work in this repository.
- Prefer small, focused modules matching the planned architecture: `registry_loader.py`, `scraper_espn.py`, `normalizer.py`, `pipeline.py`.
- Keep functions deterministic where possible (especially normalization logic) and easy to unit test.

## Architecture
- Treat this as a data pipeline project:
  - Input registry files: `data/people.csv`, `data/names.csv`
  - Optional raw match context: `data/matches_json/**`
  - Raw profile cache: `data/cache/profiles_raw.json`
  - Final output: `output/player_profiles.json`
- Keep responsibilities separated:
  - Loader parses and maps IDs
  - Scraper fetches and extracts raw profile fields
  - Normalizer transforms raw styles to canonical schema
  - Pipeline orchestrates iteration, caching, retries, and writing output

## Build and Test
- This repo is Python-oriented; do not use `msbuild` tasks for project validation.
- Use a workspace-local virtual environment and install dependencies there.
- When tests are added, prefer `pytest` and run targeted tests for changed modules first.
- Validate generated JSON output shape before considering pipeline runs complete.

## Conventions
- Continue processing on partial failures (missing `espn_id`, request failures, missing style fields).
- Scraper behavior must include timeout, retry, and polite rate limiting (1 second between network requests).
- Reuse cached raw profile responses when available to avoid repeated scraping.
- Normalize batting hand to `RHB` or `LHB`.
- Normalize bowling into structured fields (`arm`, `type`, `subtype`, `mechanism`) and preserve raw values in a `raw` object.
- Include progress logging for long runs (processed/skipped/failed counts) and design for at least 1000 players.