"""
scraper_cricbuzz.py
-------------------
Cricbuzz player discovery and profile scraping for second-pass enrichment.

Strategy:
1. Discover Cricbuzz player IDs by scraping match scorecards from known series.
2. Match discovered player names against our missing player list.
3. Fetch individual Cricbuzz profile pages for matched players.
4. Extract batting style, bowling style, and role from profile pages.
"""

from __future__ import annotations

import re
import time
import random
from typing import Dict, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup

_RATE_LIMIT = 0.6
_JITTER_MAX = 0.4

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ------------------------------------------------------------------
# Known European series on Cricbuzz (series_id -> description)
# Cricbuzz loads series match lists via JavaScript, so we maintain
# hardcoded scorecard IDs extracted via browsing each series page.
# ------------------------------------------------------------------
_KNOWN_SERIES: Dict[str, str] = {
    "8337": "icc-mens-t20-world-cup-sub-regional-europe-qualifier-b-2024",
    "8332": "nordic-t20i-cup-2024",
    "10157": "continental-cup-2025",
    "9818": "mdina-cup-2025",
    "10031": "nordic-t20i-cup-2025",
    "10108": "icc-mens-t20-world-cup-europe-qualifier-2025",
    "10278": "quadrangular-t20i-series-in-malawi-2025",
    "10746": "belgium-tour-of-austria-2025",
    "9827": "central-europe-cup-2025",
}

# Pre-collected scorecard match IDs from all known European series.
# These are Cricbuzz live-cricket-scores IDs whose scorecards contain
# player profile links.
_KNOWN_SCORECARD_IDS: List[str] = [
    # 8337: ICC Mens T20 WC Sub Regional Europe Qualifier B, 2024
    # Teams: GER, GIB, SWE, BEL, SUI, SRB, CRT, SLV, NOR, JER
    "96987", "97000", "96996", "97009", "97018", "97014",
    "97027", "97036", "97059", "97041", "97063", "97050",
    "97068", "97072", "97095", "97099", "97104", "97108",
    "97113", "97131",
    # 8332: Nordic T20I Cup 2024 — NOR, FIN
    "96964", "96973", "96982",
    # 10157: Continental Cup 2025 — FRA, MALTA, BEL, AUT, ROM, HUN
    "122203", "122209", "122220", "122225", "122231", "122236",
    "122902", "122913", "122929", "122924", "122918",
    # 9818: Mdina Cup 2025 — BEL, PORT, MALTA
    "118646", "118655", "118658", "118664", "118667", "118676", "118682",
    # 10031: Nordic T20I Cup 2025 — DEN, FIN, SWE, NOR
    "120955", "120960", "120977", "120988", "120999", "121010",
    # 10108: ICC Mens T20 WC Europe Qualifier 2025 — ITA, GGY, JER, SCO, NED
    "121692", "121697", "121703", "121714", "121725", "121730",
    "121736", "121747", "121758", "121763",
    # 10278: Quadrangular T20I Series in Malawi 2025 — GER, BHR, TAN, MWI
    "123061", "123056", "123045", "123034", "123006", "123001", "122979",
    # 10746: Belgium Tour of Austria 2025 — BEL, AUT
    "132681", "132676", "132665", "132654",
    # 9827: Central Europe Cup 2025 — CZE, AUT, NOR
    "118691", "118694", "118700", "118709", "118712", "118721",
]

# Team name -> Cricbuzz team slug/ID for teams that have results pages.
_TEAM_CB_IDS: Dict[str, str] = {
    "Germany": "germany/77",
    "Denmark": "denmark/185",
    "Italy": "italy/527",
    "Belgium": "belgium/541",
    "Jersey": "jersey/303",
}


def _polite_sleep() -> None:
    time.sleep(_RATE_LIMIT + random.uniform(0, _JITTER_MAX))


