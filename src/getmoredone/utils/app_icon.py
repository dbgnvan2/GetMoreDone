"""Application icon setup (window / taskbar / macOS Dock).

Purpose: Show the GetMoreDone brand check-mark icon for the running app instead
         of the default Python launcher rocket in the macOS Dock (and the OS
         taskbar on Windows/Linux).
Spec:    docs/changes/2026-08-06-app-dock-icon.md
Tests:   tests/test_app_icon.py

Why the rocket appears: when a plain ``python`` process runs a Tk GUI, macOS
shows the interpreter's launcher rocket in the Dock. The Dock icon of a live
process is owned by NSApplication, not by Tk's ``iconphoto`` — so on macOS we
set it through AppKit (pyobjc). ``iconphoto`` still covers the Windows title bar
and taskbar and most Linux window managers.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ..paths import resource_root


def app_icon_path() -> Path:
    """Absolute path to the bundled GMD app icon PNG.

    Resolves under the repo in dev and under the PyInstaller bundle when frozen
    (both expose ``assets/icons`` via :func:`resource_root`).
    """
    return resource_root() / "assets" / "icons" / "app_icon.png"


def set_app_icon(window) -> bool:
    """Set the GMD check-mark icon for ``window`` and the macOS Dock.

    Returns True if at least one icon channel was set. Never raises: icon setup
    is cosmetic and must never block application startup.

    Must be called *after* the Tk root exists (it is the Tk root here), so that
    on macOS ``NSApplication.sharedApplication()`` returns Tk's own application
    instance instead of creating a second one that breaks Tk initialisation.
    """
    icon_path = app_icon_path()
    if not icon_path.exists():
        print(f"[ICON] app icon not found, skipping: {icon_path}")
        return False

    ok = False

    # Cross-platform window/taskbar icon (Windows title bar + taskbar, most
    # Linux window managers). No effect on the macOS Dock — that is handled
    # via AppKit below.
    try:
        import tkinter as tk

        photo = tk.PhotoImage(master=window, file=str(icon_path))
        window.iconphoto(True, photo)
        # Keep a reference so Tk does not garbage-collect the image.
        window._gmd_app_icon = photo  # type: ignore[attr-defined]
        ok = True
    except Exception as exc:  # pragma: no cover - platform/Tk dependent
        print(f"[ICON] window iconphoto failed: {exc}")

    # macOS Dock icon for the running process.
    if sys.platform == "darwin":
        try:
            from AppKit import NSApplication, NSImage  # pyobjc, macOS only

            image = NSImage.alloc().initByReferencingFile_(str(icon_path))
            if image is not None and image.isValid():
                NSApplication.sharedApplication().setApplicationIconImage_(image)
                ok = True
            else:
                print("[ICON] macOS NSImage invalid; Dock icon unchanged")
        except ImportError:
            print(
                "[ICON] pyobjc AppKit unavailable; Dock icon unchanged "
                "(pip install pyobjc-framework-Cocoa)"
            )
        except Exception as exc:  # pragma: no cover - AppKit runtime dependent
            print(f"[ICON] macOS Dock icon set failed: {exc}")

    if ok:
        print(f"[ICON] app icon set from {icon_path.name}")
    return ok
