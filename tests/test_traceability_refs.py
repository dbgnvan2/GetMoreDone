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

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
TESTS = REPO / "tests"

# "Tests:   tests/test_x.py::test_y" and bare "# Tests: tests/test_x.py"
_REF = re.compile(r"Tests:\s*(tests/[\w/]+\.py)(?:::(\w+))?")


def _references():
    for path in sorted(SRC.rglob("*.py")):
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
    assert len(found) > 20, (
        f"only {len(found)} Tests: references found — the pattern is not "
        "matching the docstrings it is meant to check")
    assert any(name for _src, _target, name in found), (
        "no reference carries a ::test_name, so the name check is inert")
    # And a deliberately broken reference is caught by the same matcher.
    assert _REF.search("Tests:   tests/test_nope.py::test_nothing").group(1) == (
        "tests/test_nope.py")
