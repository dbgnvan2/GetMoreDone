"""No test may reach the user's real application database.

Purpose: prove the three layers of isolation actually fire, rather than
         assuming them.
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md
Tests:   this file

The incident (`3892159`): ``test_obsidian_dialogs.py::test_database`` called
``DatabaseManager()`` with no path. That resolves to the user's real
application database, and ``__init__`` calls ``initialize_schema()`` —
migrations, the Weekly Tactic dedupe (which deletes rows) and the invariant
repair (which moves dates). Every full-suite run opened production data for
months. Nothing failed, because nothing was checking.

Three layers now stand between a test and that file, and each covers a hole the
others leave:

1. ``pytest_sessionstart`` points ``GETMOREDONE_DB`` at a temp file, so the
   *default* no longer resolves to production. An environment variable has one
   identity, so it cannot be defeated the way a patched class can.
2. ``_forbid_resolving_the_real_database`` raises inside ``resolve_db_path``,
   so an escape names the offending line instead of surfacing later as a
   changed file.
3. ``pytest_sessionfinish`` fingerprints the real files and reports a mismatch,
   which catches anything that bypassed both — the artifact check that does not
   depend on any patch holding (P6).

This file asserts that layers 1 and 2 are live and can fail, and that no test
constructs a database manager without a path.
"""

from __future__ import annotations

import ast
import os
import pathlib

import pytest
from platformdirs import user_data_dir

from src.getmoredone import paths as gmd_paths
from src.getmoredone.paths import APP_AUTHOR, APP_NAME

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]


def _real_data_dir() -> pathlib.Path:
    return pathlib.Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()


# --------------------------------------------------------------------------
# Layer 2 — the guard raises, and raises on the right thing
# --------------------------------------------------------------------------

def test_resolving_the_real_database_raises():
    """Adversarial: if this does not raise, the guard is decoration.

    Asks for the real path explicitly. That is the one thing no test should
    ever be able to do, so it is the one thing worth proving is blocked.
    """
    real_db = _real_data_dir() / "getmoredone.db"

    with pytest.raises(AssertionError, match="REAL application database"):
        gmd_paths.resolve_db_path(str(real_db))


def test_the_guard_is_installed_on_both_import_spellings():
    """`getmoredone.paths` and `src.getmoredone.paths` are different modules.

    Patching one leaves the other live — the trap conftest.py already documents
    for AppSettings. A test importing the app the other way would have sailed
    straight past a single-spelling guard.
    """
    import importlib

    real_db = _real_data_dir() / "getmoredone.db"
    for module_name in ("src.getmoredone.paths", "getmoredone.paths"):
        module = importlib.import_module(module_name)
        with pytest.raises(AssertionError, match="REAL application database"):
            module.resolve_db_path(str(real_db))


def test_the_guard_allows_a_temporary_database(tmp_path):
    """The other direction: a guard that blocked everything would be found in
    seconds, but one that blocks slightly too much is a slow tax on every new
    test. A tmp_path database must pass cleanly."""
    target = tmp_path / "scratch.db"
    resolved = gmd_paths.resolve_db_path(str(target))
    assert pathlib.Path(resolved) == target.resolve()


def test_the_guard_allows_an_in_memory_database():
    """`:memory:` resolves to a string, not a Path — it must not be mangled."""
    assert gmd_paths.resolve_db_path(":memory:") == ":memory:"


# --------------------------------------------------------------------------
# Layer 1 — the environment redirect is in force
# --------------------------------------------------------------------------

def test_the_db_environment_override_points_somewhere_temporary():
    """conftest sets GETMOREDONE_DB before any test runs.

    If it is unset, every default-path construction in the suite is resolving
    to production and only layer 2 stands in the way.
    """
    override = os.environ.get("GETMOREDONE_DB")
    assert override, (
        "GETMOREDONE_DB is not set — pytest_sessionstart did not run, or "
        "something unset it mid-run"
    )
    assert not pathlib.Path(override).resolve().is_relative_to(_real_data_dir()), (
        f"GETMOREDONE_DB points inside the real data directory: {override}"
    )


def test_the_default_database_path_is_not_the_real_one():
    """End to end: what a no-argument construction would actually get."""
    resolved = gmd_paths.resolve_db_path()
    assert not pathlib.Path(resolved).resolve().is_relative_to(_real_data_dir()), (
        f"the default database path resolves into the real data directory: "
        f"{resolved}"
    )


# --------------------------------------------------------------------------
# Static — no test constructs a manager without a path
# --------------------------------------------------------------------------

def test_no_test_constructs_a_database_manager_without_a_path():
    """The shape of the original incident, forbidden outright.

    Parsed rather than greped: a substring search for ``DatabaseManager()``
    matches a docstring explaining why it must not be written — including the
    one at the top of this file. AST sees only real calls.

    A source check is right here specifically because the alternative is to
    *run* the offending construction, which is the thing being prevented.
    """
    offenders = []
    for path in sorted(REPO_ROOT.glob("tests/test_*.py")) + [REPO_ROOT / "conftest.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id not in ("DatabaseManager", "DBManager"):
                continue
            if not node.args and not node.keywords:
                offenders.append(f"{path.relative_to(REPO_ROOT)}:{node.lineno}")

    assert not offenders, (
        f"{node.func.id if offenders else ''} constructed with no path at: "
        f"{offenders}. That resolves to the user's real database and __init__ "
        "runs migrations against it. Pass an explicit tmp_path database."
    )


def test_the_static_scan_would_actually_catch_one(tmp_path):
    """Adversarial: prove the AST walk is not a no-op that passes on anything."""
    sample = tmp_path / "offender.py"
    sample.write_text("db = DatabaseManager()\n", encoding="utf-8")
    tree = ast.parse(sample.read_text(encoding="utf-8"))
    found = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "DatabaseManager" and not n.args and not n.keywords
    ]
    assert found, "the scan cannot see a bare DatabaseManager() call"

    innocent = tmp_path / "innocent.py"
    innocent.write_text(
        '"""Never write DatabaseManager() with no path."""\n'
        "db = DatabaseManager(str(tmp_path / 'x.db'))\n",
        encoding="utf-8",
    )
    tree = ast.parse(innocent.read_text(encoding="utf-8"))
    found = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id == "DatabaseManager" and not n.args and not n.keywords
    ]
    assert not found, "the scan flags a docstring mentioning the forbidden call"
