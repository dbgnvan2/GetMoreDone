"""Headless startup self-check for GetMoreDone.

Purpose: prove a build can reach a working app without opening a window, so CI
         can run it against the *packaged* binary on a real Windows/macOS runner.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1b
Tests:   tests/test_selftest_cli.py

Run as ``python run.py --selftest`` from source, or ``GetMoreDone --selftest``
from a frozen build. Exits 0 when every check passes, non-zero otherwise, and
prints one line per check. Success is decided by the exit code, never by
scraping this output for a positive word (P24).

The checks deliberately mirror what the real startup path does first — resolve
resources, then open the database — because that is where finding F1 killed
every release binary before any UI existed to report it.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Callable, List, Tuple

# Tables the app cannot function without. Kept short on purpose: this is a
# smoke check that the schema initialised, not a schema-completeness assertion.
REQUIRED_TABLES = ("action_items", "contacts", "defaults", "work_logs")

CheckResult = Tuple[bool, str]


def check_resource_root() -> CheckResult:
    """The bundle's resource root must exist and be readable."""
    from .paths import resource_root

    root = resource_root()
    if not root.is_dir():
        return False, f"resource root is not a directory: {root}"
    return True, f"resource root: {root}"


def check_themes() -> CheckResult:
    """Every theme reachable from Settings must resolve to parseable JSON.

    This is the F1 guard. In a frozen build with themes/ left out of the spec's
    ``datas``, this check fails here instead of crashing the packaged app.
    """
    from .paths import resolve_theme_path
    from .theme import THEME_NAMES

    problems: List[str] = []
    for name in THEME_NAMES:
        path = resolve_theme_path(name)
        if not path.exists():
            problems.append(f"{name}: missing ({path})")
            continue
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{name}: unreadable ({exc})")
            continue
        if not isinstance(loaded, dict) or not loaded:
            problems.append(f"{name}: empty or not a JSON object")

    if problems:
        return False, "theme problems: " + "; ".join(problems)
    return True, f"{len(THEME_NAMES)} themes resolved and parsed"


def check_theme_application() -> CheckResult:
    """Applying the persisted theme must not raise, whatever settings hold."""
    from .app_settings import AppSettings
    from .theme import apply_theme_settings

    settings = AppSettings.load()
    mode, theme_name = apply_theme_settings(settings)
    return True, f"theme applied: mode={mode} theme={theme_name}"


def check_database() -> CheckResult:
    """The database must open and carry an initialised schema."""
    from .database import Database

    db = Database()
    try:
        conn = db.connect()
        db.initialize_schema()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        present = {r[0] for r in rows}
        missing = [t for t in REQUIRED_TABLES if t not in present]
        if missing:
            return False, f"schema missing tables: {missing}"
        return True, f"database ok at {db.db_path} ({len(present)} tables)"
    finally:
        db.close()


CHECKS: Tuple[Tuple[str, Callable[[], CheckResult]], ...] = (
    ("resource-root", check_resource_root),
    ("themes", check_themes),
    ("theme-application", check_theme_application),
    ("database", check_database),
)


def run_selftest(out=None) -> int:
    """Run every check and return a process exit code (0 = all passed).

    Purpose: a single command CI can run against a built bundle to prove it starts.
    Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1b
    Tests:   tests/test_selftest_cli.py::test_rm1b_selftest_exits_zero_on_temp_db

    Every check runs even after one fails, so a single run reports every problem
    rather than only the first.
    """
    from . import branding

    stream = out or sys.stdout
    frozen = getattr(sys, "frozen", False)
    print(
        f"{branding.APP_DISPLAY_NAME} selftest "
        f"({'frozen' if frozen else 'source'})",
        file=stream,
    )

    failures = 0
    for name, check in CHECKS:
        try:
            ok, detail = check()
        except Exception as exc:  # noqa: BLE001 - a check must never abort the run
            ok, detail = False, f"raised {type(exc).__name__}: {exc}"
            traceback.print_exc(file=stream)
        status = "PASS" if ok else "FAIL"
        print(f"  [{status}] {name}: {detail}", file=stream)
        if not ok:
            failures += 1

    total = len(CHECKS)
    print(f"selftest: {total - failures}/{total} checks passed, {failures} failed", file=stream)
    return 1 if failures else 0
