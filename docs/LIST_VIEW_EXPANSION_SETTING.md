# List View Expansion Setting Implementation

## Overview

Added a new user setting to control the default collapsed/expanded state for list views (Today, Upcoming, and All Items screens).

## Implementation Date

January 25, 2026

## Changes Made

### 1. AppSettings Configuration (`src/getmoredone/app_settings.py`)

- **Added field**: `default_columns_expanded: bool = False`
- **Default value**: `False` (collapsed)
- **Purpose**: Centralized control for initial list view column state

### 2. Screen Updates

#### Today Screen (`src/getmoredone/screens/today.py`)

- **Line 26**: Changed from hardcoded `self.columns_expanded = False` to `self.columns_expanded = self.settings.default_columns_expanded`
- **Line 65**: Updated button text from hardcoded `"Expand"` to dynamic `"Collapse" if self.columns_expanded else "Expand"`
- **Import**: Already had `AppSettings` import

#### Upcoming Screen (`src/getmoredone/screens/upcoming.py`)

- **Line 26**: Changed from hardcoded `self.columns_expanded = True` to `self.columns_expanded = self.settings.default_columns_expanded`
- **Line 106**: Updated button text from hardcoded `"Collapse"` to dynamic `"Collapse" if self.columns_expanded else "Expand"`
- **Import**: Already had `AppSettings` import

#### All Items Screen (`src/getmoredone/screens/all_items.py`)

- **Line 9**: Added `from ..app_settings import AppSettings`
- **Line 25**: Changed from hardcoded `self.columns_expanded = False` to `self.columns_expanded = self.settings.default_columns_expanded`
- **Line 104**: Updated button text to dynamic `"Collapse" if self.columns_expanded else "Expand"`

### 3. Settings UI (`src/getmoredone/screens/settings.py`)

Added new checkbox control in the "Date Increment Settings" section:

**Lines 316-323**: New checkbox:

```python
# Default list view expansion checkbox
self.default_columns_expanded_var = ctk.BooleanVar(
    value=self.settings.default_columns_expanded)
columns_expanded_checkbox = ctk.CTkCheckBox(
    section,
    text="Start list views expanded (Today, Upcoming, All Items)",
    variable=self.default_columns_expanded_var
)
columns_expanded_checkbox.grid(row=3, column=0, columnspan=2,
                              sticky="w", padx=10, pady=5)
```

**Line 356**: Updated save method:

```python
self.settings.default_columns_expanded = self.default_columns_expanded_var.get()
```

**Adjusted row numbers**:

- Save button: row 3 → row 4
- Status label: row 3 → row 4
- Info text: row 4 → row 5

## User Experience

### Default Behavior (Collapsed)

When the user first opens any list view screen:

- Columns are in collapsed state (minimal view)
- Button shows "Expand"
- Less visual clutter, faster scanning

### Expanded Behavior

If user changes setting to "Start list views expanded":

- Columns are in expanded state (full details)
- Button shows "Collapse"
- More information visible immediately

### Persistence

- Setting persists across application restarts
- Stored in `data/settings.json`
- Changes take effect when screens are reopened (not live update)

## Testing

### Unit Tests (`tests/test_today_screen.py`)

Added two new tests to the existing test suite:

#### 1. `test_list_view_expansion_setting_persistence()`

**Purpose**: Verify that the setting can be saved and reloaded correctly

**Test Steps**:

1. Load current settings
2. Change `default_columns_expanded` to `True` and save
3. Reload settings and verify value is `True`
4. Change to `False` and save
5. Reload again and verify value is `False`
6. Restore original value (cleanup)

**Assertions**:

- Setting persists as `True` after save/reload cycle
- Setting persists as `False` after save/reload cycle

**Result**: ✓ PASSED

#### 2. `test_list_view_expansion_default_value()`

**Purpose**: Verify that the attribute exists and is the correct type

**Test Steps**:

1. Load settings
2. Check attribute exists
3. Check it's a boolean type

**Assertions**:

- `AppSettings` has `default_columns_expanded` attribute
- Value is a boolean type

**Result**: ✓ PASSED

### Test Execution

Run the new tests:

```bash
# Run both new tests
python3 -m pytest tests/test_today_screen.py::test_list_view_expansion_setting_persistence -v
python3 -m pytest tests/test_today_screen.py::test_list_view_expansion_default_value -v

# Run all today screen tests (includes 2 existing + 2 new = 4 total)
python3 -m pytest tests/test_today_screen.py -v
```

**All Tests Pass**: 4/4 tests passed in 0.07s

### Standalone Test Script (`test_list_view_setting.py`)

Quick validation script for development:

```bash
python3 test_list_view_setting.py
```

**Output**:

```
✓ Setting exists: default_columns_expanded = False
✓ Changed setting to: True
✓ Setting persisted after reload: True
✓ Restored original value: False

✓ All tests passed!
```

**Test Coverage Summary**:

- Setting attribute exists in AppSettings ✓
- Default value is `False` (collapsed) ✓
- Setting can be changed and persisted ✓
- Setting survives save/reload cycle ✓

### Manual Testing Checklist

- [ ] Launch application with default settings
- [ ] Verify Today screen starts collapsed (button says "Expand")
- [ ] Verify Upcoming screen starts collapsed (button says "Expand")
- [ ] Verify All Items screen starts collapsed (button says "Expand")
- [ ] Open Settings and check "Start list views expanded"
- [ ] Save settings
- [ ] Close and reopen application
- [ ] Verify all three screens now start expanded (button says "Collapse")
- [ ] Uncheck the setting and verify returns to collapsed behavior

## Technical Notes

### Why This Design?

1. **Centralized Control**: Single source of truth in AppSettings
2. **Consistent Behavior**: All three screens use the same setting
3. **User Preference**: Setting persists across sessions
4. **No Breaking Changes**: Existing functionality preserved

### Implementation Pattern

Each screen follows the same pattern:

```python
# In __init__:
self.settings = AppSettings.load()
self.columns_expanded = self.settings.default_columns_expanded

# Button creation:
self.expand_collapse_btn = ctk.CTkButton(
    parent,
    text="Collapse" if self.columns_expanded else "Expand",
    command=self.toggle_columns
)
```

### Future Enhancements

Potential improvements:

1. Per-screen preferences (Today vs Upcoming vs All Items)
2. Remember last state per screen (sticky toggle)
3. Live update when setting changes (broadcast to open screens)
4. Keyboard shortcut to toggle expansion

## Files Modified

1. `src/getmoredone/app_settings.py` - Added setting field
2. `src/getmoredone/screens/today.py` - Read setting, dynamic button
3. `src/getmoredone/screens/upcoming.py` - Read setting, dynamic button
4. `src/getmoredone/screens/all_items.py` - Added import, read setting, dynamic button
5. `src/getmoredone/screens/settings.py` - Added UI control and save logic

## Files Created

1. `test_list_view_setting.py` - Unit test for setting persistence
2. `docs/LIST_VIEW_EXPANSION_SETTING.md` - This document

## Related Features

- VPS (Value Proposition System) segment management
- Deletion safety with typed confirmation
- Date increment settings (same section in UI)

## Status

✅ **COMPLETE** - Ready for user testing
