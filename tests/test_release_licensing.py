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

R-M2.A (LICENSE exists), R-M2.C (third-party notices) and R-M2.D (no audio
committed) are covered below as of Phase 5.
"""

from __future__ import annotations

import re
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements.txt"
DEV_REQUIREMENTS = REPO_ROOT / "requirements-dev.txt"

# Substrings that mean "Lesser/Library GPL" — permitted under one-folder linking.
LGPL_MARKERS = (
    "library or lesser general public license",
    "lesser general public license",
    "lgpl",
)

# What remains after the LGPL markers are removed and still means GPL.
GPL_MARKERS = ("gpl", "general public license")


def _shell_code_only(text: str) -> str:
    """Drop `#` comments from a shell script.

    start.sh carries a comment naming the grep this split removed, in order to
    explain why it is gone. Matching on the explanation would pressure the next
    person into deleting the reasoning to get back to green.
    """
    return "\n".join(
        line.split("#", 1)[0]
        for line in text.splitlines()
        if not line.strip().startswith("#")
    )


def _parse_requirements(path: Path) -> list[str]:
    """Distribution names from a requirements file, minus comments and markers.

    ``-r other.txt`` lines are skipped rather than followed: every caller here
    wants the names *this* file declares. Following them would make
    requirements-dev.txt report the runtime set as its own and collapse the
    split this module exists to check.
    """
    names = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line.startswith("-"):                      # -r / -c / -e and friends
            continue
        line = line.split(";", 1)[0].strip()          # environment marker
        name = re.split(r"[<>=!~\[]", line, 1)[0].strip()
        if name:
            names.append(name)
    return names


def _declared_requirements() -> list[str]:
    """Runtime distribution names — the ones that ship inside the binary."""
    return _parse_requirements(REQUIREMENTS)


def _dev_requirements() -> list[str]:
    """Test-only distribution names.

    Read from requirements-dev.txt rather than hardcoded. This used to be
    ``TEST_ONLY_PACKAGES = {"pytest", "pytest-cov"}`` — a hand-maintained copy
    of the answer that the licensing and notices checks both subtracted. A
    third test-only package added to requirements.txt would have been treated
    as a runtime dependency: it would have demanded a THIRD_PARTY_NOTICES entry
    it does not need, and been asserted shippable when it is not.
    """
    return _parse_requirements(DEV_REQUIREMENTS)


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
# BI2 — the runtime/dev split is real, and nothing hardcodes a copy of it
# --------------------------------------------------------------------------

def test_bi2_dev_requirements_file_exists():
    """Everything below reads it; an absent file must fail loudly, not skip."""
    assert DEV_REQUIREMENTS.exists(), (
        "requirements-dev.txt does not exist. The test-only packages were "
        "split out of requirements.txt so nothing has to hardcode which ones "
        "they are."
    )


def test_bi2_test_only_packages_are_not_declared_as_runtime():
    """The concrete regression: pytest must not ship inside the binary.

    Stated as set disjointness rather than by naming pytest, so a third
    test-only package cannot be added to the wrong file and pass.
    """
    runtime = {name.lower() for name in _declared_requirements()}
    dev = {name.lower() for name in _dev_requirements()}
    overlap = sorted(runtime & dev)
    assert not overlap, (
        f"declared in BOTH requirements.txt and requirements-dev.txt: {overlap}. "
        "A package belongs in exactly one; the licensing and notices checks "
        "treat everything in requirements.txt as shipped."
    )


def test_bi2_pytest_is_a_dev_dependency_not_a_runtime_one():
    """Ground truth for the split (P6): assert the artifact, not the intent."""
    runtime = {name.lower() for name in _declared_requirements()}
    dev = {name.lower() for name in _dev_requirements()}

    assert "pytest" in dev, "pytest is not declared in requirements-dev.txt"
    assert "pytest" not in runtime, (
        "pytest is back in requirements.txt — it would be treated as a shipped "
        "dependency and demand a THIRD_PARTY_NOTICES.md entry"
    )


def test_bi2_dev_requirements_pulls_in_the_runtime_set():
    """One install must give a contributor everything.

    Without the -r line, `pip install -r requirements-dev.txt` yields a
    checkout that can run the tests and not the app.
    """
    text = DEV_REQUIREMENTS.read_text(encoding="utf-8")
    assert re.search(r"^-r\s+requirements\.txt\s*$", text, re.MULTILINE), (
        "requirements-dev.txt does not include '-r requirements.txt'"
    )


def test_bi2_runtime_requirements_does_not_include_the_dev_file():
    """The include must not run the other way, or the split is cosmetic."""
    text = REQUIREMENTS.read_text(encoding="utf-8")
    assert not re.search(r"^-r\s+requirements-dev\.txt", text, re.MULTILINE), (
        "requirements.txt includes requirements-dev.txt, which puts the "
        "test-only packages back into the shipped set"
    )


def test_bi2_no_module_hardcodes_a_list_of_test_only_packages():
    """The set this split removed must not grow back somewhere else.

    ``TEST_ONLY_PACKAGES = {"pytest", "pytest-cov"}`` lived here, and start.sh
    grepped the same two names out of requirements.txt. Both were copies of an
    answer the files now hold.
    """
    import ast

    def _assigns_a_test_only_list(path: Path) -> bool:
        """True when the file *assigns* such a name, not merely mentions it.

        Parsed rather than grepped, for the same reason the tkcalendar scan is:
        the docstring above explains what was removed and names it, and a text
        search would force that explanation to be deleted to stay green.
        """
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and "TEST_ONLY" in target.id.upper():
                    return True
        return False

    offenders = []
    for folder in ("src", "tests", "tools"):
        for path in sorted((REPO_ROOT / folder).rglob("*.py")):
            if _assigns_a_test_only_list(path):
                offenders.append(str(path.relative_to(REPO_ROOT)))

    start_sh = _shell_code_only((REPO_ROOT / "start.sh").read_text(encoding="utf-8"))
    if re.search(r"grep[^\n]*pytest", start_sh):
        offenders.append("start.sh")

    assert not offenders, (
        f"a hardcoded test-only package list is back in: {offenders}. "
        "requirements-dev.txt is the list."
    )


def test_bi2_requirements_parser_does_not_follow_include_lines(tmp_path):
    """Adversarial: following -r would make the disjointness test vacuous.

    If ``_parse_requirements`` followed the include, requirements-dev.txt would
    report the runtime names as its own, every name would appear in both sets,
    and ``test_bi2_test_only_packages_are_not_declared_as_runtime`` would fail
    for the wrong reason — or, had it been written as a subset check, pass
    forever.
    """
    runtime = tmp_path / "requirements.txt"
    runtime.write_text("customtkinter>=5.2.0\n", encoding="utf-8")
    dev = tmp_path / "requirements-dev.txt"
    dev.write_text("-r requirements.txt\npytest>=7.4.0\n", encoding="utf-8")

    assert _parse_requirements(dev) == ["pytest"]
    assert _parse_requirements(runtime) == ["customtkinter"]


def test_bi2_requirements_parser_handles_markers_extras_and_comments(tmp_path):
    """The real file uses all three; a parser that mangles them mis-reports."""
    sample = tmp_path / "requirements.txt"
    sample.write_text(
        "# a comment\n"
        "\n"
        "pyobjc-framework-Cocoa>=9.0; sys_platform == \"darwin\"  # trailing\n"
        "uvicorn[standard]>=0.30\n"
        "requests\n",
        encoding="utf-8",
    )
    assert _parse_requirements(sample) == [
        "pyobjc-framework-Cocoa", "uvicorn", "requests",
    ]


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


# --------------------------------------------------------------------------
# R-M2.A — a LICENSE exists and says what D1 decided
# --------------------------------------------------------------------------

LICENSE_FILE = REPO_ROOT / "LICENSE"
NOTICES_FILE = REPO_ROOT / "THIRD_PARTY_NOTICES.md"


def test_rm2a_license_file_exists_and_is_not_empty():
    """A public repo with no LICENSE is 'all rights reserved' — nobody may run it."""
    assert LICENSE_FILE.exists(), "no LICENSE at the repo root (finding F4)"
    assert len(LICENSE_FILE.read_text(encoding="utf-8").strip()) > 500


def test_rm2a_license_names_the_copyright_holder_and_year():
    text = LICENSE_FILE.read_text(encoding="utf-8")
    assert "Dave Galloway" in text, "LICENSE does not name the copyright holder"
    assert re.search(r"Copyright \(c\) 20\d\d", text), "LICENSE has no copyright line"


def test_rm2a_license_implements_the_d1_decision():
    """D1: no cost to use, copyright retained, redistribution and commercial
    use reserved so the app can be sold later."""
    text = LICENSE_FILE.read_text(encoding="utf-8").lower()
    for phrase in ("at no cost", "all rights not expressly granted", "redistribute"):
        assert phrase in text, f"LICENSE does not express D1: missing {phrase!r}"


def test_rm2a_license_carries_the_unreviewed_draft_warning():
    """This text was drafted by an AI assistant, not a lawyer. Until someone
    qualified has read it, the file must say so — removing this line is a
    decision for the copyright holder, not a tidy-up."""
    text = LICENSE_FILE.read_text(encoding="utf-8")
    assert "NOT REVIEWED BY A LAWYER" in text, (
        "the draft warning was removed from LICENSE. If that was deliberate "
        "(a lawyer has now reviewed it), delete this test in the same commit."
    )


def test_rm2a_readme_links_the_license():
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "LICENSE" in readme, "README does not reference the licence"


# --------------------------------------------------------------------------
# R-M2.C — every runtime dependency has a notice
# --------------------------------------------------------------------------

def test_rm2c_third_party_notices_exists():
    assert NOTICES_FILE.exists(), "no THIRD_PARTY_NOTICES.md"


def test_rm2c_third_party_notices_covers_every_runtime_dep():
    """Fails when a dependency is added without a notice — that is the point."""
    notices = NOTICES_FILE.read_text(encoding="utf-8").lower()
    missing = [
        name for name in _declared_requirements()
        if name.lower() not in notices
    ]
    assert not missing, (
        f"runtime dependencies with no entry in THIRD_PARTY_NOTICES.md: {missing}"
    )


def test_rm2c_pygame_lgpl_notice_present():
    """F3: LGPL is only permissible here with a notice and a relink statement."""
    notices = NOTICES_FILE.read_text(encoding="utf-8")
    lowered = notices.lower()
    assert "lgpl" in lowered, "no LGPL notice for pygame"
    assert "one-folder" in lowered, "no relink statement (one-folder packaging)"
    assert "replace" in lowered, "the notice does not state the user may relink"


def test_rm2c_bundled_lgpl_text_exists_and_is_verbatim():
    """The LGPL requires the licence to accompany the distribution.

    The notices claim the text ships with the app; this asserts the file is
    really there and is really the LGPL, rather than a paraphrase.
    """
    lgpl = REPO_ROOT / "licenses/pygame-LGPL-2.1.txt"
    assert lgpl.exists(), (
        "THIRD_PARTY_NOTICES.md says the LGPL text ships with the application, "
        "but licenses/pygame-LGPL-2.1.txt does not exist"
    )
    text = lgpl.read_text(encoding="utf-8")
    assert "GNU LESSER GENERAL PUBLIC LICENSE" in text
    assert "Version 2.1, February 1999" in text
    assert len(text.splitlines()) > 400, "LGPL text looks truncated"


def test_rm2c_spec_bundles_the_licence_files():
    """A notice that ships only in the repo does not reach the person who
    downloaded a binary (R-M4.D)."""
    spec = (REPO_ROOT / "GetMoreDone.spec").read_text(encoding="utf-8")
    for required in ("licenses", "LICENSE", "THIRD_PARTY_NOTICES.md"):
        assert required in spec, f"GetMoreDone.spec does not bundle {required}"


def test_rm2c_notices_paths_match_the_real_bundle_layout():
    """The relink instructions name real directories.

    Verified against the archives produced by run 32191656386:
    macOS `GetMoreDone.app/Contents/Resources/pygame/`, Windows `_internal/pygame/`.
    """
    notices = NOTICES_FILE.read_text(encoding="utf-8")
    assert "Contents/Resources/pygame" in notices, "macOS relink path missing or wrong"
    assert "_internal" in notices and "pygame" in notices, "Windows relink path missing"


# --------------------------------------------------------------------------
# R-M2.D — no audio ships (D3)
# --------------------------------------------------------------------------

AUDIO_EXTENSIONS = (".mp3", ".wav", ".aif", ".aiff", ".m4a", ".flac", ".ogg")


def test_rm2d_no_audio_files_tracked():
    """D3: users point Settings at their own music folder; none is distributed."""
    import subprocess

    result = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    tracked_audio = [
        line for line in result.stdout.splitlines()
        if line.lower().endswith(AUDIO_EXTENSIONS)
    ]
    assert not tracked_audio, f"audio files tracked in git: {tracked_audio}"


def test_rm2d_spec_does_not_bundle_an_audio_folder():
    spec = (REPO_ROOT / "GetMoreDone.spec").read_text(encoding="utf-8")
    code = "\n".join(
        line for line in spec.splitlines() if not line.strip().startswith("#")
    )
    assert '"audio"' not in code, "GetMoreDone.spec bundles an audio folder (D3 says none ships)"
