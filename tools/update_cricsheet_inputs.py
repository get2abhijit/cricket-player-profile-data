from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, Iterable, Optional
import zipfile

import requests


REGISTER_URL_BASE = "https://cricsheet.org/register"
DOWNLOAD_URL_BASE = "https://cricsheet.org/downloads"
FULL_T20_MALE_ZIP = f"{DOWNLOAD_URL_BASE}/t20s_male_json.zip"
RECENT_MALE_ZIP_TEMPLATE = f"{DOWNLOAD_URL_BASE}/recently_added_{{days}}_male_json.zip"

DEFAULT_REGISTRY_DIR = Path("data/registry_csv")
DEFAULT_MATCHES_DIR = Path("data/matches_json")
README_FILENAME = "README.txt"

T20_MATCH_TYPES = {"T20", "IT20"}
README_LINE_RE = re.compile(
    r"^(?P<match_date>\d{4}-\d{2}-\d{2})\s+-\s+"
    r"(?P<team_type>[^-]+)\s+-\s+"
    r"(?P<match_type>[^-]+)\s+-\s+"
    r"(?P<gender>[^-]+)\s+-\s+"
    r"(?P<match_id>\d+)\s+-\s+"
    r"(?P<description>.+)$"
)


@dataclass(frozen=True)
class ReadmeMatchEntry:
    match_id: str
    match_date: str
    team_type: str
    match_type: str
    gender: str
    description: str

    def to_line(self) -> str:
        return (
            f"{self.match_date} - {self.team_type} - {self.match_type} - "
            f"{self.gender} - {self.match_id} - {self.description}"
        )


@dataclass(frozen=True)
class ExtractionSummary:
    selected_t20_male: int
    extracted_added: int
    extracted_updated: int
    extracted_unchanged: int
    missing_in_zip: int
    readme_lines_seen: int
    readme_updated: bool

    @property
    def has_changes(self) -> bool:
        return self.extracted_added > 0 or self.extracted_updated > 0 or self.readme_updated


def _files_equal(first: Path, second: Path) -> bool:
    try:
        if first.stat().st_size != second.stat().st_size:
            return False
    except OSError:
        return False

    chunk_size = 1024 * 1024
    try:
        with first.open("rb") as first_handle, second.open("rb") as second_handle:
            while True:
                first_chunk = first_handle.read(chunk_size)
                second_chunk = second_handle.read(chunk_size)
                if first_chunk != second_chunk:
                    return False
                if not first_chunk:
                    return True
    except OSError:
        return False


def _download_file(url: str, destination: Path, timeout: int = 60) -> tuple[Path, bool]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with NamedTemporaryFile("wb", delete=False, dir=str(destination.parent)) as tmp_handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    tmp_handle.write(chunk)
            tmp_path = Path(tmp_handle.name)

    if destination.exists() and _files_equal(tmp_path, destination):
        tmp_path.unlink(missing_ok=True)
        return destination, False

    tmp_path.replace(destination)
    return destination, True


def _download_registry(registry_dir: Path, timeout: int = 60) -> Dict[str, bool]:
    registry_dir.mkdir(parents=True, exist_ok=True)
    changed_by_file: Dict[str, bool] = {}
    for filename in ("people.csv", "names.csv"):
        url = f"{REGISTER_URL_BASE}/{filename}"
        target = registry_dir / filename
        _, changed = _download_file(url=url, destination=target, timeout=timeout)
        changed_by_file[filename] = changed
        status = "updated" if changed else "unchanged"
        print(f"Downloaded {filename} -> {target} ({status})")
    return changed_by_file


def parse_readme_entries(readme_text: str) -> Dict[str, ReadmeMatchEntry]:
    entries: Dict[str, ReadmeMatchEntry] = {}
    for raw_line in readme_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = README_LINE_RE.match(line)
        if not match:
            continue

        entry = ReadmeMatchEntry(
            match_id=match.group("match_id"),
            match_date=match.group("match_date"),
            team_type=match.group("team_type").strip(),
            match_type=match.group("match_type").strip(),
            gender=match.group("gender").strip(),
            description=match.group("description").strip(),
        )
        entries[entry.match_id] = entry
    return entries


def filter_t20_male(entries: Dict[str, ReadmeMatchEntry]) -> Dict[str, ReadmeMatchEntry]:
    return {
        match_id: entry
        for match_id, entry in entries.items()
        if entry.gender.lower() == "male" and entry.match_type.upper() in T20_MATCH_TYPES
    }


