# GetMoreDone

A comprehensive Python task management application with GUI interface and SQLite database. Built to help you prioritize tasks, track time, and improve productivity through data-driven insights.

## Features

✅ **Smart Prioritization** - Automatic priority scoring based on Importance × Urgency × Effort-Cost × Value
⏱️ **Action Timer** - Floating countdown timer with pause/resume, break time, music playback, and completion workflows
📅 **Upcoming View** - See what's due in the next N days, grouped by date with total time, includes Group/Category columns
👥 **Contact Management** - Full contact/client database with autocomplete search in WHO field
🔗 **Hierarchical Tasks** - Create parent-child relationships with unlimited nesting (grandparent→parent→child→grandchild)
🌳 **Hierarchical View** - Visual tree structure showing all parent-child relationships with indentation
⚙️ **Intelligent Defaults** - System-wide and per-client default settings with date offsets
📊 **Time Tracking** - Track planned vs actual time with work logs and productivity insights
🗓️ **Time Blocks** - Plan your day with visual time block scheduling
📈 **Statistics** - Analyze planned vs actual time with insights by effort-cost and category
🔄 **Reschedule History** - Never lose track of why dates changed
📆 **Google Calendar Integration** - Create calendar events directly from action items with automatic linking
� **Visionary Planning System (VPS)** - Strategic long-term planning from 5-year visions down to weekly actions with life segment organization
🎵 **Music Playback** - Background music during work sessions with volume control and format conversion tools
✨ **11 Comprehensive Screens** - TODAY, Upcoming, All Items, Hierarchical, VPS Planning, Plan, Completed, Contacts, Defaults, Stats, Settings
⚡ **Quick Date Pickers** - Set dates with one-click buttons: Today, +1, Clear
🎯 **Date Offset Defaults** - Automatically set start/due dates relative to today
🖥️ **Responsive UI** - Two-column layout that adapts to window size, floating timer window

## Quick Start

### One-Command Startup (Recommended)

**Linux/Mac:**

```bash
./start.sh
```

**Windows:**

```cmd
start.bat
```

The startup script automatically:

- Creates virtual environment (if needed)
- Activates the environment
- Installs/updates dependencies
- Launches the application

### Manual Setup

If you prefer to run commands individually:

#### 1. Setup Environment

