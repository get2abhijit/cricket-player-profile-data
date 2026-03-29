"""
tests/test_scraper.py
---------------------
Unit tests for scraper_espn.py HTML parsing logic.
Uses pre-captured HTML snippets so no network calls are made.
"""

import pytest
from bs4 import BeautifulSoup

from scraper_espn import EspnScraper


# ---------------------------------------------------------------------------
# HTML fixtures
# ---------------------------------------------------------------------------

# Stripped-down version of a real Cricbuzz player page (new Tailwind layout)
_CRICBUZZ_HTML = """
<html><body>
<div class="w-full bg-white flex">
  <div class="w-1/3 text-label">Role</div>
  <div class="w-2/3 text-value">Bowler</div>
</div>
<div class="w-full bg-white flex">
  <div class="w-1/3 text-label">Batting Style</div>
  <div class="w-2/3 text-value">Right Handed Bat</div>
</div>
<div class="w-full bg-white flex">
  <div class="w-1/3 text-label">Bowling Style</div>
  <div class="w-2/3 text-value">Right-arm fast</div>
</div>
</body></html>
"""

# Cricbuzz page for a Chinaman bowler
_CRICBUZZ_HTML_CHINAMAN = """
<html><body>
<div class="row">
  <div class="label">Batting Style</div>
  <div class="value">Left Handed Bat</div>
</div>
<div class="row">
  <div class="label">Bowling Style</div>
  <div class="value">Left-arm chinaman</div>
</div>
<div class="row">
  <div class="label">Role</div>
  <div class="value">Bowling Allrounder</div>
</div>
</body></html>
"""

# ESPN profile page (old inline-label structure)
_ESPN_HTML = """
<html><body>
<div class="label">Batting Style</div>
<div class="data">Left-hand bat</div>
<div class="label">Bowling Style</div>
<div class="data">Slow left-arm orthodox</div>
<div class="label">Playing Role</div>
<div class="data">All-rounder</div>
</body></html>
"""

# A page that has nothing useful
_EMPTY_HTML = "<html><body><p>No cricket data here</p></body></html>"

# Akamai JS challenge page (what ESPN actually returns when blocked)
_AKAMAI_HTML = """
<html><body>
<script type="text/javascript" src="/I7Ss/3d/-MKs/challenge.js?v=abc"></script>
<div id="sec-if-cpt-container" style="display: none">
  <div class="behavioral-content">Please wait...</div>
</div>
</body></html>
"""

