# Changelog

All notable changes to GetMoreDone are recorded here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
conventions and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-18

First downloadable release. Everything before this was source-only.

### Added

- **Downloadable builds for macOS and Windows**, published on the Releases page
  with a SHA-256 checksum beside each archive.
- **`LICENSE`** — proprietary and source-available: free to use, copyright
  retained, redistribution and commercial use reserved.
- **`THIRD_PARTY_NOTICES.md`** — every runtime dependency with its licence, plus
  the pygame LGPL notice and relink statement. A verbatim copy of the LGPL ships
  with the application.
- **`INSTALL.md`** — download, the macOS Gatekeeper step, run-from-source,
  checksum verification, optional Google and music setup, where data is stored,
  and how to uninstall.
- **`run.py --selftest`** — a headless startup check (resources, themes, theme
  application, database) that exits non-zero when a build is broken. CI runs it
  against the packaged binary on both platforms, so a bundle that cannot start
  never becomes a release.
- **Test CI** (`.github/workflows/tests.yml`) — the full suite on Python 3.11,
  3.12 and 3.13, headless under xvfb so the GUI tests genuinely run.

### Fixed

- **Every previously built binary crashed on launch.** `GetMoreDone.spec`
  bundled only `assets/`, while the app loads its colour theme from
  `themes/`, so packaged builds died with `FileNotFoundError` before showing a
  window. Themes are now bundled, and a broken bundle degrades to the built-in
  theme instead of crashing.
- **Windows builds were never verified.** The release workflow now runs the
  packaged executable's selftest on a real Windows runner before publishing.
- Two test files passed only when collected after another file that happened to
  set up `sys.path` first; run alone they errored.
- `build_mac.sh` fell back to the system Python when no virtualenv was present,
  then invoked `./venv/bin/pyinstaller` regardless — the fallback could never
  have worked.
- An unknown or corrupt theme name in `settings.json` could raise during
  startup, before any window existed to report it.

### Changed

- **The download is 68 MB instead of 160 MB.** PyInstaller was bundling a
  Google API discovery document for every Google API in existence — 569 files,
  around 93 MB — while the app uses exactly two of them.
- **The date picker no longer uses `tkcalendar`**, which is GPLv3 and cannot
  ship inside a binary under this licence. It is reimplemented on Python's
  standard `calendar` module, keeps the same interface, honours the
  first-day-of-week setting, and now follows the active theme instead of
  hard-coded colours.
- The Google auth diagnostic moved from `test_auth.py` at the repository root to
  `tools/diagnose_google_auth.py`. It was never a test.
- Root-level test files moved under `tests/`.

### Known limitations

- **Builds are unsigned.** macOS requires a one-time quarantine step, documented
  in `INSTALL.md`; Windows may show a SmartScreen warning.
- No Linux binary. Linux runs from source.
- No auto-update. New versions are downloaded manually.
- No bundled music. Point Settings at a folder of your own.

[Unreleased]: https://github.com/dbgnvan2/GetMoreDone/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dbgnvan2/GetMoreDone/releases/tag/v0.1.0
