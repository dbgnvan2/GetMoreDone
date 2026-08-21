"""Tests for the GMD app-icon setup (replaces the Python launcher rocket).

Spec: docs/changes/2026-08-06-app-dock-icon.md
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.getmoredone.utils import app_icon  # noqa: E402


def test_app_icon_asset_present():
    """The bundled GMD icon PNG resolves and exists (dev resource root)."""
    path = app_icon.app_icon_path()
    assert path.name == "davipa.png"
    assert path.exists(), f"GMD app icon missing at {path}"


_TK_AVAILABLE = None


def _tk_available() -> bool:
    """Whether a Tk display can be created in this environment.

    Withdrawn before it is destroyed, and cached. This runs while the module is
    being *imported* — pytest evaluates the skipif decorators during collection,
    before any fixture — so the session-wide window guard in conftest.py cannot
    cover it, and a bare ``tk.Tk()`` here flashed a real window onto the user's
    desktop twice per run.
    """
    global _TK_AVAILABLE
    if _TK_AVAILABLE is not None:
        return _TK_AVAILABLE
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.destroy()
        _TK_AVAILABLE = True
    except Exception:
        _TK_AVAILABLE = False
    return _TK_AVAILABLE


@pytest.mark.skipif(not _tk_available(), reason="no Tk display available")
def test_set_app_icon_sets_iconphoto_and_never_raises():
    """set_app_icon returns True and keeps a reference so Tk can't GC the image."""
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        result = app_icon.set_app_icon(root)
        assert result is True
        # Reference retained on the window (prevents Tk garbage-collecting it).
        assert getattr(root, "_gmd_app_icon", None) is not None
    finally:
        root.destroy()


@pytest.mark.skipif(not _tk_available(), reason="no Tk display available")
def test_set_app_icon_missing_asset_is_safe(monkeypatch, tmp_path):
    """A missing icon file must not raise and must report failure (returns False)."""
    import tkinter as tk

    monkeypatch.setattr(app_icon, "app_icon_path", lambda: tmp_path / "nope.png")
    root = tk.Tk()
    root.withdraw()
    try:
        assert app_icon.set_app_icon(root) is False
    finally:
        root.destroy()
