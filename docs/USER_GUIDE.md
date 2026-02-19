# GetMoreDone User Guide

This guide explains what each screen, button, and workflow does, and why you might use it. It is aligned to the current UI and screen code in `src/getmoredone/screens`.

Last updated: 2026-02-19

---

## 1) What GetMoreDone is for

GetMoreDone is a desktop task manager focused on prioritization and execution.

- What: A single place to capture action items, assign priorities, and schedule work.
- Why: It helps you decide what to do next, track progress, and keep long-term planning connected to daily execution.

---

## 2) Core concepts

### Action Items (tasks)
- What: The central record you work with. Required fields: `Who` and `Title`.
- Why: A consistent structure makes filtering, scheduling, and prioritization reliable.

### Priority score
- What: Calculated as Importance x Urgency x Effort-Cost (Size) x Value.
- Why: A single number makes it easy to rank items and focus on the highest impact work.

### Dates
- What: Each item can have a Start Date and a Due Date.
- Why: Start dates help with scheduling; due dates help with deadlines.
- Rule: Due date is never earlier than start date.

### Planned minutes
- What: Your estimate for how long the item should take.
- Why: Powers time blocks, timer defaults, and planned vs actual stats.

### Status
- What: Items can be `open`, `completed`, or `canceled`.
- Why: Status controls what shows up on Today/Upcoming views and what counts toward stats.

### Contacts and Who
- What: Contacts are people/clients. The item `Who` field can link to a contact.
- Why: You can filter by Who and keep consistent naming across items.

### Links (Item Links)
- What: Attachments/URLs tied to an item (e.g., Obsidian notes, Google Calendar events).
- Why: Keeps the context for a task inside the task.

### Hierarchy (parent/child tasks)
- What: Any item can have child items.
- Why: Useful for breaking large work into smaller next actions.

### VPS (Visionary Planning System)
- What: A planning hierarchy from long-term vision down to weekly actions, grouped by life segment.
- Why: Connects long-term goals to day-to-day tasks.

---

## 3) Screen-by-screen guide (What + Why)

### Today
- What: Shows items scheduled for today, split into open and completed today.
- Why: A focused daily view of what matters right now.

Header controls:
- **Search** — What: Searches title, description, and next action within Today scope. Why: Quickly find an item.
- **Expand/Collapse** — What: Toggles extra columns and priority factor chips. Why: Show or hide detail to reduce noise.
- **Top 3** — What: Shows only the top 3 open items by priority. Why: Focus on the highest priority work.
- **+ New Item** — What: Opens the Item Editor for a new task. Why: Capture work quickly.
- **Refresh** — What: Reloads the list. Why: Pull in updates after edits.

Row controls (open items):
- **Complete checkbox** — What: Marks item completed. Why: Clear finished work and log progress.
- **Timer** — What: Opens the focused timer window. Why: Work in a time block and log actual time.
- **Edit** — What: Opens the Item Editor. Why: Adjust details or add context.
- **Push** — What: Moves start/due dates forward by 1 day using weekend settings. Why: Reschedule quickly.

### Upcoming
- What: Shows open items due within the next N days, grouped by date.
- Why: Plan and look ahead without losing overdue items.

Header controls:
- **Search** — What: Searches title, description, next action. Why: Find items fast.
- **Next N days** — What: Sets the lookahead window. Why: Match planning horizon.
- **Who** — What: Filters by Who. Why: Focus on a client or context.
- **Expand/Collapse** — What: Toggles extra columns and priority factor chips. Why: Show or hide detail.
- **+ New Item** — What: Opens the Item Editor. Why: Capture a new upcoming task.

Row controls (open items):
- **Timer** — What: Starts the timer window. Why: Execute the task in a focused block.
- **Edit** — What: Opens the Item Editor. Why: Update scheduling or details.
- **Push** — What: Moves start/due forward by 1 day (weekend-aware). Why: Reschedule quickly.

### All Items
- What: A table view of all items, with filters.
- Why: Full visibility across open, completed, and canceled items.

Header controls:
- **Search** — What: Searches title, description, next action. Why: Locate items quickly.
- **Status** — What: Filters by open/completed/canceled/all. Why: Narrow the list to the state you need.
- **Who** — What: Filters by Who. Why: Focus on a person or client.
- **Expand/Collapse** — What: Toggles extra columns and priority factor chips. Why: Show or hide detail.
- **+ New Item** — What: Opens the Item Editor. Why: Add a new item.

