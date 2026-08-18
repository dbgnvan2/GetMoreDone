"""Licensing tests for the downloadable release.

Purpose: keep GPL-licensed code out of a proprietary, source-available binary.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m2b3
Tests:   this file

Finding F2: ``tkcalendar`` is GPLv3. Shipping it inside a binary distributed
under the proprietary license of decision D1 would violate the GPL. Finding F3:
``pygame`` is LGPL, which *is* permissible in a proprietary product provided the
user can relink it — hence the one-folder packaging asserted in
``tests/test_packaging_resources.py::test_rm1d_spec_uses_onefolder_not_onefile``.

So the rule these tests encode is narrow and deliberate: **LGPL is allowed, GPL
and AGPL are not.** The second test walks the whole installed dependency tree
rather than naming tkcalendar, so a *future* GPL dependency is caught too
(meta-rule: fix the class, not the instance).

Third-party notices (R-M2.C) and the audio-file check (R-M2.D) arrive in Phase 5
alongside THIRD_PARTY_NOTICES.md; they are not in this file yet.
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"

# Declared for running the test suite, not shipped inside the binary.
TEST_ONLY_PACKAGES = {"pytest", "pytest-cov"}

# Substrings that mean "Lesser/Library GPL" — permitted under one-folder linking.
LGPL_MARKERS = (
    "library or lesser general public license",
    "lesser general public license",
    "lgpl",
)

# What remains after the LGPL markers are removed and still means GPL.
GPL_MARKERS = ("gpl", "general public license")


def _declared_requirements() -> list[str]:
    """Distribution names from requirements.txt, minus comments and markers."""
    names = []
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        line = line.split(";", 1)[0].strip()          # environment marker
        name = re.split(r"[<>=!~\[]", line, 1)[0].strip()
        if name:
            names.append(name)
    return names


def _license_strings(dist_name: str) -> list[str] | None:
    """Every license-bearing string for an installed distribution, or None."""
    try:
        meta = metadata(dist_name)
    except PackageNotFoundError:
        return None
    values = []
    if meta.get("License"):
        values.append(meta["License"])
    values.extend(
        c for c in (meta.get_all("Classifier") or []) if c.startswith("License ::")
    )
    expression = meta.get("License-Expression")
    if expression:
        values.append(expression)
    return values


def _classify(license_strings: list[str]) -> str:
    """Return 'gpl', 'lgpl', or 'other'.

    LGPL markers are stripped before the GPL search, because every LGPL string
    contains 'GPL' as a substring — a naive search flags pygame, which is
    explicitly permitted (F3).
    """
    blob = " ".join(license_strings).lower()

    stripped = blob
    for marker in LGPL_MARKERS:
        stripped = stripped.replace(marker, " ")

    if any(marker in stripped for marker in GPL_MARKERS):
        return "gpl"
    if any(marker in blob for marker in LGPL_MARKERS):
        return "lgpl"
    return "other"


# --------------------------------------------------------------------------
# R-M2.B.3 — tkcalendar is gone from the tree entirely
# --------------------------------------------------------------------------

def _imported_modules(path: Path) -> set[str]:
    """Top-level module names imported by a Python file, via the AST.

    Parsing beats grepping here: the word "tkcalendar" legitimately appears in
    docstrings that record *why* it was removed, and a text search would force
    those explanations to be deleted to stay green. An import is unambiguous.
    """
    import ast

    names: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def test_rm2b3_no_gpl_dependency_anywhere():
    """tkcalendar must appear in neither requirements.txt nor any import."""
    hits = []

    if "tkcalendar" in REQUIREMENTS.read_text(encoding="utf-8"):
        hits.append("requirements.txt")

    for folder in ("src", "tests"):
        for path in sorted((REPO_ROOT / folder).rglob("*.py")):
            if "tkcalendar" in _imported_modules(path):
                hits.append(str(path.relative_to(REPO_ROOT)))

    assert not hits, (
        f"tkcalendar (GPLv3) is still imported/declared in: {hits}. It cannot "
        "ship inside a binary distributed under a proprietary license (F2)."
    )


def test_rm2b3_import_scan_would_actually_catch_a_gpl_import(tmp_path):
    """Adversarial: prove the AST scan is not a no-op that passes on anything."""
    offender = tmp_path / "offender.py"
    offender.write_text("from tkcalendar import Calendar\n", encoding="utf-8")
    assert "tkcalendar" in _imported_modules(offender)

    aliased = tmp_path / "aliased.py"
    aliased.write_text("import tkcalendar as tkc\n", encoding="utf-8")
    assert "tkcalendar" in _imported_modules(aliased)

    innocent = tmp_path / "innocent.py"
    innocent.write_text('"""Mentions tkcalendar in prose only."""\nimport calendar\n', encoding="utf-8")
    assert "tkcalendar" not in _imported_modules(innocent)


def test_rm2b3_date_picker_uses_the_stdlib_calendar_module():
    """The replacement must be stdlib-backed, not a different third-party widget."""
    source = (REPO_ROOT / "src/getmoredone/widgets/date_picker.py").read_text(encoding="utf-8")
    assert re.search(r"^import calendar$", source, re.MULTILINE), (
        "date_picker.py should build its month grid on the stdlib calendar module"
    )


# --------------------------------------------------------------------------
# R-M2.B.3 — and no *future* dependency reintroduces the problem
# --------------------------------------------------------------------------

def test_rm2b3_installed_runtime_deps_have_no_gpl_license():
    """Walk the declared runtime tree; GPL/AGPL fails, LGPL is allowed (F3)."""
    gpl = []
    unresolved = []

    for name in _declared_requirements():
        if name.lower() in TEST_ONLY_PACKAGES:
            continue
        strings = _license_strings(name)
        if strings is None:
            unresolved.append(name)
            continue
        if _classify(strings) == "gpl":
            gpl.append((name, strings))

    # Surface what could not be checked rather than passing quietly over it (P2).
    if unresolved:
        print(f"[licensing] not installed, license unverified: {sorted(unresolved)}")

    assert not gpl, (
        "GPL-licensed runtime dependencies cannot ship in a proprietary binary: "
        f"{gpl}"
    )


def test_rm2b3_license_classifier_distinguishes_gpl_from_lgpl():
    """Adversarial: the classifier itself must not fail either way (P7).

    A check that flags every string containing 'GPL' would flag pygame and get
    weakened or deleted; one that misses 'GPLv3' would wave tkcalendar through.
    """
    assert _classify(["GPLv3"]) == "gpl"
    assert _classify(["License :: OSI Approved :: GNU General Public License v3 (GPLv3)"]) == "gpl"
    assert _classify(["AGPL-3.0"]) == "gpl"
    assert _classify(["LGPL"]) == "lgpl"
    assert _classify(
        ["License :: OSI Approved :: GNU Library or Lesser General Public License (LGPL)"]
    ) == "lgpl"
    assert _classify(["MIT License"]) == "other"
    assert _classify(["BSD-3-Clause"]) == "other"


def test_rm2b3_pygame_is_recognised_as_lgpl_not_gpl():
    """Ground-truth check against the real installed distribution (P6)."""
    strings = _license_strings("pygame")
    if strings is None:
        pytest.skip("pygame is not installed in this environment")
    assert _classify(strings) == "lgpl", f"pygame classified wrongly from {strings}"
