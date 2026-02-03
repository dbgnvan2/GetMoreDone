# GetMoreDone — User Guide

This guide explains *how to use* GetMoreDone (GMD): what each screen does, how task hierarchy and linking work, and what each major button does.

> Scope: end-user workflow and UI behavior inferred from the app’s README and the GUI code in `src/getmoredone/screens/*.py`.

---

## 1) What GetMoreDone is for

GetMoreDone is a desktop task manager designed for **prioritization + execution**:

- **One place for your action items** (tasks / next actions / reminders)
- **A consistent priority score** (Importance × Urgency × Effort-Cost × Value)
- **Planning & follow-through** (Today / Upcoming / planning time blocks)
- **Time tracking** (planned minutes vs logged minutes via the Timer)
- **Linking & context**
  - link tasks to **Contacts** (clients/people)
  - attach **links** (e.g., Obsidian notes, Google Calendar events)
- **Hierarchy**
  - create parent → child tasks (unlimited depth)
- **VPS (Visionary Planning System)**
  - organize life planning from long-term visions down to weekly actions, grouped by life segments

---

## 2) Core concepts

### Action Items (tasks)
An **Action Item** is the central record you work with. Typical fields:

- **Who** (required): the person/client/context; can be linked to a Contact
- **Title** (required)
- **Description** (optional): your main notes field (what/why/context). This is where long text (e.g. an email body) should go.
- **Next Action** (optional): a short, action-focused scratchpad (often one task per line). You can generate child tasks from it using **+ Create Tasks**.
- **Dates**
  - **Start Date** (optional)
  - **Due Date** (optional)
  - business rule: due date should not be earlier than start date
- **Planned Minutes** (optional)
- **Priority factors**: Importance, Urgency, Effort-Cost (size), Value
- **Organization**: Group, Category
- **Meeting tracking**
  - **Is Meeting** flag
  - **Meeting Time** (set automatically when creating a Google Calendar event)

### Contacts
Contacts are used for autocomplete and linking in the **Who** field.

- contact types are typically things like Client / Contact / Personal
- Contacts appear in the Who autocomplete; selecting a contact stores a `contact_id` on the item

### Links (Item Links)
Items can store “links/attachments” as `ItemLink` records.

- Examples:
  - `obsidian_note`: a note file in your Obsidian vault
  - `google_calendar`: a Google Calendar event link
  - `url` (generic)

Even if a link is created by a workflow (e.g., Calendar), it’s still stored as an item link.

### Hierarchy (parent/child tasks)
Any action item can be the **parent** of other action items.

- child items store `parent_id = <parent item id>`
- nesting is unlimited (grandparent → parent → child → …)
- if a parent is deleted, children are preserved and become root items (parent_id cleared)

---

## 3) Screen-by-screen tour

### TODAY
Shows items relevant to “today”, split into:

- **To Do** (open)
- **Completed** (completed today)

Common controls:

- **Search**: searches title/description/next action, then filters to Today’s scope
- **Expand/Collapse**: show more/less columns on each row
- **Top 3**: toggle showing only the top 3 open items by priority score
- **+ New Item**: open the Item Editor for a new item
- **Refresh**: reload items

Row actions (open items):

- **⏱ Timer**: start a focused timer session on the item
- **Edit**: open Item Editor
- **Push**: move the item forward by 1 day (weekend-aware based on settings)

### Upcoming
Shows open items due within the next N days, grouped by date.

Controls:

- **Search**
- **Next N days** selector (1/3/7/14/30)
- **Who** filter
- **Expand/Collapse**
- **+ New Item**

Row actions (open items):

- **⏱ Timer**
- **Edit**
- **Push** (weekend-aware)

### All Items
Table-style list of items.

Controls:

- **Search**
- **Status** filter (open/completed/canceled/all)
- **Who** filter
- **Expand/Collapse**
- **+ New Item**

Row actions depend on status; open items typically show:

- **⏱ Timer**
- **Edit**

