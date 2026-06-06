# Implementation Plan: Bulk Edit Start Date & Priority in Project Board

**Date:** 2026-06-06  
**Feature:** Add checkbox-based multi-select and bulk edit dialog to set Start Dates and Priority for project board action items.

## Acceptance Criteria & Verification

### AC1: Checkbox selection in project items list
**ID:** AC1  
**Description:** Each action item in the project detail panel shows a checkbox. Multiple items can be selected simultaneously.  
**Test:** 
- File: `tests/test_project_board_bulk_edit.py:test_project_board_items_have_checkboxes`
- Verify checkbox elements rendered next to each item title in the items list

### AC2: Bulk edit dialog opens from toolbar
**ID:** AC2  
**Description:** A new "Bulk Edit" button appears in the project items toolbar, only enabled when ≥1 item is selected. Button opens a dialog.  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_bulk_edit_button_enabled_when_items_selected`
- Assert button exists, disabled when no items selected, enabled when ≥1 selected
- Assert clicking button opens CTkToplevel dialog

### AC3: Dialog allows independent Start Date and Priority changes
**ID:** AC3  
**Description:** Dialog has two input fields (Start Date, Priority) with clear/omit options. User can change one, both, or neither without affecting unspecified fields.  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_bulk_edit_dialog_fields`
- Assert Start Date field exists (date picker or entry)
- Assert Priority field exists (combo box)
- Assert both have "clear/skip" options

### AC4: Date validation — future dates only
**ID:** AC4  
**Description:** Start Date field rejects past dates; only accepts today or future dates. On validation error, show error message and prevent save.  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_start_date_must_be_future`
- Attempt to set past date → error dialog shown
- Attempt to set today/future date → accepted

### AC5: Due date auto-calculation
**ID:** AC5  
**Description:** When Start Date is changed, Due Date is automatically set to Start Date + 1 day for all selected items (only items with start_date changes).  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_due_date_calculated_as_start_plus_one`
- Set Start Date to "2026-06-10" for selected items
- Verify all selected items have due_date = "2026-06-11"

### AC6: Preserve unspecified fields
**ID:** AC6  
**Description:** If user only changes Start Date (leaves Priority blank), all items keep their existing Priority values. Vice versa for Priority-only changes.  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_preserve_unspecified_fields`
- Select items with diverse priorities
- Change only Start Date in dialog → each item's priority unchanged
- Change only Priority in dialog → each item's start_date unchanged

### AC7: Bulk update persists to database
**ID:** AC7  
**Description:** After clicking "Save" in the dialog, all selected items are updated in the database with the new values (respecting AC6). UI refreshes to show changes.  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_bulk_edit_saves_to_database`
- Select 3 items, set Start Date + Priority
- Click Save → verify database rows updated
- Refresh UI → verify displayed values match

### AC8: Checkbox state persists across detail panel refresh
**ID:** AC8  
**Description:** Selected checkboxes remain checked when user updates item counts, filters, or other non-navigation events. Unchecked when different project board is selected.  
**Test:**
- File: `tests/test_project_board_bulk_edit.py:test_checkbox_state_persists_and_resets`
- Select items → check selections
- Trigger refresh (e.g., link new item) → selections remain
- Switch to different project board → selections cleared

## Implementation Order

### Phase 1: UI Layer (Checkbox Selection & Dialog)
1. **Modify `_render_detail()` in `project_boards.py`** — Add checkbox to each item row (lines 766–798)
   - Add `self.selected_item_ids: set[str] = {}` to `__init__`
   - Create checkbox variable for each item
   - Bind checkbox changes to update selection state
   - Add "Bulk Edit" button to toolbar (enabled when `len(self.selected_item_ids) > 0`)

2. **Create `BulkEditItemsDialog` class in `project_boards.py`**
   - Inherit from `ctk.CTkToplevel`
   - Fields: Start Date (CTkEntry with date picker UI), Priority (CTkComboBox with IMPORTANCE_OPTIONS)
   - Add "Clear/Skip" option for each field (checkbox or special value)
   - Buttons: Cancel, Save
   - Validation: Start Date must be ≥ today; show error if invalid
   - On Save: pass selected item IDs + changed fields to handler

3. **Integrate dialog handler in `ProjectBoardsScreen`**
   - Add `on_bulk_edit_clicked()` method
   - Instantiate `BulkEditItemsDialog`, pass selected item IDs
   - On dialog.result == "saved": call `_apply_bulk_edit()`

### Phase 2: Database / Business Logic
4. **Add `bulk_update_action_items()` method to `db_manager.py` or `db_manager_project_boards.py`**
   - Signature: `bulk_update_action_items(item_ids: list[str], start_date: Optional[str], priority: Optional[int])`
   - For each item_id in item_ids:
     - Fetch current ActionItem
     - If start_date provided: set item.start_date = start_date, item.due_date = (start_date + 1 day)
     - If priority provided: set item.importance = priority
     - Call `update_action_item(item)` to persist
   - Commit transaction

5. **Integrate bulk update into screen**
   - Add `_apply_bulk_edit(selected_ids, start_date, priority)` method
   - Call `db_manager.bulk_update_action_items(...)`
   - Clear selections: `self.selected_item_ids.clear()`
   - Refresh: `self._render_detail()`

### Phase 3: Testing & Polish
6. **Create test file `tests/test_project_board_bulk_edit.py`**
   - Fixtures for sample action items + project board
   - Test cases for all 8 ACs (see Verification section above)
   - Run: `pytest tests/test_project_board_bulk_edit.py -v`

7. **Manual QA**
   - Run app, navigate to Project Board
   - Select project with items
   - Select/deselect checkboxes → button enable/disable logic
   - Open Bulk Edit dialog → fields render correctly
   - Set Start Date in future → saves
   - Set Past Date → error shown
   - Save with only Start Date → Priority unchanged; Due Date = Start + 1
   - Verify database reflects changes

## Dependencies & Risks

- **ActionItem.validate_and_adjust_dates()** — already exists (models.py:85–100); will auto-set due_date = start_date if no explicit due_date. Our bulk update must explicitly set due_date to start_date + 1.
- **Date parsing** — use `date.fromisoformat()` for string→date, `date.isoformat()` for date→string. Consistent with existing code (see project_boards.py line 919).
- **Selection state** — clear `self.selected_item_ids` when switching projects (in `select_project()` / `_render_detail()` entry).

## Files to Modify

| File | Changes | LOC Est. |
|---|---|---|
| `src/getmoredone/screens/project_boards.py` | Add checkbox UI, BulkEditItemsDialog, integration | ~250 |
| `src/getmoredone/db_manager.py` or `db_manager_project_boards.py` | Add bulk_update_action_items() | ~30 |
| `tests/test_project_board_bulk_edit.py` | New test file, 8 test cases | ~250 |

## Status

**Ready for review and approval.** Once approved, Phase 1 (UI) will be implemented first, followed by Phase 2 (DB), then Phase 3 (testing).
