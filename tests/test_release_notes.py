"""Tests for the CHANGELOG -> release-body extractor.

Purpose: prove the published release notes really come from CHANGELOG.md, and
         that a missing section fails loudly instead of publishing nothing.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m4c
Tests:   this file

The producer (CHANGELOG.md, hand-written) and the consumer (this extractor) are
one contract. When they drift — a renamed heading, a changed format — the
failure mode to avoid is a release published with an empty body and a green
tick (P19). So the negative cases matter more here than the happy path.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools.extract_release_notes import (
    available_versions,
    extract_section,
    main,
    normalise_version,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

SAMPLE = """# Changelog

## [Unreleased]

## [0.2.0] - 2026-09-01

### Added

- A second thing.

## [0.1.0] - 2026-08-18

### Added

- The first thing.

### Fixed

- A bug.

[0.1.0]: https://example.invalid/releases/tag/v0.1.0
"""


# --------------------------------------------------------------------------
# Version normalisation
# --------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("v0.1.0", "0.1.0"),
    ("0.1.0", "0.1.0"),
    ("refs/tags/v0.1.0", "0.1.0"),
    ("V0.1.0", "0.1.0"),
    ("  v0.1.0  ", "0.1.0"),
])
def test_rm4c_normalise_version(raw, expected):
    assert normalise_version(raw) == expected


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

def test_rm4c_extracts_only_the_requested_section():
    body = extract_section(SAMPLE, "v0.1.0")
    assert "The first thing." in body
    assert "A bug." in body
    assert "A second thing." not in body, "leaked the next version's section"


def test_rm4c_extraction_stops_before_the_next_heading():
    body = extract_section(SAMPLE, "0.2.0")
    assert "A second thing." in body
    assert "The first thing." not in body


def test_rm4c_extraction_drops_link_reference_definitions():
    """`[0.1.0]: https://...` is file plumbing, not release notes."""
    body = extract_section(SAMPLE, "0.1.0")
    assert "https://example.invalid" not in body


def test_rm4c_extraction_omits_the_heading_itself():
    """GitHub already shows the tag; repeating it in the body is noise."""
    body = extract_section(SAMPLE, "0.1.0")
    assert not body.lstrip().startswith("## [")


def test_rm4c_available_versions_lists_every_heading():
    assert available_versions(SAMPLE) == ["Unreleased", "0.2.0", "0.1.0"]


# --------------------------------------------------------------------------
# Failure modes — the point of the exercise
# --------------------------------------------------------------------------

def test_rm4c_missing_version_raises_rather_than_returning_empty():
    with pytest.raises(KeyError):
        extract_section(SAMPLE, "v9.9.9")


def test_rm4c_empty_section_raises():
    """A heading with nothing under it must not become an empty release body."""
    empty = "# Changelog\n\n## [0.1.0] - 2026-08-18\n\n## [0.0.9] - 2026-01-01\n\n- old\n"
    with pytest.raises(ValueError):
        extract_section(empty, "0.1.0")


def test_rm4c_cli_exits_nonzero_for_a_missing_version(tmp_path, capsys):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE, encoding="utf-8")
    code = main(["v9.9.9", "--changelog", str(changelog)])
    assert code == 1
    assert "no section" in capsys.readouterr().err.lower()


def test_rm4c_cli_exits_nonzero_when_the_changelog_is_absent(tmp_path, capsys):
    code = main(["v0.1.0", "--changelog", str(tmp_path / "nope.md")])
    assert code == 2


def test_rm4c_cli_writes_the_output_file(tmp_path):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(SAMPLE, encoding="utf-8")
    out = tmp_path / "RELEASE_NOTES.md"

    code = main(["v0.1.0", "--changelog", str(changelog), "--output", str(out)])
    assert code == 0
    assert "The first thing." in out.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Against the real CHANGELOG — the contract that actually ships
# --------------------------------------------------------------------------

def test_rm4c_real_changelog_has_a_v0_1_0_section_the_extractor_can_read():
    """Verified against the real artifact, not a synthetic sample (P19)."""
    body = extract_section(CHANGELOG.read_text(encoding="utf-8"), "v0.1.0")
    assert len(body) > 200, "the v0.1.0 release body is suspiciously short"
    assert "crashed on launch" in body.lower(), (
        "the extracted body is missing the headline fix — check the section "
        "boundaries, not just that something was returned"
    )


def test_rm4c_real_changelog_extraction_excludes_unreleased():
    body = extract_section(CHANGELOG.read_text(encoding="utf-8"), "v0.1.0")
    assert "[Unreleased]" not in body


def test_rm4c_script_runs_as_a_subprocess_the_way_ci_invokes_it(tmp_path):
    """CI runs `python tools/extract_release_notes.py <tag> --output ...`."""
    out = tmp_path / "RELEASE_NOTES.md"
    result = subprocess.run(
        [sys.executable, "tools/extract_release_notes.py", "v0.1.0",
         "--output", str(out)],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.exists() and out.read_text(encoding="utf-8").strip()
