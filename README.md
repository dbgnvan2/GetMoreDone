# GetMoreDone

A comprehensive Python task management application with GUI interface and SQLite database. Built to help you prioritize tasks, track time, and improve productivity through data-driven insights.

## Features

✅ **Smart Prioritization** - Automatic priority scoring based on Importance × Urgency × Size × Value
⏱️ **Action Timer** - Floating countdown timer with pause/resume, break time, and completion workflows
📅 **Upcoming View** - See what's due in the next N days, grouped by date with total time, includes Group/Category columns
👥 **Contact Management** - Full contact/client database with autocomplete search in WHO field
🔗 **Hierarchical Tasks** - Create parent-child relationships with unlimited nesting (grandparent→parent→child→grandchild)
🌳 **Hierarchical View** - Visual tree structure showing all parent-child relationships with indentation
⚙️ **Intelligent Defaults** - System-wide and per-client default settings with date offsets
📊 **Time Tracking** - Track planned vs actual time with work logs and productivity insights
🗓️ **Time Blocks** - Plan your day with visual time block scheduling
📈 **Statistics** - Analyze planned vs actual time with insights by size and category
🔄 **Reschedule History** - Never lose track of why dates changed
✨ **10 Comprehensive Screens** - TODAY, Upcoming, All Items, Hierarchical, Plan, Completed, Contacts, Defaults, Stats, Settings
⚡ **Quick Date Pickers** - Set dates with one-click buttons: Today, +1, Clear
🎯 **Date Offset Defaults** - Automatically set start/due dates relative to today
🖥️ **Responsive UI** - Two-column layout that adapts to window size, floating timer window

## Quick Start

### 1. Setup Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Create Demo Data (Optional)

```bash
python create_demo_data.py
```

### 3. Run Application

```bash
python run.py
```

Or alternatively:
```bash
python -m getmoredone
```

## Project Structure

```
GetMoreDone/
├── src/
│   └── getmoredone/
│       ├── app.py              # Main application window
│       ├── database.py         # Database connection & schema
│       ├── db_manager.py       # Business logic & queries
│       ├── models.py           # Data models (ActionItem, Contact, WorkLog, etc.)
│       ├── validation.py       # Validation logic
│       ├── app_settings.py     # Application settings persistence
│       └── screens/            # GUI screens
│           ├── today.py        # Today's items (start <= today)
│           ├── upcoming.py     # Next N days view
│           ├── all_items.py    # Complete item list
│           ├── hierarchical.py # Parent-child tree view
│           ├── plan.py         # Time block planner
│           ├── completed.py    # Completed items
│           ├── timer_window.py # Action timer (floating window)
│           ├── manage_contacts.py  # Contact list screen
│           ├── edit_contact.py     # Contact create/edit dialog
│           ├── defaults.py     # Default settings
│           ├── stats.py        # Statistics & insights
│           ├── settings.py     # App settings
│           ├── item_editor.py  # Create/edit dialog (with sub-items)
│           └── reschedule_dialog.py
├── docs/                       # Documentation
│   └── action-timer-requirements.md  # Timer feature spec
├── tests/                      # Test suite
│   ├── test_contact_integration.py  # Contact tests
│   ├── test_database.py
│   ├── test_timer.py           # Timer functionality tests
│   └── ...
├── data/                       # Database files (gitignored)
├── run.py                      # Run script
├── create_demo_data.py         # Demo data generator
└── requirements.txt            # Dependencies
```

## Usage Guide

### Managing Contacts

1. Go to **Contacts** screen
2. Click **"+ New Contact"** to add a client or contact
3. Fill in: Name (required), Type (Client/Contact/Personal), Email, Phone, Notes
4. Click on any contact to edit or deactivate
5. Contacts appear in WHO field autocomplete when creating items

### Creating Items

1. Click **"+ New Item"** from any screen
2. **Who field**: Type to search contacts, or click + to add new contact inline
3. Required fields: **Who** (client/person) and **Title**
4. Optional: Description, dates, priority factors, organization, planned time
5. Priority score auto-calculates: I × U × S × V
6. To create a **sub-item**: Edit an existing item and click **"+ Create Sub-Item"**

### Priority Factors

- **Importance**: Critical (20), High (10), Medium (5), Low (1), None (0)
- **Urgency**: Critical (20), High (10), Medium (5), Low (1), None (0)
- **Size**: XL (16), L (8), M (4), S (2), P (0)
- **Value**: XL (16), L (8), M (4), S (2), P (0)

