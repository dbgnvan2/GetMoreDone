# Spec — Downloadable GitHub Release (GetMoreDone v0.1.0)

**Status:** Draft, awaiting approval
**Date:** 2026-08-18
**Spec ID root:** `R`
**Supersedes:** nothing. Extends `docs/STANDALONE_BUILD.md`.

---

## 1. Goal

A person who has never seen GetMoreDone can visit
`https://github.com/dbgnvan2/daVIPA`, either download a build for their OS
or clone and run from source, and reach a working **Today** screen — legally,
and without hitting a crash.

## 2. Non-goals

- Web, server, or hosted deployment (Railway / Vercel). Explicitly out of scope.
- Multi-user support, authentication, or any `user_id` concept.
- Code signing / notarization on macOS (no Apple Developer account — see `R-M5.D`).
- Linux binaries. Linux users run from source. `paths.py` already supports Linux.
- Auto-update.

## 3. Decisions taken (2026-08-18, user)

| # | Decision |
|---|---|
| D1 | **License is proprietary + source-available.** No cost to use today; copyright retained by Dave Galloway; redistribution and commercial use reserved so the app can be sold later. |
| D2 | **macOS build ships unsigned.** Gatekeeper workaround is documented rather than paid for. |
| D3 | **No audio ships.** Users point Settings at their own music folder. |

## 4. Known blocking findings (discovered during spec research)

| ID | Finding | Evidence |
|---|---|---|
| F1 | **Every binary the release workflow has ever produced crashes on launch.** `GetMoreDone.spec` line 29 bundles only `assets`. `paths.bundled_themes_dir()` resolves to `sys._MEIPASS/themes`, and CustomTkinter's `ThemeManager.load_theme` does a bare `open()` with no fallback → `FileNotFoundError` before any window appears. | No `apple_grey.json` anywhere in local `dist/GetMoreDone.app`; `customtkinter/windows/widgets/theme/theme_manager.py` |
| F2 | **`tkcalendar` is GPLv3.** Distributing it inside a binary under a proprietary license (D1) violates the GPL. | `importlib.metadata` reports `GPLv3` |
| F3 | **`pygame` is LGPL.** Permissible in a proprietary product only if the user can relink the library — i.e. one-folder packaging, plus a shipped notice. | `importlib.metadata` reports `LGPL` |
| F4 | **No `LICENSE` file.** A public repo without one is "all rights reserved"; nobody may legally run it. | `ls LICENSE*` → none |
| F5 | **No test CI.** Only `agent-docs-gate.yml` and `build-release.yml` exist. A blank-machine run is exactly what would have caught F1. | `.github/workflows/` |
| F6 | `build_mac.sh` falls back to `python3` when `venv/` is absent, then hardcodes `./venv/bin/pyinstaller` — the fallback path cannot work. | `build_mac.sh` |

`F1` and `F2` are release blockers. `F4` is a legal blocker.

---

## 5. Requirements

### R-M1 — Frozen-build correctness

The binary produced by CI must actually launch. Fixes F1, F6.

- **R-M1.A** — `GetMoreDone.spec` bundles every runtime resource the app reads
  through `paths.resource_root()`.
  - **R-M1.A.1** — `themes/` is present in the frozen bundle, and
    `paths.resolve_theme_path()` returns an existing file for every theme name
    reachable from Settings.
  - **R-M1.A.2** — An unknown, empty, or corrupt theme name resolves to a theme
    file that exists on disk. `apply_theme_settings()` never raises.
  - **R-M1.A.3** — An absent `audio/` directory degrades to "no music library".
    `music_library` returns `None`, never raises.
- **R-M1.B** — `run.py --selftest` loads settings, applies the theme, opens and
  migrates a database at a caller-supplied path, prints a one-line result, and
  exits `0` — without creating a window. Non-zero exit on any failure. This is
  the CI-runnable proof of R-M1.A and the gate in R-M4.A.
- **R-M1.C** — `build_mac.sh` and `build_windows.ps1` succeed on a machine with
  no `venv/`.
- **R-M1.D** — One-folder packaging (`COLLECT` + `BUNDLE`) is retained. `--onefile`
  is prohibited: it would statically absorb pygame and break the LGPL relink
  obligation (F3). The prohibition is recorded as a comment in `GetMoreDone.spec`.

### R-M2 — Licensing and third-party compliance

Fixes F2, F3, F4. Implements D1, D3.

- **R-M2.A** — `LICENSE` exists at repo root implementing D1: no-cost personal
  and internal use, copyright retained, redistribution prohibited, commercial
  use reserved, no warranty. Referenced from `README.md`.
