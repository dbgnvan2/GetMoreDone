"""Pytest path setup for the whole repository.

Purpose: make every test importable regardless of collection order or which
         subset of the suite is invoked.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m3d
Tests:   tests/test_ci_contract.py::test_rm3d_every_test_file_is_importable_on_its_own

Two import styles coexist in this suite: `from src.getmoredone...` (needs the
repo root on sys.path) and `from getmoredone...` (needs src/). Several test
files used to insert src/ themselves — and two of them imported `getmoredone`
*before* their own insert ran, so they only worked when an alphabetically
earlier file had already done it. Running either alone was an error.

Putting both roots on the path once, here, removes that ordering dependency:
pytest imports conftest.py before collecting anything.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for path in (ROOT, ROOT / "src"):
    entry = str(path)
    if entry not in sys.path:
        sys.path.insert(0, entry)


# ---------------------------------------------------------------------------
# Keep the test suite out of the user's real application data directory.
# ---------------------------------------------------------------------------

import logging
import weakref

import pytest


def _user_data_fingerprint():
    """(mtime, size, sha256) for the real settings file and database.

    Content as well as mtime, because the app rewriting the same values on a
    window move is not the same event as a test corrupting the file, and the
    two deserve different words (P1: a transient condition must not be reported
    as a terminal one).

    Built without ``paths.default_settings_path()``, which calls
    ``app_data_dir_path()`` and *creates* the directory — a read-only guard
    should not bring the user's data directory into existence on a machine
    where the app has never run.
    """
    import hashlib

    from platformdirs import user_data_dir

    from src.getmoredone.paths import APP_AUTHOR, APP_NAME

    # Test-only seam: the guard's own test points a nested pytest run at a fake
    # data directory, so exercising the guard does not require touching the real
    # files it exists to protect. This lives in conftest, not in the app.
    override = os.environ.get("GETMOREDONE_TEST_GUARD_DIR")
    if override:
        base = Path(override)
    else:
        # user_data_dir() computes the path; app_data_dir_path() would also
        # create it, and a read-only guard must not.
        base = Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()

    fingerprint = {}
    for key, name in (("settings", "settings.json"), ("database", "getmoredone.db")):
        target = base / name
        if not target.exists():
            fingerprint[key] = None
            continue
        stat = target.stat()
        digest = hashlib.sha256(target.read_bytes()).hexdigest() if key == "settings" else None
        fingerprint[key] = (stat.st_mtime_ns, stat.st_size, digest, str(target))
    return fingerprint


def remove_test_db_dir(path) -> bool:
    """Delete the temp directory sessionstart made. Returns whether it went.

    Purpose: ``tempfile.mkdtemp`` does not clean up after itself and nothing
             here did either, so every run left one behind for good.
    Tests:   tests/test_settings_isolation.py::test_the_temp_database_directory_is_removed_at_the_end_of_a_run
             tests/test_settings_isolation.py::test_remove_test_db_dir_refuses_a_directory_it_did_not_make

    Refuses anything not named like one of ours. This runs at the end of every
    test session on a developer's machine, and a mis-set attribute pointing at
    a real directory would take it with no way back — the guard is cheap and
    the failure it prevents is not recoverable.
    """
    import shutil

    if not path:
        return False
    target = Path(path)
    if not target.name.startswith("gmd-test-db-"):
        print(f"[WARN] refusing to remove {target}: not a gmd-test-db- directory")
        return False
    try:
        shutil.rmtree(target)
        return True
    except OSError as exc:
        # A leftover directory is untidy; a run that goes red at the last hook
        # over one is worse, and the message would land on top of the report.
        print(f"[WARN] could not remove {target}: {exc}")
        return False


def pytest_sessionstart(session):
    """Stamp the user's real data files so an escape is detected, not assumed.

    The redirect fixture below patches class objects. That is exactly the kind
    of guard that can be defeated without anyone noticing — the suite once
    imported `getmoredone.*` and `src.getmoredone.*` in different files, which
    Python loads as two distinct modules with two distinct classes, so patching
    one left the other writing the user's real file while a test asserting "the
    redirect is in force" passed against the patched twin.

    This checks the artifacts instead of the mechanism (P6). It also points
    GETMOREDONE_DB at a temporary file: an environment variable has one
    identity, so it cannot be defeated the way a patched class was.
    """
    import tempfile

    session.config._user_data_before = _user_data_fingerprint()

    # DatabaseManager() with no path resolves to the real database and runs
    # migrations on it. paths.resolve_db_path honours this variable first.
    if not os.environ.get("GETMOREDONE_DB"):
        handle = tempfile.mkdtemp(prefix="gmd-test-db-")
        os.environ["GETMOREDONE_DB"] = str(Path(handle) / "test.db")
        session.config._gmd_db_env_set = True
        # Remembered so sessionfinish can remove it. mkdtemp does not clean up
        # after itself, and nothing else did either: 1449 of these had
        # accumulated here since 2026-08-19, one per run, most of them empty.
        # Same shape as P30 — the directory was isolated, which was mistaken
        # for it being released.
        session.config._gmd_db_dir = handle


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    """Report an escape without destroying the test report.

    Raising here aborts the hook chain before the terminal reporter writes its
    summary: the run goes red, but with no FAILURES section and no counts —
    only this message, which may not even be the real problem. So it writes a
    line and sets the exit status instead (P24: the human must be shown the
    real cause, not a substituted one).
    """
    if getattr(session.config, "_gmd_db_env_set", False):
        os.environ.pop("GETMOREDONE_DB", None)
        remove_test_db_dir(getattr(session.config, "_gmd_db_dir", None))

    before = getattr(session.config, "_user_data_before", None)
    if before is None:
        return
    after = _user_data_fingerprint()

    touched = [key for key in before if before[key] != after[key]]
    if not touched:
        return

    lines = []
    for key in touched:
        old, new = before[key], after[key]
        path = (new or old)[3] if (new or old) else key
        content_changed = (
            old is None or new is None
            or old[1] != new[1] or (old[2] is not None and old[2] != new[2])
        )
        lines.append(
            f"GUARD: the user's real {key} file changed during this run: {path}"
        )
        lines.append(
            "  Its CONTENT changed — a test wrote it, or it was edited."
            if content_changed else
            "  Only its timestamp moved — most likely the GetMoreDone app is "
            "running and saved on a window move or column drag, which is "
            "harmless. Re-run with the app closed to be sure."
        )
    lines.append(
        "  If a test did it: something bypassed the isolation in conftest.py."
    )

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        for line in lines:
            reporter.write_line(line, red=True)
    else:
        print("\n".join(lines))

    if any(
        before[key] is None or after[key] is None
        or before[key][1] != after[key][1]
        or (before[key][2] is not None and before[key][2] != after[key][2])
        for key in touched
    ):
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


@pytest.fixture(autouse=True, scope="session")
def _forbid_resolving_the_real_database():
    """Fail the test that reaches for the real database, at the moment it does.

    Purpose: turn a silent write to production data into an immediate error.
    Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md
    Tests:   tests/test_live_data_guard.py

    ``GETMOREDONE_DB`` (set in ``pytest_sessionstart``) already redirects the
    default, and the fingerprint check at session end *detects* an escape. Both
    are worth keeping, but neither says WHICH test did it: the fingerprint fires
    after the run, naming a file rather than a test.

    This raises inside ``resolve_db_path`` instead, so the traceback points at
    the offending line. It is the third layer on purpose — the incident in
    `3892159` was ``DatabaseManager()`` with no path, whose ``__init__`` runs
    migrations, a row-deleting dedupe and a date-moving repair against the
    user's real data.

    Patched on both import spellings: ``getmoredone.paths`` and
    ``src.getmoredone.paths`` are different module objects, and patching one
    leaves the other live — the trap this file already documents for
    ``AppSettings``.
    """
    import importlib

    from platformdirs import user_data_dir

    from src.getmoredone.paths import APP_AUTHOR, APP_NAME

    real_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()

    patched = []
    for module_name in ("src.getmoredone.paths", "getmoredone.paths"):
        module = importlib.import_module(module_name)
        original = module.resolve_db_path

        def _guarded(db_path=None, __original=original):
            resolved = __original(db_path)
            # An in-memory target is a string, not a path — always fine.
            if isinstance(resolved, Path):
                try:
                    inside_real = resolved.resolve().is_relative_to(real_dir)
                except (OSError, ValueError):
                    inside_real = False
                if inside_real:
                    raise AssertionError(
                        f"a test resolved the REAL application database: "
                        f"{resolved}\n"
                        "Pass an explicit tmp_path database. Constructing a "
                        "DatabaseManager with no path runs migrations, a "
                        "row-deleting dedupe and a date-moving repair against "
                        "the user's own data."
                    )
            return resolved

        module.resolve_db_path = _guarded
        patched.append((module, original))
    try:
        yield real_dir
    finally:
        for module, original in patched:
            module.resolve_db_path = original


@pytest.fixture(autouse=True, scope="session")
def _isolate_user_settings(tmp_path_factory):
    """Keep the suite out of the user's real settings.json.

    Purpose: several tests call ``AppSettings.load()`` and ``.save()`` with no
             path. ``get_settings_path`` resolves to the real application data
             directory, so a test run rewrote the user's settings file — and
             ``save()`` writes ``asdict(self)`` while ``load()`` filters to the
             dataclass fields, so any key the file carried that the dataclass no
             longer has would be destroyed by a test. One of those tests
             (``test_list_view_setting``) flips a value with no try/finally, so
             a failing assert left the real setting flipped.
    Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
    Tests:   tests/test_settings_isolation.py

    Session-scoped and autouse, the same shape as the log fixture below: this
    has to be in place before the first test that touches settings, whichever
    file that turns out to be.
    """
    import importlib

    settings_path = tmp_path_factory.mktemp("settings") / "settings.json"
    redirect = classmethod(lambda cls: settings_path)

    # Both import spellings, because they are two different class objects and
    # patching one leaves the other pointed at the user's real file.
    originals = []
    for module_name in ("src.getmoredone.app_settings", "getmoredone.app_settings"):
        module = importlib.import_module(module_name)
        cls = module.AppSettings
        originals.append((cls, cls.__dict__.get("get_settings_path")))
        cls.get_settings_path = redirect
    try:
        yield settings_path
    finally:
        for cls, original in originals:
            if original is not None:
                cls.get_settings_path = original
            else:
                # Inherited rather than defined here: removing the override
                # restores the inherited one. Silently skipping would leave the
                # redirect installed on that class for the rest of the process.
                delattr(cls, "get_settings_path")


@pytest.fixture(autouse=True, scope="session")
def _isolate_weekly_tactic_log(tmp_path_factory):
    """Redirect the weekly-tactic log away from the real app data directory.

    Purpose: `weekly_tactic_debug.log` is where the migration records which rows
             it merged, deleted and moved — the file a human reads to audit an
             automatic data change. A test run appending its own tracebacks to
             it makes that audit harder, and one of those tracebacks is
             deliberately raised by a test.
    Spec:    docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m7b

    Session-scoped and autouse because the logger is built at import time, so
    the handler is already attached before any test runs.
    """
    from src.getmoredone.weekly_tactic_logging import LOGGER_NAME

    logger = logging.getLogger(LOGGER_NAME)
    original = list(logger.handlers)
    for handler in original:
        logger.removeHandler(handler)

    handler = logging.FileHandler(
        tmp_path_factory.mktemp("logs") / "weekly_tactic_debug.log", encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    try:
        yield
    finally:
        logger.removeHandler(handler)
        handler.close()
        for restored in original:
            logger.addHandler(restored)


# Every DatabaseManager / VPSManager built during the run, weakly held.
#
# The same question the window leak forced (P30): who gives this back, and when?
# Each one holds an open SQLite connection and its file descriptor. Twelve test
# functions build one and never close it — several of them helpers called from
# many tests, so the real count is higher than twelve.
#
# A net rather than twelve edits, for the same reason as the window sweeper: it
# covers the helpers, the failure paths, and the thirteenth one somebody adds.
_LIVE_CONNECTIONS = weakref.WeakSet()


def close_connections_created_since(snapshot):
    """Close every manager not in ``snapshot``. Returns how many.

    Tests: tests/test_connection_leak.py::test_a_manager_left_open_is_closed_at_teardown
    """
    closed = 0
    for manager in list(_LIVE_CONNECTIONS):
        if manager in snapshot:
            continue
        try:
            manager.close()
            closed += 1
        except Exception:
            pass          # already closed, or its Database went first
    return closed


@pytest.fixture(autouse=True, scope="session")
def _track_open_connections():
    """Register every manager at construction so teardown can close it."""
    from src.getmoredone.db_manager import DatabaseManager
    from src.getmoredone.vps_manager import VPSManager

    patched = []
    for cls in (DatabaseManager, VPSManager):
        original = cls.__init__

        def _init(self, *args, __original=original, **kwargs):
            __original(self, *args, **kwargs)
            try:
                _LIVE_CONNECTIONS.add(self)
            except TypeError:
                pass

        patched.append((cls, original))
        cls.__init__ = _init

    try:
        yield
    finally:
        for cls, original in reversed(patched):
            cls.__init__ = original


@pytest.fixture(autouse=True, scope="session")
def _no_connection_may_outlive_the_run(_track_open_connections):
    """P30 — assert the release, not the concealment.

    Tests: tests/test_connection_leak.py proves the sweeper this depends on.

    Would have caught the twelve unclosed managers on the run that introduced
    them, instead of leaving them to be found by counting file descriptors.
    """
    yield
    survivors = []
    for manager in list(_LIVE_CONNECTIONS):
        try:
            manager.db.conn.execute("SELECT 1")
            survivors.append(type(manager).__name__)
        except Exception:
            pass          # closed, which is what we want
    assert not survivors, (
        f"{len(survivors)} database connection(s) outlived the run: "
        f"{sorted(set(survivors))}. Each holds a file descriptor until the "
        "process exits."
    )


@pytest.fixture(autouse=True)
def _close_connections_left_open_by_this_test(_track_open_connections):
    """Function-scoped net under every test that opens a database."""
    before = set(_LIVE_CONNECTIONS)
    try:
        yield
    finally:
        close_connections_created_since(before)


# Set while a test has explicitly asked for a mapped window (see the
# ``mapped_windows`` fixture). Everything else is withdrawn on creation.
_WINDOWS_MAY_BE_MAPPED = False


# Every Tk window built during the run, weakly held.
#
# The guard below already intercepts every window at construction, so it knew
# about all of them — it just never owned them. Withdrawing a window hides it;
# it does not release it. A run leaked 37 live windows (measured with
# CGWindowList: climbing monotonically through the run, dropping to zero only
# at exit), because five helpers built a root, withdrew it, and returned it
# with nothing anywhere to destroy it. Tk drives one UI thread, so the
# WindowServer work those windows keep alive is what made the machine crawl.
#
# Weak, so registration itself can never be the thing keeping a window alive.
_LIVE_WINDOWS = weakref.WeakSet()


def destroy_windows_created_since(snapshot):
    """Destroy every live window not in ``snapshot``. Returns how many.

    Purpose: WL-1 — make a leak impossible regardless of any one test's
             hygiene, including a test that fails its assertion before it
             reaches its own ``destroy()``.
    Tests:   tests/test_tk_offscreen.py::test_a_leaked_window_is_destroyed_at_teardown
             tests/test_tk_offscreen.py::test_the_sweeper_leaves_earlier_windows_alone

    Membership is by object identity and deliberately not by ``id()``: ids are
    recycled after a collection, so an id-based snapshot can mistake a new
    window for an old one, or the reverse.

    Errors are swallowed. Destroying a root destroys its children, so a child
    still in the registry raises when its turn comes — the normal case, not a
    fault.
    """
    destroyed = 0
    for window in list(_LIVE_WINDOWS):
        if window in snapshot:
            continue
        try:
            window.destroy()
            destroyed += 1
        except Exception:
            pass
    return destroyed


@pytest.fixture(autouse=True, scope="session")
def _no_window_may_outlive_the_run():
    """WL-7 — assert the release, not the concealment.

    Purpose: P30 was written from this very bug: a guard that hides a resource
             gets mistaken for one that frees it. The 37-to-0 result that proved
             this fix is a manual CGWindowList measurement in a handoff note,
             which nothing re-runs. This is the automated half.
    Tests:   this is itself the check; tests/test_tk_offscreen.py proves the
             registry and the sweeper it depends on.

    It would have caught the original leak on the run that introduced it.
    """
    yield
    survivors = []
    for window in list(_LIVE_WINDOWS):
        try:
            if window.winfo_exists():
                survivors.append(type(window).__name__)
        except Exception:
            pass          # its interpreter is gone, which is what we want
    assert not survivors, (
        f"{len(survivors)} window(s) outlived the run: {sorted(set(survivors))}. "
        "Withdrawing a window hides it; it does not release it, and the "
        "WindowServer resources are held until the process exits."
    )


@pytest.fixture(autouse=True)
def _destroy_windows_left_behind_by_this_test():
    """Function-scoped net under every test that builds a window.

    Purpose: WL-1 — a window a test creates must not outlive it.
    Tests:   tests/test_tk_offscreen.py::test_a_leaked_window_is_destroyed_at_teardown

    Every window fixture in this suite is function-scoped, so nothing a later
    test needs can be swept away here. That was checked before this was written
    rather than assumed — a module- or session-scoped window fixture would make
    this actively wrong.

    The snapshot holds strong references for the length of one test, which is
    what stops a pre-existing window being collected and its identity reused.
    """
    before = set(_LIVE_WINDOWS)
    try:
        yield
    finally:
        destroy_windows_created_since(before)


# Setting this makes ``mapped_windows`` skip instead of mapping, for running
# the suite on a machine someone is working on. It is deliberately an opt-IN
# with a loud skip reason rather than a default: the three tests it disables
# are the only ones that read real geometry, and a silent skip would let them
# rot. tests/test_ci_contract.py asserts no workflow ever sets it.
NO_MAPPED_WINDOWS_ENV = "GETMOREDONE_NO_MAPPED_WINDOWS"

# Values that mean "off". Exported so tests/test_ci_contract.py can import it
# rather than keeping a second copy that silently drifts from this one (P5).
NO_MAPPED_WINDOWS_OFF_VALUES = ("", "0", "false", "no", "off", "n")


def mapped_windows_suppressed() -> bool:
    """Is the opt-out on? The single reader of the variable."""
    return (
        os.environ.get(NO_MAPPED_WINDOWS_ENV, "").strip().lower()
        not in NO_MAPPED_WINDOWS_OFF_VALUES
    )


@pytest.fixture
def mapped_windows():
    """Let this test's windows actually appear.

    Only for tests that read real geometry — ``winfo_width`` on a withdrawn
    window returns 1, so the sash-drag contract cannot be checked without a
    laid-out window. Everything else stays withdrawn, so a full run puts one
    window on screen briefly instead of dozens of modals over the user's work.

    A mapped window on macOS takes keyboard focus, which interrupts whoever is
    using the machine. Set ``GETMOREDONE_NO_MAPPED_WINDOWS=1`` to skip these
    tests during local iteration; the skip names the variable so a run that
    disabled them cannot be mistaken for a run that passed them.
    """
    # Not a bare truthiness check: os.environ.get() is true for "0" and
    # "false", so someone setting GETMOREDONE_NO_MAPPED_WINDOWS=0 to turn the
    # opt-out OFF would have turned it on.
    if mapped_windows_suppressed():
        pytest.skip(
            f"{NO_MAPPED_WINDOWS_ENV} is set: this test needs a real on-screen "
            "window and would take keyboard focus. Unset it to run the "
            "geometry tests."
        )

    global _WINDOWS_MAY_BE_MAPPED
    # Mapped, and — like every other window in the suite — fully transparent.
    # Tk still lays it out, so winfo_width()/winfo_x() return real numbers and
    # event_generate works, but nothing is drawn. Moving it off-screen does not
    # work here (macOS clamps it back onto the display); alpha does.
    _WINDOWS_MAY_BE_MAPPED = True
    try:
        yield
    finally:
        _WINDOWS_MAY_BE_MAPPED = False


def reapply_transparency(window) -> None:
    """Re-assert alpha 0 on a window that has just been (re-)mapped.

    Purpose: keep the transparency invariant across a deiconify, on every
             platform rather than only the one the author was sitting at.
    Tests:   tests/test_tk_offscreen.py::test_reapply_transparency_sets_alpha_to_zero
             tests/test_tk_offscreen.py::test_a_mapped_window_is_invisible_but_still_measurable

    Setting alpha once at creation is not enough. On X11 the attribute is the
    ``_NET_WM_WINDOW_OPACITY`` property, and re-mapping a window drops it, so
    ``deiconify()`` restores full opacity. On macOS it is a window property
    that survives, which is why the suite was green on the author's machine
    and red on CI for five consecutive runs against the same assertion.

    Swallows errors on purpose: a window destroyed between the deiconify and
    this call must not turn into a test error.
    """
    try:
        window.attributes("-alpha", 0.0)
    except Exception:
        pass


def wrap_reapplying_transparency(original):
    """Call through to ``original``, then put the transparency back.

    Purpose: keep a window invisible across every call that can map it or
             settle its layout, without stopping any of them happening.
    Tests:   tests/test_tk_offscreen.py::test_the_wrapper_reapplies_after_calling_through

    Wraps ``deiconify``, ``update_idletasks`` and ``update``. Setting alpha
    once at construction is not enough on X11: the attribute is the
    ``_NET_WM_WINDOW_OPACITY`` property and **every** map drops it, the first
    one included — so a window created under the ``mapped_windows`` fixture
    was already opaque by the time a test measured it, not merely after a
    deiconify.

    The layout calls rather than a ``<Map>`` binding, because ``<Map>`` is a
    real event and ``update_idletasks()`` processes only idle callbacks: the
    binding would not have fired by the time a test reads the attribute. Every
    test that reads geometry or opacity settles the window first, so wrapping
    those calls is deterministic where the event is not.

    A named factory rather than a closure inside the fixture, so a test can
    build one over a stub and prove it both calls through AND reapplies —
    neither of which is observable from the installed wrapper without a real
    mapped window, which is what this module exists to avoid.
    """
    def _wrapped(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        reapply_transparency(self)
        return result

    _wrapped._gmd_reapplies_transparency = True
    return _wrapped


@pytest.fixture(autouse=True, scope="session")
def _keep_tk_windows_off_screen():
    """No test may put a window over the user's work or take their keyboard.

    Purpose: several tests build a real ``CTk`` root or ``CTkToplevel`` because
             that is the only way to prove a control is wired to the database
             rather than merely rendered (P25). On macOS every one of those
             appears, raises itself and grabs focus, so a full run threw dozens
             of modals over whatever the user was doing.
    Tests:   tests/test_tk_offscreen.py

    Windows are withdrawn on creation. Moving them off-screen instead does not
    work here: macOS clamps a window back onto the display (``+12000+12000``
    lands at the bottom-right corner), so it would still be visible.

    Session-scoped and autouse because the classes are patched once, at import
    time, and a window built at module scope has to be covered too.
    """
    import customtkinter as ctk
    import tkinter as tk

    patched = []

    def _silence(cls, name, replacement):
        if hasattr(cls, name):
            patched.append((cls, name, getattr(cls, name)))
            setattr(cls, name, replacement)

    # tk.Tk and tk.Toplevel as well as the ctk pair. customtkinter's classes
    # subclass them, so patching only the ctk two left raw tkinter windows with
    # neither the alpha nor the withdraw — tests/test_app_icon.py builds three
    # of those and each one flashed a real window on screen.
    for cls in (ctk.CTk, ctk.CTkToplevel, tk.Tk, tk.Toplevel):
        original_init = cls.__init__

        def _init(self, *args, __original=original_init, **kwargs):
            __original(self, *args, **kwargs)
            # Registered before anything else can fail. A window that raises
            # while being hidden is exactly the one that most needs sweeping.
            try:
                _LIVE_WINDOWS.add(self)
            except TypeError:
                pass
            # Transparent FIRST, unconditionally. withdraw() happens after the
            # window already exists and has been mapped, so every one of the
            # hundreds of window-building tests flashed a visible frame in the
            # gap — withdrawing later removes the window, not the flash. Alpha
            # closes the gap; the withdraw below still does the real work.
            try:
                self.attributes("-alpha", 0.0)
            except Exception:
                pass
            if _WINDOWS_MAY_BE_MAPPED:
                # Stays mapped and transparent, so geometry resolves.
                return
            try:
                self.withdraw()
            except Exception:
                pass

        patched.append((cls, "__init__", original_init))
        cls.__init__ = _init

        # The calls that would show a window, raise it, or seize the keyboard.
        _silence(cls, "lift", lambda self, *a, **k: None)  # noqa: E731
        _silence(cls, "focus_force", lambda self, *a, **k: None)
        _silence(cls, "grab_set", lambda self, *a, **k: None)

        # -topmost was the hole in the three above. Silencing lift() but not
        # this one meant any code that raised a modal by re-asserting -topmost
        # still forced hundreds of window-server round-trips during a run, and
        # the machine beachballed while the suite was going. The alpha the
        # wrapper above sets is passed straight through; only -topmost is
        # dropped, and only for the run.
        # Both spellings. tkinter.Wm.attributes IS tkinter.Wm.wm_attributes —
        # the same function under two names — so patching one leaves the other
        # as an unguarded way to raise a window, and the guard's own test would
        # stay green because it exercises the patched spelling.
        _original_attributes = cls.attributes

        def _attributes(self, *args, __original=_original_attributes, **kwargs):
            if args and args[0] == "-topmost" and len(args) > 1:
                return None
            return __original(self, *args, **kwargs)

        for _name in ("attributes", "wm_attributes"):
            patched.append((cls, _name, getattr(cls, _name)))
            setattr(cls, _name, _attributes)
        # deiconify is WRAPPED, not silenced. Silencing it hung
        # tests/test_item_editor_sash.py — verified by bisection — because the
        # window never maps and its geometry never resolves.
        #
        # Wrapping is needed because the old reasoning here was wrong. It said
        # silencing was "unnecessary: the alpha above is applied at creation,
        # so a window that deiconifies is mapped and still fully transparent".
        # That holds on macOS, where alpha is a window property that survives a
        # re-map. On X11 it is the _NET_WM_WINDOW_OPACITY property, which the
        # re-map drops — so deiconify restored full opacity and
        # test_a_mapped_window_is_invisible_but_still_measurable failed on all
        # three Python versions in CI while passing on the author's Mac. The
        # comment was the claim; CI was the measurement.
        # deiconify maps the window; update_idletasks/update are where the
        # first map actually settles. X11 drops the opacity on every one of
        # them, so all three call through and then put it back.
        for call in ("deiconify", "update_idletasks", "update"):
            original_call = getattr(cls, call, None)
            if original_call is None:
                continue
            patched.append((cls, call, original_call))
            setattr(cls, call, wrap_reapplying_transparency(original_call))

        # deiconify additionally RE-WITHDRAWS, which the transparency wrapper
        # alone did not do.
        #
        # Application code calls deiconify: ItemEditorDialog._finalize_dialog_window
        # does it on every dialog it builds. So a window conftest withdrew at
        # construction mapped itself again moments later and stayed mapped —
        # invisible at alpha 0, but a real on-screen window as far as the
        # WindowServer is concerned. Measured with CGWindowList: 30 of them
        # alive at once mid-run, `onscreen=True, alpha=0.0`, named "Edit Action
        # Item" and "New Action Item".
        #
        # The withdraw happens AFTER the call through, so the layout the
        # deiconify was needed for has already resolved. That is the difference
        # from silencing deiconify outright, which hung test_item_editor_sash
        # because the geometry never settled.
        original_deiconify = getattr(cls, "deiconify", None)
        if original_deiconify is not None:
            wrapped_deiconify = getattr(cls, "deiconify")

            def _deiconify(self, *args, __wrapped=wrapped_deiconify, **kwargs):
                result = __wrapped(self, *args, **kwargs)
                if not _WINDOWS_MAY_BE_MAPPED:
                    try:
                        self.withdraw()
                    except Exception:
                        pass
                return result

            # Keeps the marker the installed-ness guard looks for: this
            # wrapper still reapplies transparency, through the wrapper it
            # calls. It carries its own marker as well, so the re-withdraw is
            # checkable in its own right rather than implied.
            _deiconify._gmd_reapplies_transparency = True
            _deiconify._gmd_rewithdraws = True
            setattr(cls, "deiconify", _deiconify)

    try:
        yield
    finally:
        for cls, name, original in reversed(patched):
            setattr(cls, name, original)
