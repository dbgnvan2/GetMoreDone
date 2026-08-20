"""Where GoogleCalendarManager looks for its credentials, and what it creates.

Purpose: constructing the manager must read its arguments before it touches the
         filesystem, and the three sites that resolve a default path must all
         resolve to the same one.
Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-3
Tests:   this file

BI3. ``__init__`` used to run::

    self.data_dir = Path.home() / ".getmoredone"
    self.data_dir.mkdir(exist_ok=True)

*before* looking at ``credentials_file`` / ``token_file``, so merely
constructing the object with two explicit paths created a folder in the real
home directory that nothing then used. Tests worked around it by redirecting
``Path.home()``; ``tests/test_first_run.py`` asserted the workaround.

Two rules govern every test here:

* **Never reach the network.** ``__init__`` ends in ``_authenticate()``, which
  runs a real OAuth flow when it finds a usable credentials file. Every
  construction below points at a path that does not exist, so ``_authenticate``
  raises ``FileNotFoundError`` before it builds a flow.
* **Never assert against the real home directory.** A test that checks
  ``~/.getmoredone`` is absent fails on any machine where the user genuinely
  has one — this developer's machine included. The home directory is redirected
  and the assertions are made against the redirected one.
"""

from __future__ import annotations

import contextlib
import io
import os
import pickle
import sys
import tempfile
from pathlib import Path

import pytest

# `src.getmoredone.*` deliberately: the repo also imports `getmoredone.*`, and
# Python loads those as different module objects. `google_calendar` holds a
# reference to the `paths` module, so patching must target the same identity
# the module under test resolved.
from src.getmoredone import paths as gmd_paths
from src.getmoredone.google_calendar import GoogleCalendarManager


@pytest.fixture
def redirected_home(tmp_path, monkeypatch):
    """A home directory and app data directory this test owns.

    Returns ``(home, app_data)``. Neither exists on entry beyond ``home``
    itself, so "was this created?" is answerable.

    ``paths.legacy_dot_dir`` and ``paths.app_data_dir_path`` are patched rather
    than ``Path.home`` alone: ``app_data_dir_path`` goes through platformdirs,
    which does not follow a patched ``Path.home`` on macOS. ``Path.home`` is
    patched as well so anything reaching for it directly still lands inside the
    temporary tree instead of the real one.
    """
    home = tmp_path / "home"
    home.mkdir()
    app_data = tmp_path / "appdata"

    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(gmd_paths, "legacy_dot_dir", lambda: home / ".getmoredone")
    monkeypatch.setattr(gmd_paths, "app_data_dir_path", lambda: app_data)
    return home, app_data


def _requires_google_libs():
    if not GoogleCalendarManager.is_available():
        pytest.skip("google client libraries not installed")


# --------------------------------------------------------------------------
# BI3 — the headline criterion: explicit paths create nothing
# --------------------------------------------------------------------------

def test_bi3_constructing_with_explicit_paths_creates_no_directory(redirected_home, tmp_path):
    """The whole of BI3 as one assertion.

    Before the fix this left ``<home>/.getmoredone`` behind. Both arguments are
    given, so nothing in the object needs a default directory at all.
    """
    _requires_google_libs()
    home, app_data = redirected_home

    with pytest.raises((FileNotFoundError, RuntimeError)):
        GoogleCalendarManager(
            credentials_file=str(tmp_path / "nope.json"),
            token_file=str(tmp_path / "nope.pickle"),
        )

    assert list(home.iterdir()) == [], (
        f"constructing with explicit paths created {list(home.iterdir())} in "
        "the home directory"
    )
    assert not app_data.exists(), (
        "constructing with explicit paths created the app data directory"
    )


def test_bi3_constructing_with_default_paths_still_creates_nothing(redirected_home):
    """Even on the default path, resolving where a file *would* live is a
    read-only act. The directory is created when the token is written, not when
    the manager is built."""
    _requires_google_libs()
    home, app_data = redirected_home

    with pytest.raises((FileNotFoundError, RuntimeError)):
        GoogleCalendarManager()

    assert list(home.iterdir()) == [], (
        f"constructing with default paths created {list(home.iterdir())}"
    )
    assert not app_data.exists()


