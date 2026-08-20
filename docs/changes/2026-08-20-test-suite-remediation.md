# Handoff Note

- Date: 2026-08-20
- Agent: Code
- Topic: Test-suite remediation — meta marker, source-grep removal, live-data guard, vacuous-test scan

## Summary

All four tasks from `prompt-test-suite-remediation.md`, plus one fix for a
problem the user hit during the work (the suite putting windows on their
screen). No `src/` behaviour changed; the only `src/` edit is a docstring-free
refactor of `google_calendar`'s prints, committed earlier.

## Verification

| Run | Result | Wall clock |
|---|---|---|
| `pytest` | **1136 passed, 6 skipped, exit 0** | 55.9s |
| `pytest -m "not meta"` | **931 passed, 5 skipped, 206 deselected, exit 0** | **27.4s** |
| `pytest -m meta` | 198 passed, exit 0 | ~25s |
| Every file in **reverse** order | 1136 passed, 6 skipped, exit 0 | 56.2s |

Baseline before this batch: 1108 passed / 5 skipped, ~50s.

Success read from the **exit code** throughout, never from parsing stdout.

`pytest-randomly` is **not** in dev deps, so the prompt's randomised-order check
was conditional and did not apply. Rather than add a dependency, the suite was
run with every file in reverse order — the dependency-free equivalent for gross
order-dependence. Identical result, so **no order-dependent failure found**.
A true random-order check remains untested; recorded in `BACKLOG.md`.

## Task 1 — Quarantine the meta-test layer

**198 of 1113 tests (17.8%)** across seven files assert on the repository —
workflow YAML, packaging, licence files, docs, traceability — not on
application behaviour.

Marked with a module-level `pytestmark = pytest.mark.meta`, registered in
`pytest.ini`. `pytest -m "not meta"` is **45% faster** (27.4s vs 55.9s). The
default run is unchanged and still includes all of them.

Three guards stop the marker becoming silent coverage loss, driven through real
collection rather than by reading source for `pytestmark`:

- the marker covers **exactly** those files, so one added later cannot be
  marked per-function and miss a test;
- the default run still collects them — if `addopts` ever grew a default
  deselection, this catches it;
- `-m "not meta"` actually deselects, so the documented invocation is not a lie.

Mutation-checked: removing the marker from one file turns two of the three red.

**Worth recording:** the first insertion pass used "the last line matching
`^(import|from)`" and put the assignment **inside a parenthesised multi-line
import** — a `SyntaxError`. `end_lineno` is the only thing that knows where a
statement really ends.

## Task 2 — Eliminate source-grepping assertions

Five assertions used `inspect.getsource` plus a substring match: the shape that
produced the guard dead for months in `3892159`.

A substring match fails in **both** directions. It passes on a comment
containing the word — including the comment explaining why the check exists —
and it fails on a rename that changed nothing that matters.

| Assertion | Was | Now |
|---|---|---|
| `save_vision` must not use `CTkMessageBox` | substring | `references_name` — a real identifier, bare or attribute |
| `save_vision` still reports errors | substring | `calls_any_attribute` |
| `VPSPlanningScreen` tracks `selected_segments` | substring (satisfied by a *read*, or by prose) | `assigns_self_attribute` — a write |
| `pick_color` reaches the colour chooser | substring | `calls_attribute` |
| Settings iterates the counts **mapping** | substring | `iterates_mapping` |

Helpers in `tests/source_asserts.py`, with **12 tests of their own** — a helper
that silently returned `False` would make every converted assertion vacuous.
The positive cases are hostile on purpose: a docstring naming the call, a string
literal containing it, a variable of the same name, and a read where a write is
required. Each is what the replaced checks accepted.

Mutation-checked against **real app source**, not fixtures: removing the
`messagebox` call from `TLVisionEditorDialog.save_vision`, and the
`self.selected_segments` assignment from `VPSPlanningScreen.__init__`, each turn
the converted assertions red.

**Retained as source checks, with reasons:**

- The five above stay source checks because the alternative is building a full
  CustomTkinter screen with populated entry widgets — heavier and more brittle
  than the test it replaces. They are now *parsed*, which is the durable half.
- Everything else lives in files now marked `meta`, where asserting on the
  repository **is** the point (`test_ci_contract`, `test_release_licensing`,
  `test_traceability_refs`, …).
- No `> N` floor was introduced. `eac201f`'s floor was already fixed to an
  exact count before this batch.

## Task 3 — Verify no test can touch live data

**The audit found nothing to convert:** all 41 `DatabaseManager`/`DBManager`
constructions in tests already pass an explicit path — `3892159` fixed that.
The work was the guard that keeps it true.

Two layers existed: `pytest_sessionstart` redirects `GETMOREDONE_DB`, and
`pytest_sessionfinish` fingerprints the real files. Both are worth keeping, but
neither says **which test** did it — the fingerprint fires after the run,
naming a file.

`_forbid_resolving_the_real_database` now raises inside `resolve_db_path`, so an
escape names the offending line. Patched on **both** import spellings:
`getmoredone.paths` and `src.getmoredone.paths` are different module objects.

`tests/test_live_data_guard.py` proves all three layers fire. Mutation-checked:

| Mutation | Result |
|---|---|
| Remove the guard | 2 tests red |
| Patch only one import spelling | 1 test red — the two-module trap, caught |
| A test that asks for the real database path | Blocked, message names the file |

Plus a static AST check that no test constructs a manager with no arguments —
right here specifically because the alternative is to *run* the construction,
which is the thing being prevented.

## Task 4 — Vacuous-test scan

Scanned all 90 files for three shapes. Raw counts **19 / 10 / 0** — and most of
the first two were my scanner's false positives, which mattered more than the
fixes:

- 17 of 19 "returns a value" were `return` inside a **nested helper**. The real
  2 were `@pytest.fixture` functions named `test_*` (`test_item`,
  `test_contact`), which must return values. **Genuine count: zero**, confirmed
  by pytest reporting **0** `PytestReturnNotNoneWarning`.
- 3 of 10 "no verdict" assert through a shared `_assert_refiled()` helper.

A scan reporting those would have been switched off within a week, so the
permanent guard models fixtures, nested returns and asserting helpers — and has
adversarial tests in **both** directions.

**Seven genuine ones fixed, none deleted:**

| Test | Was | Now |
|---|---|---|
| `test_project_board_edit_icon_image_is_loaded` | body was `pass` | asserts `__init__` assigns `edit_icon_image`, which the card dereferences |
| `test_vps_init` | print-only; claimed "All VPS tests passed!" with no assertion; wrote `data/test_vps.db` **into the working directory** | `tmp_path`, real assertions on schema, seeding and a manager round-trip |
| `test_comprehensive_count` | print-only, including a line claiming the implementation "sees ALL record types" | asserts the refusal, the mapping type, that the reported total matches the blocking rows, and that nothing was deleted |
| `test_bulk_update_empty_list` | "should not raise" | snapshots before/after, asserts nothing moved |
| `test_bulk_update_nonexistent_items` | "should not raise" | same, plus no rows created |
| `test_refresh_timer_button_state_noop_without_button` | "must not raise" | asserts the outcome |
| `test_reload_swallows_widget_teardown_error` | "must not raise" | asserts the reload still happened |

**Three of my own assertions were wrong while writing these**, each corrected as
**(c) over-specified** rather than by weakening anything:

1. "one row per table" — creating a month tactic seeds its weeks, so the
   fixture yields 2 and 9, not 1 and 1;
2. a hardcoded six-table list — `delete_segment` counts **seven**, including
   `annual_initiatives`;
3. "every level populated" — `action_items` carries the column and legitimately
   holds zero.

The table list is now **derived from the schema**, so a new VPS level is covered
the day it is added.

`tests/test_no_vacuous_tests.py` keeps the class closed. Static on purpose, and
one of the few places that is right: a vacuous test cannot be found by running
it — running it is what produces the false green.

## Out of scope, fixed anyway: the suite was putting windows on screen

Raised by the user twice mid-batch. The guard called `withdraw()` **after**
CustomTkinter had already created and mapped the window, so every one of the
hundreds of window-building tests flashed a frame. Withdrawing later removes the
window, not the flash.

Alpha is now set at creation, before the withdraw — nothing is ever drawn.
Verified: `alpha=0.0, mapped=0` for an ordinary window; `alpha=0.0, width=400`
for one that needs real geometry.

**A first attempt made it worse.** I also silenced `deiconify` (it undoes
`withdraw`, so it looked like an obvious gap) and it **hung**
`tests/test_item_editor_sash.py`. Found by bisecting file-by-file with a
per-file timeout, confirmed by reverting that one line. It is also unnecessary:
with alpha applied at creation, a deiconified window is mapped and still
transparent. `conftest.py` records both halves so it is not re-added.

`GETMOREDONE_NO_MAPPED_WINDOWS=1` still exists but should now rarely be needed.

## Risks / Known gaps

- **Random-order testing is still untested.** `pytest-randomly` is not a dev
  dependency and one was not added. The reverse-order run catches gross
  order-dependence, not seed-sensitive interactions. In `BACKLOG.md`.
- **The `meta` split does not reduce what CI runs**, by design. It is a local
  iteration switch. If the 198 repo-assertion tests are genuinely too brittle,
  that is a separate decision about whether they should exist — not something
  a marker settles.
- **Ten tests from Batch 3 recorded in `BACKLOG.md` as unable to fail were not
  fixed here.** They pre-date this batch's scan shapes (they assert *something*,
  just not the thing they name), so the vacuous scan does not catch them. They
  need individual attention.
- **`test_source_asserts.py` and `test_live_data_guard.py` are not marked
  `meta`.** They test helpers and path behaviour, not the repository. Arguable
  either way; left unmarked deliberately.

## Next agent actions

- The ten Batch 3 tests in `BACKLOG.md` that assert the wrong thing.
- The four remaining files describing the retired multi-agent workflow
  (`docs/MULTI_AGENT_WORKFLOW.md`, `.agents/prompts/*.md`,
  `tools/agents/setup_worktrees.sh`).
- Batch 4 of the backlog-clearance plan: rename-safe links, spec and plan
  approved, nothing built.
