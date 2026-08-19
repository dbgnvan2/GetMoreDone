# Changelog

All notable changes to GetMoreDone are recorded here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
conventions and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **File an Action Item under a Project from the item editor.** A new **Set Project**
  button beside Set Wk Tactic opens a project picker that also creates a Project inline
  (**+ New Project**), so a new task and the project it belongs to can be created from one
  screen. **Clear Project** unfiles the item. Filing stamps the project's Annual Plan Element
  onto the item — the same rule as dragging onto a project in the Scheduler — and the link is
  only written when the selection actually changes, so an ordinary Save can never clear it.
- **An Action Plan block in the top left of the item editor**, showing the item's Project and
  Weekly Tactic together. The Weekly Tactic and Orig. Week fields moved here from the
  Organization tab, which now holds Group and Category only.
- **A follow-up inherits the original's Project**, the way it already inherited the weekly
  lineage. The same applies to complete-and-create. Previously a follow-up of a project task
  landed unfiled.

- **A Weekly Tactic link of its own.** `action_items.weekly_tactic_id` replaces the
  overloaded use of `parent_id`, which previously served both ordinary subtask nesting
  and the week bucket at the same time — so attaching a tactic silently destroyed a
  hierarchy, and setting a parent silently destroyed the tactic link. An item can now be
  both a subtask and week-filed. The migration moves existing week links across and
  leaves daily nesting untouched, reporting both counts.
- **One owner of week identity and week numbering** (`week_calendar.py`). Week numbers
  now carry their year: 2026-12-28 and 2027-01-01 are both ISO week 53, and a bare `53`
  cannot say which. A new **First week of year** rule (`iso`, `jan1`, `first_full`)
  defaults to `iso`, which is how every existing database was numbered.
- **Project start and end dates** on Project Boards. Informational only — never
  validated and never derived from the items on the board, because a project may span
  any timeframe.
- **`weekly_tactic_start_date`** on Action Items, recording the week an item was
  originally meant to start. Existing items are left blank; nothing is backfilled.
- **Changing an Action Item's start date re-files it into the right Weekly Tactic**,
  creating any missing Quarter, Month and Week records along the way — including across
  a year boundary. The item's dates move by whole weeks so a Thursday task stays on a
  Thursday, and an item never spans two weeks.
- **Completing an item re-files it to the week you completed it in**, while
  `weekly_tactic_start_date` goes on holding the week it was originally meant to start,
  so a push-out stays visible. Re-opening does not undo that.
- **A new year is built from your existing plan structure, not invented.** The vision
  element, segment and key field carry across; the editorial text — vision statement, key
  priorities, theme, objective — is left blank for you to write, and those rows are
  flagged so the app can tell a stub from something you wrote. When a save creates them,
  it says so.
- **A first-week-of-year setting** under Settings, and project start/end dates on Project
  Boards.

### Fixed

- **Duplicate Weekly Tactics are merged**, one per Annual Plan Element per week, and a
  unique index keeps it that way. The surviving tactic keeps whichever row held more
  children, every reference is moved onto it before the other is deleted, and its title
  is re-derived — the real duplicate in the wild was titled `W8` for a week that is
  ISO week 9, so keeping the older row alone would have kept a wrong number.
- **A Weekly Tactic that cannot move now says so.** Only one tactic can occupy a week
  for a plan element, and a move onto an occupied week used to be reported as a clean
  save while nothing happened. The Today, Upcoming, All Items and Reschedule surfaces
  now tell you, and the reschedule history records where the item actually landed
  rather than where it was asked to go.
- **The weekly-items drag path reports what happened.** Dragging a plan element onto a
  week that already had a tactic produced no refresh, no message and no sign of
  rejection; the same drag with no week selected did nothing at all.



- **Two release-workflow steps could have succeeded while publishing nothing.**
  `actions/upload-artifact` defaults `if-no-files-found` to `warn`, and
  `softprops/action-gh-release` defaults `fail_on_unmatched_files` to `false` — so a
  glob matching nothing would have produced a green run with a missing artifact, or a
  public Release with correct notes and zero downloadable assets. Both now fail. The
  two are not equally strict — `if-no-files-found` fires only when a step's whole path
  set matches nothing, while `fail_on_unmatched_files` is per-pattern.

### Added

- **The release workflow can now sign and notarise the macOS build**, which removes the
  Gatekeeper prompt entirely. It is off until six Apple credentials are configured as
  repository secrets, and skips itself cleanly when they are absent — see
  `docs/CODE_SIGNING.md`. With credentials present, any signing failure fails the build
  rather than quietly publishing an unsigned one.

### Changed

- **The item editor's Duplicate button is gone; Add Follow-up is the one copy path.** A
  follow-up is a copy that also keeps the link back to the original, and it now saves the
  edits on screen before copying — a guard the Duplicate path had and the follow-up path
  did not, so a follow-up used to be built from the stored row while on-screen edits were
  left behind.
- **Item editor buttons re-paired**: Cancel sits beside Timer, Add Follow-up beside Add
  Subtasks (renamed from "Add Sub-tasks"), Set Parent beside Show Related, and Set Wk Tactic
  beside Set Project.
- Gatekeeper instructions now lead with the macOS 15 (Sequoia) System Settings route.
  Apple removed the Control-click override in macOS 15, so the old advice was wrong for
  every current Mac.
- All GitHub Actions moved off the deprecated Node 20 runtime: `actions/checkout` v7,
  `actions/setup-python` v7, `actions/upload-artifact` v7,
  `softprops/action-gh-release` v3.

## [0.2.0] - 2026-08-18

The first release whose binaries actually run.

Versions v0.1.0, v0.1.2 and v0.1.05 (February 2026) shipped binaries that
crashed on launch before showing a window — see "Fixed" below. This release
skips to 0.2.0 rather than reusing a version number that already has a
published release.

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

[Unreleased]: https://github.com/dbgnvan2/GetMoreDone/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dbgnvan2/GetMoreDone/releases/tag/v0.2.0