def _read_existing_readme_entries(readme_path: Path) -> Dict[str, ReadmeMatchEntry]:
    if not readme_path.exists():
        return {}
    try:
        return parse_readme_entries(readme_path.read_text(encoding="utf-8"))
    except OSError:
        return {}


def _build_compact_readme(entries: Iterable[ReadmeMatchEntry]) -> str:
    lines = [entry.to_line() for entry in entries]
    header = [
        "Auto-maintained T20/IT20 male match index for pipeline incremental detection.",
        "Source: Cricsheet downloads (README.txt lines merged from refresh runs).",
        "",
    ]
    if not lines:
        return "\n".join(header) + "\n"
    return "\n".join(header + lines) + "\n"


def merge_and_write_readme(
    readme_path: Path,
    existing_entries: Dict[str, ReadmeMatchEntry],
    fresh_entries: Dict[str, ReadmeMatchEntry],
) -> bool:
    merged = dict(existing_entries)
    merged.update(fresh_entries)

    sorted_entries = sorted(
        merged.values(),
        key=lambda item: (item.match_date, item.match_id),
        reverse=True,
    )
    new_content = _build_compact_readme(sorted_entries)

    old_content = ""
    if readme_path.exists():
        try:
            old_content = readme_path.read_text(encoding="utf-8")
        except OSError:
            old_content = ""

    if new_content == old_content:
        return False

    readme_path.parent.mkdir(parents=True, exist_ok=True)
    readme_path.write_text(new_content, encoding="utf-8")
    return True


def extract_t20_matches_from_zip(zip_path: Path, matches_dir: Path) -> ExtractionSummary:
    if not zip_path.exists():
        raise FileNotFoundError(f"Zip file not found: {zip_path}")

    matches_dir.mkdir(parents=True, exist_ok=True)
    readme_path = matches_dir / README_FILENAME
    existing_readme_entries = _read_existing_readme_entries(readme_path)

    with zipfile.ZipFile(zip_path, "r") as archive:
        names = set(archive.namelist())
        readme_name = README_FILENAME if README_FILENAME in names else None
        if readme_name is None:
            for name in names:
                if name.lower() == README_FILENAME.lower():
                    readme_name = name
                    break
        if readme_name is None:
            raise RuntimeError(f"{README_FILENAME} not found in {zip_path}")

        readme_text = archive.read(readme_name).decode("utf-8", errors="replace")
        parsed_entries = parse_readme_entries(readme_text)
        t20_male_entries = filter_t20_male(parsed_entries)

        added = 0
        updated = 0
        unchanged = 0
        missing = 0

        for match_id in sorted(t20_male_entries.keys()):
            zip_member = f"{match_id}.json"
            if zip_member not in names:
                missing += 1
                continue

            payload = archive.read(zip_member)
            target = matches_dir / zip_member
            if target.exists():
                try:
                    existing = target.read_bytes()
                except OSError:
                    existing = b""

                if existing == payload:
                    unchanged += 1
                    continue

                updated += 1
            else:
                added += 1

            target.write_bytes(payload)

    readme_updated = merge_and_write_readme(readme_path, existing_readme_entries, t20_male_entries)

    return ExtractionSummary(
        selected_t20_male=len(t20_male_entries),
        extracted_added=added,
        extracted_updated=updated,
        extracted_unchanged=unchanged,
        missing_in_zip=missing,
        readme_lines_seen=len(parsed_entries),
        readme_updated=readme_updated,
    )


def _match_zip_url(days: int) -> str:
    if days not in (2, 7):
        raise ValueError("days must be one of: 2, 7")
    return RECENT_MALE_ZIP_TEMPLATE.format(days=days)


def _looks_bootstrapped(matches_dir: Path) -> bool:
    return any(matches_dir.glob("*.json"))


