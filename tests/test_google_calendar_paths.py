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
    monkeypatch.setattr(
        gmd_paths, "app_data_dir_path", lambda create=True: app_data
    )
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

def test_bi3_auth_dir_prefers_the_legacy_directory_when_it_exists(redirected_home):
    """An existing install keeps working.

    README.md and INSTALL.md both tell people to put ``credentials.json`` in
    ``~/.getmoredone``, and ``tools/import_gmd_from_gmail.py`` reads it from
    there. Moving the default would log those users out silently.
    """
    home, _ = redirected_home
    legacy = home / ".getmoredone"
    legacy.mkdir()

    assert gmd_paths.google_auth_dir() == legacy


def test_bi3_auth_dir_falls_back_to_the_app_data_dir(redirected_home):
    """A machine with no legacy directory uses the app data directory, like
    every other user-writable file."""
    home, app_data = redirected_home
    assert not (home / ".getmoredone").exists()

    assert gmd_paths.google_auth_dir() == app_data


def test_bi3_auth_dir_does_not_create_anything_by_default(redirected_home):
    """``create`` defaults to False: three of the four callers only need to
    know where to look."""
    home, app_data = redirected_home

    resolved = gmd_paths.google_auth_dir()

    assert not resolved.exists()
    assert list(home.iterdir()) == []


def test_bi3_auth_dir_creates_only_when_asked(redirected_home):
    home, app_data = redirected_home

    resolved = gmd_paths.google_auth_dir(create=True)

    assert resolved.is_dir()
    assert resolved == app_data


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
    home, app_data = redirected_home
    app_data.mkdir(parents=True)

    (app_data / "credentials.json").write_text("{}", encoding="utf-8")
    assert GoogleCalendarManager.has_credentials() is True, (
        "has_credentials does not look where google_auth_dir points"
    )

    result = GoogleCalendarManager.check_token_validity()
    assert result["exists"] is False
    (app_data / "token.pickle").write_bytes(pickle.dumps({"stub": True}))
    assert GoogleCalendarManager.check_token_validity()["exists"] is True, (
        "check_token_validity does not look where google_auth_dir points"
    )


def test_bi3_has_credentials_does_not_create_the_directory_it_checks(redirected_home):
    """A question must not have a side effect."""
    _requires_google_libs()
    home, app_data = redirected_home

    assert GoogleCalendarManager.has_credentials() is False
    assert not app_data.exists(), "has_credentials created the directory"
    assert list(home.iterdir()) == []


def test_bi3_explicit_argument_still_wins_over_the_default(redirected_home, tmp_path):
    """The default must not override an argument that was given."""
    _requires_google_libs()
    explicit = tmp_path / "elsewhere" / "creds.json"
    explicit.parent.mkdir()
    explicit.write_text("{}", encoding="utf-8")

    assert GoogleCalendarManager.has_credentials(str(explicit)) is True
    assert GoogleCalendarManager.has_credentials(str(tmp_path / "absent.json")) is False


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


def test_bi3_saving_a_token_sets_owner_only_permissions(redirected_home, tmp_path):
    """An OAuth token is a credential; it must not be world-readable."""
    _requires_google_libs()
    manager = GoogleCalendarManager.__new__(GoogleCalendarManager)
    manager.token_file = str(tmp_path / "tok" / "token.pickle")

    assert manager._save_token({"stub": True}) is True
    mode = os.stat(manager.token_file).st_mode & 0o777
    assert mode == 0o600, f"token saved with mode {oct(mode)}"


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
