#!/usr/bin/env python3
"""The list-view expansion setting round-trips through save/load.

Under pytest the settings path is redirected to a temporary file by the autouse
fixture in the repo-root conftest.py, so this never touches the real file.

Run directly, it used to write the user's real settings.json — and if the
assertion between the flip and the restore failed, it left the setting flipped.
It now redirects the path itself and restores in a `finally`, so neither the
suite nor a direct run can leave anything behind.
"""

# Keep the repo root importable when this file is run directly (it has a
# __main__ block). Under pytest the repo-root conftest.py does the same thing;
# this must come before the src.getmoredone imports either way.
import sys
import tempfile
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from src.getmoredone.app_settings import AppSettings  # noqa: E402


def test_default_setting():
    """The setting exists, defaults sanely, and survives a save/load round trip."""
    settings = AppSettings.load()

    assert hasattr(settings, "default_columns_expanded"), \
        "default_columns_expanded attribute missing from AppSettings"
    assert isinstance(settings.default_columns_expanded, bool)

    original_value = settings.default_columns_expanded
    try:
        settings.default_columns_expanded = not original_value
        settings.save()

        reloaded = AppSettings.load()
        assert reloaded.default_columns_expanded == (not original_value), \
            "the setting did not persist after save/reload"
    finally:
        # Always, even if the assertion above failed: a test must not leave a
        # setting flipped.
        restored = AppSettings.load()
        restored.default_columns_expanded = original_value
        restored.save()

    assert AppSettings.load().default_columns_expanded == original_value


if __name__ == "__main__":
    # A direct run has no conftest, so redirect the path here rather than
    # writing the real settings file.
    _tmp = _Path(tempfile.mkdtemp(prefix="gmd-settings-")) / "settings.json"
    AppSettings.get_settings_path = classmethod(lambda cls: _tmp)
    test_default_setting()
    print(f"✓ passed against {_tmp}")