# --------------------------------------------------------------------------
# BI3 — the resolver's rule
# --------------------------------------------------------------------------

def test_bi3_auth_dir_is_the_legacy_dot_directory(redirected_home):
    """One fixed location, whether or not it exists yet.

    ``~/.getmoredone`` is shared by design: ``gmail_importer``,
    ``tools/import_gmd_from_gmail.py`` (run from a launchd timer), six
    diagnostic scripts, README.md, INSTALL.md and
    docs/google-calendar-setup.md all name it.
    """
    home, _ = redirected_home
    legacy = home / ".getmoredone"

    assert gmd_paths.google_auth_dir() == legacy, "the directory is not fixed"
    assert not legacy.exists(), "resolving a path must not create it"

    legacy.mkdir()
    assert gmd_paths.google_auth_dir() == legacy, (
        "the answer changed once the directory existed"
    )


def test_bi3_auth_dir_does_not_change_when_the_directory_appears(redirected_home):
    """The regression three reviews found, as a dirty-state test (P8).

    ``google_auth_dir`` used to return the app data directory on a machine with
    no ``~/.getmoredone``, and the legacy directory once one existed. Nothing
    recorded which branch had been taken, and
    ``gmail_importer._load_creds`` creates ``~/.getmoredone`` unconditionally
    before it checks anything — reachable from Settings > Integrations and from
    a launchd job. So a user who set the calendar up, then ran a Gmail import,
    had the resolver flip: "credentials not found", a second trip through OAuth,
    and a working token orphaned where nothing looked for it.

    Asserting across the transition, not on each branch in isolation — testing
    the branches separately is what let the flip through.
    """
    home, app_data = redirected_home
    legacy = home / ".getmoredone"

    before = gmd_paths.google_auth_dir()

    # Exactly what gmail_importer does, and a bare `mkdir ~/.getmoredone`.
    legacy.mkdir(parents=True, exist_ok=True)
    after_legacy_appears = gmd_paths.google_auth_dir()

    app_data.mkdir(parents=True, exist_ok=True)
    after_app_data_appears = gmd_paths.google_auth_dir()

    assert before == after_legacy_appears == after_app_data_appears, (
        "the Google auth directory changed as other code created directories: "
        f"{before} -> {after_legacy_appears} -> {after_app_data_appears}"
    )


def test_bi3_auth_dir_never_creates_anything(redirected_home):
    """Resolving where a file would live is a read-only act."""
    home, app_data = redirected_home

    resolved = gmd_paths.google_auth_dir()

    assert not resolved.exists()
    assert list(home.iterdir()) == []
    assert not app_data.exists()


# --------------------------------------------------------------------------
# BI3 — the three entry points must agree (P5: fix the class, not the instance)
# --------------------------------------------------------------------------

def test_bi3_the_three_default_path_sites_resolve_to_one_directory(redirected_home):
    """``has_credentials`` runs *before* ``__init__`` in the calendar dialog.

    Changing only ``__init__`` would have left the check looking in
    ``~/.getmoredone`` while the constructor looked in the app data directory —
    "no credentials found" for a file that is sitting right there.
    """
    _requires_google_libs()
    home, _ = redirected_home
    auth_dir = gmd_paths.google_auth_dir()
    auth_dir.mkdir(parents=True)

    (auth_dir / "credentials.json").write_text("{}", encoding="utf-8")
    assert GoogleCalendarManager.has_credentials() is True, (
        "has_credentials does not look where google_auth_dir points"
    )

    result = GoogleCalendarManager.check_token_validity()
    assert result["exists"] is False
    (auth_dir / "token.pickle").write_bytes(pickle.dumps({"stub": True}))
    assert GoogleCalendarManager.check_token_validity()["exists"] is True, (
        "check_token_validity does not look where google_auth_dir points"
    )


def test_bi3_has_credentials_does_not_create_the_directory_it_checks(redirected_home):
    """A question must not have a side effect."""
    _requires_google_libs()
    home, app_data = redirected_home

    assert GoogleCalendarManager.has_credentials() is False
    assert not app_data.exists(), "has_credentials created the app data directory"
    assert list(home.iterdir()) == [], "has_credentials created a directory in home"


