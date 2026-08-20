"""No test in this suite may be incapable of failing.

Purpose: keep the suite honest about its own coverage.
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md
Tests:   this file

A test that returns a bool, has no check in its body, or asserts a literal is
green forever — including when the thing it protects has been dead for months.
It is invisible precisely because the suite looks healthy: the count goes up,
the colour stays green, and the coverage is imaginary.

`3892159` fixed sixteen of them across four files. One,
``test_enhanced_deletion_protection``, was ``return False`` — a *failing* test
reporting green — over segment-deletion protection that had been dead since
``delete_segment``'s return shape changed. Nothing could tell.

This is a static check on purpose, and it is one of the few places where that
is the right answer: a vacuous test cannot be detected by running it. Running
it is what produces the false green.
"""

from __future__ import annotations

import ast
import pathlib

import pytest

pytestmark = pytest.mark.meta

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]

# Calls that constitute a real verdict even without a bare `assert`.
VERDICT_CALLS = {"fail", "skip", "xfail", "raises", "warns", "approx"}


def _test_files() -> list[pathlib.Path]:
    return sorted(REPO_ROOT.glob("tests/test_*.py")) + [REPO_ROOT / "conftest.py"]


def _is_fixture(fn: ast.AST) -> bool:
    """A fixture named ``test_*`` is not a test, and must return a value.

    ``tests/test_obsidian_integration.py`` has ``test_item`` and
    ``test_contact`` — both fixtures. A scan that missed this would report two
    permanent false positives and get switched off.
    """
    return any("fixture" in ast.dump(d) for d in fn.decorator_list)


def _returns_a_value(fn: ast.AST) -> list[ast.Return]:
    """``return <value>`` belonging to THIS function, not a nested def.

    Nested helpers legitimately return things; only the test body matters.
    """
    found: list[ast.Return] = []

    def walk(node, top=False):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Return) and child.value is not None:
                found.append(child)
            walk(child)

    walk(fn, top=True)
    return found


def _asserting_helpers(tree: ast.AST) -> set[str]:
    """Module-level functions that contain an assert.

    A test whose only check is ``_assert_refiled(...)`` is not vacuous. Three
    tests in ``test_weekly_tactic_surfaces.py`` are exactly that shape, and a
    scan without this reported them as findings.
    """
    return {
        fn.name
        for fn in ast.walk(tree)
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        and any(isinstance(n, ast.Assert) for n in ast.walk(fn))
    }


def _has_a_verdict(fn: ast.AST, helpers: set[str]) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assert):
            return True
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if not name:
                continue
            if name in VERDICT_CALLS or name.startswith("assert") or name in helpers:
                return True
    return False


def _display(path: pathlib.Path) -> str:
    """Repo-relative where possible; absolute otherwise.

    The adversarial tests below point the scan at tmp_path files, which are not
    under the repo root — `relative_to` raises there.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _scan():
    returns, no_verdict, constant = [], [], []
    for path in _test_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        helpers = _asserting_helpers(tree)
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not fn.name.startswith("test_") or _is_fixture(fn):
                continue
            where = f"{_display(path)}:{fn.lineno} {fn.name}"
            if _returns_a_value(fn):
                returns.append(where)
            if not _has_a_verdict(fn, helpers):
                no_verdict.append(where)
            for node in ast.walk(fn):
                if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant):
                    constant.append(f"{where} (assert {node.test.value!r})")
    return returns, no_verdict, constant


def test_no_test_returns_a_value():
    """pytest ignores the return, so the verdict is thrown away."""
    returns, _, _ = _scan()
    assert not returns, (
        f"tests that return a value instead of asserting: {returns}. "
        "pytest discards the return — `return False` reports GREEN."
    )


def test_every_test_has_a_verdict():
    """A body with no assert, no pytest.raises and no asserting helper."""
    _, no_verdict, _ = _scan()
    assert not no_verdict, (
        f"tests with nothing that can fail: {no_verdict}. Add a real "
        "assertion, or delete the test — deleting one that asserts nothing is "
        "a valid fix."
    )


def test_no_test_asserts_a_literal():
    """`assert True` and `assert 1` cannot fail."""
    _, _, constant = _scan()
    assert not constant, (
        f"tests asserting a literal: {constant}"
    )


def test_the_scan_would_actually_catch_each_shape(tmp_path, monkeypatch):
    """Adversarial: prove the scan is not a no-op that passes on anything.

    Without this, all three checks above pass on an empty result set — which is
    exactly what a broken scanner produces, and exactly the failure this file
    exists to prevent. So the scanner gets the same treatment it applies.
    """
    offenders = tmp_path / "tests"
    offenders.mkdir()
    (offenders / "test_bad.py").write_text(
        "def test_returns_a_bool():\n"
        "    return False\n"
        "\n"
        "def test_has_no_verdict():\n"
        "    value = 1 + 1\n"
        "\n"
        "def test_asserts_a_literal():\n"
        "    assert True\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        __import__(__name__, fromlist=["_test_files"]),
        "_test_files",
        lambda: [offenders / "test_bad.py"],
    )

    returns, no_verdict, constant = _scan()
    assert any("test_returns_a_bool" in r for r in returns)
    assert any("test_has_no_verdict" in r for r in no_verdict)
    assert any("test_asserts_a_literal" in r for r in constant)


def test_the_scan_does_not_flag_legitimate_tests(tmp_path, monkeypatch):
    """The other direction — a scanner that flags everything gets switched off.

    Each of these is a real shape in this suite that an earlier version of the
    scan reported as a finding.
    """
    good = tmp_path / "tests"
    good.mkdir()
    (good / "test_good.py").write_text(
        "import pytest\n"
        "\n"
        "def _assert_refiled(x):\n"
        "    assert x\n"
        "\n"
        "@pytest.fixture\n"
        "def test_item():\n"                      # a fixture named test_*
        "    return {'id': 1}\n"
        "\n"
        "def test_uses_a_helper():\n"             # verdict is in the helper
        "    _assert_refiled(True)\n"
        "\n"
        "def test_uses_raises():\n"               # pytest.raises is a verdict
        "    with pytest.raises(ValueError):\n"
        "        raise ValueError()\n"
        "\n"
        "def test_has_a_nested_helper():\n"       # nested return is not the test's
        "    def inner():\n"
        "        return 5\n"
        "    assert inner() == 5\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        __import__(__name__, fromlist=["_test_files"]),
        "_test_files",
        lambda: [good / "test_good.py"],
    )

    returns, no_verdict, constant = _scan()
    assert returns == [], f"false positive on a return: {returns}"
    assert no_verdict == [], f"false positive on a verdict: {no_verdict}"
    assert constant == [], f"false positive on a literal: {constant}"