Row controls:
- **Complete checkbox** — What: Marks an open item completed. Why: Clear finished work.
- **Timer** — What: Starts a timer for open items. Why: Track actual work time.
- **Edit** — What: Opens the Item Editor. Why: Modify item details.

### Hierarchical
- What: Tree view of parent/child relationships.
- Why: Visualize complex tasks and their sub-items.

Header controls:
- **Search** — What: Searches items. Why: Find a node quickly.
- **Status** — What: Filters by open/completed/all. Why: Reduce tree noise.
- **+ New Item** — What: Creates a new item. Why: Add tasks from the hierarchy view.

Behavior:
- Without search: shows roots and children indented.
- With search: shows a flat list of matching items.

### Drag Schedule
- What: A drag-and-drop rescheduling view. Left column shows Next Items; right column shows date boxes.
- Why: Quickly drag tasks onto a specific date and reschedule in one move.

Header controls:
- **Next N days** — What: Sets how many date boxes to show. Why: Adjust your planning horizon.
- **Who** — What: Filters the left list by Who. Why: Focus on one client or context.

Main area:
- **Next Items list (left)** — What: Open items with no dates plus upcoming items in the selected window. Why: A short list of items worth scheduling.
- **Date boxes (right)** — What: Drop targets for dates. Why: Reschedule by drag-and-drop.
  - Date label format: `Day - MM/DD - N items - Nh Mm`
  - Date label style: font is 30% larger than previous baseline.
  - Date/future box height: controlled by setting (`Drag Schedule box height (px)`).
- **Next item rows (left)** — What: draggable source records. Why: schedule items quickly.
  - Row height: uses the same `Drag Schedule box height (px)` setting for visual alignment with right-side boxes.
- **Future options (bottom)** — What: Mid Term, Long Term, 1st Next Month, 1st Next Quarter boxes. Why: Fast scheduling to common future anchors.

Drag behavior:
- What: Drag an item title onto a date box.
- Why: Sets both Start Date and Due Date to the drop date in one action.

### Plan (Time Blocks)
- What: A time block planning view with a backlog of open items and a day plan.
- Why: Translate tasks into a concrete daily schedule.

Backlog panel:
- **Open Items list** — What: Top open items by priority. Why: Pick the best tasks to schedule.

Day planner:
- **Date** — What: The date for time blocks. Why: Plan the right day.
- **Load** — What: Loads time blocks for the selected date. Why: Refresh or switch dates.
- **+ Add Block** — What: Opens the Add Time Block dialog. Why: Create a block of focused time.

Time blocks list:
- **Delete** — What: Removes a time block. Why: Adjust your plan.

Add Time Block dialog:
- **Start Time / End Time** — What: Time range for the block. Why: Define the schedule.
- **Label** — What: Optional label for the block. Why: Add a note or task name.
- **Save** — What: Creates the block. Why: Commit the plan.

### Completed
- What: Shows completed items over the last N days.
- Why: Review progress and time spent.

Header controls:
- **Last N days** — What: Sets the lookback window. Why: Focus on a recent period.
- **Who** — What: Filter by Who. Why: Review work for a client or context.
- **Expand/Collapse** — What: Toggles priority factor chips. Why: Show or hide detail.
- **Stats label** — What: Shows count and total planned minutes. Why: Quick summary.

Row controls:
- **Edit** — What: Opens the Item Editor. Why: Review or adjust completed items.
- **Reopen** — What: Changes status back to open. Why: Restore work that was completed by mistake.

### Contacts
- What: Manage your contacts (people/clients).
- Why: Cleaner Who values and faster filtering.

Header controls:
- **Search** — What: Searches name/email/phone. Why: Find contacts quickly.
- **+ New Contact** — What: Opens the contact editor. Why: Add a new contact.

Row behavior:
- **Click a contact** — What: Opens the contact editor. Why: Update details.

### Defaults
- What: Set default values for new items, system-wide or per Who.
- Why: Reduce repetitive data entry and standardize priority factors.

