# Implementation Plan — Resizable columns on the Scheduler tab (Action Items list)

Date: 2026-06-22
Target file: `src/getmoredone/screens/drag_schedule.py`
Supporting file: `src/getmoredone/app_settings.py`

## Feature request (verbatim intent)

On the **Scheduler** tab, the **Action Items** list (left panel) columns —
Title, Segment, SubSegment, Category, Start — must be **resizable by dragging a
divider between the column headings**, the way most list views behave. "Title"
is the motivating column, but the behavior applies to every column.

User decisions (confirmed 2026-06-22):
- Column widths **persist across app restarts**.
- **No** double-click-to-auto-fit (drag-resize only).

## Current state / why a small refactor is needed

In `DragScheduleScreen` (left "Action Items" list):
- The header is built inline in `refresh()` (lines ~306–327) as its own frame
  with **5** grid columns and per-column `minsize` from class constants
  (`TITLE_COL_MIN_WIDTH=260`, `LINEAGE_COL_MIN_WIDTH=150`).
- Each data row is a **separate frame** returned by `create_item_row()`
  (lines ~658–767) with **6** grid columns using **different** constants
  (`ITEM_TITLE_COL_WIDTH=220`, `ITEM_META_COL_WIDTH=170`), plus a trailing
  "Start" column the header never declares.

Consequences that block the feature and are corrected here:
- Header and rows are **not aligned today** (different widths; header missing
  the Start heading).
- There is no shared column-width model to drive a drag, and no sash widgets.

Approach: keep the per-row-frame structure (needed for per-row background,
height, hover, drag-to-schedule) but drive **all** frames (header + every row)
from a single shared width model so columns stay aligned, then overlay draggable
sash grips on the header.

## Design

1. **Shared width model.** New instance dict
   `self.col_widths = {"check","title","segment","subsegment","category","start"}`
   (pixels), seeded from settings, falling back to defaults derived from current
   constants.

2. **Settings persistence.** Add to `AppSettings`:
   ```python
   scheduler_action_col_widths: dict = field(default_factory=dict)
   ```
   (requires importing `field`). Empty dict ⇒ use code defaults. Saved/loaded by
   the existing `asdict`/`load` machinery (dict of ints is JSON-safe). A
   normalizer drops unknown keys and clamps each width to a minimum.

3. **One column-config helper.** `_apply_action_columns(frame)` sets
   `grid_columnconfigure(idx, minsize=w)` for all 6 columns from `self.col_widths`
   (last column `weight=1` to absorb slack). Used by **both** the header and
   every row frame, guaranteeing alignment.

4. **Header gains all 6 columns**, including the missing **Start** heading, and
   uses `_apply_action_columns`.

5. **Labels track pixel width.** Each row label's `width=` is set from
   `self.col_widths`; the char-truncation count passed to `format_column_text`
   is derived from the pixel width (≈ width / avg-char-px) so widening Title
   shows more text instead of staying clipped at a fixed char count.

6. **Sash grips.** After the header is built, overlay thin (6px) grip frames
   (cursor `sb_h_double_arrow`) at each interior column boundary using `.place()`
   at the cumulative-width x-offset, `relheight=1`. Bound to:
   - `<ButtonPress-1>` → record start x.
   - `<B1-Motion>` → `_resize_action_column(boundary_index, delta_px)`: widen the
     left column / clamp to `COL_MIN_PX`, re-apply `_apply_action_columns` to
     header + all visible row frames live, reposition grips.
   - `<ButtonRelease-1>` → write `self.col_widths` into settings and `save()`.
   Grip x-positions recomputed on resize and on header `<Configure>`.

7. **Drag-to-schedule isolation.** Grips are separate widgets bound only to their
   own handlers; they do not call `bind_drag_handlers`, so column-resize never
   triggers an item drag.

## Acceptance criteria → verification

Self-assigned IDs (no upstream spec). Each criterion maps to a file line, an
automated test, or flagged human verification.

| ID | Criterion | Verification |
|----|-----------|--------------|
| RC1 | `AppSettings` has `scheduler_action_col_widths` defaulting to `{}` | pytest `test_rc1_settings_field_default` — `AppSettings().scheduler_action_col_widths == {}` |
| RC2 | Column widths round-trip through save/load | pytest `test_rc2_col_widths_persist` — set dict, `save()`, `load()`, assert equal |
| RC3 | Width normalizer clamps below-min and drops unknown keys | pytest `test_rc3_col_widths_normalized` — feed bad dict, assert clamped/filtered |
| RC4 | Header declares all 6 columns incl. a "Start" heading | pytest widget test `test_rc4_header_has_start_heading` — build screen, assert a header label text == "Start" |
| RC5 | Header and a data row share identical column minsizes | pytest widget test `test_rc5_columns_aligned` — assert `grid_columnconfigure(i,'minsize')` equal for header vs row, all i |
| RC6 | `_resize_action_column` widens target column and persists | pytest widget test `test_rc6_resize_updates_and_saves` — call with +40px, assert `col_widths['title']` grew and settings saved |
| RC7 | Column width below `COL_MIN_PX` is clamped on resize | pytest widget test `test_rc7_resize_clamped` — call with large negative delta, assert == `COL_MIN_PX` |
| RC8 | Sash grip widgets exist (one per interior boundary) | pytest widget test `test_rc8_grips_present` — assert count of grip widgets == 5 |
| RC9 | **Human:** dragging a divider visibly resizes the column live and the width survives an app restart; app.log clean | **Human verification** — run under venv, drag Title divider, restart, confirm width retained (per memory: real-widget verification required) |

RC9 is flagged as not fully code-testable: real mouse-drag feel and the
restart-persistence round trip through the live UI need a human check. Automated
tests cover the underlying `_resize_action_column` logic and persistence (RC6/RC2)
so the human check is confirmation, not the only evidence.

## Order of implementation

1. RC1–RC3: settings field + normalizer (+ unit tests). No UI dependency.
2. RC4–RC5: shared `_apply_action_columns`, rebuild header with 6 cols, route
   `create_item_row` through it. (Alignment fix.)
3. RC6–RC8: `self.col_widths` model, sash grips, `_resize_action_column`,
   persist-on-release.
4. RC9: run app, manual verify, capture in handoff note.

## Adjacent issues found, not fixed (per workflow rule 8)

- **A1** — The **Date Boxes** list (`_configure_date_box_columns`, lines ~830–835)
  and the **Projects** boxes use their own fixed `minsize` columns and are also
  not user-resizable. Out of scope for this request (Action Items list only);
  noted in case you want the same treatment later.
- **A2** — `create_item_row` hard-codes per-column `width=` and char counts
  (`ITEM_TITLE_CHARS`, `ITEM_META_CHARS`); these constants become partly
  redundant once widths are dynamic. This change will leave them as the seed
  defaults rather than deleting them, to keep the diff reviewable.

## Out of scope

- Reordering columns, hiding columns, or resizing the Date Boxes / Calendar /
  Projects tabs.
- Auto-fit on double-click (explicitly declined).
