"""Every ``Tests:`` reference in the source must point at something real.

CLAUDE.md makes these references load-bearing for review: a docstring says
which test proves the behaviour it describes, and a reviewer follows it. Two of
them pointed at ``tests/test_vps_ape_deletion.py``, a file that has never
existed — written from memory of what the test was going to be called. Nothing
checked, so nothing said.

This is a source check because the thing being verified *is* the source text.
It fails loudly on a name that does not resolve, and the last test here proves
it can fail at all (P24).
"""

import re
from pathlib import Path

import pytest

# This whole file asserts on the REPOSITORY — workflows, packaging, licences,
# docs, traceability — not on application behaviour. Marked `meta` so
# `pytest -m "not meta"` gives a fast app-only run. The default `pytest` run
# still includes it: the marker is for speed, never for skipping.
pytestmark = pytest.mark.meta

REPO = Path(__file__).resolve().parents[1]

# Scanned in full rather than just src/: the first version of this guard looked
# only under src/, and there was a broken reference in conftest.py at the time
# — the exact defect it was written to catch, in a file it could not see.
SCANNED = ("src", "tools", "conftest.py")
SKIP_DIRS = {"venv", ".git", "build", "dist", "__pycache__"}

# A reference is any tests/... path, wherever it appears. Anchoring on the
# "Tests:" label matched only the first path on that line, so the 22 references
# written as indented continuation lines under a Tests: header were never
# checked — 15% of the domain the docstring claims (P24: a guard whose
# unchecked input path is a silent pass).
_REF = re.compile(r"(tests/[\w/]+\.py)(?:::(\w+))?")


def _scanned_files():
    for entry in SCANNED:
        target = REPO / entry
        if target.is_file():
            yield target
        elif target.is_dir():
            for path in sorted(target.rglob("*.py")):
                if SKIP_DIRS & set(path.parts):
                    continue
                yield path


def _references():
    for path in _scanned_files():
        text = path.read_text(encoding="utf-8")
        for match in _REF.finditer(text):
            yield path.relative_to(REPO), match.group(1), match.group(2)


def _test_names(path):
    """Test functions and the classes that group them.

    A reference may name either — ``::TestM3UI`` points at a class of tests,
    which is a perfectly good pointer for a reviewer to follow.
    """
    text = path.read_text(encoding="utf-8")
    return (set(re.findall(r"^\s*def (test_\w+)", text, re.M))
            | set(re.findall(r"^class (Test\w+)", text, re.M)))


def test_every_referenced_test_file_exists():
    missing = sorted({
        f"{src}: {target}"
        for src, target, _name in _references()
        if not (REPO / target).exists()
    })
    assert not missing, (
        "these docstrings name a test file that does not exist:\n  "
        + "\n  ".join(missing))


def test_every_referenced_test_name_exists():
    missing = []
    for src, target, name in _references():
        if not name:
            continue
        path = REPO / target
        if not path.exists():
            continue                      # reported by the test above
        if name not in _test_names(path):
            missing.append(f"{src}: {target}::{name}")
    assert not missing, (
        "these docstrings name a test that does not exist:\n  "
        + "\n  ".join(sorted(missing)))


def test_this_guard_can_actually_fire():
    """Guards the guard: the sweep has to be reading real references."""
    found = list(_references())
    # An exact floor, not "more than 20": the first version was satisfied by
    # 127 references as comfortably as by the 149 that exist, so narrowing the
    # scan by 15% went unnoticed. If this number drops, the scan shrank.
    assert len(found) >= 140, (
        f"only {len(found)} references found — the scan or the pattern has "
        "narrowed; it must cover every tests/... path under "
        f"{SCANNED}")
    assert any(name for _src, _target, name in found), (
        "no reference carries a ::test_name, so the name check is inert")
    assert any(str(src) == "conftest.py" for src, _t, _n in found), (
        "conftest.py is not being scanned — that is where the first broken "
        "reference this guard missed was living")
    # A continuation line under a Tests: header must be matched too.
    block = "    Tests:   tests/test_a.py\n             tests/test_b.py::test_c\n"
    assert [m.group(1) for m in _REF.finditer(block)] == [
        "tests/test_a.py", "tests/test_b.py"]
