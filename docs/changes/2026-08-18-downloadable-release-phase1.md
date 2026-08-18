# Handoff — Downloadable release, Phase 1 (frozen-build correctness)

**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_downloadable_release.md` — R-M1
**Plan:** `docs/implementation_plan_2026-08-18_downloadable_release.md` — Phase 1
**Agent:** Code

## Summary

Fixed finding F1: every binary the release workflow has ever produced crashed on
launch. `GetMoreDone.spec` bundled only `assets`, while `paths.bundled_themes_dir()`
reads `sys._MEIPASS/themes`, so CustomTkinter's `ThemeManager.load_theme` hit a
bare `open()` on a missing file and raised `FileNotFoundError` before any window
appeared.

Also fixed F6 (the build scripts' unusable fallback path) and added
`--selftest`, the headless startup check CI will run against the packaged
binary in Phase 4.

The test for F1 was written first and confirmed **red** against the unmodified
spec before the fix landed.

## Files changed

| File | Change |
|---|---|
| `GetMoreDone.spec` | Bundle `themes/` in `datas`; comment recording why one-folder packaging is an LGPL requirement (R-M1.A.1, R-M1.D) |
| `src/getmoredone/paths.py` | `resource_root()` honours `GETMOREDONE_RESOURCE_ROOT`; `resolve_theme_path()` falls back requested → default → any present theme (R-M1.A.2) |
| `src/getmoredone/theme.py` | `normalize_*` coerce non-string settings values; `apply_theme_settings()` guards the theme load so a broken bundle degrades to CustomTkinter's default instead of crashing (R-M1.A.2) |
| `src/getmoredone/selftest.py` | **New.** Four checks: resource root, themes parse, theme application, database schema. Exit code decides success (R-M1.B) |
| `run.py` | `--selftest` flag; app import deferred so the selftest never pulls in the GUI |
| `build_mac.sh` | Run PyInstaller as `$PY -m PyInstaller` so the `python3` fallback works; selftest the built bundle against a temp DB (R-M1.C) |
| `build_windows.ps1` | Same, plus an explicit `$LASTEXITCODE` check |
| `tests/test_packaging_resources.py` | **New.** 23 tests |
| `tests/test_selftest_cli.py` | **New.** 8 tests |

## Test / verification status

| Check | Result |
|---|---|
| `pytest -q` (full suite) | **474 passed, 1 skipped — exit 0** (baseline was 443; +31 new) |
| F1 test red before the fix | Confirmed — `test_rm1a_frozen_mode_resource_root_finds_bundled_themes` failed against the unmodified spec |
| Local PyInstaller rebuild | exit 0 |
| `apple_grey.json` present in `dist/GetMoreDone.app` | **Yes** — `Contents/Resources/themes/`, reachable via the `Frameworks/themes` symlink PyInstaller creates |
| Packaged `--selftest` | **4/4 checks passed, exit 0** |
| Packaged `--selftest` against an empty resource root | **exit 1**, themes check FAILs by name — proves the guard is not a no-op |
| Packaged GUI launch | Process alive 12s, clean log. Degraded run (no themes) also stayed alive, with `[WARN] Theme file not found … Using the built-in default.` |

Windows packaging remains **integration-only** — unverifiable from this Mac,
and proven only by a green CI run (spec R-M4.A).

## Follow-ups

- Phases 2–6 of the plan are untouched: GPL/`tkcalendar` removal, `tests.yml`,
  release-pipeline hardening, `LICENSE`/`INSTALL.md`/`CHANGELOG.md`, hygiene.
- `learning-qa` review over the full diff is scheduled for Phase 6 step 25 and
  has **not** been run yet.
- `run.py --selftest` with no `GETMOREDONE_DB` set touches the real user
  database. The operation is non-destructive (`CREATE TABLE IF NOT EXISTS`) and
  checking the real path is the point, but the build scripts now pass a temp DB
  so a local build leaves the developer's data alone. Phase 4 must do the same
  in CI.

## Adjacent issues found, not fixed

- `tests/test_vps_segments.py` has two tests that `return` a bool instead of
  asserting; pytest warns `PytestReturnNotNoneWarning`. They can pass while
  asserting nothing.
- `themes/base_dark_blue.json` ships but is not in `theme.THEME_NAMES`, so it is
  bundled and unreachable from Settings.
