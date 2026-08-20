"""The suite must not touch the user's real settings file or database.

Several tests call ``AppSettings.load()`` / ``.save()`` with no path, and
``DatabaseManager()`` with no path opens the real database and runs migrations
on it. Both are redirected by conftest.py.

The first version of this file checked only ``src.getmoredone.app_settings`` —
the same copy the fixture patched — and passed while the *other* module object
(`getmoredone.app_settings`, a different class) went on writing the real file.
So it asserts both class objects now, and it exercises the session hooks in a
nested pytest run rather than trusting that they work.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
"""

import importlib
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
from platformdirs import user_data_dir

from src.getmoredone.paths import APP_AUTHOR, APP_NAME

REAL_DATA_DIR = Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()


@pytest.mark.parametrize("module_name", [
    "src.getmoredone.app_settings",
    "getmoredone.app_settings",
])
def test_every_copy_of_appsettings_is_redirected(module_name):
    """Both import spellings are different class objects. Patch both, check both."""
    settings_cls = importlib.import_module(module_name).AppSettings
    in_use = Path(settings_cls.get_settings_path())

    assert in_use != REAL_DATA_DIR / "settings.json", (
        f"{module_name} still points at the real settings file")
    assert REAL_DATA_DIR not in in_use.parents, (
        f"{module_name} redirects inside the real data directory: {in_use}")


def test_the_two_import_spellings_really_are_different_classes():
    """If this ever fails, the both-classes patch has become unnecessary."""
    a = importlib.import_module("src.getmoredone.app_settings").AppSettings
    b = importlib.import_module("getmoredone.app_settings").AppSettings

    assert a is not b, (
        "the two module objects have merged — simplify the conftest fixture")


def test_the_database_is_redirected_away_from_the_real_one():
    """DatabaseManager() with no path runs migrations on whatever it opens."""
    from src.getmoredone.paths import resolve_db_path

    assert os.environ.get("GETMOREDONE_DB"), (
        "GETMOREDONE_DB is unset, so a pathless DatabaseManager would open the "
        "user's real database and migrate it")
    assert Path(str(resolve_db_path(None))) != REAL_DATA_DIR / "getmoredone.db"


def test_saving_settings_does_not_write_the_real_file(tmp_path):
    from src.getmoredone.app_settings import AppSettings

    real = REAL_DATA_DIR / "settings.json"
    before = real.stat().st_mtime_ns if real.exists() else None

    AppSettings.load().save()

    assert Path(AppSettings.get_settings_path()).exists(), "the save went nowhere"
    if before is not None:
        assert real.stat().st_mtime_ns == before, "the real settings file was written"


def _run_nested_pytest(tmp_path, probe_body):
    """Run a throwaway pytest whose conftest carries our two session hooks."""
    repo_root = Path(__file__).resolve().parents[1]
    # Loaded by path under a distinct module name: a nested file called
    # conftest.py cannot `from conftest import ...` — it would import itself.
    (tmp_path / "conftest.py").write_text(textwrap.dedent(f"""
        import importlib.util
        import sys

        sys.path.insert(0, {str(repo_root)!r})
        _spec = importlib.util.spec_from_file_location(
            "gmd_root_conftest", {str(repo_root / "conftest.py")!r})
        _root = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_root)

        pytest_sessionstart = _root.pytest_sessionstart
        pytest_sessionfinish = _root.pytest_sessionfinish
    """))
    (tmp_path / "test_probe.py").write_text(textwrap.dedent(probe_body))
    # The nested run watches a fake data directory, so exercising the guard
    # never touches the real files — and never trips the parent run's own guard.
    fake_data_dir = tmp_path / "fake_app_data"
    fake_data_dir.mkdir()
    (fake_data_dir / "settings.json").write_text('{"stub": true}')

    env = dict(os.environ, GETMOREDONE_TEST_GUARD_DIR=str(fake_data_dir))
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-q", str(tmp_path)],
        capture_output=True, text=True, cwd=str(tmp_path), timeout=180, env=env,
    )
    result.fake_settings = fake_data_dir / "settings.json"
    return result


def test_the_session_guard_fails_the_run_when_content_changes(tmp_path):
    """A test that rewrites the real settings file must turn the run red.

    Nothing exercised these hooks before; "it fires" had been checked by hand.
    The probe restores the file it edits, so this test is safe to run anywhere.
    """
    result = _run_nested_pytest(tmp_path, """
        import os
        from pathlib import Path

        def test_probe():
            watched = Path(os.environ["GETMOREDONE_TEST_GUARD_DIR"]) / "settings.json"
            watched.write_text('{"stub": true, "written_by_a_test": true}')
    """)

    assert "GUARD:" in result.stdout, (
        f"the guard did not report an escape:\n{result.stdout}\n{result.stderr}")
    assert "CONTENT changed" in result.stdout, result.stdout
    assert result.returncode != 0, "the guard did not fail the run"


def test_the_session_guard_leaves_a_clean_run_alone(tmp_path):
    result = _run_nested_pytest(tmp_path, """
        def test_probe():
            assert True
    """)

    assert result.returncode == 0, f"a clean run was failed:\n{result.stdout}"
    assert "GUARD:" not in result.stdout