### Working with Hierarchical Tasks

1. **Create a sub-item**: Open any existing item and click **"+ Create Sub-Item"**
2. Sub-items inherit the WHO field from parent and can be edited independently
3. **Navigate hierarchy**: Click "View Parent" button on sub-items to go up
4. **Hierarchical View**: Click **Hierarchical** in sidebar to see full tree structure
   - Shows parent-child relationships with visual indentation
   - Displays child count for parent items
   - Filter by status (open/completed/all)
5. **Multi-level nesting**: Create grandchildren by adding sub-items to sub-items

### Setting Defaults

1. Go to **Defaults** screen
2. Choose **System Defaults** (apply to all) or **Who-specific** (per client)
3. Set priority factors, group, category, planned minutes
4. Precedence: Manual entry > Who defaults > System defaults

### Using the Action Timer

The Action Timer helps you stay focused on tasks with countdown timing, break management, and productivity tracking.

**Starting a Timer:**
1. Click the **"⏱ Timer"** button on any open action item (found in TODAY, Upcoming, or All Items screens)
2. The timer window opens showing:
   - **Time Block**: Total allocated time (e.g., 30 minutes)
   - **Time To Finish**: Countdown for work time (e.g., 25 minutes)
   - **Wrap/Break**: Break duration (e.g., 5 minutes)
   - **Next Steps**: Shows the action item's description to help you get started
3. Optionally edit the Time Block value before starting
4. Click **Start** to begin the countdown

