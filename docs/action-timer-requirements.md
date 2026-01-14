# Action Timer Module - Functional Requirements

## Overview
The Action Timer Module provides a popup countdown timer to guide users through completing action items with time blocking, break management, and completion workflows.

---

## FR-AT-001: Popup Timer Display
**User Story**: As a user I want to see a pop up count down timer screen to guide me to complete work.

**Description**: Display a popup timer window showing countdown and action details.

**Requirements**:
- Display action item title prominently
- Show three time values:
  - **Time Block**: Total allocated time (e.g., 30 minutes)
  - **Time To Finish**: Work time remaining before break (e.g., 25 minutes)
  - **Wrap/Break**: Break duration (e.g., 5 minutes)
- Display countdown timer with minutes and seconds
- Show Start/Pause/Stop control buttons
- Timer updates every second

**Acceptance Criteria**:
- Timer window appears on demand when user starts a time block
- All three time values are clearly labeled and visible
- Countdown shows MM:SS format
- Window stays on top of other windows

---

## FR-AT-002: Next Steps Display
**User Story**: I want to be reminded of the next steps so I can get started easier.

**Description**: Display next steps/notes from the action item to help user get started.

**Requirements**:
- Show "Next Steps:" section in timer window
- Display the action item's description or notes field
- Text should be readable but not dominate the timer display
- Support multi-line text display

**Acceptance Criteria**:
- Next steps text is visible in timer window
- Text wraps appropriately within window bounds
- Empty next steps shows placeholder text or empty section

---

## FR-AT-003: Pause and Resume Timer
**User Story**: As a user I want to pause my timer and then restart the timer and keep track of the time worked versus the total elapsed time from start to stop.

**Description**: Allow pausing and resuming timer while tracking both work time and total elapsed time.

**Requirements**:
- **Start** button initiates countdown
- **Pause** button:
  - Stops countdown
  - Changes to "Resume" button
  - Maintains current time remaining
- **Resume** button restarts countdown from paused time
- Track two separate time values:
  - **Work Time**: Sum of all active (non-paused) time periods
  - **Elapsed Time**: Total time from first Start to final Stop
- **Stop** button ends the time block completely

**Acceptance Criteria**:
- Pause/Resume can be used multiple times in one session
- Work time only increments when timer is actively running
- Elapsed time continues even when paused
- Both times are saved to WorkLog when stopped

---

## FR-AT-004: Complete Time Block and Action
**User Story**: As a user I want to complete the time block, add a Completion Note to the Action, and complete the Action.

**Description**: Provide "Finished" workflow to complete both time block and action item.

**Requirements**:
- **Finished** button available when timer is stopped
- Clicking Finished:
  1. Shows "Completion Note" dialog
  2. Saves work log entry with work time and elapsed time
  3. Adds completion note to action item
  4. Marks action item as completed with completion timestamp
  5. Closes timer window
- Completion note is optional but dialog must be shown
- User can cancel to return to timer without completing

**Acceptance Criteria**:
- Finished workflow saves WorkLog entry
- Action item status changes to "completed"
- Completion note is appended to action item notes/description
- Timer window closes after successful completion
- All data persisted to database

---

## FR-AT-005: Continue Action to Next Day
**User Story**: As a user I want to be able to Continue an Action Item by completing the Next Action I'm working and Create a new Next Action that is a duplicate of the current one, but for the next day.

**Description**: Provide "Continue" workflow for ongoing actions that span multiple days.

**Requirements**:
- **Continue** button available when timer is stopped
- Clicking Continue:
  1. Shows "Completion Note" dialog for current work
  2. Saves work log entry for time block
  3. Shows "Next Steps Note" dialog for future work
  4. Marks current action item as completed
  5. Creates duplicate action item with:
     - Same title, who, priority factors, category, group
     - Start date = tomorrow (today + 1 day)
     - Due date = tomorrow (or due + 1 day if original due > start)
     - Notes/description = Next Steps Note entered
     - Status = "open"
     - New unique ID
  6. Shows newly created action item in editor
- Both dialogs are optional but must be presented

**Acceptance Criteria**:
- Current action marked completed with work log
- New action created for next day
- New action opens in editor for review
- All relevant fields copied to new action
- Dates properly incremented
- Next steps note populates new action's description

---

## FR-AT-006: Default Break Time
**User Story**: As user I want default break time e.g. 5 minutes at the end of the Time Block (subtracted from the Time Block). A 30 minute time block is 25 minutes + 5 minute Break time.

**Description**: Automatically allocate break time at end of work time.

**Requirements**:
- Default break time = 5 minutes (configurable in settings)
- Break time is **subtracted** from total time block
- Calculation: Work Time = Time Block - Break Time
- Example: 30 minute block = 25 min work + 5 min break
- Timer counts down work time first, then break time
- Display shows three values:
  - Time Block: Total allocated (30)
  - Time To Finish: Work time countdown (25)
  - Wrap/Break: Break duration (5)