### Hierarchical
Tree-style view of parent/child relationships.

Controls:

- **Search**
- **Status** filter (open/completed/all)
- **+ New Item**

Behavior:

- without search: shows **root items** and recursively displays children with indentation
- with search: shows a flat list of matches

### Plan
Time-block planning screen (visual planner).

- intended to plan your day by time blocks and assign items to blocks

### Completed
Review completed work (typically by date range), including summary stats.

### Contacts
Contact list screen.

- search by name/email/etc
- **+ New Contact** creates a contact
- click a contact row to edit

### Defaults
Configure default values used when creating items.

- supports **System Defaults** (global) and **Who-specific** defaults
- includes date offsets (Start/Due offsets in days from “today”)

### Stats
Statistics and insights (planned vs actual time, accuracy, etc.).

### Settings
Application settings. Tabs include:

- **Database Management** (backup + Obsidian)
- **Appearance** (UI + date increment behavior)
- **Timer & Audio**
- **Organizational Factors** (groups/categories management)
- **VPS Life Segments** (segment CRUD)

### VPS Planning
The Visionary Planning System screen.

- filter which life segments are shown
- expand/collapse all
- create new top-level vision
- expand each level of the VPS hierarchy
- add/edit/delete at each level

---

## 4) Linking: Contacts, Item Links, and Google Calendar

### 4.1 Linking items to Contacts (the Who field)
In the Item Editor, the **Who** field supports autocomplete against Contacts.

- When you pick a contact, the item stores both:
  - the display name in **Who**
  - the contact’s internal id as `contact_id`

Why it matters:

- you can filter lists by Who
- you can keep consistent naming (autocomplete prevents variants)

### 4.2 Item Links (general mechanism)
Item Links are attachments/URLs associated with an item.

- each link has:
  - `url`
  - optional `label`
  - `link_type` (e.g., `obsidian_note`, `google_calendar`)

### 4.3 Obsidian note links
In the Item Editor **Notes** tab you can:

- **+ Create Note**: create a new Obsidian note for the item
- **+ Link Note**: link an existing Obsidian note
- each linked note appears in the list with:
  - **Open** (opens the note)
  - **×** (removes the link)

> Note: Obsidian linking requires configuring your vault path in **Settings → Database Management → Obsidian Integration**.

### 4.4 Google Calendar links
From the Item Editor you can create a Google Calendar event:

- click **📅 Calendar**
- fill out date/time/duration/attendees
- click **Create Calendar Event**

What happens:

- a Calendar event is created via Google Calendar API
- the event’s `htmlLink` is stored as an `ItemLink` with `link_type="google_calendar"`
- the item is updated:
  - **Is Meeting** becomes true
  - **Meeting Time** is stored
- the event opens in your browser

---

## 5) Hierarchy: parents, children, and “related” items

### 5.1 Creating child tasks from Next Action
In the Item Editor (existing items), **+ Create Tasks** creates *one child item per line* in the **Next Action** field.

Example:

```
Draft proposal
Send to client
Schedule review call
```

Result:

- three new child items are created
- each child inherits key fields from the parent (Who/contact, dates, priority, group/category, planned minutes, etc.)
- each child’s title is `"<Parent Title> - <line text>"`

### 5.2 Setting or changing a parent
In the Item Editor, **Set Parent** opens a dialog to select another item as the parent.

### 5.3 Viewing related items
In the Item Editor, **Show Related** opens a dialog showing parent and children for navigation.

### 5.4 Sub-item indicator
If an item is a sub-item (has a parent), the Item Editor shows a banner: “Sub-item of: …” plus a **View Parent** button.

---

## 6) Key dialogs and buttons (button-by-button)

### 6.1 Item Editor (Create/Edit Action Item)
**Where you’ll see it:**

- **+ New Item** buttons
- **Edit** on list rows

#### Main fields (left column)
- **Who** (required)
  - autocomplete + dropdown suggestions
  - **+** button adds a new contact inline