```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Create Demo Data (Optional)

```bash
python create_demo_data.py
```

#### 3. Run Application

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

### Item Editor Buttons

When editing an existing item, you have several action buttons:

- **Save** - Saves changes and keeps the window open (shows "✓ Saved" confirmation)
- **Save & Close** - Saves changes and closes the window
- **Save + New** - (New items only) Saves, closes, and opens a blank editor
- **Duplicate** - Saves current changes, then opens the duplicate in a NEW window
- **Create Follow-up** - Creates a new item linked to current, with dates +1 day
- **Create Tasks** - Creates child items from Next Action field (one per line)
- **Complete** - Marks item as complete and closes
- **📅 Calendar** - Creates a Google Calendar event

### Creating Child Tasks

To break down a task into sub-tasks:

1. Open an existing item in the editor
2. Add tasks to the **Next Action** field, one per line. Example:
   ```
   Design homepage
   Write product copy
   Set up payment system
   Test checkout flow
   ```
3. Click **"+ Create Tasks"** button
4. Creates one child item for each line with:
   - Title: "Parent Title - Task text"
   - Description: The task text
   - Same dates, priority, and other fields as parent
   - Parent-child relationship established

### Deleting Items

1. **From Item Editor**: Open an item and click the red **Delete** button (bottom right)
2. **Confirmation**: Dialog asks you to confirm deletion
3. **Child Items**: If the item has children:
   - A warning dialog appears showing the number of child items
   - Children are **NOT deleted** - they become root items (parent_id set to NULL)
   - You can still proceed with deletion or cancel
4. **Cascading**: Related data is handled automatically:
   - Work logs: Deleted with the item
   - Links (notes, URLs): Deleted with the item
   - Reschedule history: Deleted with the item
   - Child items: **Preserved** and become root items
5. **No Undo**: Deletion is permanent and cannot be undone

### Priority Factors

- **Importance**: Critical (20), High (10), Medium (5), Low (1)
- **Urgency**: Critical (20), High (10), Medium (5), Low (1)
- **Effort-Cost**: XL (16), L (8), M (4), S (2)
- **Value**: XL (16), L (8), M (4), S (2)

### Working with Hierarchical Tasks

1. **Create a sub-item**: Open any existing item and click **"+ Create Sub-Item"**
   - Sub-item is created as a **duplicate** of the parent (all fields copied)
   - Includes: WHO, title, description, dates, priority factors, group, category, planned time
   - Parent relationship is automatically set (parent_id)
   - Edit the sub-item to customize as needed
2. **Navigate hierarchy**: Click "View Parent" button on sub-items to go up
3. **Hierarchical View**: Click **Hierarchical** in sidebar to see full tree structure
   - Shows parent-child relationships with visual indentation
   - Displays child count for parent items
   - Filter by status (open/completed/all)
4. **Multi-level nesting**: Create grandchildren by adding sub-items to sub-items

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
   - **Currently Playing**: Track name from your music folder (if configured)
3. Optionally edit the Time Block value before starting
4. Click **Start** to begin the countdown (music starts automatically if configured)

**Timer Controls:**

- **Start**: Begin countdown (required click, doesn't auto-start)
- **Pause/Resume**: Pause work time (elapsed time continues, work time pauses)
- **Stop**: End the timer session (shows Finished/Continue buttons)
- **Close Window**: Same as clicking Stop

**Music Controls (Independent):**

- **🎵 Play**: Start or resume music playback (purple button)
- **⏸ Pause**: Pause or resume music (purple button, changes to "▶ Resume" when paused)
- **Independent Operation**: Music controls work separately from timer controls
  - Pausing the timer does NOT pause the music
  - You can control music anytime without affecting the timer
  - Music only stops when you click Stop or close the window

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

**Music Playback:**

- **Independent Controls**: Separate Play/Pause buttons (purple) for music control
- **Background Music**: Plays random tracks from your configured music folder during work sessions
- **Manual Control**: Start/pause music anytime without affecting the timer state
- **Continuous Playback**: Music continues playing even when timer is paused
- **Track Display**: Currently playing track name shown in status (♫ Track Name)
- **Volume Control**: Adjustable volume slider in Settings > Timer & Audio (0-100%)
- **Supported Formats**: MP3, WAV, OGG (best compatibility)
- **Format Conversion**: Use `convert_music_to_mp3.py` script to convert M4A/AAC/WMA/FLAC to MP3
- **Configuration**: Set music folder path in Settings > Timer & Audio

**Audio Alerts:**

- **Break Start Sound**: Plays when work time ends and break begins
- **Break End Sound**: Plays when break time expires
- Sounds are **optional** - can be enabled/disabled in Settings
- Custom WAV files can be specified in Settings
- Falls back to system beep if no custom sound specified
- Cross-platform support (Windows, macOS, Linux)

**Settings:**

- **Default Time Block**: 30 minutes (editable in Settings > Timer & Audio)
- **Default Break Time**: 5 minutes (editable in Settings > Timer & Audio)
- **Warning Time**: Green warning appears at < 10 minutes (editable in Settings > Timer & Audio)
- **Enable Break Sounds**: Toggle audio alerts on/off
- **Break Start Sound**: Path to custom WAV file (optional)
- **Break End Sound**: Path to custom WAV file (optional)
- **Music Folder**: Path to folder containing music files for timer playback
- **Music Volume**: Volume slider (0-100%, default 70%)

**Single Timer Policy:**

- Only one timer can run at a time (prevents confusion)
- Timer must be stopped/completed before starting another

### Google Calendar Integration

Create Google Calendar events directly from action items with automatic linking and meeting tracking.

**Configuration Directory:**
GetMoreDone stores credentials in your home directory:

```
~/.getmoredone/credentials.json  # OAuth credentials (you provide)
~/.getmoredone/token.pickle      # Auth token (auto-generated)
```

This keeps credentials secure and shared across all projects.

**Setup (One-Time):**

1. See detailed setup instructions: `docs/google-calendar-setup.md`
2. Get OAuth credentials from Google Cloud Console
3. Place `credentials.json` in `~/.getmoredone/`
4. First use will prompt for authorization in browser

**Creating Calendar Events:**

1. Open an action item in Item Editor
2. Click **"📅 Calendar"** button (purple)
3. Fill in event details:
   - **Title**: Pre-filled from action item
   - **Date**: Use quick buttons or enter YYYY-MM-DD
   - **Time**: Set hour, minute, AM/PM (uses your local timezone automatically)
   - **Duration**: Minutes (default: 60)
   - **Description**: Optional (defaults to item description)
   - **Location**: Optional meeting location or URL
   - **Attendees**: Optional, comma-separated emails
4. Click **"Create Calendar Event"**
5. Event appears as a link in the item's Links tab
6. Action item automatically marked as meeting with scheduled time displayed

**Meeting Tracking:**

- ✅ **"Is Meeting"** checkbox automatically checked when calendar event created
- 🕒 **"Meeting Time"** field displays the scheduled date/time
- 📊 Track which action items are meetings vs regular tasks
- 🔍 Filter and report on meetings separately

**Benefits:**

- 📆 Schedule meetings without leaving GetMoreDone
- 🔗 Calendar link stored with action item for easy access
- ⏰ Pre-fills event with action item details
- 🌍 Uses your local timezone automatically (no more timezone confusion!)
- 📧 Optionally invite attendees
- 📍 Add location/meeting URL
- 📝 Automatically tracks meeting status and time

**Note:** Requires Google Calendar API credentials. See `docs/google-calendar-setup.md` for full setup instructions.

**Troubleshooting Authentication Issues:**

🧟 **ZOMBIE TOKEN PROBLEM** (Most Common Issue):
If Google login shows a **different project name** than expected (e.g., shows "bowen1rag" instead of "getmoredone"), you have a zombie token from an old project.

**Quick Fix:**

```bash
# Delete the old token
rm ~/.getmoredone/token.pickle

