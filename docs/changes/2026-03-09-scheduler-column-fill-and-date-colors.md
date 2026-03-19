# Handoff Note

- Date: 2026-03-09
- Agent: Code
- Topic: scheduler-column-fill-and-date-colors

## Summary
Updated the Drag Schedule screen UI to present itself as `Scheduler`, widened the Segment/SubSegment/Category cells into fixed-width filled columns, restored the left list to the intended four-column layout (`Title`, `Segment`, `SubSegment`, `Category`) by removing the separate Date list column, changed the item date cell background logic to overdue red, today green, and future yellow, converted the Date Boxes list into aligned left-justified Day/Date/Items/Time columns with full weekday names, added a draggable vertical splitter between the two panels, renamed the left panel to `Action Items` with darker drag guidance text, added a manual refresh button next to the Days selector that clears any clicked date filter and restores the full Next-days/Who result set, added click-to-filter behavior from date targets, added header filters for `Segment` and `SubSegment` that apply to both the left list and right-side date views, and added a right-side `Calendar` tab that renders the visible month as a calendar-style drop/filter view with footer boxes for `Next Month`, `Next Quarter`, `Near Term`, and `Long Term`. Also added a shared lineage helper and updated the `Today`, `Upcoming`, `All Items`, and `Hierarchical` List Views to show the additional `Segment`, `SubSegment`, and `Category` columns. Also added a persisted `business_year_start_mmdd` setting and exposed it in Settings -> Database Management, and improved date-target contrast by using contrast-aware text fallback plus softer high-load pink/red tones.

## Files changed
- src/getmoredone/screens/drag_schedule.py
- src/getmoredone/screens/item_lineage.py
- src/getmoredone/screens/today.py
- src/getmoredone/screens/upcoming.py
- src/getmoredone/screens/all_items.py
- src/getmoredone/screens/hierarchical.py
- src/getmoredone/app_settings.py
- src/getmoredone/screens/settings.py
- tests/test_vision_planning_regressions.py
- tests/test_theme_settings.py
- tests/test_future_dates.py

## Verification
- Command: `python3 -m py_compile src/getmoredone/screens/drag_schedule.py src/getmoredone/app_settings.py src/getmoredone/screens/settings.py`
- Result: PASS
- Command: `pytest -q tests/test_vision_planning_regressions.py tests/test_theme_settings.py tests/test_future_dates.py`
- Result: PASS
- Command: `pytest -q tests/test_vision_planning_regressions.py tests/test_color_contrast.py`
- Result: PASS
- Command: `pytest -q tests/test_vision_planning_regressions.py`
- Result: PASS

## Risks / Known gaps
- The sidebar navigation label remains `Schedule`; only the screen header was renamed to `Scheduler`.
- The lineage columns are fixed to a 15-character display width via truncation plus fixed column width, not dynamic font-measured sizing.
- The new calendar tab shows a single month grid for the current month; it does not yet page across months or render multi-month ranges when the selected day window extends further.

## Next agent actions
- Terminology note: `List Views` means the `Today`, `Upcoming`, `All Items`, and `Hierarchical` screens.
- Save for next phase: review documentation drift, especially mixed-case user-guide references and index accuracy.
- Save for next phase: continue the color-token refactor, since the UI still has many hard-coded color overrides outside this screen.
- Save for next phase: clean up legacy root-level tests that return booleans instead of asserting, which currently emits pytest warnings and could break under stricter pytest behavior.
- Save for next phase: do a broader pass on architecture seams in the screen layer, since feature complexity is still concentrated there.
