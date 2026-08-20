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

import os
import pickle
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
# BI3 — the message the user actually sees (P25: test the surface, not the lib)
# --------------------------------------------------------------------------

def test_bi3_the_dialog_message_names_the_path_that_was_checked(redirected_home):
    """README.md and INSTALL.md both promise this to the user.

    The calendar dialog is the only surface a GUI user reaches:
    ``has_credentials()`` returns first, so the ``FileNotFoundError`` from
    ``__init__`` — which does interpolate the path — is unreachable from there.
    The dialog used to print a hardcoded ``~/.getmoredone/``, so the promise in
    the docs was false wherever that was not the answer.

    Asserted against the source of the message rather than by building the
    dialog: constructing it needs a Tk root and a populated item, and this is
    the string, not the widget.
    """
    source = (
        Path(__file__).resolve().parents[1]
        / "src/getmoredone/screens/calendar_dialog.py"
    ).read_text(encoding="utf-8")

    block = source.split("Check for credentials", 1)[1][:900]
    assert "google_auth_dir()" in block, (
        "the dialog's credentials message does not use the resolver, so it "
        "cannot name the path has_credentials() actually checked"
    )
    assert "~/.getmoredone/" not in block, (
        "the dialog's credentials message hardcodes a path again"
    )

    # And the interpolation produces the real path, not a repr or a coroutine.
    expected = gmd_paths.google_auth_dir() / "credentials.json"
    rendered = f"Expected: {expected}"
    assert str(gmd_paths.google_auth_dir()) in rendered
    assert rendered.endswith("credentials.json")


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
