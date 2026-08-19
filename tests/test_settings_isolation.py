"""The suite must not touch the user's real settings file.

Several tests call ``AppSettings.load()`` / ``.save()`` with no path, and
``get_settings_path`` resolves to the real application data directory. A test
run was rewriting the user's settings.json — and ``save()`` writes every
dataclass field while ``load()`` filters to them, so a key the file carried that
the dataclass had dropped would be destroyed by a test.

Guarded by an autouse session fixture in conftest.py; this asserts the guard is
actually in force, because a fixture that silently stops applying leaves no
trace until someone's settings change.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
"""

from pathlib import Path

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.paths import default_settings_path


def test_the_settings_path_is_redirected_away_from_the_real_one():
    in_use = Path(AppSettings.get_settings_path())
    real = Path(default_settings_path())

    assert in_use != real, (
        "tests are pointed at the real settings.json — a save would rewrite it")
    assert real.parent not in in_use.parents, (
        f"the redirect still lands inside the real app data directory: {in_use}")


def test_saving_settings_writes_only_to_the_redirected_path():
    """A real save, then proof the real file was not the thing written."""
    real = Path(default_settings_path())
    before = real.stat().st_mtime if real.exists() else None

    settings = AppSettings.load()
    settings.save()

    assert Path(AppSettings.get_settings_path()).exists(), "the save went nowhere"
    if before is not None:
        assert real.stat().st_mtime == before, "the real settings file was written"
