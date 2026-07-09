# Handoff Note

- Date: 2026-07-08
- Agent: Code
- Topic: Reusable column resizing; Scheduler all-columns resize + title-fill fix

## Summary
Extracted the column-resize behaviour into a reusable module and routed both list
screens through it. Fixed the Scheduler bug where a wide Title column still showed a
truncated title, and made **every** Scheduler data column resizable.

- **New** `src/getmoredone/screens/column_resize.py`: `ColumnResizer`, `ColumnSpec`,
  `chars_for_width`. One instance per screen owns column widths, persistence, the
  draggable divider handles, and live re-clamping of cell text. `set_cell_width`
  toggles whether a row cell's own width is set (Scheduler pills: yes; Today title,
  which sits inside a sub-frame: no — grid minsize + text clamp carry the width).
- **Scheduler** (`drag_schedule.py`): Title/Segment/SubSegment/Category/Start Date all
  resizable via dividers; slack moved to a trailing spacer column (col 6). Title text now
  clamps to the actual column width (fixed the fixed-20-char truncation). Deleted the
  old title-only handlers (`_on_title_resize_*`, `_update_column_widths`) and the now-dead
  `ITEM_/TITLE_/LINEAGE_` class constants.
- **Today** (`today.py`): migrated onto the shared resizer (Title-only, behaviour
  unchanged); deleted its bespoke handlers and the `clamp_title_col_width` helper.
- **AppSettings**: new `today_col_widths` / `drag_schedule_col_widths` dict fields
  (+`field` import); legacy `*_title_col_width` scalars kept as fallback.

## Files changed
- New: `src/getmoredone/screens/column_resize.py`, `tests/test_column_resize.py`.
- `src/getmoredone/app_settings.py`, `src/getmoredone/screens/drag_schedule.py`,
  `src/getmoredone/screens/today.py`.
- `tests/test_today_title_col_width.py` (updated to the new dict field).
- Docs: `docs/USER_GUIDE.md`, `NOTES.md`, this note.

## Verification
- Command: `./venv/bin/python -m pytest -q` → **365 passed, 1 skipped**.
- Headless smoke (`scratchpad/smoke_scheduler.py`): built Today → Scheduler → Today with
  real data and simulated resizing every column; **0 errors**. Title clamp at 700px = 87
  chars (was hard-capped at 20). App launches clean; `app.log` empty.
- Interactive drag/alignment: user visual pass pending (computer-use access denied this
  session).

## Risks / Known gaps
- Char clamp is an ~8px/char heuristic (proportional font); precise `font.measure()` is a
  possible later refinement — flagged, not changed.
- Scheduler dividers now use `palette["border"]` (visible) instead of the old invisible
  handle — intended (they mark the column end), but a visual change to confirm.

## Next agent actions
- Human: on the **Scheduler**, confirm titles fill the column (no premature "…"), every
  column has a draggable divider, and widths persist across restart. On **Today**, confirm
  the Title still resizes and the header stays pinned.