def test_bi3_explicit_argument_still_wins_over_the_default(redirected_home, tmp_path):
    """The default must not override an argument that was given."""
    _requires_google_libs()
    explicit = tmp_path / "elsewhere" / "creds.json"
    explicit.parent.mkdir()
    explicit.write_text("{}", encoding="utf-8")

    assert GoogleCalendarManager.has_credentials(str(explicit)) is True
    assert GoogleCalendarManager.has_credentials(str(tmp_path / "absent.json")) is False


# --------------------------------------------------------------------------
# BI3 — a status line must never be able to invalidate a credential
# --------------------------------------------------------------------------

class _BrokenStdout(io.TextIOBase):
    """A stdout whose every write fails, the way a closed pipe does.

    Needed alongside the cp1252 console because the two status lines that
    discarded a credential are pure ASCII — ``"Loaded existing token from:"``
    encodes fine on cp1252, so an encoding-only fixture cannot reach that bug.
    An earlier version of the test below used only cp1252 and therefore passed
    against the defect it named.
    """

    def write(self, _text):
        raise OSError(32, "Broken pipe")

    def writable(self):
        return True


@contextlib.contextmanager
def _stdout_that_fails_every_write():
    original = sys.stdout
    sys.stdout = _BrokenStdout()
    try:
        yield
    finally:
        sys.stdout = original


@contextlib.contextmanager
def _console_that_rejects_emoji():
    """A real cp1252 stdout — what a Windows console gives you.

    Not a mock: `print("✅")` genuinely raises UnicodeEncodeError here, which
    is the whole point. Restored in a finally so it cannot leak into the next
    test.
    """
    original = sys.stdout
    sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    try:
        yield
    finally:
        sys.stdout = original


def test_bi3_the_hostile_stdout_fixtures_really_do_raise():
    """Adversarial: if these pass, every test below is testing nothing."""
    with _console_that_rejects_emoji():
        try:
            print("✅ emoji")
            emoji_raised = False
        except UnicodeEncodeError:
            emoji_raised = True
    assert emoji_raised, "the cp1252 fixture no longer reproduces that console"

    with _stdout_that_fails_every_write():
        try:
            print("plain ascii")
            ascii_raised = False
        except OSError:
            ascii_raised = True
    assert ascii_raised, (
        "the broken-pipe fixture no longer fails on an ASCII write, so the "
        "credential-discard test below cannot reach the bug it names"
    )


def test_bi3_a_failed_status_print_does_not_discard_a_valid_token(
    redirected_home, tmp_path, monkeypatch
):
    """The regression a fourth review round found.

    ``print("Loaded existing token from:", ...)`` sat INSIDE the try whose
    ``except Exception`` sets ``creds = None``. On a cp1252 console the print
    raised, the handler ran, and a token that had loaded perfectly was thrown
    away — turning a transient console problem into "credentials not found" on
    every launch (P1).
    """
    _requires_google_libs()

    token = tmp_path / "token.pickle"
    token.write_bytes(pickle.dumps({"stub": "a valid-looking token"}))

    loaded = {}

    def _capture(path, *args, **kwargs):
        with open(path, "rb") as handle:
            loaded["creds"] = pickle.load(handle)
        return loaded["creds"]

    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    manager.token_file = str(token)
    manager.credentials_file = str(tmp_path / "absent.json")
    manager.service = None

    # A stdout that fails EVERY write, not just an emoji one: the status line
    # in question is pure ASCII. With no credentials file present, a discarded
    # token falls through to FileNotFoundError; a surviving one fails later and
    # differently (the stub has no `.valid`), which is what we assert.
    with _stdout_that_fails_every_write():
        try:
            manager._authenticate()
            error = None
        except Exception as exc:
            error = exc

    assert not isinstance(error, FileNotFoundError), (
        "a status print that failed to encode discarded a valid token and the "
        "run fell through to 'credentials not found'"
    )
    assert not isinstance(error, UnicodeEncodeError), (
        "a status print propagated out of _authenticate"
    )


