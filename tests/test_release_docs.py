"""Documentation contract tests for the downloadable release.

Purpose: keep the release docs factually in step with the code and the artifacts.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m5d, #r-m6
Tests:   this file

These tests assert **presence and accuracy of specific strings**, which is all
that is code-testable. Whether the docs are any *good* is not — that needs a
person to read INSTALL.md once as a first-time user. Flagged HUMAN in the plan
and still outstanding.

Where a doc makes a checkable claim about the code (a command that must exist, a
path the app really uses), the test checks it against the code rather than
against another doc — otherwise two documents can agree with each other and
both be wrong.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# This whole file asserts on the REPOSITORY — workflows, packaging, licences,
# docs, traceability — not on application behaviour. Marked `meta` so
# `pytest -m "not meta"` gives a fast app-only run. The default `pytest` run
# still includes it: the marker is for speed, never for skipping.
pytestmark = pytest.mark.meta

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL = REPO_ROOT / "INSTALL.md"
README = REPO_ROOT / "README.md"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
STANDALONE = REPO_ROOT / "docs/STANDALONE_BUILD.md"


# --------------------------------------------------------------------------
# R-M6.A — INSTALL.md covers the whole first-run path
# --------------------------------------------------------------------------

def test_rm6a_install_doc_exists():
    assert INSTALL.exists(), "no INSTALL.md"


REQUIRED_INSTALL_TOPICS = {
    "download per OS": ("daVIPA-mac.zip", "daVIPA-win64.zip"),
    "run from source": ("start.sh", "requirements.txt"),
    "optional Google setup": ("credentials.json",),
    "optional music folder": ("Settings",),
    "where data is stored": ("Application Support", "APPDATA"),
    "uninstall": ("Uninstalling",),
    "checksum verification": ("sha256",),
}


@pytest.mark.parametrize("topic,markers", sorted(REQUIRED_INSTALL_TOPICS.items()))
def test_rm6a_install_doc_has_required_sections(topic, markers):
    text = INSTALL.read_text(encoding="utf-8")
    missing = [m for m in markers if m.lower() not in text.lower()]
    assert not missing, f"INSTALL.md does not cover {topic}: missing {missing}"


# --------------------------------------------------------------------------
# R-M5.D — the Gatekeeper workaround, with the exact command
# --------------------------------------------------------------------------

def test_rm5d_install_doc_documents_gatekeeper_step():
    """D2: the macOS build ships unsigned, so this step is required, not optional."""
    text = INSTALL.read_text(encoding="utf-8")
    assert "xattr -d com.apple.quarantine" in text, (
        "INSTALL.md must give the exact quarantine command — without it a "
        "downloaded macOS build looks broken on first launch"
    )
    assert "unsigned" in text.lower() or "not signed" in text.lower(), (
        "INSTALL.md should say why the step is needed"
    )


def test_rm5d_install_doc_documents_the_sequoia_path():
    """Apple removed the Control-click override in macOS 15.

    Leading with Control-click sends anyone on a current Mac down a path that
    no longer exists. The System Settings route must be present and attached to
    the version that needs it.
    """
    text = INSTALL.read_text(encoding="utf-8")
    for marker in ("Privacy & Security", "Open Anyway", "Sequoia"):
        assert marker in text, (
            f"INSTALL.md does not document the macOS 15+ approval path: {marker!r} "
            "is missing. Control-click alone is wrong for every current Mac."
        )


def test_rm5d_install_doc_does_not_present_control_click_as_the_current_route():
    """Control-click may be documented for macOS 14 and earlier, but must not be
    offered as the general answer."""
    text = INSTALL.read_text(encoding="utf-8")
    control_click = text.find("Control-click")
    settings = text.find("Privacy & Security")
    assert control_click == -1 or settings < control_click, (
        "INSTALL.md offers Control-click before the System Settings route; on "
        "macOS 15+ the former does nothing"
    )


def test_rm5d_readme_also_carries_the_gatekeeper_step():
    """Someone who never opens INSTALL.md still hits this on first launch."""
    assert "xattr -d com.apple.quarantine" in README.read_text(encoding="utf-8")


def test_rm5d_gatekeeper_command_targets_the_real_app_name():
    """The command must name the bundle the release actually produces."""
    spec = (REPO_ROOT / "daVIPA.spec").read_text(encoding="utf-8")
    # Whatever the spec calls the bundle, not a pinned literal. Hardcoding the
    # name here made the test assert the rename had NOT happened, which is the
    # opposite of "names the bundle the release actually produces".
    bundle = re.search(r'name="([^"]+\.app)"', spec)
    assert bundle, "could not find the .app name in daVIPA.spec"
    assert bundle.group(1) in INSTALL.read_text(encoding="utf-8"), (
        f"INSTALL.md does not mention {bundle.group(1)}, the bundle the spec builds"
    )


# --------------------------------------------------------------------------
# R-M6.B — README leads with Download and links the licence
# --------------------------------------------------------------------------

def test_rm6b_readme_quick_start_leads_with_download():
    text = README.read_text(encoding="utf-8")
    quick_start = text.index("## Quick Start")
    section = text[quick_start:quick_start + 1200]
    download_at = section.lower().find("download")
    source_at = section.lower().find("from source")
    assert download_at != -1, "README Quick Start does not mention downloading"
    assert source_at == -1 or download_at < source_at, (
        "README Quick Start leads with run-from-source; a downloadable release "
        "should lead with the download"
    )


def test_rm6b_readme_links_license_and_install():
    text = README.read_text(encoding="utf-8")
    for target in ("LICENSE", "INSTALL.md", "THIRD_PARTY_NOTICES.md"):
        assert target in text, f"README does not link {target}"


def test_rm6b_readme_links_resolve_to_real_files():
    """A link to a file that does not exist is worse than no link."""
    text = README.read_text(encoding="utf-8")
    broken = []
    for target in re.findall(r"\]\(([^)#][^)]*)\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path = REPO_ROOT / target.split("#", 1)[0]
        if not path.exists():
            broken.append(target)
    assert not broken, f"README links to missing files: {broken}"


def test_rm6b_install_doc_links_resolve_to_real_files():
    text = INSTALL.read_text(encoding="utf-8")
    broken = []
    for target in re.findall(r"\]\(([^)#][^)]*)\)", text):
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        path = REPO_ROOT / target.split("#", 1)[0]
        if not path.exists():
            broken.append(target)
    assert not broken, f"INSTALL.md links to missing files: {broken}"


def test_rm6b_docs_do_not_reference_the_moved_auth_script():
    """`test_auth.py` no longer exists; a doc telling users to run it is a dead end."""
    offenders = []
    for doc in (README, INSTALL, CHANGELOG):
        if "python3 test_auth.py" in doc.read_text(encoding="utf-8"):
            offenders.append(doc.name)
    assert not offenders, f"docs still tell users to run test_auth.py: {offenders}"


# --------------------------------------------------------------------------
# R-M6.C — the stale claim in STANDALONE_BUILD.md is gone
# --------------------------------------------------------------------------

def test_rm6c_standalone_build_doc_has_no_stale_spec_claim():
    """It said "We can add a .spec file later if needed" — it has existed for months."""
    text = STANDALONE.read_text(encoding="utf-8")
    assert "add a `.spec` file later" not in text, (
        "docs/STANDALONE_BUILD.md still says the spec file could be added later"
    )
    assert "daVIPA.spec" in text


def test_rm6c_standalone_build_doc_does_not_recommend_onefile():
    """--onefile would break the LGPL relink guarantee (F3)."""
    text = STANDALONE.read_text(encoding="utf-8").lower()
    assert "do not switch to `--onefile`" in text or "do not switch to --onefile" in text, (
        "STANDALONE_BUILD.md should warn against --onefile, not suggest it"
    )


# --------------------------------------------------------------------------
# R-M6.D — CHANGELOG with a v0.1.0 entry
# --------------------------------------------------------------------------

def test_rm6d_changelog_exists():
    assert CHANGELOG.exists(), "no CHANGELOG.md"


def test_rm6d_changelog_has_v0_2_0_entry():
    text = CHANGELOG.read_text(encoding="utf-8")
    assert re.search(r"^## \[0\.2\.0\]", text, re.MULTILINE), (
        "CHANGELOG.md has no [0.2.0] section"
    )


def test_rm6d_changelog_records_the_launch_crash_fix():
    """The headline fix of this release must be in its notes."""
    text = CHANGELOG.read_text(encoding="utf-8").lower()
    assert "crashed on launch" in text or "crash on launch" in text, (
        "CHANGELOG does not mention that previous binaries crashed on launch"
    )


def test_rm6d_changelog_records_the_known_limitations():
    """An unsigned build and no Linux binary are things a downloader must know."""
    text = CHANGELOG.read_text(encoding="utf-8").lower()
    for expected in ("unsigned", "linux"):
        assert expected in text, f"CHANGELOG does not state the {expected} limitation"


def test_rm6d_changelog_version_matches_the_release_tag_format():
    """R-M4.C reads this section by tag name, so the heading must be parseable."""
    text = CHANGELOG.read_text(encoding="utf-8")
    versions = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    assert versions, "no parseable version headings in CHANGELOG.md"
    for version in versions:
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
