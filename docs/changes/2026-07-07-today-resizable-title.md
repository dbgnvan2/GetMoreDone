# Handoff Note

- Date: 2026-07-07
- Agent: Code
- Topic: Today view — pinned column headers + resizable Title column

## Summary
Brought the Scheduler's spreadsheet-style column resizing (commit `13cab10`) to the
**Today** screen. Added a pinned column-heading row that stays fixed while the list
scrolls, and made the first text column ("Title", grid column 1) a fixed, draggable
width. A 4px vertical divider on the right edge of the "Title" header is both the
"end of column" line and the drag handle (`sb_h_double_arrow` cursor). Dragging
live-resizes the column and re-clamps each row's title text with `…`. The width
persists across sessions via a new `today_title_col_width` AppSettings field
(default 260px, clamped to 120–800). Scope: **Title column only**, per user choice.

## Files changed
- `src/getmoredone/app_settings.py` — new `today_title_col_width: int = 260` field.
- `src/getmoredone/screens/today.py` — module-level `clamp_title_col_width` +
  `TITLE_COL_MIN/MAX_WIDTH`; `__init__` re-layout (toolbar row 0, pinned header row 1,
  scroll list row 2); `_build_column_header`, `_on_title_resize_start/drag/stop`,
  `_title_max_chars`, `_update_title_column_width`; `create_item_row` now sets a fixed
  minsize on col 1, a trailing weight spacer (col 99), clamps the title text, and stashes
  `frame.item` / `_title_label` / `_title_has_badge` for live resize.
- `tests/test_today_title_col_width.py` — new (default, save/load round-trip, clamp bounds).
- `docs/USER_GUIDE.md`, `NOTES.md` — documented the feature.

## Verification
- Command: `./venv/bin/python -m pytest -q`
- Result: PASS — 357 passed, 1 skipped (was 354 before; +3 new).
- App launch: `./venv/bin/python run.py` starts clean; `app.log` empty (no exceptions).
- GUI: user-confirmed "all good" on the running app — header renders as a single
  row-height pinned line with aligned columns and a working Title drag-divider.
- Fix during review: the divider `CTkFrame` had no `height`, so it defaulted to 200px and
  inflated the header band; set `height=22` to collapse the header to one row's height.

## Risks / Known gaps
- **Pinned-header alignment** uses a fixed `padx=25` inset (scroll outer 20 + per-row 5)
  to line the header columns up over the scrolled rows. This is an estimate of the
  `CTkScrollableFrame` inset; if columns drift on a given display, tune the header
  `padx` and the leading-cell paddings in `_build_column_header`.
- Title text re-clamp uses an ~8px/char heuristic (`_title_max_chars`); very wide/narrow
  fonts may clamp slightly early/late. Cosmetic only.
- Header colors are captured at build time; a live theme switch won't recolor the header
  until the screen is recreated (matches existing screen behavior).

## Next agent actions
- Human: open **Today**, confirm the header stays pinned while scrolling, drag the Title
  divider to resize, confirm titles re-clamp and the width survives an app restart. Adjust
  `padx` inset if needed.
- Docs Agent: none required — USER_GUIDE + NOTES updated here.