def test_bi3_saving_a_token_survives_a_console_that_rejects_emoji(
    redirected_home, tmp_path
):
    """The token reaches disk and the caller is told so, on a cp1252 console.

    ``_save_token`` prints in three places — success, write failure and chmod
    failure. Guarding only the success one left the except-handler print able
    to propagate out of the function on the path where degrading gracefully
    matters most.
    """
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    manager.token_file = str(tmp_path / "deep" / "token.pickle")

    with _console_that_rejects_emoji():
        result = manager._save_token({"stub": True})

    assert result is True
    assert Path(manager.token_file).exists()


def test_bi3_a_failed_save_on_such_a_console_still_returns_false(tmp_path):
    """The write-failure branch prints too, and its print must not escape."""
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    blocker = tmp_path / "blocker"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    manager.token_file = str(blocker / "token.pickle")

    with _console_that_rejects_emoji():
        result = manager._save_token({"stub": True})

    assert result is False


def test_bi3_no_bare_print_remains_in_the_module():
    """Fix the class, not the site (P5).

    Nine of twenty-two prints were routed through ``_say`` and the commit
    message called it class-wide. The thirteen left included one in the exact
    position the guard had occupied, and two inside credential-handling try
    blocks.
    """
    import ast

    source = (
        Path(__file__).resolve().parents[1] / "src/getmoredone/google_calendar.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    offenders = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "print":
            continue
        # The one inside _say itself is the implementation.
        enclosing = [
            n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "_say"
            and node.lineno >= n.lineno and node.lineno <= (n.end_lineno or n.lineno)
        ]
        if not enclosing:
            offenders.append(node.lineno)

    assert not offenders, (
        f"bare print() at lines {offenders} in google_calendar.py. Every status "
        "line goes through _say(), or the guard covers whichever call site "
        "someone happened to report."
    )


# --------------------------------------------------------------------------
# BI3 — the message the user actually sees (P25: test the surface, not the lib)
# --------------------------------------------------------------------------

def test_bi3_the_dialog_actually_uses_the_message_helper():
    """P25 — wired at the library, unverified at the front end.

    ``missing_credentials_message()`` is tested directly below, but nothing
    bound it to the surface that shows it. Verified by mutation: reverting the
    dialog's call site to the old hardcoded string, leaving the helper intact,
    left the whole file green. The assertion that used to catch that was
    removed along with a tautology in the same edit.

    AST rather than a substring: this file has already been bitten three times
    by a text match hitting a comment.
    """
    import ast

    source = (
        Path(__file__).resolve().parents[1]
        / "src/getmoredone/screens/calendar_dialog.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    calls = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "missing_credentials_message"
    ]
    assert calls, (
        "calendar_dialog.py never calls missing_credentials_message(). The "
        "helper is tested and the dialog shows something else."
    )

    # And that call must be what the error label is configured with.
    wired = False
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "configure":
            continue
        for keyword in node.keywords:
            if keyword.arg != "text":
                continue
            if any(
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Name)
                and inner.func.id == "missing_credentials_message"
                for inner in ast.walk(keyword.value)
            ):
                wired = True
    assert wired, (
        "no error label is configured with missing_credentials_message(). The "
        "dialog builds its own string, so the path it names is not the path "
        "has_credentials() checked — which README.md and INSTALL.md promise."
    )


