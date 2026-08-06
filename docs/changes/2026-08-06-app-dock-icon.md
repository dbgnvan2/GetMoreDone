# Handoff Note

- Date: 2026-08-06
- Agent: Code
- Topic: app-dock-icon (replace default Python rocket with GMD check-mark)

## Summary
The running app showed the default Python launcher **rocket** in the macOS Dock
because nothing set a Dock icon at runtime, and the packaged `.app` used
`icon=None`. Now the GetMoreDone brand check-mark icon is shown instead:

- Runtime: new `set_app_icon()` sets the window/taskbar icon via Tk `iconphoto`
  (Windows/Linux) and the macOS Dock icon via AppKit `setApplicationIconImage_`
  (pyobjc). Called once from `GetMoreDoneApp.__init__` after the window exists.
  Fully guarded — any failure logs `[ICON] …` and never blocks startup.
- Packaged app: `GetMoreDone.spec` BUNDLE now points `icon=` at the bundled
  `.icns`, so the built `GetMoreDone.app` no longer shows the rocket either.
- The icon reuses the existing brand asset from `GetMoreDone Launcher.app`
  (blue rounded square + white check), copied into `assets/icons/app_icon.{png,icns}`
  so it ships via the spec's `assets` datas and resolves through `resource_root()`
  in both dev and frozen runs.

## Files changed
- src/getmoredone/utils/app_icon.py  (new — icon setup utility)
- src/getmoredone/app.py             (import + `set_app_icon(self)` call)
- assets/icons/app_icon.png          (new — GMD icon, runtime)
- assets/icons/app_icon.icns         (new — GMD icon, packaged bundle)
- GetMoreDone.spec                   (BUNDLE `icon=` -> app_icon.icns)
- requirements.txt                   (pyobjc-framework-Cocoa; macOS only)
- tests/test_app_icon.py             (new — 3 tests)

## Verification
- Command: `pytest -q`
- Result: PASS (425 passed, 1 skipped)
- Command: `pytest tests/test_app_icon.py -v`
- Result: PASS (3 passed)
- Runtime (real app): `venv/bin/python -u run.py` prints
  `[ICON] app icon set from app_icon.png`, no traceback, process stays up.
- In-process read-back inside a CTk root:
  `NSApplication.sharedApplication().applicationIconImage()` is present, valid,
  1024x1024 — the OS-level Dock icon is actually applied (not just "no error").

## Risks / Known gaps
- macOS Dock icon needs `pyobjc-framework-Cocoa` (added to requirements, macOS
  marker). If absent, code logs `[ICON] pyobjc AppKit unavailable …` and falls
  back gracefully; Dock keeps the rocket until deps are installed.
- Windows `.exe` icon (PyInstaller `EXE(icon=...)`) not set — needs an `.ico`;
  out of scope for this macOS-focused change. Follow-up if Windows packaging matters.

## Next agent actions
- Docs Agent: `requirements.txt` gained `pyobjc-framework-Cocoa` (macOS) — reflect
  in any dependency docs if needed.
