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

    When packaged via PyInstaller, files added with --add-data land under sys._MEIPASS.
    """
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


def resolve_theme_path(theme_name: str) -> Path:
    """Resolve a named theme file from bundled themes, fallback to apple_grey."""
    slug = (theme_name or "").strip().lower() or "apple_grey"
    themes_dir = bundled_themes_dir()
    candidate = themes_dir / f"{slug}.json"
    if candidate.exists():
        return candidate
    return themes_dir / "apple_grey.json"


def legacy_dot_dir() -> Path:
    """Legacy location used for Google credentials/token.

    Kept for backward compatibility.
    """
    return Path.home() / ".getmoredone"