Controls:
- **Defaults For** — What: System Defaults or Who-specific defaults. Why: Apply defaults globally or per client.
- **Priority Factors** — What: Importance, Urgency, Effort-Cost, Value. Why: Auto-populate priority for new items.
- **Organization** — What: Default Group and Category. Why: Keep items organized.
- **Planned Minutes** — What: Default time estimate. Why: Set a typical duration.
- **Date Offsets section** — What: Start/Due offsets. Why: Centralize scheduling defaults.
- **Save Defaults** — What: Stores the defaults. Why: Make them apply to new items.
- **Clear Form** — What: Resets inputs. Why: Start over.

### Stats
- What: Planned vs actual time statistics for items that used the Timer.
- Why: Improve estimation accuracy and understand time usage.

Controls:
- **Refresh** — What: Reloads stats. Why: Update after new work logs.

### Settings
- What: Application configuration and data management.
- Why: Control behavior, integrations, and maintenance.

Tabs and controls:

Database Management:
- **Database Path** — What: Shows the current DB file. Why: Know where your data lives.
- **Backup Database** — What: Creates a timestamped backup. Why: Protect against loss.
- **Load Demo Data** — What: Adds sample items to the current DB. Why: See how the app works.

Obsidian Integration:
- **Vault Path** — What: Path to your Obsidian vault. Why: Enable note linking.
- **Notes Subfolder** — What: Subfolder for notes. Why: Keep GMD notes organized.
- **Save Settings** — What: Stores vault settings. Why: Persist configuration.
- **Test Connection** — What: Validates vault path and subfolder. Why: Confirm setup is correct.

Date Increment Settings:
- **First day of week (VPS)** — What: Sets week start day for APE Period week generation. Why: Keep weekly planning aligned with your calendar.
- **Drag Schedule date text color** — What: Hex color for date-box text (default `#FFFFFF`). Why: Improve readability across box colors.
  - Includes **Pick Color** button for visual selection.
- **Drag Schedule box height (px)** — What: Controls the height of all Drag Schedule date/future boxes. Why: Match readability and spacing preferences.

### Vision Planning (Unified Hub)
- What: A single workspace with top navigation for all vision-planning flows.
- Why: Removes redundant screens and keeps workflows in one place.

Top buttons:
- **Vision Elements** — Create and maintain Segment|SubSegment|Category keys.
- **Annual Vision Segments** — Promote Vision Elements into Annual Vision/Plan records.
- **APE Assignment** — Assign Annual Plan Elements to quarters and months.
- **APE Period View** — Select weeks within a month and create weekly parent records.
- **APE Weekly** — Work weekly parent records and their daily child Action Items.

APE Weekly behavior:
- Left list shows weekly parent records (weekly tactics).
- Right list shows child daily Action Items linked by parent.
- New daily item title format: `Weekly Title Prefix - Action Item Title`.
- Prefix shortening rule: first two pipe-delimited parts become initials.
  - Example: `Purposeful Work|Living Systems|Blog` → `PW|LS|Blog`.
- Week token normalization: `Week 8` is normalized to `W8` in generated/normalized titles.

Appearance:
- **Theme** — What: Dark/light/system. Why: Choose a comfortable look.

Date Increment Settings:
- **Include Saturday** — What: Weekend-aware push and +/- logic. Why: Control scheduling on weekends.
- **Include Sunday** — What: Same as above. Why: Adjust weekend behavior.
- **Start list views expanded** — What: Default expanded/collapsed state for Today/Upcoming/All Items. Why: Match your preference.
- **Future Date Options** — What: Mid Term and Long Term day offsets for Drag Schedule. Why: Customize long-range targets without manual date picking.
- **Save Settings** — What: Saves date increment preferences. Why: Apply behavior consistently.

Timer & Audio:
- **Music Folder** — What: Folder of audio files used during the timer. Why: Automatically play focus music.
- **Browse** — What: Opens a folder picker. Why: Choose the music folder.
- **Music Volume** — What: Slider for playback volume. Why: Adjust sound level.
- **Save Settings** — What: Saves audio settings. Why: Keep them persistent.

