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


def env_db_path() -> Path | None:
    """Optional override DB path via env var GETMOREDONE_DB."""
    import os

    v = os.environ.get("GETMOREDONE_DB")
    if not v:
        return None
    return Path(v).expanduser().resolve()


def resolve_db_path(db_path: str | None = None) -> Path:
    """Resolve DB path using (1) explicit arg, (2) env override, (3) default."""
    if db_path:
        return Path(db_path).expanduser().resolve()
    env = env_db_path()
    if env is not None:
        return env
    return default_db_path()


def default_settings_path() -> Path:
    return app_data_dir_path() / "settings.json"


def legacy_dot_dir() -> Path:
    """Legacy location used for Google credentials/token.

    Kept for backward compatibility.
    """
    return Path.home() / ".getmoredone"
