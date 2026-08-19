# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: csdp-sweep-fixes

## Summary

The `/csdp` pre-push sweep over the six-commit item-editor batch, and the
second-pass sweep over the fixes it produced. Twelve findings, ten fixed, two
answered as doc corrections.

**First pass (8 findings, over `d0c65af...64221c2`):**

1. `save_item_if_needed` is the *second* insert path for a new item — "Create
   Note", "Link Note" and the calendar all go through it — and it applied
   neither the Project chosen before the first save nor the pending Weekly
   Tactic. The Action Plan block went on displaying a choice with no row behind
   it (P5 sibling, P6).
2. The tactic picker tears the dialog down and reopens it, discarding an
   unsaved Project — and Set Wk Tactic now sits directly beside Set Project.
3. Two stale column indices survived the Context removal: `today.btn_col_start`
   and `all_items`' action-button `col`, both computed away from the deleted
   cell (P12).
4. An exclusive re-link on a multi-linked item removed the others silently.
5. Nothing said that filing an item stamps the project's APE onto it.
6. `link_item_to_project_exclusive` deletes before it inserts with no
   transaction — a failure between the two left the item filed under nothing.
7. `complete_and_create` has no caller in `src/`; the docs implied two live
   paths. Corrected, not code-changed.
8. A raise in the picker's "+ New Project" callback was swallowed by Tk.

**Second pass (4 findings, over the fix commit) — two of them in the fixes:**

1. Fix 1 had **inverted the APE precedence**: it applied the project link before
   the tactic, and the tactic re-file writes its own APE, so the stored value
   depended on whether the user pressed Save or Create Note. Reordered to match
   `save_item`.
2. The new column checker **deduplicated** the column list, so two widgets in
   one cell read as OK — and over-correcting a stale index produces exactly that
   overlap, in the direction all three constants had just moved (P24). It now
   reports `DUP` separately and renders the expanded layout too.
3. The confirmation dialog had no test running its body; both tests replaced it
   with a lambda.
4. `save_item_if_needed` still missed three more of `save_item`'s new-item
   fields. Two applied (`segment_description_id`, the original-week stamp);
   `week_action_id` deliberately left out as the dead legacy FK.

## Files changed

- `src/getmoredone/screens/item_editor.py`, `item_editor_notes.py`,
  `item_editor_project_dialog.py`, `today.py`, `all_items.py`
- `src/getmoredone/db_manager.py`, `db_manager_project_boards.py`
- `tests/render_list_screen.py` (new subprocess helper),
  `tests/test_item_editor_project_link.py`, `tests/test_item_editor_no_context.py`,
  `tests/test_weekly_tactic_surfaces.py`
- `LEARNINGS.md`, `BACKLOG.md`, `CHANGELOG.md`,
  `docs/spec_coverage_2026-08-19_item_editor_project_link.md`

## Verification

- Command: `venv/bin/python -m pytest -q`
- Result: PASS — 899 passed, 2 skipped, exit code 0
- Each high-severity fix has a test **proven to fail without it**:
  - atomicity: without the transaction the item ends up with zero links
  - stale column: reports `GAP [0..8, 10]`
  - over-corrected column: reports `DUP [0..8, 8]`
  - APE precedence: "the two insert paths disagree: Save -> A, Create Note -> B"

## Risks / Known gaps

- The column check renders in a **subprocess** with a 120s timeout, because
  CustomTkinter hangs when a screen is built after other tests in the same
  interpreter have created and destroyed CTk roots. It skips rather than fails
  when Tk has no display.
- Answering "No" to the multi-link confirmation still closes the picker —
  `SetProjectDialog._finish` destroys unconditionally. The selection is
  correctly unchanged; the user just has to reopen it.
- The confirm alert is parented to the editor while the picker holds the grab.
  Fine on macOS; may stack oddly on X11/Windows. Untested.
- `with self.db.conn:` rolls back the whole connection — recorded as an open
  risk in `LEARNINGS.md` for the day either function is called inside a
  `transaction()` whose exception is caught.

## What the sweep did not assess

Both passes cover one family — failures that hide, in I/O, external calls,
ingest, state and scoring. Neither covers logic correctness generally,
concurrency, authz, injection, performance, dependency risk, API compatibility,
or CustomTkinter visual regression across the other screens.

## Next agent actions

- Restart GetMoreDone to pick up the batch.
- Work the deferred decisions now listed in `BACKLOG.md`, starting with which
  linking model is the rule.