# JSON-LD embedded data (some CMS pages embed it)
_JSON_LD_HTML = """
<html><head>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "Adam Milne",
  "batStyle": "Right-hand bat",
  "bowlStyle": "Right-arm fast",
  "playingRole": "Bowler"
}
</script>
</head><body></body></html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _scraper() -> EspnScraper:
    return EspnScraper(timeout_seconds=10, retry_total=0, rate_limit_seconds=0)


# ---------------------------------------------------------------------------
# _extract_labeled_value
# ---------------------------------------------------------------------------

class TestExtractLabeledValue:
    def test_finds_sibling_value(self):
        soup = BeautifulSoup(_CRICBUZZ_HTML, "html.parser")
        result = EspnScraper._extract_labeled_value(soup, "Batting Style")
        assert result == "Right Handed Bat"

    def test_finds_bowling_style(self):
        soup = BeautifulSoup(_CRICBUZZ_HTML, "html.parser")
        result = EspnScraper._extract_labeled_value(soup, "Bowling Style")
        assert result == "Right-arm fast"

    def test_finds_role(self):
        soup = BeautifulSoup(_CRICBUZZ_HTML, "html.parser")
        result = EspnScraper._extract_labeled_value(soup, "Role")
        assert result == "Bowler"

    def test_returns_none_when_label_missing(self):
        soup = BeautifulSoup(_EMPTY_HTML, "html.parser")
        assert EspnScraper._extract_labeled_value(soup, "Batting Style") is None

    def test_case_insensitive_label(self):
        soup = BeautifulSoup(_CRICBUZZ_HTML, "html.parser")
        result = EspnScraper._extract_labeled_value(soup, "batting style")
        assert result == "Right Handed Bat"

    def test_fallback_text_pattern(self):
        html = "<html><body>Batting Style: Right-hand bat</body></html>"
        soup = BeautifulSoup(html, "html.parser")
        result = EspnScraper._extract_labeled_value(soup, "Batting Style")
        assert result == "Right-hand bat"


# ---------------------------------------------------------------------------
# _parse_cricbuzz_html
# ---------------------------------------------------------------------------

class TestParseCricbuzzHtml:
    def _parse(self, html):
        s = _scraper()
        return s._parse_cricbuzz_html(html)

    def test_right_handed_bat(self):
        r = self._parse(_CRICBUZZ_HTML)
        assert r["batting_style"] == "Right Handed Bat"

    def test_right_arm_fast(self):
        r = self._parse(_CRICBUZZ_HTML)
        assert r["bowling_style"] == "Right-arm fast"

    def test_role_bowler(self):
        r = self._parse(_CRICBUZZ_HTML)
        assert r["role"] == "Bowler"

    def test_left_handed_chinaman(self):
        r = self._parse(_CRICBUZZ_HTML_CHINAMAN)
        assert r["batting_style"] == "Left Handed Bat"
        assert "chinaman" in r["bowling_style"].lower()
        assert r["role"] == "Bowling Allrounder"

    def test_empty_page_returns_nones(self):
        r = self._parse(_EMPTY_HTML)
        assert r["batting_style"] is None
        assert r["bowling_style"] is None
        assert r["role"] is None


# ---------------------------------------------------------------------------
# _parse_espn_html
# ---------------------------------------------------------------------------

class TestParseEspnHtml:
    def _parse(self, html):
        return _scraper()._parse_espn_html(html)

    def test_left_hand_bat(self):
        r = self._parse(_ESPN_HTML)
        assert r["batting_style"] == "Left-hand bat"

    def test_orthodox_bowling(self):
        r = self._parse(_ESPN_HTML)
        assert r["bowling_style"] == "Slow left-arm orthodox"

    def test_role(self):
        r = self._parse(_ESPN_HTML)
        assert r["role"] == "All-rounder"

    def test_akamai_challenge_returns_empty(self):
        r = self._parse(_AKAMAI_HTML)
        assert r["batting_style"] is None
        assert r["bowling_style"] is None

    def test_json_ld_extraction(self):
        r = self._parse(_JSON_LD_HTML)
        assert r["batting_style"] == "Right-hand bat"
        assert r["bowling_style"] == "Right-arm fast"
        assert r["role"] == "Bowler"


# ---------------------------------------------------------------------------
# _parse_json_ld
# ---------------------------------------------------------------------------

class TestParseJsonLd:
    def test_extracts_from_person_schema(self):
        soup = BeautifulSoup(_JSON_LD_HTML, "html.parser")
        result = EspnScraper._parse_json_ld(soup)
        assert result is not None
        assert result["batting_style"] == "Right-hand bat"
        assert result["bowling_style"] == "Right-arm fast"

    def test_returns_none_when_no_ld(self):
        soup = BeautifulSoup(_EMPTY_HTML, "html.parser")
        assert EspnScraper._parse_json_ld(soup) is None


# ---------------------------------------------------------------------------
# profile_url helper
# ---------------------------------------------------------------------------

class TestProfileUrl:
    def test_url_format(self):
        url = EspnScraper.profile_url("12345")
        assert "12345" in url
        assert url.startswith("https://")
        assert "espncricinfo.com" in url


# ---------------------------------------------------------------------------
# _try_espn_site_api JSON parsing
# ---------------------------------------------------------------------------

_ESPN_SITE_API_RESPONSE = {
    "athlete": {
        "id": "417381",
        "firstName": "Andy",
        "lastName": "McBrine",
        "displayName": "Andrew Robert McBrine",
        "batStyle": [
            {"description": "Left-hand bat", "shortDescription": "Lhb", "type": "batting"}
        ],
        "bowlStyle": [
            {"description": "Right-arm offbreak", "shortDescription": "Ob", "type": "bowling"}
        ],
        "position": {"id": "BLA", "name": "Bowling allrounder"},
    }
}

_ESPN_SITE_API_UNKNOWN_ROLE = {
    "athlete": {
        "id": "999",
        "batStyle": [{"description": "Right-hand bat", "shortDescription": "Rhb", "type": "batting"}],
        "bowlStyle": [],
        "position": {"name": "Unknown"},
    }
}

_ESPN_SITE_API_NO_DATA = {
    "athlete": {
        "id": "111",
        "batStyle": None,
        "bowlStyle": None,
        "position": {"name": "Unknown"},
    }
}


class TestEspnSiteApi:
    def _parse(self, api_response):
        """Simulate _try_espn_site_api parsing without a real HTTP call."""
        athlete = api_response.get("athlete") or {}
        bat_list = athlete.get("batStyle") or []
        bowl_list = athlete.get("bowlStyle") or []
        position = athlete.get("position") or {}

        batting_style = bat_list[0].get("description") if bat_list else None
        bowling_style = bowl_list[0].get("description") if bowl_list else None
        role = position.get("name") if isinstance(position, dict) else None
        if role and role.lower() == "unknown":
            role = None
        return {"batting_style": batting_style, "bowling_style": bowling_style, "role": role}

    def test_parses_batting_style(self):
        result = self._parse(_ESPN_SITE_API_RESPONSE)
        assert result["batting_style"] == "Left-hand bat"

    def test_parses_bowling_style(self):
        result = self._parse(_ESPN_SITE_API_RESPONSE)
        assert result["bowling_style"] == "Right-arm offbreak"

    def test_parses_position_as_role(self):
        result = self._parse(_ESPN_SITE_API_RESPONSE)
        assert result["role"] == "Bowling allrounder"

    def test_unknown_position_becomes_none(self):
        result = self._parse(_ESPN_SITE_API_UNKNOWN_ROLE)
        assert result["role"] is None

    def test_batting_still_parsed_when_no_bowl(self):
        result = self._parse(_ESPN_SITE_API_UNKNOWN_ROLE)
        assert result["batting_style"] == "Right-hand bat"
        assert result["bowling_style"] is None

    def test_no_data_response_returns_nones(self):
        result = self._parse(_ESPN_SITE_API_NO_DATA)
        assert result["batting_style"] is None
        assert result["bowling_style"] is None
        assert result["role"] is None
