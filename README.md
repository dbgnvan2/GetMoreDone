# GetMoreDone

A comprehensive Python task management application with GUI interface and SQLite database. Built to help you prioritize tasks, track time, and improve productivity through data-driven insights.

## Features

✅ **Smart Prioritization** - Automatic priority scoring based on Importance × Urgency × Size × Value
📅 **Upcoming View** - See what's due in the next N days, grouped by date with total time
⚙️ **Intelligent Defaults** - System-wide and per-client default settings with date offsets
📊 **Time Tracking** - Track planned vs actual time to improve estimates
🗓️ **Time Blocks** - Plan your day with visual time block scheduling
📈 **Statistics** - Analyze planned vs actual time with insights by size and category
🔄 **Reschedule History** - Never lose track of why dates changed
✨ **7 Comprehensive Screens** - Upcoming, All Items, Plan, Completed, Defaults, Stats, Settings
⚡ **Quick Date Pickers** - Set dates with one-click buttons: Today, +1, Clear
🎯 **Date Offset Defaults** - Automatically set start/due dates relative to today
🖥️ **Responsive UI** - Two-column layout that adapts to window size

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
│       ├── models.py           # Data models
│       ├── validation.py       # Validation logic
│       └── screens/            # GUI screens
│           ├── upcoming.py     # Next N days view
│           ├── all_items.py    # Complete item list
│           ├── plan.py         # Time block planner
│           ├── completed.py    # Completed items
│           ├── defaults.py     # Default settings
│           ├── stats.py        # Statistics & insights
│           ├── settings.py     # App settings
│           ├── item_editor.py  # Create/edit dialog
│           └── reschedule_dialog.py
├── tests/                      # Test suite
├── data/                       # Database files (gitignored)
├── run.py                      # Run script
├── create_demo_data.py         # Demo data generator
└── requirements.txt            # Dependencies
```

## Usage Guide

### Creating Items

1. Click **"+ New Item"** from any screen
2. Required fields: **Who** (client/person) and **Title**
3. Optional: Description, dates, priority factors, organization, planned time
4. Priority score auto-calculates: I × U × S × V

### Priority Factors

- **Importance**: Critical (20), High (10), Medium (5), Low (1), None (0)
- **Urgency**: Critical (20), High (10), Medium (5), Low (1), None (0)
- **Size**: XL (16), L (8), M (4), S (2), P (0)
- **Value**: XL (16), L (8), M (4), S (2), P (0)

### Setting Defaults

1. Go to **Defaults** screen
2. Choose **System Defaults** (apply to all) or **Who-specific** (per client)
3. Set priority factors, group, category, planned minutes
4. Precedence: Manual entry > Who defaults > System defaults

### Time Planning

1. Go to **Plan** screen
2. See open items on left (sorted by priority)
3. Select date and add time blocks on right
4. Link items to blocks or create standalone blocks

### Tracking Progress

- **Upcoming**: See what's due soon, complete items with checkbox
- **All Items**: Filter, sort, and bulk manage items
- **Completed**: Review completed items by date range
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
- Schema includes: action_items, defaults, time_blocks, work_logs, reschedule_history, item_links

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

## Specification

See `GetMoreDone_MasterSpec_SQLite_v1.md` for complete requirements and design decisions.

## License

Private project - All rights reserved

## Support

For issues or questions, create an issue in the repository.
