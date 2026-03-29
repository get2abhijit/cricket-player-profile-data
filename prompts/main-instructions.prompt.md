Build a standalone "Player Intelligence Engine" in Python.

GOAL

Create a system that reads Cricsheet registry files and generates a clean JSON dataset of player profiles including batting hand and bowling style classification.

--------------------------------------------------

INPUT DATA

Files:

data/cricsheet/people.csv
data/cricsheet/names.csv

These contain:

- cricsheet player IDs
- player names
- external IDs (espn, cricbuzz)

--------------------------------------------------

OUTPUT

Generate:

output/player_profiles.json

Each player entry must include:

player_id
player_name

external_ids:
    espn
    cricbuzz

batting:
    hand (RHB or LHB)

bowling:
    arm (Left or Right)
    type (Pace or Spin)
    subtype:
        Right Arm Off Spin
        Right Arm Leg Spin
        Left Arm Orthodox
        Left Arm Chinaman
        Seam
    mechanism:
        Finger
        Wrist
        None

role

raw:
    batting_style
    bowling_style

source
last_updated

--------------------------------------------------

ARCHITECTURE

Create modules:

registry_loader.py
scraper_espn.py
normalizer.py
pipeline.py

--------------------------------------------------

REGISTRY LOADER

Parse people.csv and names.csv

Build mapping:

cricsheet_id → player_name → espn_id → cricbuzz_id

--------------------------------------------------

SCRAPER

Fetch ESPN Cricinfo profile using espn_id.

Extract:

Batting Style
Bowling Style
Role

Use requests + BeautifulSoup

Add:

timeout
retry
rate limiting (sleep 1 sec)

--------------------------------------------------

NORMALIZATION

Implement:

normalize_batting_hand()

Right → RHB
Left → LHB

Implement:

classify_bowling_style()

Rules:

fast / medium → Pace

offbreak → Right Arm Off Spin → Finger
legbreak → Right Arm Leg Spin → Wrist
orthodox → Left Arm Orthodox → Finger
chinaman / left-arm wrist → Left Arm Chinaman → Wrist

Extract bowling_arm separately

--------------------------------------------------

PIPELINE

For each player:

1. Get espn_id
2. Fetch profile
3. Normalize
4. Append to output list

Skip players already cached

--------------------------------------------------

CACHING

Store raw responses in:

data/cache/profiles_raw.json

Reuse cached data if available

--------------------------------------------------

OUTPUT

Write final JSON to:

output/player_profiles.json

--------------------------------------------------

ERROR HANDLING

Handle:

missing espn_id
failed requests
missing fields

Continue processing

--------------------------------------------------

LOGGING

Print progress:

Processing player X
Skipped player Y
Failed player Z

--------------------------------------------------

PERFORMANCE

Allow processing at least 1000 players safely

--------------------------------------------------

DELIVERABLE

Working pipeline that produces a complete player_profiles.json

--------------------------------------------------

ENSURE:
- local workspace level venv with dependencies
- clear README for setup and usage - github repository style
- summary and learnings in dedicated file.