- **R-M2.B** — **`tkcalendar` is removed from the dependency tree.** Its single
  use (`widgets/date_picker.py:121`) is replaced by a CustomTkinter month grid
  built on the stdlib `calendar` module — the pattern already used at
  `screens/drag_schedule.py:1009`.
  - **R-M2.B.1** — The replacement picker preserves the existing public
    interface of `date_picker.py` so no calling screen changes.
  - **R-M2.B.2** — The replacement honours the existing
    `settings.first_day_of_week` setting.
  - **R-M2.B.3** — `tkcalendar` appears in neither `requirements.txt` nor any
    import anywhere in `src/` or `tests/`.
- **R-M2.C** — `THIRD_PARTY_NOTICES.md` lists every runtime dependency with its
  license, and carries the pygame LGPL notice and relink statement required by
  R-M1.D.
- **R-M2.D** — No audio file is committed or bundled. `audio/` remains ignored.

### R-M3 — Continuous verification on a blank machine

Fixes F5.

- **R-M3.A** — `.github/workflows/tests.yml` runs the full suite on
  `ubuntu-latest` for each supported Python version, installing only from
  `requirements.txt`.
- **R-M3.B** — The suite runs headless. The 9 test files that instantiate real
  `ctk.CTk()` windows execute under `xvfb`, not skipped.
- **R-M3.C** — Success is determined by the pytest **exit code**. No step decides
  pass/fail by grepping stdout for `passed` (P24).
- **R-M3.D** — Root-level `test_*.py` files are collected by the same run, or
  relocated under `tests/` so they are.
- **R-M3.E** — The workflow contains no assertion of its own; every check lives
  in the pytest suite and can be run locally.

### R-M4 — Release pipeline hardening

- **R-M4.A** — After building, each OS job runs `--selftest` **from inside the
  packaged bundle** and fails the job on non-zero exit. A build that cannot
  start never becomes a release. This is the automated guard against F1
  recurring.
- **R-M4.B** — A SHA-256 checksum file is published beside each artifact.
- **R-M4.C** — Release body is populated from the matching `CHANGELOG.md` section.
- **R-M4.D** — `LICENSE` and `THIRD_PARTY_NOTICES.md` are included inside every
  distributed archive, not only in the repo.

### R-M5 — First-run experience

- **R-M5.A** — The app starts with no `credentials.json` present. Google Calendar
  and Gmail features are visibly unavailable with an explanatory message; no
  traceback, no crash, no blocking dialog.
- **R-M5.B** — The app starts with no music folder configured and none bundled.
- **R-M5.C** — The app starts against a brand-new empty database (schema init on
  first run) and, separately, against an existing populated database (P8).
- **R-M5.D** — The macOS Gatekeeper workaround is documented in `INSTALL.md`
  with the exact command, because the build is unsigned (D2).

### R-M6 — Documentation

- **R-M6.A** — `INSTALL.md` covers: download per OS, first-launch Gatekeeper
  step, run-from-source, optional Google setup, optional music folder, where
  data is stored per OS, and how to uninstall / remove data.
- **R-M6.B** — `README.md` Quick Start leads with **Download**, then
  run-from-source. Links `LICENSE` and `INSTALL.md`.
- **R-M6.C** — `docs/STANDALONE_BUILD.md` is corrected. It currently says "We can
  add a `.spec` file later if needed" — the spec file exists and is the
  supported path.
- **R-M6.D** — `CHANGELOG.md` exists with a `v0.1.0` entry.

### R-M7 — Repo hygiene

- **R-M7.A** — The 14 tracked root-level `test_*`, `diagnose_*`, `fix_*`,
  `debug_*` files are relocated (`tests/`, `tools/diagnostics/`) or removed.
- **R-M7.B** — `.gitignore copy` is deleted. The blanket `*.json` ignore rule is
  reviewed so a future required JSON resource is not silently dropped from the
  distribution — the same class of failure as F1.
- **R-M7.C** — Root-level docs aimed at agents rather than users (`GEMINI.md`,
  `AGENT_UI_REGRESSION_POLICY.md`, `QUICK_FIX_ZOMBIE_TOKEN.md`,
  `CLEAR_BROWSER_CACHE.md`, `AUDIO_TROUBLESHOOTING.md`, `fix_oauth_app_name.md`)
  are moved under `docs/` so the repo root reads as a product.

---

## 6. Out-of-scope items noted during research (not fixed here)

Per global rule 10 — adjacent issues found, deliberately not fixed:

- `google_calendar.py:322` reads credentials from `~/.getmoredone/` while
  `gmail_importer.py:75` uses `legacy_dot_dir()` and `paths.py` prefers
  `app_data_dir_path()`. Three locations for one concept. Not a release blocker.
- `test_obsidian_dialogs.py::test_dialog_instantiation` returns `bool` instead of
  asserting (PytestReturnNotNoneWarning). Will be a pytest error in a future
  major version.
- `requirements.txt` carries commented-out PyQt6 and Kivy blocks that no longer
  reflect any real option.

## 7. Definition of done

All `R-M*` criteria in §5 reach `done` in the status report, with a file path,
test name, or output artifact proving each. Criteria flagged human-review-only
in the implementation plan are signed off by explicit user confirmation.