def test_bi3_the_dialog_message_names_the_path_that_was_checked(
    redirected_home, monkeypatch
):
    """README.md and INSTALL.md both promise this to the user.

    The calendar dialog is the only surface a GUI user reaches:
    ``has_credentials()`` returns first, so the ``FileNotFoundError`` from
    ``__init__`` — which does interpolate the path — is unreachable from there.
    The dialog used to print a hardcoded ``~/.getmoredone/``, so the promise in
    the docs was false wherever that was not the answer.

    The message is produced by ``missing_credentials_message()`` so this can
    call it. An earlier version of this test built the string itself and
    asserted the path was in it — true for every possible path, and therefore
    an assertion about nothing. Extracting the producer gives the test
    something that can disagree with it.
    """
    from src.getmoredone.screens.calendar_dialog import missing_credentials_message

    home, _ = redirected_home

    # A DISTINCTIVE directory, deliberately not under the redirected home.
    # The fixture points legacy_dot_dir() and Path.home() at the same place, so
    # `google_auth_dir()` and a hand-rolled `Path.home() / ".getmoredone"` are
    # indistinguishable under it — an earlier version of this test passed with
    # the resolver replaced by exactly that literal. Patching the resolver
    # itself is what separates them.
    sentinel = Path(tempfile.mkdtemp()) / "sentinel-auth-dir"
    monkeypatch.setattr(gmd_paths, "google_auth_dir", lambda: sentinel)

    rendered = missing_credentials_message()

    assert str(sentinel / "credentials.json") in rendered, (
        "the message does not name the path the RESOLVER returns — it is "
        f"reading somewhere else.\nexpected: {sentinel / 'credentials.json'}\n"
        f"message was:\n{rendered}"
    )
    assert str(home) not in rendered, (
        f"the message names the home directory rather than the resolver's "
        f"answer:\n{rendered}"
    )

    # And the same resolver is what has_credentials() consults, which is the
    # promise README.md and INSTALL.md actually make to the user.
    sentinel.mkdir(parents=True)
    assert GoogleCalendarManager.has_credentials() is False
    (sentinel / "credentials.json").write_text("{}", encoding="utf-8")
    assert GoogleCalendarManager.has_credentials() is True, (
        "the message names a path that has_credentials() does not consult"
    )


# --------------------------------------------------------------------------
# BI3 — the directory is created where the file is written
# --------------------------------------------------------------------------

def test_bi3_saving_a_token_creates_its_parent_directory(redirected_home, tmp_path):
    """The adjacent bug the fix exposes.

    The token write is warn-only, so an explicit ``token_file`` in a directory
    that did not exist used to fail quietly and re-authenticate on every run.
    ``__init__`` only ever created the *default* directory, never this one.
    """
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    manager.token_file = str(tmp_path / "made" / "up" / "token.pickle")

    assert manager._save_token({"stub": True}) is True

    saved = Path(manager.token_file)
    assert saved.exists(), "the token was not written"
    assert pickle.loads(saved.read_bytes()) == {"stub": True}


@pytest.mark.skipif(
    os.name == "nt",
    reason="POSIX mode bits: on Windows os.chmod only toggles the read-only "
           "flag, so st_mode & 0o777 is 0o666/0o444 and this cannot hold. The "
           "repo ships a Windows binary, so this is a real platform gap, not a "
           "test defect — recorded in BACKLOG.md.",
)
def test_bi3_saving_a_token_sets_owner_only_permissions(redirected_home, tmp_path):
    """An OAuth token is a credential; it must not be world-readable."""
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    manager.token_file = str(tmp_path / "tok" / "token.pickle")

    assert manager._save_token({"stub": True}) is True
    mode = os.stat(manager.token_file).st_mode & 0o777
    assert mode == 0o600, f"token saved with mode {oct(mode)}"


def test_bi3_a_token_that_reached_disk_is_reported_saved_even_if_chmod_fails(
    redirected_home, tmp_path, monkeypatch
):
    """A failing chmod must not be reported as a failed save.

    chmod runs *after* a successful write. Folding it into the same try made
    the function print "Failed to save token / you may need to re-authenticate"
    and return False while a world-readable token sat on disk — both halves of
    that message untrue, and the security problem unmentioned.
    """
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    manager.token_file = str(tmp_path / "chmodfail" / "token.pickle")

    def _boom(*args, **kwargs):
        raise PermissionError("no chmod on this filesystem")

    monkeypatch.setattr(os, "chmod", _boom)

    assert manager._save_token({"stub": True}) is True, (
        "a token that reached disk was reported as not saved"
    )
    assert Path(manager.token_file).exists()


def test_bi3_a_failed_token_save_reports_false_rather_than_raising(tmp_path):
    """Warn-only is deliberate — losing the token must not fail the sign-in.

    But the caller has to be able to tell the two apart, which is why this
    returns a bool instead of leaving the answer in stdout (P14).
    """
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    blocker = tmp_path / "blocker"
    blocker.write_text("I am a file, not a directory", encoding="utf-8")
    manager.token_file = str(blocker / "token.pickle")

    assert manager._save_token({"stub": True}) is False
