# GetMoreDone

A comprehensive Python task management application with GUI interface and SQLite database. Built to help you prioritize tasks, track time, and improve productivity through data-driven insights.

## Features

✅ **Smart Prioritization** - Automatic priority scoring based on Importance × Urgency × Size × Value
📅 **Upcoming View** - See what's due in the next N days, grouped by date with total time, includes Group/Category columns
👥 **Contact Management** - Full contact/client database with autocomplete search in WHO field
🔗 **Hierarchical Tasks** - Create parent-child relationships with unlimited nesting (grandparent→parent→child→grandchild)
🌳 **Hierarchical View** - Visual tree structure showing all parent-child relationships with indentation
⚙️ **Intelligent Defaults** - System-wide and per-client default settings with date offsets
📊 **Time Tracking** - Track planned vs actual time to improve estimates
🗓️ **Time Blocks** - Plan your day with visual time block scheduling
📈 **Statistics** - Analyze planned vs actual time with insights by size and category
🔄 **Reschedule History** - Never lose track of why dates changed
✨ **9 Comprehensive Screens** - Upcoming, All Items, Hierarchical, Plan, Completed, Contacts, Defaults, Stats, Settings
⚡ **Quick Date Pickers** - Set dates with one-click buttons: Today, +1, Clear
🎯 **Date Offset Defaults** - Automatically set start/due dates relative to today
🖥️ **Responsive UI** - Two-column layout that adapts to window size (600×800 dialogs)

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
│       ├── models.py           # Data models (ActionItem, Contact, etc.)
│       ├── validation.py       # Validation logic
│       └── screens/            # GUI screens
│           ├── upcoming.py     # Next N days view
│           ├── all_items.py    # Complete item list
│           ├── hierarchical.py # Parent-child tree view
│           ├── plan.py         # Time block planner
│           ├── completed.py    # Completed items
│           ├── manage_contacts.py  # Contact list screen
│           ├── edit_contact.py     # Contact create/edit dialog
│           ├── defaults.py     # Default settings
│           ├── stats.py        # Statistics & insights
│           ├── settings.py     # App settings
│           ├── item_editor.py  # Create/edit dialog (with sub-items)
│           └── reschedule_dialog.py
├── tests/                      # Test suite
│   ├── test_contact_integration.py  # Contact tests
│   ├── test_database.py
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

### Time Planning

1. Go to **Plan** screen
2. See open items on left (sorted by priority)
3. Select date and add time blocks on right
4. Link items to blocks or create standalone blocks

### Tracking Progress

- **Upcoming**: See what's due soon with Group/Category columns, complete items with checkbox
- **All Items**: Filter, sort, and bulk manage items
- **Hierarchical**: View parent-child relationships in tree structure with indentation
- **Completed**: Review completed items by date range
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