# Or use the fix script
./fix_zombie_token.sh

# Then re-authenticate
python3 test_auth.py
```

**Other Issues:** See `docs/EMAIL-AUTH-TROUBLESHOOTING.md` or run `./verify_auth.sh` to diagnose problems.

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
- **Stats**: Analyze planned vs actual time, accuracy by effort-cost

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
  - **action_items** - Tasks with parent_id for hierarchical relationships, is_meeting flag, and meeting_start_time
  - **contacts** - Clients/contacts with name, type, email, phone, notes
  - **defaults** - System and per-contact default settings
  - **time_blocks** - Time block planning
  - **work_logs** - Time tracking
  - **reschedule_history** - Change audit trail
  - **item_links** - Attachments and references (including google_calendar links)
- Foreign keys: contact_id → contacts, parent_id → action_items (self-referencing)
- Automatic migrations for schema updates (including new meeting tracking fields)

## Technologies

- **Python 3.11+** - Modern Python with type hints
- **SQLite** - Embedded database (no server required)
- **CustomTkinter** - Modern, customizable GUI framework
- **pygame** - Audio playback for timer music and sound effects
- **pytest** - Comprehensive testing framework
- **Google Calendar API** - OAuth 2.0 integration for calendar events
- **tzlocal** - Automatic timezone detection for accurate event scheduling
- **cairosvg** - SVG icon rendering for modern UI controls
- **Pillow** - Image processing for icon conversion

## Architecture

- **Database Layer**: SQLite with schema initialization and connection management
- **Business Logic**: DatabaseManager handles CRUD, queries, defaults, validation
- **Models**: Dataclasses for type-safe entities
- **GUI**: CustomTkinter with screen-based navigation
- **Validation**: Field-level validation with error reporting

## Recent Improvements

### VPS Segment Management in Settings (January 2026)

- **New Settings Tab** - "VPS Life Segments" tab for managing all life segments
- **Full CRUD Operations** - Create, edit, and delete life segments
- **Visual Color Picker** - Native color picker dialog with hex code input and live preview
- **Segment Properties**:
  - Name and description
  - Color (hex code with visual preview)
  - Display order (for sorting)
  - Active/Inactive status toggle
- **Smart Features**:
  - Color preview boxes in segment list
  - Status badges (✓ Active / ○ Inactive)
  - Enhanced deletion protection:
    - Reports exact count of linked visions
    - Shows step-by-step instructions to remove linked records
    - Prevents accidental data loss
  - Refresh button to reload segment list
- **Comprehensive Testing** - 9 new unit tests covering all CRUD operations and edge cases

### VPS (Visionary Planning System) Bug Fixes (January 2026)

- **Fixed New Vision button crash** - Replaced non-existent `CTkMessageBox` with standard `tkinter.messagebox`
- **Fixed empty year field validation** - Now provides sensible defaults (current year for start, +10 years for end)
- **Added segment multi-select** - New checkbox dialog to select/deselect multiple life segments for display
  - "Select Segments..." button shows selection dialog with checkboxes
  - Select All / Deselect All buttons for convenience
  - Button displays count of selected segments (e.g., "3 of 5 Segments")
  - Filtered tree view shows only selected segments
- All error messages now use proper tkinter messagebox for consistency
- Comprehensive test coverage added (5 new tests in test_vps_integration.py)

### Action Timer Module (NEW)

- Floating, resizable countdown timer window with always-on-top behavior
- Pause/Resume functionality tracking work time vs elapsed time
- Automatic break time calculation (Time Block - Break = Work Time)
- Visual indicators: White time display, green warning (< 10 min), blue break time
- **Audio alerts**: Plays sound at break start and break end (optional, customizable)
- **Music playback**: Background music during work sessions with pygame integration
  - Random track selection from configured music folder
  - Supports MP3, WAV, OGG formats (best compatibility)
  - Volume control slider (0-100%)
  - Currently playing track display (♫ Track Name)
  - Automatic pause/resume with timer controls
  - Format conversion tool for M4A/AAC to MP3 (`convert_music_to_mp3.py`)
- **SVG icon support**: Modern, scalable icons for play, pause, stop, volume, and music controls
  - Icon caching system for performance
  - cairosvg-based rendering
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
- Settings for time block (30 min), break (5 min), audio alerts, custom sounds, music folder, and volume

### Item Deletion (NEW - January 2026)

- Delete button in Item Editor (red button, bottom right)
- Two-stage confirmation dialog with clear warnings
- Smart child handling: Children are preserved and become root items (not deleted)
- Warning dialog when deleting items with children shows count
- Automatic cascade deletion of related data:
  - Work logs deleted with item
  - Links (notes, URLs) deleted with item
  - Reschedule history deleted with item
  - Child items preserved (parent_id set to NULL)
- Comprehensive test coverage (4 new tests in test_database.py)

### Google Calendar Integration (NEW - January 2026)

- Create calendar events directly from action items
- 📅 Calendar button in Item Editor (purple, on button bar)
- OAuth 2.0 authentication with secure token storage
- Pre-fills event with action item details (title, description, dates)
- Set start time, duration, location, and attendees
- **Automatic timezone detection** - Uses your local timezone (no more hardcoded timezones!)
- **Meeting tracking** - Automatically sets is_meeting flag and meeting_start_time when creating events
- Calendar links automatically stored in item_links table
- Events appear as clickable links in Links tab
- Cross-platform support (requires credentials.json setup)
- Complete setup guide in docs/google-calendar-setup.md
- Features:
  - 12-hour time format with AM/PM
  - Quick date buttons (Today, +1)
  - Duration in minutes (default: 60)
  - Optional location and attendees
  - Automatic browser authorization on first use
  - **"Is Meeting" checkbox** automatically checked after event creation
  - **"Meeting Time" field** displays scheduled meeting date/time
  - Timezone auto-detection using tzlocal library
- Link type: "google_calendar" for easy identification
- Meeting data stored in action_items table (is_meeting, meeting_start_time)

### Contact Management

- Full contact/client database with CRUD operations
- Case-insensitive search across name, email, phone, notes
- Contact types: Client, Contact, Personal
- WHO field autocomplete with inline contact creation
- Link action items to contacts via contact_id foreign key

### Hierarchical Task Structure

- Parent-child relationships with unlimited nesting levels
- Create sub-items from any existing item with "+ Create Sub-Item" button
  - Sub-items duplicate parent (all fields copied including title, dates, priority, etc.)
  - Edit the duplicated sub-item to customize as needed
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

## Testing

### Running Tests

The project includes comprehensive test coverage with 21+ VPS-specific tests:

**Run all tests:**

```bash
python3 -m pytest tests/ -v
```

**Run VPS tests only:**

```bash
python3 -m pytest tests/test_vps_integration.py -v
```

**Run standalone VPS test:**

```bash
python3 test_vps_segments.py
```

### Test Coverage

- **14 Integration Tests** (`tests/test_vps_integration.py`):
  - 5 bug fix tests (CTkMessageBox, year validation, segment filtering)
  - 9 segment management tests (CRUD, deletion protection, color validation)
- **7 Standalone Tests** (`test_vps_segments.py`):
  - Structure validation
  - Method existence checks
  - Enhanced deletion protection verification

- **Additional Tests**:
  - Database operations
  - Contact management
  - Date validation
  - Timer functionality
  - Obsidian integration

See [docs/VPS_TESTING_SUMMARY.md](docs/VPS_TESTING_SUMMARY.md) for detailed test documentation.

### Test Results

All tests pass consistently with 100% success rate. Tests use in-memory databases for isolation and run in < 1 second total.