**Acceptance Criteria**:
- Break time automatically calculated from time block
- Work timer counts down before break starts
- Break timer starts automatically when work time reaches zero
- User can skip break and finish immediately
- Break time setting available in application settings

---

## FR-AT-007: Resizable Floating Window
**User Story**: As a user I want to have the Action Timer as a resizable floating window with the Time remaining in the title bar.

**Description**: Timer appears as floating, always-on-top, resizable window.

**Requirements**:
- Timer window is a separate floating window
- Window properties:
  - Always on top of other application windows
  - Resizable by dragging edges/corners
  - Minimum size: 300x200 pixels
  - Maximum size: unlimited
  - Remembers size preference for future sessions
- Title bar shows: "[Action Title] - [MM:SS remaining]"
- Title bar updates every second with countdown
- Window can be moved anywhere on screen

**Acceptance Criteria**:
- Timer window stays on top during use
- User can resize window and size persists
- Time remaining visible in window title bar
- Window position and size saved between sessions
- Can be minimized but remains accessible

---

## FR-AT-008: Green Title Bar Warning
**User Story**: As a user I want the title bar to be green when Time remaining is < 10 minutes.

**Description**: Change title bar color to green as visual warning when approaching deadline.

**Requirements**:
- Default title bar color: System default or application theme
- When time remaining < 10 minutes (during work time):
  - Title bar background changes to **green**
  - Text remains readable (white or black based on contrast)
- Color change applies to window title bar decoration
- Green color persists until timer stops or time expires

**Acceptance Criteria**:
- Title bar turns green at 9:59 remaining
- Color change is immediately visible
- Text remains readable on green background
- Returns to normal color if timer is reset/restarted above 10 min
- Only applies during work time, not break time

---

## FR-AT-009: Break Time Title Bar
**User Story**: As a user I want the title Bar to show "BREAK" and time remaining in time block when time remaining is <= Break Time.

**Description**: Display "BREAK" indicator in title bar during break period.

**Requirements**:
- When work time reaches 00:00, break time begins
- Title bar changes to show:
  - Format: "[Action Title] - BREAK [MM:SS remaining]"
  - Example: "Write Report - BREAK 04:32"
- Break time counts down from break duration (e.g., 5:00)
- Title bar color during break: Different from work time (suggest yellow/amber)
- "BREAK" text prominently displayed in title

**Acceptance Criteria**:
- Title changes to BREAK format when work time expires
- Break countdown starts at break duration
- BREAK indicator clearly visible in title bar
- Title bar color distinguishes break from work time
- User can skip break and click Finished/Continue during break

---

## FR-AT-010: Time Block Initialization
**Supporting Requirement**: How timer is started from action items.

**Description**: Launch timer from action item with pre-populated data.

**Requirements**:
- Add "Start Timer" button to action item screens:
  - Today screen
  - Upcoming screen
  - All Items screen
  - Item editor
- Button only visible for open (non-completed) items
- Clicking "Start Timer":
  1. Reads action item's `planned_minutes` field
  2. Calculates work time and break time
  3. Opens timer window with action data
  4. Auto-starts countdown (or requires Start click)
- If `planned_minutes` is null/empty, prompt for time block duration

**Acceptance Criteria**:
- Timer can be launched from any action item view
- Planned minutes used as default time block
- User prompted if no planned time set
- Timer window opens with correct action details
- Can only run one timer at a time

---

## FR-AT-011: Work Log Persistence
**Supporting Requirement**: How timer data is saved.

**Description**: Save all timer activity to WorkLog table.

**Requirements**:
- Create WorkLog entry when timer stops containing:
  - `item_id`: Action item ID
  - `started_at`: Timestamp when Start first clicked (ISO format)
  - `ended_at`: Timestamp when Stop clicked (ISO format)
  - `minutes`: Work time (minutes actively worked, excluding pauses)
  - `note`: Completion note or next steps note
  - `created_at`: Record creation timestamp
- WorkLog uses existing database schema (see models.py)
- Multiple work logs can exist per action item
- Work logs viewable in action item history

**Acceptance Criteria**:
- Every timer session creates a WorkLog entry
- All timestamps use local timezone (not UTC)
- Work time accurately reflects active (non-paused) time
- Notes properly saved to WorkLog entry
- Data persists correctly to database

---

## Data Flow

### Finished Flow:
```
Timer Running → Stop → Finished Button →
  Completion Note Dialog →
    Save WorkLog (work + elapsed time) →
    Add note to Action Item →
    Mark Action as Completed →
    Close Timer
```

### Continue Flow:
```
Timer Running → Stop → Continue Button →
  Completion Note Dialog →
  Next Steps Note Dialog →
    Save WorkLog →
    Complete Current Action →
    Create New Action (duplicate for tomorrow) →
    Add Next Steps to New Action →
    Show New Action in Editor
```

