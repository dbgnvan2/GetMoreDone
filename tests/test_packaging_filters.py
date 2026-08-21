"""Tests for the bundle-content filter.

Purpose: prove the filter drops only what an end user does not need, and never
         the two Google discovery documents the app depends on.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1a
Tests:   this file

The risk here is asymmetric. Keeping a file that is not needed costs disk
space; dropping one that *is* needed breaks a feature in the packaged app only,
where it will not show up in any source-run test. So the keep cases below carry
more weight than the drop cases, and they are asserted against the real
`googleapiclient` layout rather than an invented one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.packaging_filters import (
    DISCOVERY_KEEP,
    EXCLUDED_FROM_BUNDLE,
    filter_datas,
    should_bundle,
)

# This whole file asserts on the REPOSITORY — workflows, packaging, licences,
# docs, traceability — not on application behaviour. Marked `meta` so
# `pytest -m "not meta"` gives a fast app-only run. The default `pytest` run
# still includes it: the marker is for speed, never for skipping.
pytestmark = pytest.mark.meta

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS = "googleapiclient/discovery_cache/documents"


# --------------------------------------------------------------------------
# The app's own Google services must survive
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(DISCOVERY_KEEP))
def test_required_discovery_documents_are_kept(name):
    assert should_bundle(f"{DOCS}/{name}") is True


def test_keep_list_matches_the_services_the_code_actually_builds():
    """Derived from the source, not from a comment.

    If someone adds a third `build("drive", "v3", ...)` call, this fails and
    points at the keep list — rather than the packaged app quietly losing Drive.
    """
    import re

    services = set()
    for rel in ("src/getmoredone/google_calendar.py", "src/getmoredone/gmail_importer.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for api, version in re.findall(r"build\(\s*[\"'](\w+)[\"']\s*,\s*[\"'](\w+)[\"']", text):
            services.add(f"{api}.{version}.json")

    assert services, "found no build() calls to derive the keep list from"
    missing = sorted(services - set(DISCOVERY_KEEP))
    assert not missing, (
        f"the code builds Google services whose discovery documents the "
        f"packaging filter drops: {missing}. Add them to DISCOVERY_KEEP."
    )


def test_required_discovery_documents_exist_upstream():
    """Ground truth: a keep entry naming a file that does not exist keeps nothing."""
    import googleapiclient

    docs_dir = Path(googleapiclient.__file__).parent / "discovery_cache/documents"
    if not docs_dir.is_dir():
        pytest.skip("googleapiclient discovery cache not present in this environment")
    for name in DISCOVERY_KEEP:
        assert (docs_dir / name).exists(), (
            f"DISCOVERY_KEEP names {name}, which does not exist upstream"
        )


# --------------------------------------------------------------------------
# Everything else in the discovery cache goes
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "adsense.v2.json", "youtube.v3.json", "bigquery.v2.json",
    "gmailpostmastertools.v1.json", "calendar.v3beta.json",
])
def test_unused_discovery_documents_are_dropped(name):
    assert should_bundle(f"{DOCS}/{name}") is False


def test_filter_is_not_a_no_op_on_the_real_cache():
    """Adversarial: a filter that keeps everything would pass every keep test."""
    import googleapiclient

    docs_dir = Path(googleapiclient.__file__).parent / "discovery_cache/documents"
    if not docs_dir.is_dir():
        pytest.skip("googleapiclient discovery cache not present in this environment")

    entries = [(f"{DOCS}/{p.name}", str(p), "DATA") for p in docs_dir.glob("*.json")]
    kept, dropped = filter_datas(entries)

    assert len(dropped) > 100, (
        f"expected the filter to drop most of the discovery cache, dropped "
        f"{len(dropped)} of {len(entries)}"
    )
    assert {Path(k[0]).name for k in kept} == set(DISCOVERY_KEEP)


# --------------------------------------------------------------------------
# Developer-only files
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", sorted(EXCLUDED_FROM_BUNDLE))
def test_developer_only_files_are_dropped(path):
    assert should_bundle(path) is False


def test_the_lgpl_text_is_never_dropped():
    """The LGPL requires the licence to accompany the distribution — dropping it
    would be a licence violation, not a size optimisation."""
    assert should_bundle("licenses/pygame-LGPL-2.1.txt") is True


def test_excluded_theme_is_not_selectable_from_settings():
    """Justifies excluding base_dark_blue.json: no user can ever pick it."""
    from src.getmoredone import theme

    assert "base_dark_blue" not in theme.THEME_NAMES


def test_every_selectable_theme_survives_the_filter():
    """The F1 class again: a theme the user can pick must reach the bundle."""
    from src.getmoredone import theme

    for name in theme.THEME_NAMES:
        assert should_bundle(f"themes/{name}.json") is True, (
            f"the packaging filter drops a selectable theme: {name}"
        )


# --------------------------------------------------------------------------
# Everything not named is kept
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", [
    "assets/icons/davipa.icns",
    "themes/apple_grey.json",
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "customtkinter/assets/themes/blue.json",
    "pygame/base.cpython-311-darwin.so",
])
def test_ordinary_files_are_kept(path):
    assert should_bundle(path) is True


def test_windows_style_separators_are_handled():
    """PyInstaller emits native separators; the filter must not miss on Windows."""
    assert should_bundle("googleapiclient\\discovery_cache\\documents\\youtube.v3.json") is False
    assert should_bundle("googleapiclient\\discovery_cache\\documents\\calendar.v3.json") is True
    assert should_bundle("themes\\base_dark_blue.json") is False


def test_filter_datas_reports_both_halves():
    """The spec prints what it dropped; silence would hide a bad filter (P2)."""
    entries = [
        ("themes/apple_grey.json", "/src/a", "DATA"),
        (f"{DOCS}/youtube.v3.json", "/src/b", "DATA"),
    ]
    kept, dropped = filter_datas(entries)
    assert [k[0] for k in kept] == ["themes/apple_grey.json"]
    assert [d[0] for d in dropped] == [f"{DOCS}/youtube.v3.json"]


def test_spec_applies_the_filter():
    """Built-but-not-wired guard (P21): the module could exist and never run."""
    spec = (REPO_ROOT / "daVIPA.spec").read_text(encoding="utf-8")
    code = "\n".join(l for l in spec.splitlines() if not l.strip().startswith("#"))
    assert "filter_datas" in code, "daVIPA.spec never applies the packaging filter"
    assert "a.datas" in code


@pytest.mark.parametrize("path", [
    "assets/.DS_Store",
    "assets/icons/.DS_Store",
    "themes/Thumbs.db",
])
def test_os_debris_is_dropped(path):
    """A .DS_Store from the building Mac would make a local build differ from
    a CI build, and ships a file no end user needs."""
    assert should_bundle(path) is False


def test_os_debris_exclusion_does_not_catch_real_files():
    """Adversarial: matching too broadly would drop legitimate resources."""
    assert should_bundle("assets/icons/davipa.icns") is True
    assert should_bundle("themes/apple_grey.json") is True
