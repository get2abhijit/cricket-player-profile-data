from __future__ import annotations

import zipfile

from tools.update_cricsheet_inputs import (
    extract_t20_matches_from_zip,
    filter_t20_male,
    parse_readme_entries,
)


def _make_zip(path, readme_text: str, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme_text)
        for name, payload in members.items():
            archive.writestr(name, payload)


def test_parse_and_filter_t20_male_entries() -> None:
    readme = "\n".join(
        [
            "2026-10-24 - club - ODC - male - 1544852 - Victoria vs Tasmania",
            "2026-10-24 - international - T20 - male - 1544853 - Team A vs Team B",
            "2026-10-23 - international - IT20 - male - 1544867 - Team C vs Team D",
            "2026-10-23 - international - T20 - female - 1544868 - Team E vs Team F",
        ]
    )

    entries = parse_readme_entries(readme)
    selected = filter_t20_male(entries)

    assert set(entries.keys()) == {"1544852", "1544853", "1544867", "1544868"}
    assert set(selected.keys()) == {"1544853", "1544867"}


def test_extract_t20_matches_and_merge_readme(tmp_path) -> None:
    matches_dir = tmp_path / "matches"
    matches_dir.mkdir()

    existing_readme = (
        "Auto-maintained T20/IT20 male match index for pipeline incremental detection.\n"
        "Source: Cricsheet downloads (README.txt lines merged from refresh runs).\n\n"
        "2026-10-20 - international - T20 - male - 1000 - Old Team A vs Old Team B\n"
    )
    (matches_dir / "README.txt").write_text(existing_readme, encoding="utf-8")

    zip_path = tmp_path / "recently_added_7_male_json.zip"
    readme = "\n".join(
        [
            "2026-10-24 - club - ODC - male - 2001 - Team X vs Team Y",
            "2026-10-24 - international - T20 - male - 2002 - Team A vs Team B",
            "2026-10-23 - international - IT20 - male - 2003 - Team C vs Team D",
            "2026-10-23 - international - T20 - female - 2004 - Team E vs Team F",
        ]
    )
    _make_zip(
        zip_path,
        readme,
        {
            "2002.json": b"{\"info\": {\"match_type\": \"T20\"}}",
            "2003.json": b"{\"info\": {\"match_type\": \"IT20\"}}",
            "2001.json": b"{\"info\": {\"match_type\": \"ODI\"}}",
        },
    )

    summary = extract_t20_matches_from_zip(zip_path=zip_path, matches_dir=matches_dir)

    assert summary.selected_t20_male == 2
    assert summary.extracted_added == 2
    assert summary.extracted_updated == 0
    assert summary.extracted_unchanged == 0
    assert summary.missing_in_zip == 0
    assert summary.readme_updated is True

    assert (matches_dir / "2002.json").exists()
    assert (matches_dir / "2003.json").exists()
    assert not (matches_dir / "2001.json").exists()

    merged_entries = parse_readme_entries((matches_dir / "README.txt").read_text(encoding="utf-8"))
    assert set(merged_entries.keys()) == {"1000", "2002", "2003"}

    # Running again should mark both extracted files as unchanged.
    rerun = extract_t20_matches_from_zip(zip_path=zip_path, matches_dir=matches_dir)
    assert rerun.extracted_added == 0
    assert rerun.extracted_updated == 0
    assert rerun.extracted_unchanged == 2
    assert rerun.readme_updated is False