Organizational Factors:
- **Groups tab** — What: Manage Group values used on items. Why: Keep grouping consistent.
- **Categories tab** — What: Manage Category values used on items. Why: Keep categorization consistent.
- **Rename** — What: Renames a value across items (optional). Why: Fix naming without manual edits.
- **Delete** — What: Removes a value, with optional replacement. Why: Clean up unused values.
- **Refresh List** — What: Reloads values. Why: See recent changes.

Email Import (Gmail):
- **Enable Gmail import** — What: Turns the importer on or off. Why: Pause imports without changing config.
- **Trigger Label** — What: Gmail label to scan for new items. Why: Control which emails become tasks.
- **Processed Label** — What: Label applied after import. Why: Prevent duplicate imports.
- **Poll Interval** — What: Seconds between import checks. Why: Control frequency.
- **Save Email Import Settings** — What: Stores config. Why: Persist your choices.
- **Run Import Now** — What: Runs the importer immediately. Why: Pull in emails on demand.
- **Open Logs** — What: Opens importer logs. Why: Debug or confirm imports.
- **Gmail account** — What: Uses the Gmail account authorized on this machine. Why: Keeps imports tied to the correct inbox.

VPS Life Segments:
- **+ New Segment** — What: Creates a new life segment. Why: Organize VPS plans by life area.
- **Refresh** — What: Reloads the list. Why: See recent changes.
- **Edit** — What: Modify segment details. Why: Keep segments accurate.
- **Delete** — What: Deletes a segment if no linked VPS records exist. Why: Clean up unused segments.
- **Deletion protection** — What: If linked VPS records exist, deletion is blocked and you are guided to remove child records first. Why: Prevent accidental data loss.

Future Date Options:
- **Near Term / Long Term** — What: Offsets from today. Why: Quick scheduling targets for Drag Schedule.
- **1st Next Month / 1st Next Quarter** — What: Offsets from the 1st of next month/quarter. Why: Align with month/quarter starts.

### VPS Planning
- What: The Visionary Planning System hierarchy.
- Why: Turn long-term vision into concrete actions.

Common controls:
- **Expand All / Collapse** — What: Opens or collapses all nodes. Why: Fast navigation.
- **Segment filter** — What: Filter by VPS segment. Why: Focus on a life area.
- **Add buttons** — What: Create new TL Vision, Annual Vision, Annual Plan, Quarter Initiative, Month Tactic, Week Action. Why: Build the planning tree.
- **Edit** — What: Modify a plan node. Why: Keep planning current.
- **Delete** — What: Remove a node (with safety checks). Why: Clean up or reorganize.

---

## 4) Item Editor (What + Why)

The Item Editor is where you create and edit Action Items. It appears from **+ New Item** and **Edit** buttons.

Main fields:
- **Who** — What: Person/client/context. Why: Filter and group items by owner.
- **Title** — What: Task name. Why: The primary label everywhere in the app.
- **Description** — What: Longer notes. Why: Store context or details.
- **Next Action** — What: Short, action-focused notes, often one per line. Why: Break a task into next steps.
- **Planned Minutes** — What: Time estimate. Why: Better scheduling and stats.

Tabs:

Dates:
- **Start Date** — What: When work should start. Why: Schedule intentionally.
- **Due Date** — What: Deadline. Why: Keep commitments visible.
- **Today / -1 / +1 / Clear** — What: Quick date controls. Why: Fast scheduling.
- **Is Meeting** — What: Meeting flag. Why: Track meeting tasks and calendar links.
- **Meeting Time** — What: Auto-filled from Calendar events. Why: Keep meeting time visible.

Priority:
- **Importance, Urgency, Effort-Cost, Value** — What: Priority factors. Why: Compute priority score and compare items.

Organization:
- **Group, Category** — What: Organizational labels. Why: Filter and report by area.
- **Status / Completed Date** — What: Item state. Why: Control workflow and visibility.

Notes:
- **+ Create Note** — What: Creates an Obsidian note for the item. Why: Keep longer notes linked.
- **+ Link Note** — What: Links an existing Obsidian note. Why: Connect existing context.
- **Open** — What: Opens a linked note. Why: Jump to details quickly.
- **Remove (X)** — What: Unlinks the note. Why: Clean up attachments.