- **Title** (required)
- **Description** (optional)
- **Next Action** (optional; multi-line)
- **Planned Minutes** (optional)

#### Tabs (right column)

**Dates tab**
- **Start Date** entry + quick buttons:
  - **Today** (set to today)
  - **-1** / **+1** (adjust)
  - **Clear**
- **Due Date** entry + quick buttons (same)
- **Is Meeting** checkbox
- **Meeting Time** display (read-only; set by Calendar creation)

**Priority tab**
- Set Importance / Urgency / Effort-Cost / Value (used to compute priority score)

**Organization tab**
- **Group**
- **Category**
- **Status / Completed Date** (completed date is display-only)

**Notes tab (Obsidian links)**
- **+ Create Note**
- **+ Link Note**
- List of linked notes:
  - **Open**
  - **×** (unlink)

#### Buttons (bottom)

Top row:
- **Save**: saves changes and keeps the editor open
- **Save & Close**: saves and closes the editor
- **Save + New** (new items only): saves, closes, then opens a fresh new editor
- **Duplicate** (existing items only): creates a duplicate item and opens it
- **Create Follow-up** (existing items only): creates a follow-up item (typically tomorrow) linked to the original workflow
- **Complete** (existing items only): marks item completed
- **📅 Calendar**: open the Calendar dialog and link a Google Calendar event
- **Cancel**: close without saving new changes
- **Delete** (existing items only): deletes the item (children are preserved; you’ll be warned if children exist)

Second row (existing items only):
- **+ Create Tasks**: create one child task per line of the Next Action field
- **Show Related**: open related-items dialog (parent/children)
- **Set Parent**: open set-parent dialog

---

### 6.2 Today / Upcoming / All Items list controls

#### Header controls
- **Search**: searches text fields; press Enter in the search box or click Search
- **Expand/Collapse**: toggles condensed vs expanded row detail
- **Filters** (Upcoming / All Items): choose date range / who / status
- **Top 3** (Today only): toggle between all open items and top 3 by priority score
- **+ New Item**: opens Item Editor
- **Refresh** (Today): reloads

#### Row buttons (common)
- **⏱ Timer**: opens the Timer window for that item
- **Edit**: opens Item Editor
- **Push** (Today/Upcoming): moves start/due dates forward (weekend-aware)

---

### 6.3 Timer window (Action Timer)
**Purpose:** run a focused work block, optionally with music, then complete or continue the task.

Top section:
- **Time Block** (minutes): the total block length
- **Time To Finish**: countdown of work portion
- **Wrap/Break**: break minutes

Timer controls:
- **Start**: begins the timer
- **Pause** / **Resume**: pauses or resumes countdown
- **Stop**: stops the session and reveals completion actions

Music controls:
- **▶ Play**: start music playback
- **⏸ Pause** / **▶ Resume**: pause/resume music playback

Completion actions (appear after Stop):
- **Finished**: complete the item and log work
- **Continue**: complete current item, then create a continued item with new dates and next steps

Notes section:
- **Pop Out**: open notes in a separate window
- **Save Notes**: saves edits back to the item’s description

---

### 6.4 Calendar dialog (Create Calendar Event)
Fields:

- **Event Title** (pre-filled from item title)
- **Date (YYYY-MM-DD)** with quick buttons:
  - **Today**
  - **+1** (weekend-aware)
- **Start Time**
  - hour, minute, AM/PM
- **Duration** (minutes)
- **Description** (optional; prefilled from item description)
- **Location** (optional)
- **Attendees** (optional; comma-separated emails)

Buttons:

- **Create Calendar Event**: creates the event, links it to the item, marks the item as a meeting, opens event in browser
- **Cancel**: closes dialog

---

### 6.5 Defaults screen
Use Defaults to pre-fill new items.

Controls:

- **Defaults For**:
  - **System Defaults** (global)
  - **Who-specific** (defaults for a given Who)

Editable defaults:

- **Default Who**
- Priority factors: Importance, Urgency, Effort-Cost, Value
- Organization: Group, Category
- Planned Minutes
- **Date Offsets**: Start Date Offset, Due Date Offset (days from today)

Buttons:

- **Save Defaults**: store changes
- **Clear Form**: reset inputs

---

### 6.6 Settings

#### Database Management tab
- **Backup Database**: creates a timestamped `.db` backup next to your current database file
- **Load Demo Data**: adds a small set of sample items to the *current* database (does not delete anything)

#### Obsidian Integration (within Database Management)
- **Vault Path**: where your Obsidian vault lives
- **Browse**: file chooser
- **Notes Subfolder**: optional subfolder for created notes
- **Save Settings** / **Test** (if present): saves and verifies configuration

#### Appearance tab
- theme/appearance options (varies by build)
- **Date Increment Settings** (weekend behavior)
  - include/exclude Saturday/Sunday for +1 logic
  - “Start list views expanded (Today, Upcoming, All Items)” (default column state)

#### Timer & Audio tab
- default time block minutes
- break minutes
- warning threshold
- enable/disable sounds
- choose sound files
- music folder + volume

#### Organizational Factors tab
Manage reusable lists:

- **Groups**
- **Categories**

#### VPS Life Segments tab
See section 6.7.

---

### 6.7 VPS Life Segments (Settings → VPS Life Segments)

Header controls:

- **+ New Segment**: create a segment
- **↻ Refresh**: reload the list

Each segment row shows:

- color swatch
- name and description
- status badge (✓ Active / ○ Inactive)
- **✎ Edit**
- **🗑 Delete**

Deletion behavior:

- if the segment has linked VPS records, deletion is blocked and you’ll see a detailed warning with instructions to delete child records first

#### VPS Segment Editor dialog (New/Edit Segment)
Fields:

- **Name***: segment name (required)
- **Description**: optional details
- **Color***: hex color (required)
  - color preview swatch
  - editable hex code
  - **🎨 Pick Color** opens a color picker
- **Display Order**: controls sorting order
- **Active (visible in VPS Planning)**: toggle whether it shows in VPS Planning

Buttons:

- **Save**: validate and save the segment
- **Cancel**: close without saving

---

## 7) Tips and common workflows

### Create an item quickly
- TODAY → **+ New Item** → enter **Who** and **Title** → **Save & Close**

### Break a big item into child tasks
- Open item → add one task per line in **Next Action** → **+ Create Tasks**

### Convert an action into a meeting
- Open item → **📅 Calendar** → create event → item becomes **Is Meeting** with **Meeting Time** stored

### Stay focused
- From a list row → **⏱ Timer** → work → **Finished** or **Continue**

---

## 8) Data location, demo data, and backups

### Production (normal install)
For normal use, GetMoreDone stores your data in your user profile:

- **macOS:** `~/Library/Application Support/GetMoreDone/getmoredone.db`
- **Windows:** `%APPDATA%\GetMoreDone\getmoredone.db`

### Development (repo)
When running from the repo, you can keep a separate dev database by setting:

- `GETMOREDONE_DB=/path/to/your/dev/getmoredone.db`

(The repo `start.sh` defaults this to `./data/getmoredone.db` so your dev data stays separate.)

### Demo data
For new installs or for people you share the app with:

- Go to **Settings → Database Management → Load Demo Data**
- This will **ADD** a small set of sample Action Items to the *current* database.
- It does **not** delete or overwrite your existing items.

### Backups
Use **Settings → Database Management → Backup Database** to create a timestamped `.db` backup next to your current database file.

---

## Appendix A — Glossary

- **Who**: the person/client/context the item is for
- **Planned minutes**: your estimate for how long the task should take
- **Work log**: a record created by the Timer when you finish/continue
- **Item link**: a stored URL/reference tied to an item (Obsidian note, Google Calendar event, etc.)
- **VPS Segment**: a “life area” bucket for your VPS planning tree
