# Automation Guide

This guide explains exactly what is downloaded, when the pipeline runs, what gets generated, and how dashboard hosting works.

## 1) Inputs and Outputs

### Inputs fetched from Cricsheet

- Register CSVs:
  - `https://cricsheet.org/register/people.csv`
  - `https://cricsheet.org/register/names.csv`
- Match zip feeds:
  - 2-day feed: `recently_added_2_male_json.zip`
  - 7-day feed: `recently_added_7_male_json.zip`
- Full bootstrap archive (when needed):
  - `t20s_male_json.zip`

### Inputs written locally

- `data/registry_csv/people.csv`
- `data/registry_csv/names.csv`
- `data/matches_json/*.json` (male `T20` / `IT20` only)
- `data/matches_json/README.txt` (compact merged index for incremental matching)

### Outputs written by enrichment

- `output/player_profiles.json`
- `output/dashboard_data.json`
- `output/dashboard.html`

## 2) Updater Script Contract

Script: `tools/update_cricsheet_inputs.py`

What it does:

1. Downloads latest register CSVs.
2. Downloads requested match archive (2-day, 7-day, or full).
3. Parses archive `README.txt`.
4. Filters to male `T20`/`IT20` matches only.
5. Extracts only selected match JSON files.
6. Merges `data/matches_json/README.txt` and preserves match timestamps for incremental logic.
7. Can emit machine-readable summary JSON (`--summary-json`) with a top-level `changed` flag.

No-change behavior:

- If the downloaded data is byte-identical and no T20/IT20 additions/updates are detected, summary reports `changed=false`.
- GitHub workflow uses this signal to skip pipeline/dashboard regeneration.

## 3) GitHub Schedule (2-Step)

Workflow: `.github/workflows/enrich-players.yml`

- Step 1 cadence: every 2 days -> refresh from 2-day feed.
- Step 2 cadence: every 7 days -> consolidation from 7-day feed.

Manual trigger inputs:

- `window_days`: `2` or `7`
- `no_fetch`: run pipeline in cache-only mode
- `workers`: parallel workers for fetch stage
- `force_pipeline`: run pipeline even when refresh has no changes

Execution gates:

- Refresh always runs.
- Pipeline/test/dashboard regeneration run only when:
  - updater summary says `changed=true`, or
  - `force_pipeline=true`.

This avoids unnecessary dashboard rewrites when 2-day/7-day downloads contain no effective updates.

## 4) Keep Dashboard Always Online

The workflow publishes dashboard artifacts to GitHub Pages every run.

One-time repository setup:

1. `Settings -> Actions -> General`: set workflow permissions to **Read and write**.
2. `Settings -> Pages`: set source to **GitHub Actions**.
3. If branch protection blocks pushes, allow bot commits or switch to PR-based updates.

Result:

- Dashboard remains continuously accessible via GitHub Pages URL.
- When no data changes exist, existing dashboard stays online unchanged.

## 5) One-Click Local Scripts

All scripts are in `tools/` and are safe default entry points.

- `run_auto_2d.bat`:
  - Download 2-day feed + run pipeline
- `run_auto_7d.bat`:
  - Download 7-day feed + run pipeline
- `run_auto_complete.bat`:
  - Download full archive + run pipeline
- `run_auto_update_only_2d.bat`:
  - Download/apply 2-day feed only (no pipeline)
- `run_auto_update_only_7d.bat`:
  - Download/apply 7-day feed only (no pipeline)
- `run_auto_full_clean.bat`:
  - Remove runtime artifacts and match cache, then full archive rebuild + pipeline

Advanced options can be passed through to the orchestrator, for example:

```powershell
tools\run_auto_7d.bat --workers 8
tools\run_auto_complete.bat --no-fetch
```

## 6) Git Cleanup Policy

The following transient files are intentionally not committed:

- Download zips such as `data/recently_added_7_male_json.zip`
- Full archive `data/t20s_male_json.zip`
- Temporary automation summary file `data/automation_update_summary.json`

This is enforced in `.gitignore`.