---

## UI Component Hierarchy

```
TimerWindow (Floating, Resizable, Always On Top)
├── Title Bar: "[Title] - [MM:SS]" or "[Title] - BREAK [MM:SS]"
├── Main Content Area
│   ├── Action Title (large, bold)
│   ├── Time Block Display
│   │   ├── Time Block: [30 min]
│   │   ├── Time To Finish: [25 min] (countdown)
│   │   └── Wrap/Break: [5 min]
│   ├── Timer Controls
│   │   ├── Start Button (when not running)
│   │   ├── Pause Button (when running) / Resume Button (when paused)
│   │   └── Stop Button
│   ├── Next Steps Section
│   │   ├── "Next Steps:" label
│   │   └── Description/Notes text (scrollable)
│   └── Completion Controls (when stopped)
│       ├── Finished Button → Complete & Close
│       └── Continue Button → Complete & Duplicate
```

---

## Settings Configuration

New settings needed in AppSettings:

```python
@dataclass
class AppSettings:
    # ... existing settings ...

    # Timer settings
    default_break_minutes: int = 5
    timer_window_width: int = 400
    timer_window_height: int = 500
    timer_window_x: Optional[int] = None
    timer_window_y: Optional[int] = None
    timer_warning_minutes: int = 10  # When to show green warning
```

---

## Database Schema Changes

No schema changes needed. Uses existing:
- `ActionItem` table (existing)
- `WorkLog` table (existing in models.py)

WorkLog schema (already defined):
```python
@dataclass
class WorkLog:
    item_id: str              # References action_items.id
    started_at: str           # ISO datetime (local timezone)
    minutes: int              # Work time in minutes
    ended_at: Optional[str]   # ISO datetime (local timezone)
    note: Optional[str]       # Completion or next steps note
    id: str                   # UUID
    created_at: str           # ISO datetime (local timezone)
```

---

## Implementation Notes

1. **Timer Window**: Create new `TimerWindow` class inheriting from `CTkToplevel`
2. **File Location**: `src/getmoredone/screens/timer_window.py`
3. **Title Bar Color**: May need platform-specific code (Windows/Mac/Linux differ)
4. **Always On Top**: Use `window.attributes('-topmost', True)` for Tkinter
5. **Thread Safety**: Use `after()` for timer updates to avoid threading issues
6. **State Management**: Track timer state (stopped, running, paused, in_break)

---

## Testing Requirements

1. **Unit Tests**:
   - Time calculations (work time, break time, elapsed time)
   - State transitions (stop → start → pause → resume)
   - WorkLog data creation

2. **Integration Tests**:
   - Finished flow: Timer → WorkLog → Complete Action
   - Continue flow: Timer → Complete → Duplicate → Next Day
   - Multiple pause/resume cycles

3. **Manual Tests**:
   - Window resizing and positioning
   - Title bar color changes
   - Always-on-top behavior
   - Cross-platform testing (if applicable)

---

## Open Questions for Review

1. **Q**: Should the timer auto-start when window opens, or require clicking Start?
   - **Suggestion**: Require Start click for explicit user control

2. **Q**: What happens if user closes timer window without finishing?
   - **Suggestion**: Prompt "Save work log?" with Yes/No/Cancel options

3. **Q**: Can user edit time block duration after starting?
   - **Suggestion**: No editing during active session; restart required

4. **Q**: Should break time be optional per session?
   - **Suggestion**: Yes, show checkbox "Include break time" when starting

5. **Q**: What if action item has no planned_minutes set?
   - **Suggestion**: Prompt for time block duration before opening timer

6. **Q**: Should elapsed time include break time?
   - **Suggestion**: Yes, elapsed = total wall clock time from start to stop

7. **Q**: Break time title bar color - yellow/amber or different?
   - **Suggestion**: Amber/orange to distinguish from work (green warning)

8. **Q**: Can multiple timers run simultaneously for different actions?
   - **Suggestion**: No, enforce single active timer (prevents confusion)

---

## Priority / Phases

**Phase 1 (MVP)**:
- FR-AT-001: Popup Timer Display
- FR-AT-003: Pause and Resume
- FR-AT-006: Default Break Time
- FR-AT-010: Timer Initialization
- FR-AT-011: Work Log Persistence

**Phase 2**:
- FR-AT-004: Complete Time Block (Finished flow)
- FR-AT-007: Resizable Floating Window
- FR-AT-002: Next Steps Display

**Phase 3**:
- FR-AT-005: Continue Action (duplicate for next day)
- FR-AT-008: Green Title Bar Warning
- FR-AT-009: Break Time Title Bar

---

## Dependencies

- CustomTkinter for UI components
- Existing DBManager for WorkLog persistence
- Existing ActionItem model and CRUD operations
- AppSettings for configuration persistence
