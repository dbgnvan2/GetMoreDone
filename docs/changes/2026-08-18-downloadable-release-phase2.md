# Handoff — Downloadable release, Phase 2 (remove the GPL dependency)

**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_downloadable_release.md` — R-M2.B
**Plan:** `docs/implementation_plan_2026-08-18_downloadable_release.md` — Phase 2
**Agent:** Code

## Summary

Fixed finding F2: `tkcalendar` is GPLv3, and shipping it inside a binary
distributed under the proprietary license of decision D1 would violate the GPL.
Its single use — the calendar popup in `widgets/date_picker.py` — is
reimplemented on the stdlib `calendar` module, following the pattern already in
`screens/drag_schedule.py`.

`pygame` (LGPL, finding F3) is deliberately **kept**. LGPL is permissible in a
proprietary product provided the user can relink, which the one-folder
packaging asserted in Phase 1 provides.

Per the plan's ordering, the picker's contract tests were written against the
**tkcalendar-backed** widget and confirmed green *before* the rewrite. A
contract recorded after a rewrite only describes the rewrite.

## Files changed

| File | Change |
|---|---|
| `src/getmoredone/widgets/date_picker.py` | Rewritten on stdlib `calendar`. Public interface unchanged. New pure functions `month_grid`, `weekday_headers`, `normalize_first_day_of_week`; new methods `select_day`, `select_today`, `show_next_month`, `show_previous_month`, `close_calendar`, `visible_month`, `header_labels`. Colors now come from theme tokens (R-M2.B.1, R-M2.B.2) |
| `requirements.txt` | `tkcalendar` removed (R-M2.B.3) |
| `tests/test_date_picker.py` | **New.** 30 tests |
| `tests/test_release_licensing.py` | **New.** 6 tests |

### Interface additions (all backward compatible)

`DatePickerButton.__init__` gains an optional `settings=None` keyword, resolved
lazily from `AppSettings.load()` when the popup opens. Both existing call sites
(`screens/vps_editors.py:1248`, `:1257`) construct the picker with a parent and
nothing else, and needed no change.

## Test / verification status

| Check | Result |
|---|---|
| Contract tests green against the **old** tkcalendar widget | Confirmed — 9 passed before the rewrite; 21 new-behaviour tests red at that point |
| `pytest tests/test_date_picker.py` after the rewrite | **30 passed** — including all 9 pre-recorded contract tests |
| `pytest tests/test_release_licensing.py` | **6 passed** (3 were red before the swap) |
| Full suite, **tkcalendar and babel uninstalled from the venv** | **511 passed, 1 skipped — exit 0** |
| `tkcalendar` importable? | No — `ModuleNotFoundError`, confirmed after uninstall |
| Remaining `tkcalendar` references | Prose only (spec, plan, handoffs, docstrings explaining the removal). No import, no requirements entry. Verified by AST scan, not grep |
| Real-screen check | `WeekActionEditorDialog` built under the venv with a real `CTk` root: 31 day buttons for 2026-08, headers `Mon…Sun` from the real setting, month navigation across the boundary, selection writes `2026-09-12` back and closes the popup, second picker independent |
| `run.py --selftest` | 4/4 passed, exit 0 |
| App launch from source | Alive 10s, no errors in the log |

## Notes on test design

- `test_rm2b3_no_gpl_dependency_anywhere` parses **imports via the AST** rather
  than grepping for the string. A text search flagged the docstrings that record
  *why* tkcalendar was removed, which would have pressured someone into deleting
  the explanation to stay green. `test_rm2b3_import_scan_would_actually_catch_a_gpl_import`
  proves the scan is not a no-op.
- `test_rm2b3_installed_runtime_deps_have_no_gpl_license` walks the whole
  declared runtime tree, so a *future* GPL dependency fails too — not just this
  one. Its classifier separates GPL from LGPL and has its own adversarial test,
  because a naive `"gpl" in text` check flags pygame and would get weakened.
- `test_rm2b2_month_grid_matches_stdlib_calendar` asserts against
  `calendar.Calendar(...).monthdayscalendar` for all 7 first-day values across 5
  months, rather than a recorded snapshot.

## Follow-ups

- Phases 3–6 remain: `tests.yml` CI, release-pipeline hardening, `LICENSE` /
  `THIRD_PARTY_NOTICES.md` / `INSTALL.md` / `CHANGELOG.md`, hygiene.
- R-M2.C (third-party notices) and R-M2.D (no audio committed) are **not** in
  `tests/test_release_licensing.py` yet — they arrive in Phase 5 with the
  notices file. The module docstring says so.
- `learning-qa` over the full diff is still scheduled for Phase 6 step 25.
- The venv on this machine no longer has `tkcalendar`/`babel`. Another machine
  syncing this repo should reinstall from `requirements.txt` to match.

## Adjacent issues found, not fixed

- Carried over from Phase 1: two tests in `tests/test_vps_segments.py` `return`
  a bool instead of asserting; `themes/base_dark_blue.json` ships but is absent
  from `theme.THEME_NAMES`.
- `requirements.txt` mixes test-only dependencies (`pytest`, `pytest-cov`) with
  runtime ones. The licensing test has to carry a hardcoded `TEST_ONLY_PACKAGES`
  set to tell them apart. A `requirements-dev.txt` split would remove that
  guesswork.

## Correction — unrelated work swept into this commit

Commit `81f9b54` was staged with `git add -A`, which picked up two files that
are **not** part of Phase 2 and were being edited concurrently in another
session on this same working tree:

- `src/getmoredone/screens/item_editor_weekly_tactic_dialog.py` — assigns
  `self.palette = semantic_colors()`, fixing a `SetWeeklyTacticDialog` that
  referenced `self.palette` without ever setting it
- `tests/test_weekly_item_filters.py` — the regression test for that fix

Nothing was lost and both are correct — `tests/test_weekly_item_filters.py`
passes (2 passed), and the full-suite result of 511 quoted above already
included them. But the commit message describes only the tkcalendar work, so
`81f9b54` contains more than it claims.

History was left alone rather than rewritten: `main` is already pushed, and the
other session may have work based on it. Staging for the remaining phases uses
explicit paths instead of `git add -A`.
