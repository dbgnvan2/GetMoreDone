"""Decide which collected files belong in a distributed build.

Purpose: keep out of the download anything an end user running the app does not
         need, without dropping anything the app does need.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1a
Tests:   tests/test_packaging_filters.py

Imported by ``GetMoreDone.spec`` to filter PyInstaller's collected ``datas``.
The logic lives here rather than inline in the spec because a spec file cannot
be imported or unit-tested — and dropping the wrong file here silently breaks a
feature in the packaged app only, where nobody sees it until a user does.

The big one is googleapiclient's discovery cache: PyInstaller collects a
discovery document for **every** Google API, ~93 MB across 569 files, when this
app calls exactly two of them.
"""

from __future__ import annotations

from pathlib import PurePosixPath

# Google API discovery documents this app actually builds a service for.
# google_calendar.py: build("calendar", "v3", ...)
# gmail_importer.py:  build("gmail", "v1", ...)
#
# google-api-python-client v2 prefers the STATIC discovery document shipped in
# the package, so these two must survive the filter or both integrations break
# in the packaged app while continuing to work from source.
DISCOVERY_KEEP = frozenset({
    "calendar.v3.json",
    "gmail.v1.json",
})

_DISCOVERY_MARKER = "googleapiclient/discovery_cache/documents/"

# Files that are collected but only matter to someone developing GetMoreDone.
EXCLUDED_FROM_BUNDLE = frozenset({
    # Input for tools/generate_ctk_themes.py; not offered in Settings, so an
    # end user can never select it.
    "themes/base_dark_blue.json",
    # Explains to a maintainer where the vendored licence text came from. The
    # licence text itself (licenses/pygame-LGPL-2.1.txt) must stay — the LGPL
    # requires it to accompany the distribution.
    "licenses/README.md",
})


def _normalise(dest: str) -> str:
    """PyInstaller emits OS-native separators; compare on one form."""
    return PurePosixPath(str(dest).replace("\\", "/")).as_posix()


def should_bundle(dest: str) -> bool:
    """True if a collected file belongs in the distributed application.

    Args:
        dest: the file's destination path *inside* the bundle, as PyInstaller
              records it in ``Analysis.datas`` (element 0 of each tuple).
    """
    path = _normalise(dest)

    if path in EXCLUDED_FROM_BUNDLE:
        return False

    if _DISCOVERY_MARKER in path:
        return PurePosixPath(path).name in DISCOVERY_KEEP

    return True


def filter_datas(datas):
    """Apply :func:`should_bundle` to a PyInstaller ``datas`` list.

    Returns:
        (kept, dropped) — both lists, so the spec can report what it removed
        rather than shrinking the build silently (P2/P9).
    """
    kept, dropped = [], []
    for entry in datas:
        (kept if should_bundle(entry[0]) else dropped).append(entry)
    return kept, dropped
