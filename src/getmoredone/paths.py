"""Path utilities for GetMoreDone.

Goals:
- Keep *user-writable* files (SQLite DB, settings) out of the source tree.
- Work both when running from source and when packaged (PyInstaller).

User data location:
- macOS: ~/Library/Application Support/GetMoreDone/
- Windows: %APPDATA%\\GetMoreDone\\
- Linux: ~/.local/share/GetMoreDone/

We use `platformdirs` for correct platform behavior.
"""

from __future__ import annotations

import sys
from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "GetMoreDone"
APP_AUTHOR = "GetMoreDone"


def project_root() -> Path:
    """Project root when running from source (repo root)."""
    # src/getmoredone/paths.py -> src/getmoredone -> src -> repo root
    return Path(__file__).resolve().parents[2]


def resource_root() -> Path:
    """Root for bundled resources.

    Purpose: locate read-only resources (themes, assets) in both source and frozen runs.
    Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1a
    Tests:   tests/test_packaging_resources.py::test_rm1a_frozen_mode_resource_root_finds_bundled_themes

    Precedence:
      1. ``GETMOREDONE_RESOURCE_ROOT`` — explicit override, used by ``--selftest``
         and by tests that need to exercise a specific bundle layout.
      2. ``sys._MEIPASS`` — PyInstaller extracts ``datas`` entries here.
      3. The repo root, when running from source.
    """
    import os

    override = (os.environ.get("GETMOREDONE_RESOURCE_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(getattr(sys, "_MEIPASS")).resolve()
    return project_root()


def app_data_dir_path() -> Path:
    """Directory for user-writable app data (DB, settings, exports, etc.)."""
    p = Path(user_data_dir(APP_NAME, APP_AUTHOR)).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def default_db_path() -> Path:
    return app_data_dir_path() / "getmoredone.db"


def _is_memory_db_target(value: str) -> bool:
    """Return True for SQLite in-memory DB targets."""
    v = (value or "").strip().lower()
    if v == ":memory:":
        return True
    if v.startswith("file::memory:"):
        return True
    return v.startswith("file:") and "mode=memory" in v


def env_db_path() -> Path | str | None:
    """Optional override DB path via env var GETMOREDONE_DB."""
    import os

    v = os.environ.get("GETMOREDONE_DB")
    if not v:
        return None
    if _is_memory_db_target(v):
        return v
    return Path(v).expanduser().resolve()


def resolve_db_path(db_path: str | None = None) -> Path | str:
    """Resolve DB path using (1) explicit arg, (2) env override, (3) default."""
    if db_path:
        if _is_memory_db_target(db_path):
            return db_path
        return Path(db_path).expanduser().resolve()
    env = env_db_path()
    if env is not None:
        return env
    return default_db_path()


def default_settings_path() -> Path:
    return app_data_dir_path() / "settings.json"


def bundled_themes_dir() -> Path:
    """Directory containing app theme JSON files."""
    return resource_root() / "themes"


def bundled_audio_dir() -> Path:
    """Directory of background-music tracks shipped with the app.

    Used as the default timer music folder when the user has not configured
    one of their own (Settings > Timer & Audio).
    """
    return resource_root() / "audio"


DEFAULT_THEME_SLUG = "apple_grey"


def resolve_theme_path(theme_name: str) -> Path:
    """Resolve a named theme file, preferring one that actually exists.

    Purpose: never hand CustomTkinter a path it will fail to open.
    Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1a2
    Tests:   tests/test_packaging_resources.py::test_rm1a2_unknown_theme_name_falls_back_to_existing_file

    Order: the requested theme, then the default theme, then any theme file
    present. Only when the themes folder is empty or absent does this return a
    path that does not exist — callers must guard on ``.exists()`` rather than
    assume, because a broken bundle must degrade rather than crash on startup.
    """
    slug = str(theme_name or "").strip().lower() or DEFAULT_THEME_SLUG
    themes_dir = bundled_themes_dir()

    candidate = themes_dir / f"{slug}.json"
    if candidate.exists():
        return candidate

    default = themes_dir / f"{DEFAULT_THEME_SLUG}.json"
    if default.exists():
        return default

    try:
        available = sorted(themes_dir.glob("*.json"))
    except OSError:
        available = []
    if available:
        return available[0]

    return default


def legacy_dot_dir() -> Path:
    """Legacy location used for Google credentials/token.

    Kept for backward compatibility.
    """
    return Path.home() / ".getmoredone"