**Timer Controls:**
- **Start**: Begin countdown (required click, doesn't auto-start)
- **Pause/Resume**: Pause work time (elapsed time continues, work time pauses)
- **Stop**: End the timer session (shows Finished/Continue buttons)
- **Close Window**: Same as clicking Stop

**Visual Indicators:**
- Title bar shows time remaining (e.g., "Task Name - 12:34")
- When < 10 minutes remaining: Time turns **green** as a warning
- During break time: Title shows "BREAK" in **blue** with break countdown
- Window is always-on-top and resizable
- Position and size are saved between sessions

**Completion Options (after Stop):**

**Finished Workflow:**
1. Click **Finished** button
2. Enter optional completion note describing what you accomplished
3. Timer saves a work log entry with actual work time (excluding pauses)
4. Action item is marked as completed
5. Timer window closes

**Continue Workflow** (for ongoing multi-day tasks):
1. Click **Continue** button
2. Enter optional completion note for today's work
3. Enter optional next steps note and **select dates** for the continued action:
   - Next Steps Note: Text describing what to do next
   - Start Date: When to start the next action (default: tomorrow)
   - Due Date: When it's due (default: tomorrow)
   - Quick buttons: "Today" and "+1" to adjust dates
   - Validation: Due date must be >= Start date
4. Current action is marked as completed with work log
5. New duplicate action is created with your selected dates:
   - Same title, priority, who, category, group
   - Start and due dates as you specified
   - Description updated with next steps note
6. New action opens in editor for review

**Time Tracking:**
- **Work Time**: Actual productive time (excludes pauses), saved to work log
- **Elapsed Time**: Total wall clock time from start to stop
- Work logs are viewable in the action item's history

**Break Time:**
- Automatically calculated: Work Time = Time Block - Break Time
- Default: 30 min block = 25 min work + 5 min break
- Break countdown starts automatically when work time reaches 00:00
- You can click Finished/Continue during break (no need to wait)
- Break time is not optional (but you can ignore it and finish early)

**Audio Alerts:**
- **Break Start Sound**: Plays when work time ends and break begins
- **Break End Sound**: Plays when break time expires
- Sounds are **optional** - can be enabled/disabled in Settings
- Custom WAV files can be specified in Settings
- Falls back to system beep if no custom sound specified
- Cross-platform support (Windows, macOS, Linux)

**Settings:**
- **Default Time Block**: 30 minutes (editable in Settings)
- **Default Break Time**: 5 minutes (editable in Settings)
- **Warning Time**: Green warning appears at < 10 minutes (editable in Settings)
- **Enable Break Sounds**: Toggle audio alerts on/off
- **Break Start Sound**: Path to custom WAV file (optional)
- **Break End Sound**: Path to custom WAV file (optional)

**Single Timer Policy:**
- Only one timer can run at a time (prevents confusion)
- Timer must be stopped/completed before starting another

### Time Planning

1. Go to **Plan** screen
2. See open items on left (sorted by priority)
3. Select date and add time blocks on right
4. Link items to blocks or create standalone blocks

### Tracking Progress

- **TODAY**: See all items with start date <= today, separated into To Do and Completed sections with stats
- **Upcoming**: See what's due soon with Group/Category columns, complete items with checkbox
- **All Items**: Filter, sort, and bulk manage items
- **Hierarchical**: View parent-child relationships in tree structure with indentation
- **Completed**: Review completed items by date range with count and total time stats
- **Contacts**: Manage clients and contacts with searchable list
- **Stats**: Analyze planned vs actual time, accuracy by size

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/getmoredone

# Run specific test file
pytest tests/test_database.py -v
```

### Database

- Location: `data/getmoredone.db`
- Backup from Settings screen or copy the file
- Schema includes:
  - **action_items** - Tasks with parent_id for hierarchical relationships
  - **contacts** - Clients/contacts with name, type, email, phone, notes
  - **defaults** - System and per-contact default settings
  - **time_blocks** - Time block planning
  - **work_logs** - Time tracking
  - **reschedule_history** - Change audit trail
  - **item_links** - Attachments and references
- Foreign keys: contact_id → contacts, parent_id → action_items (self-referencing)
- Automatic migrations for schema updates

## Technologies

- **Python 3.11+** - Modern Python with type hints
- **SQLite** - Embedded database (no server required)
- **CustomTkinter** - Modern, customizable GUI framework
- **pytest** - Comprehensive testing framework

## Architecture

- **Database Layer**: SQLite with schema initialization and connection management
- **Business Logic**: DatabaseManager handles CRUD, queries, defaults, validation
- **Models**: Dataclasses for type-safe entities
- **GUI**: CustomTkinter with screen-based navigation
- **Validation**: Field-level validation with error reporting

## Recent Improvements

### Action Timer Module (NEW)
- Floating, resizable countdown timer window with always-on-top behavior
- Pause/Resume functionality tracking work time vs elapsed time
- Automatic break time calculation (Time Block - Break = Work Time)
- Visual indicators: White time display, green warning (< 10 min), blue break time
- **Audio alerts**: Plays sound at break start and break end (optional, customizable)
- Finished workflow: Complete action with work log and completion note
- **Continue workflow**: Complete current, select dates for next action, capture next steps
  - Custom date selection with quick buttons (Today, +1)
  - Validation ensures due date >= start date
- Next Steps display to help you get started on tasks
- Window close equals Stop (saves position/size between sessions)
- Timer buttons on TODAY, Upcoming, and All Items screens
- **NEW: "+ New Item" button on TODAY screen** for quick action creation
- Work logs saved with started_at, ended_at, minutes, and notes
- Single timer policy (one at a time)
- Settings for time block (30 min), break (5 min), audio alerts, custom sounds

### Contact Management
- Full contact/client database with CRUD operations
- Case-insensitive search across name, email, phone, notes
- Contact types: Client, Contact, Personal
- WHO field autocomplete with inline contact creation
- Link action items to contacts via contact_id foreign key

### Hierarchical Task Structure
- Parent-child relationships with unlimited nesting levels
- Create sub-items from any existing item with "+ Create Sub-Item" button
- Navigate up with "View Parent" button on sub-items
- Dedicated Hierarchical View screen with tree visualization
- Breadth-first traversal for efficient subtree queries
- Auto-populated parent_id field with ON DELETE SET NULL

### UI Enhancements
- WHO field dropdown with click-outside detection
- Group and Category columns in Upcoming view
- Centered dialogs (600×800) above main window
- Error messages displayed between buttons
- Tab/Shift+Tab/Escape keyboard navigation
- Improved time block validation with user-friendly error messages

### Database Improvements
- Automatic migrations for contact_id and parent_id columns
- Indexes on contact_id and parent_id for performance
- Self-referencing foreign key for hierarchical relationships
- Soft delete pattern for contacts (is_active flag)

## Specification

See `GetMoreDone_MasterSpec_SQLite_v1.md` for complete requirements and design decisions.

## License

Private project - All rights reserved

## Support

For issues or questions, create an issue in the repository.
