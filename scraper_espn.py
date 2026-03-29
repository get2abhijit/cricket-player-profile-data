from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_RETRY_TOTAL = 2
DEFAULT_RATE_LIMIT_SECONDS = 0.5  # Site API is a proper JSON endpoint; 0.5s is polite

# Jitter added on top of the base rate limit (0..JITTER_MAX seconds)
_JITTER_MAX = 0.5

# HTTP 429 back-off: wait this many seconds before re-attempting
_RATE_LIMITED_BACKOFF = 30

# Number of consecutive 429s before giving up on current espn_id
_RATE_LIMITED_MAX_RETRIES = 2

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}


def _polite_sleep(base: float) -> None:
    """Sleep for base seconds plus a small random jitter."""
    jitter = random.uniform(0, _JITTER_MAX)
    time.sleep(base + jitter)


_ESPN_SITE_API_BASE = "https://site.api.espn.com/apis/common/v3/sports/cricket/athletes"


class EspnScraper:
    """
    Fetches player profile data from ESPN Cricinfo.

    Fetch strategy (in order):
      0. ESPN Site API (JSON)   (site.api.espn.com — NOT Akamai-blocked)
      1. ESPN Cricinfo legacy JSON API  (/ci/engine/player/{id}.json)
      2. ESPN Cricinfo HTML page         (full browser headers)
      3. Cricbuzz HTML profile           (if cricbuzz_id available)
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        retry_total: int = DEFAULT_RETRY_TOTAL,
        rate_limit_seconds: float = DEFAULT_RATE_LIMIT_SECONDS,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.rate_limit_seconds = rate_limit_seconds
        self.session = self._build_session(retry_total=retry_total)

    @staticmethod
    def _build_session(retry_total: int) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=retry_total,
            connect=retry_total,
            read=retry_total,
            backoff_factor=2,
            # 429 handled manually below so we can log + respect Retry-After
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.headers.update(_BROWSER_HEADERS)
        return session

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @staticmethod
    def profile_url(espn_id: str, player_name: Optional[str] = None) -> str:
        """
        Return a canonical ESPN Cricinfo player profile URL.
        
        If player_name is provided, generates a slug-based URL (preferred):
          https://www.espncricinfo.com/cricketers/{firstname-lastname}-{id}
        Otherwise falls back to ID-only format:
          https://www.espncricinfo.com/cricketers/_/id/{id}
        """
        if not player_name:
            return f"https://www.espncricinfo.com/cricketers/_/id/{espn_id}"
        
        # Generate slug from player name: lowercase, spaces->hyphens, remove special chars
        slug = player_name.strip().lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)  # Remove special chars
        slug = re.sub(r"\s+", "-", slug)  # Replace whitespace with hyphens
        slug = re.sub(r"-+", "-", slug)  # Collapse multiple hyphens
        slug = slug.rstrip("-")  # Remove trailing hyphens
        
        return f"https://www.espncricinfo.com/cricketers/{slug}-{espn_id}"

    def fetch_profile(
        self,
        espn_id: str,
        cricbuzz_id: Optional[str] = None,
        skip_espn: bool = False,
        player_name: Optional[str] = None,
    ) -> Dict[str, Optional[str]]:
        """
        Try available sources in priority order and return the first successful
        result.  Never raises — empty dict on total failure.

        Parameters
        ----------
        skip_espn:  When True the ESPN strategies are skipped entirely.  Use
                    this when ESPN is known to be blocked (Akamai 403/JS
                    challenge) to avoid unnecessary network round-trips.
        """
        strategies: List = []
        if espn_id:
            # Strategy 0: ESPN Site API (JSON — not Akamai-blocked)
            strategies.append(lambda eid=espn_id, pn=player_name: self._try_espn_site_api(eid, pn))
        if not skip_espn and espn_id:
            strategies.append(lambda eid=espn_id: self._try_espn_legacy_json(eid))
            strategies.append(lambda eid=espn_id: self._try_espn_html(eid))
        if cricbuzz_id:
            strategies.append(lambda cbid=cricbuzz_id: self._try_cricbuzz_html(cbid))  # type: ignore[arg-type]

        last_exc: Optional[Exception] = None
        for strategy in strategies:
            try:
                result = strategy()
                if result and any(result.get(k) for k in ("batting_style", "bowling_style", "role")):
                    return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc

        # Return a shell so cache still records the attempt
        return {
            "batting_style": None,
            "bowling_style": None,
            "role": None,
            "source_url": self.profile_url(espn_id, player_name),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "fetch_error": str(last_exc) if last_exc else "all_sources_empty",
        }

    # ------------------------------------------------------------------
    # Strategy 0: ESPN Site API (JSON — not Akamai-blocked)
    # ------------------------------------------------------------------

    def _try_espn_site_api(self, espn_id: str, player_name: Optional[str] = None) -> Optional[Dict[str, Optional[str]]]:
        """
        Fetch from the ESPN public athlete JSON API.
        Returns structured JSON with batStyle/bowlStyle lists.
        This endpoint is not protected by Akamai and returns 200 JSON.
        """
        url = f"{_ESPN_SITE_API_BASE}/{espn_id}"
        # Use a lighter Accept header for JSON endpoint
        api_headers = {
            "User-Agent": _BROWSER_HEADERS["User-Agent"],
            "Accept": "application/json",
        }
        try:
            response = self.session.get(url, headers=api_headers, timeout=self.timeout_seconds)
        except requests.RequestException:
            return None

        if response.status_code != 200:
            return None

        try:
            data = response.json()
        except ValueError:
            return None

        athlete = data.get("athlete") or {}
        if not isinstance(athlete, dict):
            return None

        # batStyle / bowlStyle are lists of {description, shortDescription, type}
        bat_list = athlete.get("batStyle") or []
        bowl_list = athlete.get("bowlStyle") or []
        position = athlete.get("position") or {}

        batting_style = bat_list[0].get("description") if bat_list else None
        bowling_style = bowl_list[0].get("description") if bowl_list else None
        role = position.get("name") if isinstance(position, dict) else None

        # Normalise position "Unknown" to None
        if role and role.lower() == "unknown":
            role = None

        # Use ESPN's own displayName for the slug (most accurate full name)
        espn_display_name = athlete.get("displayName") or player_name

        _polite_sleep(self.rate_limit_seconds)
        return {
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "role": role,
            "source_url": self.profile_url(espn_id, espn_display_name),
            "espn_display_name": espn_display_name,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Strategy 1: ESPN legacy JSON API
    # ------------------------------------------------------------------

    def _try_espn_legacy_json(self, espn_id: str) -> Optional[Dict[str, Optional[str]]]:
        url = f"https://www.espncricinfo.com/ci/engine/player/{espn_id}.json"
        response = self._get_with_rate_limit_guard(url)
        if response is None or response.status_code != 200:
            return None

        try:
            data = response.json()
        except ValueError:
            return None

        batting_style = self._dig(data, "player", "batting_style")
        bowling_style = self._dig(data, "player", "bowling_style")
        role = self._dig(data, "player", "playing_role") or self._dig(data, "player", "role")

        _polite_sleep(self.rate_limit_seconds)
        return {
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "role": role,
            "source_url": url,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Strategy 2: ESPN HTML page with browser impersonation
    # ------------------------------------------------------------------

    def _try_espn_html(self, espn_id: str) -> Optional[Dict[str, Optional[str]]]:
        url = f"https://www.espncricinfo.com/cricketers/_/id/{espn_id}"
        # A Referer from the team listing page reduces bot-detection chance
        self.session.headers.update(
            {"Referer": "https://www.espncricinfo.com/cricket-teams/"}
        )
        response = self._get_with_rate_limit_guard(url)
        self.session.headers.pop("Referer", None)

        if response is None or response.status_code != 200:
            return None

        parsed = self._parse_espn_html(response.text)
        parsed["source_url"] = url
        parsed["fetched_at"] = datetime.now(timezone.utc).isoformat()

        _polite_sleep(self.rate_limit_seconds)
        return parsed

    def _parse_espn_html(self, html: str) -> Dict[str, Optional[str]]:
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD embedded data first (most reliable when present)
        result = self._parse_json_ld(soup)
        if result:
            return result

        batting_style = (
            self._extract_labeled_value(soup, "Batting Style")
            or self._extract_labeled_value(soup, "batting style")
        )
        bowling_style = (
            self._extract_labeled_value(soup, "Bowling Style")
            or self._extract_labeled_value(soup, "bowling style")
        )
        role = (
            self._extract_labeled_value(soup, "Playing Role")
            or self._extract_labeled_value(soup, "Role")
        )

        return {
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "role": role,
        }

    @staticmethod
    def _parse_json_ld(soup: BeautifulSoup) -> Optional[Dict[str, Optional[str]]]:
        """Extract player info from JSON-LD structured data if present."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
            except (ValueError, TypeError):
                continue
            if not isinstance(data, dict):
                continue
            batting = data.get("batStyle") or data.get("batting_style")
            bowling = data.get("bowlStyle") or data.get("bowling_style")
            role = data.get("playingRole") or data.get("role")
            if batting or bowling or role:
                return {
                    "batting_style": batting,
                    "bowling_style": bowling,
                    "role": role,
                }
        return None

    # ------------------------------------------------------------------
    # Strategy 3: Cricbuzz HTML profile
    # ------------------------------------------------------------------

    def _try_cricbuzz_html(self, cricbuzz_id: str) -> Optional[Dict[str, Optional[str]]]:
        url = f"https://www.cricbuzz.com/profiles/{cricbuzz_id}"
        self.session.headers.update({"Referer": "https://www.cricbuzz.com/"})
        response = self._get_with_rate_limit_guard(url)
        self.session.headers.pop("Referer", None)

        if response is None or response.status_code != 200:
            return None

        parsed = self._parse_cricbuzz_html(response.text)
        parsed["source_url"] = url
        parsed["fetched_at"] = datetime.now(timezone.utc).isoformat()

        _polite_sleep(self.rate_limit_seconds)
        return parsed

    def _parse_cricbuzz_html(self, html: str) -> Dict[str, Optional[str]]:
        """
        Parse batting / bowling / role from a Cricbuzz player profile page.

        Cricbuzz's HTML uses Tailwind CSS utility classes whose names change over
        time.  The most robust strategy is the same label-sibling text approach
        used for ESPN HTML: find the exact text node for each label, then return
        the text of its next sibling element.
        """
        soup = BeautifulSoup(html, "html.parser")

        # Cricbuzz uses capitalised label names
        batting_style = (
            self._extract_labeled_value(soup, "Batting Style")
            or self._extract_labeled_value(soup, "batting style")
        )
        bowling_style = (
            self._extract_labeled_value(soup, "Bowling Style")
            or self._extract_labeled_value(soup, "bowling style")
        )
        role = (
            self._extract_labeled_value(soup, "Role")
            or self._extract_labeled_value(soup, "Playing Role")
        )

        return {
            "batting_style": batting_style,
            "bowling_style": bowling_style,
            "role": role,
        }

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _get_with_rate_limit_guard(self, url: str) -> Optional[requests.Response]:
        """GET a URL; back off politely on HTTP 429, return None on 403."""
        for attempt in range(_RATE_LIMITED_MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=self.timeout_seconds)
            except requests.RequestException:
                return None

            if response.status_code == 403:
                return None  # Blocked — caller will try next source.

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", _RATE_LIMITED_BACKOFF))
                wait = max(retry_after, _RATE_LIMITED_BACKOFF)
                print(f"Rate limited (429) on {url} — waiting {wait}s (attempt {attempt + 1})")
                time.sleep(wait + random.uniform(0, _JITTER_MAX))
                if attempt >= _RATE_LIMITED_MAX_RETRIES:
                    return None
                continue

            return response
        return None

    @staticmethod
    def _dig(data: Dict, *keys: str) -> Optional[str]:
        """Safely navigate nested dict keys."""
        current: object = data
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return str(current).strip() if current else None

    @staticmethod
    def _extract_labeled_value(soup: BeautifulSoup, label: str) -> Optional[str]:
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

        text_blob = soup.get_text("\n", strip=True)
        pattern = re.compile(rf"{re.escape(label)}\s*:?\s*([^\n\r]+)", flags=re.IGNORECASE)
        match = pattern.search(text_blob)
        if match:
            value = match.group(1).strip()
            return value or None

        return None