def _normalize_name(name: str) -> str:
    """Normalize a player name for fuzzy matching."""
    # Remove special characters, lowercase, collapse whitespace
    name = name.strip().lower()
    name = re.sub(r"[^a-z\s]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def _name_slug(name: str) -> str:
    """Create a hyphenated slug from a player name."""
    slug = name.strip().lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    return slug.strip("-")


class CricbuzzScraper:
    """Discovers Cricbuzz player IDs and fetches profile data."""

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)
        # Cache of discovered profiles: cricbuzz_id -> slug
        self._discovered: Dict[str, str] = {}
        # Reverse map: normalized_name -> (cricbuzz_id, original_name)
        self._name_index: Dict[str, Tuple[str, str]] = {}

    # ------------------------------------------------------------------
    # Phase 1: Discover Cricbuzz IDs from series / scorecards
    # ------------------------------------------------------------------

    def discover_from_series(self, series_ids: Optional[List[str]] = None) -> int:
        """
        Discover player profiles from hardcoded scorecard IDs for known series.
        Returns the total number of unique player profiles found.
        """
        scorecard_ids = list(_KNOWN_SCORECARD_IDS)
        print(f"  Scraping {len(scorecard_ids)} known European scorecard pages...")
        for mid in scorecard_ids:
            self._scrape_scorecard(mid)
            _polite_sleep()
        print(f"  Total discovered profiles: {len(self._discovered)}")
        return len(self._discovered)

    def discover_from_team_results(self, teams: Optional[List[str]] = None) -> int:
        """Discover profiles from team results pages on Cricbuzz."""
        teams_to_check = teams or list(_TEAM_CB_IDS.keys())
        count = 0

        for team in teams_to_check:
            cb_path = _TEAM_CB_IDS.get(team)
            if not cb_path:
                continue
            print(f"  Checking {team} results page...")
            match_ids = self._get_team_match_ids(cb_path)
            if not match_ids:
                print(f"    No match IDs found")
                continue
            print(f"    Found {len(match_ids)} matches, scraping top 3")
            for mid in match_ids[:3]:
                c = self._scrape_scorecard(mid)
                count += c
                _polite_sleep()

        return count

    def discover_from_scorecard_ids(self, match_ids: List[str]) -> int:
        """Directly scrape a list of known Cricbuzz scorecard IDs."""
        count = 0
        for mid in match_ids:
            c = self._scrape_scorecard(mid)
            count += c
            _polite_sleep()
        return count

    def _get_team_match_ids(self, cb_path: str) -> List[str]:
        """Get match IDs from a team's results page."""
        url = f"https://www.cricbuzz.com/cricket-team/{cb_path}/results"
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return []
        except requests.RequestException:
            return []

        _polite_sleep()
        # Filter to associate-level matches by excluding IPL/PSL etc
        all_ids = re.findall(r"live-cricket-scores/(\d+)/", r.text)
        return list(dict.fromkeys(all_ids))

    def _scrape_scorecard(self, match_id: str) -> int:
        """Scrape a single scorecard page for player profile links."""
        url = f"https://www.cricbuzz.com/live-cricket-scorecard/{match_id}"
        try:
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return 0
        except requests.RequestException:
            return 0

        profiles = re.findall(r"/profiles/(\d+)/([a-z0-9-]+)", r.text)
        new_count = 0
        for cb_id, slug in profiles:
            if cb_id not in self._discovered:
                self._discovered[cb_id] = slug
                # Index by normalized slug and name variants
                name_from_slug = slug.replace("-", " ")
                norm = _normalize_name(name_from_slug)
                self._name_index[norm] = (cb_id, name_from_slug)
                new_count += 1

        return new_count

    # ------------------------------------------------------------------
    # Phase 2: Match against missing players
    # ------------------------------------------------------------------

    def find_cricbuzz_id(self, player_name: str) -> Optional[str]:
        """
        Find a Cricbuzz profile ID for a given player name.
        Uses progressively looser matching with safety checks.
        """
        norm = _normalize_name(player_name)

        # 1. Direct exact match
        if norm in self._name_index:
            return self._name_index[norm][0]

        parts = norm.split()
        if len(parts) < 2:
            return None

        # 2. Match where last name is identical and first name shares initial
        #    e.g., "B Ess" -> "benjamin ess", "A Randhawa" -> "armaan randhawa"
        first_initial = parts[0][0]
        last_name = parts[-1]
        candidates = []
        for key, (cb_id, _) in self._name_index.items():
            key_parts = key.split()
            if len(key_parts) < 2:
                continue
            if key_parts[-1] == last_name and key_parts[0][0] == first_initial:
                candidates.append(cb_id)

        # Only accept if exactly one candidate (avoid ambiguity)
        if len(candidates) == 1:
            return candidates[0]

        # 3. For multi-word names (non-initial), try matching first+last name
        #    e.g., "Khaled Khan" -> "khaled khan"
        if len(parts[0]) > 2:  # Not an initial
            for key, (cb_id, _) in self._name_index.items():
                key_parts = key.split()
                if len(key_parts) >= 2:
                    if key_parts[0] == parts[0] and key_parts[-1] == parts[-1]:
                        return cb_id

        # 4. Check if all player name parts appear as consecutive parts
        #    in a discovered name (e.g., "Ziaur Rehman" in "Muhammad Ziaur Rehman")
        if len(parts) >= 2 and len(parts[0]) > 2:
            name_str = " ".join(parts)
            candidates = []
            for key, (cb_id, _) in self._name_index.items():
                if name_str in key:
                    candidates.append(cb_id)
            if len(candidates) == 1:
                return candidates[0]

        return None

    # ------------------------------------------------------------------
    # Phase 3: Fetch Cricbuzz profile
    # ------------------------------------------------------------------

    def fetch_profile(self, cricbuzz_id: str) -> Optional[Dict[str, Optional[str]]]:
        """Fetch batting/bowling/role data from a Cricbuzz profile page."""
        slug = self._discovered.get(cricbuzz_id, cricbuzz_id)
        url = f"https://www.cricbuzz.com/profiles/{cricbuzz_id}/{slug}"

        try:
            r = self.session.get(url, timeout=20)
            if r.status_code != 200:
                return None
        except requests.RequestException:
            return None

        _polite_sleep()
        return self._parse_profile(r.text, url)

    def _parse_profile(self, html: str, url: str) -> Dict[str, Optional[str]]:
        """Extract batting/bowling/role and country from a Cricbuzz profile."""
        soup = BeautifulSoup(html, "html.parser")

        batting_style = (
            self._extract_labeled_value(soup, "Batting Style")
            or self._extract_labeled_value(soup, "batting style")
            or self._extract_labeled_value(soup, "BATTING STYLE")
        )
        bowling_style = (
            self._extract_labeled_value(soup, "Bowling Style")
            or self._extract_labeled_value(soup, "bowling style")
            or self._extract_labeled_value(soup, "BOWLING STYLE")
        )
        role = (
            self._extract_labeled_value(soup, "Role")
            or self._extract_labeled_value(soup, "ROLE")
        )

        # Try to extract country from the page
        country = self._extract_country(soup)

        return {
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "role": role,
            "country": country,
            "source_url": url,
            "source": "cricbuzz",
        }

    @staticmethod
    def _extract_labeled_value(soup: BeautifulSoup, label: str) -> Optional[str]:
        """Find a labeled value using text node + sibling pattern."""
        label_lower = label.lower()

        for text_node in soup.find_all(string=True):
            text = text_node.strip()
            if text.lower() != label_lower:
                continue
            parent = text_node.parent
            if parent is None:
                continue
            sibling = parent.find_next_sibling()
            while sibling is not None:
                value = sibling.get_text(" ", strip=True)
                if value and value.lower() != label_lower:
                    return value
                sibling = sibling.find_next_sibling()

        # Fallback: regex on full text
        text_blob = soup.get_text("\n", strip=True)
        pattern = re.compile(
            rf"{re.escape(label)}\s*:?\s*([^\n\r]+)", flags=re.IGNORECASE
        )
        match = pattern.search(text_blob)
        if match:
            value = match.group(1).strip()
            return value or None

        return None

    @staticmethod
    def _extract_country(soup: BeautifulSoup) -> Optional[str]:
        """Try to extract the player's country from the profile page."""
        # Look for small flag images (30x20 dimensions) — their alt text is the country
        for img in soup.find_all("img", alt=True):
            src = img.get("src", "")
            alt = img["alt"].strip()
            if alt and "30x20" in src:
                return alt.replace("-", " ").title()

        # Fallback: look for the "Teams" labeled field
        for text_node in soup.find_all(string=True):
            if text_node.strip().lower() == "teams":
                parent = text_node.parent
                if parent:
                    sibling = parent.find_next_sibling()
                    if sibling:
                        val = sibling.get_text(" ", strip=True)
                        if val:
                            return val
        return None

    @staticmethod
    def profile_url(cricbuzz_id: str, player_name: Optional[str] = None) -> str:
        """Generate a Cricbuzz profile URL."""
        slug = _name_slug(player_name) if player_name else cricbuzz_id
        return f"https://www.cricbuzz.com/profiles/{cricbuzz_id}/{slug}"