def _run_bootstrap_if_needed(matches_dir: Path, timeout: int) -> Optional[ExtractionSummary]:
    if _looks_bootstrapped(matches_dir):
        return None

    print("No existing matches detected. Bootstrapping from full T20 men archive...")
    bootstrap_zip = matches_dir.parent / "t20s_male_json.zip"
    _, zip_changed = _download_file(FULL_T20_MALE_ZIP, bootstrap_zip, timeout=timeout)
    zip_status = "updated" if zip_changed else "unchanged"
    print(f"Downloaded bootstrap zip: {FULL_T20_MALE_ZIP} -> {bootstrap_zip} ({zip_status})")
    summary = extract_t20_matches_from_zip(bootstrap_zip, matches_dir)
    print(
        "Bootstrap summary: "
        f"selected={summary.selected_t20_male}, "
        f"added={summary.extracted_added}, "
        f"updated={summary.extracted_updated}, "
        f"unchanged={summary.extracted_unchanged}, "
        f"missing={summary.missing_in_zip}, "
        f"readme_updated={summary.readme_updated}"
    )
    return summary


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Refresh Cricsheet inputs (people.csv, names.csv, and men T20/IT20 match JSON files) "
            "for the local pipeline."
        )
    )
    parser.add_argument(
        "--window-days",
        type=int,
        choices=(2, 7),
        default=7,
        help="Recent archive window to use from Cricsheet downloads.",
    )
    parser.add_argument(
        "--full-archive",
        action="store_true",
        help="Use full t20s_male_json.zip instead of a recent window archive.",
    )
    parser.add_argument(
        "--zip-file",
        type=Path,
        default=None,
        help="Use an already-downloaded zip file instead of fetching from Cricsheet.",
    )
    parser.add_argument(
        "--skip-registry",
        action="store_true",
        help="Skip downloading people.csv and names.csv.",
    )
    parser.add_argument(
        "--skip-matches",
        action="store_true",
        help="Skip updating match JSON files.",
    )
    parser.add_argument(
        "--registry-dir",
        type=Path,
        default=DEFAULT_REGISTRY_DIR,
        help="Directory where people.csv and names.csv are stored.",
    )
    parser.add_argument(
        "--matches-dir",
        type=Path,
        default=DEFAULT_MATCHES_DIR,
        help="Directory where match JSON files and README.txt are stored.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="HTTP timeout in seconds.",
    )
    parser.add_argument(
        "--no-bootstrap",
        action="store_true",
        help="Do not auto-download the full T20 men archive when matches directory is empty.",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Optional path to write machine-readable refresh summary JSON.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    registry_changes: Dict[str, bool] = {}
    registry_changed = False

    if not args.skip_registry:
        registry_changes = _download_registry(registry_dir=args.registry_dir, timeout=args.timeout)
        registry_changed = any(registry_changes.values())

    if args.skip_matches:
        print("Skipped matches update")
        summary_payload = {
            "registry": registry_changes,
            "registry_changed": registry_changed,
            "matches": None,
            "matches_changed": False,
            "changed": registry_changed,
        }
        if args.summary_json:
            args.summary_json.parent.mkdir(parents=True, exist_ok=True)
            args.summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")
        return 0

    bootstrap_summary: Optional[ExtractionSummary] = None
    if not args.no_bootstrap:
        bootstrap_summary = _run_bootstrap_if_needed(matches_dir=args.matches_dir, timeout=args.timeout)

    zip_path: Path
    if args.zip_file:
        zip_path = args.zip_file
        print(f"Using local zip: {zip_path}")
    else:
        if args.full_archive:
            zip_url = FULL_T20_MALE_ZIP
            zip_path = args.matches_dir.parent / "t20s_male_json.zip"
        else:
            zip_url = _match_zip_url(args.window_days)
            zip_path = args.matches_dir.parent / f"recently_added_{args.window_days}_male_json.zip"

        _, zip_changed = _download_file(zip_url, zip_path, timeout=args.timeout)
        zip_status = "updated" if zip_changed else "unchanged"
        print(f"Downloaded matches zip: {zip_url} -> {zip_path} ({zip_status})")

    summary = extract_t20_matches_from_zip(zip_path=zip_path, matches_dir=args.matches_dir)
    bootstrap_changed = bool(bootstrap_summary and bootstrap_summary.has_changes)
    matches_changed = bootstrap_changed or summary.has_changes
    print(
        "Matches update summary: "
        f"readme_lines={summary.readme_lines_seen}, "
        f"selected_t20_male={summary.selected_t20_male}, "
        f"added={summary.extracted_added}, "
        f"updated={summary.extracted_updated}, "
        f"unchanged={summary.extracted_unchanged}, "
        f"missing={summary.missing_in_zip}, "
        f"readme_updated={summary.readme_updated}"
    )

    summary_payload = {
        "registry": registry_changes,
        "registry_changed": registry_changed,
        "matches": {
            "readme_lines_seen": summary.readme_lines_seen,
            "selected_t20_male": summary.selected_t20_male,
            "extracted_added": summary.extracted_added,
            "extracted_updated": summary.extracted_updated,
            "extracted_unchanged": summary.extracted_unchanged,
            "missing_in_zip": summary.missing_in_zip,
            "readme_updated": summary.readme_updated,
            "bootstrap_changed": bootstrap_changed,
        },
        "matches_changed": matches_changed,
        "changed": registry_changed or matches_changed,
    }
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())