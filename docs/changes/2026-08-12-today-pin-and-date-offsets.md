# Handoff Note

- Date: 2026-08-12
- Agent: Code
- Topic: today-drag-to-top-pin + inline-date-offset-ladder

## Summary
Two Today-list enhancements.

1. **Drag an item to the top of Today = pin above all others (persistent).**
   New nullable `action_items.today_pin_rank` column (independent of the derived
   `priority_score`, which stays `I×U×S×V`). Each open row gets a drag grip
   (`⣿`); **dragging the grip upward** (≥ `PIN_DRAG_THRESHOLD` px) calls
   `DatabaseManager.pin_item_to_today_top()`, which sets the item's rank one
   above the current max so it sorts first. Ordering keys float pinned rows to
   the front in normal, Top-3, and search modes. The pin survives editor saves,
   priority edits, and reschedules (nothing recomputes it).

   Drag mechanics: the pin decision is made purely from the press→release
   `y_root` delta. The first implementation gated on `<B1-Motion>` and a live
   `winfo_pointery()` drop-zone; `<B1-Motion>` does not fire reliably on a
   CTkLabel, so `moved` never became true and no gesture ever pinned. Press and
   release are bound directly on the grip (Tk's implicit button grab keeps both
   on the grip), with no toplevel binding.

2. **Inline date modal (Start/Due) offset ladder.** In `InlineDateDialog`,
   removed the old current-date `+1` button and added a "From today:" row of
   `+1 +2 +3 +4 +5 +6 +7 +10 +14` buttons (config: `TODAY_OFFSET_BUTTONS`), each
   setting the date to today + N (weekend-aware via `set_today`). `Today`, `-1`,
   `Clear` retained; dialog resized to 600x175.

## Files changed
- src/getmoredone/models.py (add `today_pin_rank` field)
- src/getmoredone/database.py (schema column + idempotent migration)
- src/getmoredone/db_manager.py (INSERT/UPDATE/row-map + `pin_item_to_today_top`)
- src/getmoredone/screens/today.py (grip, drag handlers, pin-aware sort keys, COL0_WIDTH)
- src/getmoredone/screens/inline_editors.py (offset ladder, `TODAY_OFFSET_BUTTONS`)
- tests/test_today_pin.py (new — migration, pin ordering, persistence, adversarial sort)
- tests/test_today_pin_drag.py (new — drag-gesture handlers + end-to-end render order)
- tests/test_inline_date_offsets.py (new — offset ladder buttons + behavior)

## Verification
- Command: `./venv/bin/python -m pytest -q`
- Result: PASS (440 passed, 1 skipped pre-existing) before new tests;
  new+related subset: `pytest tests/test_today_pin.py tests/test_today_pin_drag.py tests/test_inline_date_offsets.py tests/test_today_screen.py tests/test_date_adjustment.py tests/test_today_title_col_width.py` → 22 passed.

## Risks / Known gaps
- Drag-to-top pins on any sufficient upward grip drag (the only destination is
  the top). Downward/no-travel gestures are no-ops; there is no arbitrary
  reorder and no explicit "unpin" UI. Ranks are monotonic integers.
- GUI test note: `event_generate` + `root.update()` deadlocks on a *withdrawn*
  CTk window; the event-level drag test keeps the window mapped.
- Docs sync: user-facing behavior changed → USER_GUIDE / CHANGELOG should note
  both features (Docs Agent).

## Next agent actions
- Docs Agent: add both enhancements to `docs/USER_GUIDE.md` and `CHANGELOG.md`.
- Optional follow-up: extend drag to arbitrary reorder + an unpin affordance.