Buttons (top row):
- **Save** — What: Saves changes, keeps editor open. Why: Iterate without reopening.
- **Save & Close** — What: Saves and closes. Why: Finish editing quickly.
- **Save + New** — What: Saves and opens a new item. Why: Rapid entry of multiple tasks.
- **Duplicate** — What: Creates a copy of the item. Why: Repeat similar tasks.
- **Create Follow-up** — What: Creates a follow-up item. Why: Continue work without losing history.
- **Complete** — What: Marks the item completed. Why: Track progress.
- **Calendar** — What: Opens Calendar dialog. Why: Schedule a meeting and link it.
- **Cancel** — What: Closes without saving. Why: Discard changes.
- **Delete** — What: Deletes the item (children are preserved). Why: Remove obsolete tasks.

Buttons (second row):
- **+ Create Tasks** — What: Creates one child item per line in Next Action. Why: Quickly split work.
- **Show Related** — What: Shows parent and children. Why: Navigate the hierarchy.
- **Set Parent** — What: Assigns a parent item. Why: Organize tasks into a tree.

---

## 5) Timer window (What + Why)

The Timer supports focused work sessions and time tracking.

Controls:
- **Time Block** — What: Total minutes for the session. Why: Set a time boundary.
- **Time To Finish** — What: Countdown of work time. Why: Keep pace.
- **Wrap/Break** — What: Break duration. Why: Account for wrap-up time.
- **Start** — What: Starts the timer. Why: Begin the session.
- **Pause / Resume** — What: Pause or resume the countdown. Why: Handle interruptions.
- **Stop** — What: Stops the timer and shows completion actions. Why: End the session cleanly.

Music controls:
- **Play** — What: Starts music from your configured folder. Why: Focus support.
- **Pause** — What: Pauses music. Why: Quiet when needed.

Completion actions:
- **Finished** — What: Completes the item and logs work. Why: Close the loop on finished work.
- **Continue** — What: Completes current item, creates a new one, and prompts for next steps and dates. Why: Continue work into the next day without losing history.

Notes:
- **Pop Out** — What: Opens the notes in a separate window. Why: More space to write.
- **Save Notes** — What: Saves edits to the item description. Why: Keep notes synced.

---

## 6) Calendar dialog (What + Why)

The Calendar dialog schedules a Google Calendar event and links it to an item.

Fields:
- **Event Title** — What: Calendar event title. Why: Clear meeting name.
- **Date** — What: Meeting date with Today and +1 buttons. Why: Quick scheduling.
- **Start Time** — What: Hour/minute/AM-PM. Why: Exact start time.
- **Duration** — What: Minutes. Why: Accurate calendar blocks.
- **Description** — What: Event details. Why: Add context.
- **Location** — What: Meeting location. Why: Keep logistics visible.
- **Attendees** — What: Comma-separated emails. Why: Invite participants.

Buttons:
- **Create Calendar Event** — What: Creates the event and links it to the item. Why: Keep tasks and calendar connected.
- **Cancel** — What: Closes dialog without changes. Why: Back out safely.

---

## 7) Common workflows (Why you would use them)

- **Daily focus**: Today screen + Top 3 to focus on the highest priority items.
- **Weekly planning**: Upcoming and Drag Schedule to place tasks on dates.
- **Time blocking**: Plan screen to translate tasks into a daily schedule.
- **Meetings**: Item Editor + Calendar dialog to schedule and link meetings.
- **Hierarchy**: Next Action + Create Tasks to break down large projects.
- **Review**: Completed and Stats to review progress and time accuracy.

---

## 8) Data location and backups

Default locations:
- macOS: `~/Library/Application Support/GetMoreDone/getmoredone.db`
- Windows: `%APPDATA%\GetMoreDone\getmoredone.db`

Development mode:
- Set `GETMOREDONE_DB=/path/to/your/dev/getmoredone.db`
- `start.sh` defaults to `./data/getmoredone.db`

Backups:
- Use **Settings → Database Management → Backup Database** to create a timestamped backup next to your current DB file.

---

## Appendix: Glossary

- **Who**: Person/client/context the item is for.
- **Planned minutes**: Your estimated duration for the task.
- **Work log**: A record created by the Timer when you finish or continue.
- **Item link**: A stored URL/reference tied to an item (Obsidian note, Google Calendar event, etc.).
- **VPS Segment**: A life area bucket for VPS planning.
