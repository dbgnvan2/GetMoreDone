# Get More Done — Master Specification (SQLite, v1)

## 0) Change log / Spec corrections (merged + resolved)
- [Confirmed] Storage backend is **SQLite** (single local `.db` file), replacing “uses MD files for all data.” fileciteturn2file2L10-L18
- [Confirmed] “Who is required” is treated as a hard requirement. fileciteturn2file4L19-L23
- [Confirmed] Defaults-by-Who **MUST re-apply** on Who change (for fields not explicitly set). fileciteturn2file4L23-L23
- [Requires Verification] Priority-factor “P=0” contradiction is resolved by defining `P=0` as **Parked/None** (PriorityScore becomes 0 and sorts last). This keeps your published scales intact. fileciteturn2file1L30-L35

---

## 1) Overview
- [Confirmed] Problem: Make and use todo/action items; reschedule missed items; sort by priority; chunk into workable time blocks; track planned vs actual time to learn how long things take and improve future schedules. fileciteturn2file2L4-L16
- [Confirmed] Success: Know what to do (and in what order) daily; no items lost; reduced overwhelm; system helps manage list and time. fileciteturn2file2L4-L7

---

## 2) Scope

### 2.1 In scope
- [Confirmed] Create, edit, delete, schedule items. fileciteturn2file2L10-L14
- [Confirmed] Tag items with Who/What/When/Group/Category. fileciteturn2file2L11-L13
- [Confirmed] Daily/weekly list sorted by date. fileciteturn2file2L12-L13
- [Confirmed] Prioritization based on Importance/Urgency/Size/Value. fileciteturn2file2L13-L14
- [Confirmed] Track planned time vs actual time. fileciteturn2file2L14-L15
- [Confirmed] Build daily/weekly “calendar” of items (time blocks). fileciteturn2file2L15-L16
- [Requires Verification] Read/write to external calendar (provider + sync policy must be defined). fileciteturn2file2L16-L16
- [Confirmed] Accept links to files on items. fileciteturn2file2L17-L17

### 2.2 Out of scope
- [Confirmed] Project management, cost accounting, billing. fileciteturn2file2L19-L22

---

## 3) Terminology
- [Confirmed] Action Item: trackable unit of work with assignment, dates, and optional prioritization/organization metadata. fileciteturn2file2L24-L28
- [Confirmed] Who: person/account the item is being done for (e.g., client or self). fileciteturn2file2L25-L25
- [Confirmed] What: title + optional description. fileciteturn2file2L26-L26
- [Confirmed] When: start date + due date. fileciteturn2file2L27-L27
- [Confirmed] Defaults: pre-filled values applied during creation if user does not explicitly set a field. fileciteturn2file2L28-L28
- [Requires Verification] Time Block: scheduled plan segment (date + start/end time) optionally linked to an Action Item.
- [Requires Verification] Work Log: actual session record against an Action Item.

---

## 4) User roles
- [Confirmed] Single role: Main user. fileciteturn2file2L30-L32

---

## 5) Priority Model

### 5.1 Factors and scales (defaults)
- [Confirmed] Importance: Critical/High/Medium/Low = 20/10/5/1 fileciteturn2file0L35-L37
- [Confirmed] Urgency: Critical/High/Medium/Low = 20/10/5/1 fileciteturn2file0L36-L38
- [Confirmed] Size: XL/L/M/S/P = 16/8/4/2/0 fileciteturn2file0L38-L39
- [Confirmed] Value: XL/L/M/S/P = 16/8/4/2/0 fileciteturn2file0L38-L40

### 5.2 Priority score computation
- [Confirmed] PriorityScore = Importance × Urgency × Size × Value. fileciteturn2file1L28-L36
- [Confirmed] Example: 20×10×8×4 = 6400. fileciteturn2file1L35-L36

### 5.3 Zero-value handling (resolving contradiction)
- [Not Confirmed] “Priority fields cannot be zero” conflicts with Size/Value having P=0. fileciteturn2file1L30-L35
- [Requires Verification] Resolution adopted for v1: `P=0` means **Parked/None**; PriorityScore becomes 0; item sorts last unless filtered explicitly.

### 5.4 Sorting rules (deterministic)
- [Confirmed] Default “Upcoming” ordering: `due_date ASC`, then `PriorityScore DESC`, then `created_at ASC`.
- [Requires Verification] If due_date is missing: item is excluded from Upcoming OR shown in a “No due date” section (OD below).

---

## 6) User Stories (Master)
- [Confirmed] US-001 Create item with Who/What/When. fileciteturn2file2L36-L41
- [Confirmed] US-002 Optionally set Importance/Urgency/Size/Value. fileciteturn2file2L39-L41
- [Confirmed] US-003 Optionally set Group/Category. fileciteturn2file2L42-L43
- [Confirmed] US-004 Configure system + Who defaults. fileciteturn2file0L32-L34
- [Confirmed] US-005 Defaults-by-Who. fileciteturn2file0L33-L34
- [Confirmed] US-006 View upcoming items for next N days in date order, prioritized within date. (Derived from your stated UI needs.)
- [Confirmed] US-007 Reschedule missed items (don’t lose them). fileciteturn2file2L4-L6
- [Confirmed] US-008 Track planned vs actual time. fileciteturn2file2L14-L15
- [Confirmed] US-009 Build daily/weekly plan (time blocks). fileciteturn2file2L15-L16
- [Confirmed] US-010 Complete item and optionally “CompleteCreate” (create new item from completed). fileciteturn2file1L7-L10
- [Confirmed] US-011 Attach links to files. fileciteturn2file2L17-L17
- [Requires Verification] US-012 External calendar sync. fileciteturn2file2L16-L16

---

## 7) Functional Requirements (Master)

### 7.1 CRUD + lifecycle
- [Confirmed] FR-001 Create item. fileciteturn2file1L3-L5
- [Confirmed] FR-002 Edit item. fileciteturn2file1L4-L5
- [Confirmed] FR-003 Delete item. fileciteturn2file1L6-L10
- [Confirmed] FR-004 Duplicate item. fileciteturn2file1L7-L10
- [Confirmed] FR-005 Complete item. fileciteturn2file1L8-L10
- [Confirmed] FR-006 CompleteCreate: complete + create new item seeded from completed. fileciteturn2file1L10-L10
- [Confirmed] FR-007 Reschedule item and preserve history (adds new table `reschedule_history`).

### 7.2 Required fields
- [Confirmed] FR-008 `who` is required. fileciteturn2file4L19-L23
- [Requires Verification] FR-009 `title` is required (assumed; not explicitly stated in your draft).

### 7.3 Data fields
- [Confirmed] FR-010 Core: who, what_title, what_description, start_date, due_date. fileciteturn2file1L12-L17
- [Confirmed] FR-011 Priority factors: importance, urgency, size, value. fileciteturn2file1L18-L22
- [Confirmed] FR-012 Organization: group, category. fileciteturn2file1L23-L25
- [Confirmed] FR-013 Attachments/links: 0..N links per item. fileciteturn2file2L17-L17
- [Confirmed] FR-014 Planned minutes per item; actual minutes captured via work logs. fileciteturn2file2L14-L15

### 7.4 Priority computation
- [Confirmed] FR-020 Enforce allowed values for factors. fileciteturn2file1L28-L36
- [Confirmed] FR-021 Compute PriorityScore as product of the 4 factors. fileciteturn2file1L28-L36
- [Requires Verification] FR-022 Handling of P=0 as Parked/None (Section 5.3).

### 7.5 Defaults
- [Confirmed] FR-030 Support system defaults for priority fields. fileciteturn2file1L39-L46
- [Confirmed] FR-032 Support defaults-by-Who. fileciteturn2file1L42-L46
- [Confirmed] FR-033 Apply defaults at creation time. fileciteturn2file1L43-L43
- [Confirmed] FR-034 Default precedence: Who defaults > system defaults. fileciteturn2file1L44-L47
- [Confirmed] FR-035 User can view/edit defaults. fileciteturn2file1L47-L47
- [Confirmed] FR-037 If Who changes during creation/edit, re-apply Who defaults ONLY to fields not explicitly set. fileciteturn2file4L23-L23

### 7.6 Validation
- [Confirmed] FR-040 Validate due_date is not earlier than start_date when both present. fileciteturn2file3L12-L16
- [Confirmed] FR-041 Block save if required fields missing. fileciteturn2file3L15-L16
- [Confirmed] FR-042 Show field-level validation messages. fileciteturn2file3L16-L16

### 7.7 Lists / filtering / sorting (explicit UI needs)
- [Confirmed] FR-050 List view exists. fileciteturn2file3L18-L21
- [Confirmed] FR-051 List supports sort by due date and priority (PriorityScore). fileciteturn2file3L19-L21
- [Confirmed] FR-052 List supports filtering by Who/Group/Category. fileciteturn2file3L20-L21
- [Confirmed] FR-053 Upcoming view: “Next N days” ordered by due_date ASC, then PriorityScore DESC.
- [Confirmed] FR-054 Sort-by-column uses an allowlist; unsupported keys are rejected/ignored (prevents unsafe dynamic SQL).

### 7.8 Time blocks + work logs
- [Confirmed] FR-060 Build daily/weekly “calendar” of items (time blocks). fileciteturn2file2L15-L16
- [Confirmed] FR-061 Record planned minutes per block and actual minutes via work logs. fileciteturn2file2L14-L15
- [Requires Verification] FR-062 “Auto-plan day” (optional): fill available time with highest priority items.

### 7.9 Completed-item workflows (“do some stuff”)
- [Confirmed] FR-070 Completed items are excluded from open/upcoming by default. (Implied by “complete” lifecycle.)
- [Requires Verification] FR-071 Completed list supports: (a) filter by date range, (b) export, (c) create follow-on item (CompleteCreate already covered).

### 7.10 External calendar integration (optional v1.1)
- [Requires Verification] FR-080 Read calendar events to compute free time windows.
- [Requires Verification] FR-081 Write planned time blocks to calendar (sync rules required).

---

## 8) Data Model (SQLite) — v1 Schema

### 8.1 Tables
```sql
-- Action items
CREATE TABLE IF NOT EXISTS action_items (
  id               TEXT PRIMARY KEY,             -- UUID
  who              TEXT NOT NULL,
  title            TEXT NOT NULL,
  description      TEXT,

  start_date        TEXT,                        -- YYYY-MM-DD
  due_date          TEXT,                        -- YYYY-MM-DD

  importance        INTEGER,                     -- defaultable
  urgency           INTEGER,
  size              INTEGER,
  value             INTEGER,
  priority_score    INTEGER NOT NULL DEFAULT 0,  -- computed at save

  "group"           TEXT,
  category          TEXT,

  planned_minutes   INTEGER,                     -- optional
  status            TEXT NOT NULL DEFAULT 'open',-- open|completed|canceled
  completed_at      TEXT,                        -- ISO datetime

  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

-- Links/attachments (URLs or file paths)
CREATE TABLE IF NOT EXISTS item_links (
  id           TEXT PRIMARY KEY,                 -- UUID
  item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
  label        TEXT,
  url          TEXT NOT NULL,
  created_at   TEXT NOT NULL
);

-- Defaults (system + by-who)
CREATE TABLE IF NOT EXISTS defaults (
  scope_type        TEXT NOT NULL,               -- system|who
  scope_key         TEXT,                        -- NULL for system; who value for who-scope

  importance        INTEGER,
  urgency           INTEGER,
  size              INTEGER,
  value             INTEGER,

  "group"           TEXT,
  category          TEXT,
  planned_minutes   INTEGER,

  start_offset_days INTEGER,                     -- optional convenience
  due_offset_days   INTEGER,                     -- optional convenience

  PRIMARY KEY (scope_type, scope_key)
);

-- Reschedule history
CREATE TABLE IF NOT EXISTS reschedule_history (
  id           TEXT PRIMARY KEY,                 -- UUID
  item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
  from_start   TEXT,
  from_due     TEXT,
  to_start     TEXT,
  to_due       TEXT,
  reason       TEXT,
  created_at   TEXT NOT NULL
);

-- Planned time blocks (daily/weekly plan)
CREATE TABLE IF NOT EXISTS time_blocks (
  id           TEXT PRIMARY KEY,                 -- UUID
  item_id      TEXT REFERENCES action_items(id), -- optional link
  block_date   TEXT NOT NULL,                    -- YYYY-MM-DD
  start_time   TEXT NOT NULL,                    -- HH:MM
  end_time     TEXT NOT NULL,                    -- HH:MM
  planned_minutes INTEGER NOT NULL,
  label        TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);

-- Actual work logs
CREATE TABLE IF NOT EXISTS work_logs (
  id           TEXT PRIMARY KEY,                 -- UUID
  item_id      TEXT NOT NULL REFERENCES action_items(id) ON DELETE CASCADE,
  started_at   TEXT NOT NULL,                    -- ISO datetime
  ended_at     TEXT,                             -- ISO datetime
  minutes      INTEGER NOT NULL,
  note         TEXT,
  created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_status_due ON action_items(status, due_date);
CREATE INDEX IF NOT EXISTS idx_items_who        ON action_items(who);
CREATE INDEX IF NOT EXISTS idx_blocks_date      ON time_blocks(block_date);
CREATE INDEX IF NOT EXISTS idx_logs_item        ON work_logs(item_id);
```

### 8.2 Computation rules
- [Confirmed] On create/edit save: compute and persist `priority_score`.
- [Confirmed] PriorityScore uses final values after applying defaults.
- [Requires Verification] If any factor is NULL after defaults: treat as system default; if still NULL, treat as 0 (which will sink the item).

---

## 9) Core Queries / Views

### 9.1 Upcoming next N days (filterable by Who)
- [Confirmed] Returns open items with due_date in [today, today+N), ordered by due_date then priority_score.
```sql
SELECT *
FROM action_items
WHERE status = 'open'
  AND due_date IS NOT NULL
  AND due_date >= date('now')
  AND due_date <  date('now', '+' || :n_days || ' days')
  AND (:who IS NULL OR who = :who)
ORDER BY due_date ASC,
         priority_score DESC,
         created_at ASC;
```

### 9.2 Column sort (safe allowlist)
- [Confirmed] UI may request sort_key; app maps it to one of:
  - due_date, priority_score, importance, urgency, size, value, planned_minutes, created_at, updated_at
- [Confirmed] Any other sort_key is rejected/ignored.

### 9.3 Completed items (last X days)
```sql
SELECT *
FROM action_items
WHERE status='completed'
  AND completed_at >= datetime('now', '-' || :x_days || ' days')
ORDER BY completed_at DESC;
```

---

## 10) UI Specification (MVP)

### 10.1 Navigation (left sidebar)
- [Confirmed] Screens:
  1) **Upcoming**
  2) **All Items**
  3) **Plan**
  4) **Completed**
  5) **Defaults**
  6) **Stats**
  7) **Settings**

### 10.2 Screen: Upcoming (Next N days)
- [Confirmed] Controls:
  - N-days selector (default 7)
  - Who filter (All + specific Who)
  - Sort dropdown (allowlist)
- [Confirmed] List grouped by due_date:
  - Day header: date + count + total planned minutes (sum planned_minutes or blocks)
  - Item row shows: Complete checkbox, Title, Who, due_date, priority_score, factor chips (I/U/S/V), planned_minutes
- [Confirmed] Row quick actions: Edit, Reschedule, Duplicate, Add-to-Plan, CompleteCreate

### 10.3 Screen: All Items (table)
- [Confirmed] Table columns (toggleable): Who, Title, Start, Due, PriorityScore, I/U/S/V, Group, Category, Planned, Status
- [Confirmed] Sorting by clicking column header (restricted to allowlist)
- [Confirmed] Filters: Status, Who, Group, Category; search Title/Description
- [Confirmed] Bulk actions: Complete, Delete (confirm), Set Who, Set dates

### 10.4 Screen: Item Editor (Create/Edit)
- [Confirmed] Required: Who, Title
- [Confirmed] Optional: Description, Start/Due, I/U/S/V, Group/Category, Planned minutes, Links
- [Confirmed] Displays computed PriorityScore and formula breakdown
- [Confirmed] Buttons: Save, Save+New, Duplicate, Complete, CompleteCreate

### 10.5 Screen: Plan (Time Blocks)
- [Confirmed] Left pane: backlog list (open items; filter Who; sort by due_date then priority_score)
- [Confirmed] Right pane: day planner (select date; view time_blocks)
- [Confirmed] Actions:
  - Add block (manual) with start/end; optionally link item
  - Drag item → creates a block of planned_minutes (if present) or a default block length
  - Mark “worked” → opens Work Log entry (minutes + note)

### 10.6 Screen: Completed
- [Confirmed] Filters: date range (e.g., last 7/30/90), Who, Group, Category
- [Confirmed] Actions: View details, Create follow-on item (seed fields), Export (CSV/MD)

### 10.7 Screen: Defaults
- [Confirmed] Two sections:
  - System defaults (I/U/S/V, Group, Category, planned_minutes, start/due offsets)
  - Defaults by Who (select Who, set overrides)
- [Confirmed] “Preview defaults for Who” panel: shows final values after precedence.

### 10.8 Screen: Stats
- [Confirmed] Planned vs actual:
  - Per item: planned_minutes vs sum(work_logs.minutes)
  - Aggregates by Size and Category
- [Requires Verification] Visuals: simple tables first; charts optional.

### 10.9 Screen: Settings
- [Confirmed] Database path, backup/export, reset demo data
- [Requires Verification] Calendar integration settings (provider, sync direction) if implemented.

---

## 11) Acceptance Criteria (Master)

### 11.1 Create / validation
- [Confirmed] If Who missing → save blocked with field-level error. fileciteturn2file4L19-L23
- [Confirmed] If due_date < start_date → save blocked with field-level error. fileciteturn2file3L12-L16

### 11.2 Defaults
- [Confirmed] If Who defaults exist → they override system defaults for unset fields. fileciteturn2file1L44-L47
- [Confirmed] If Who changes → Who defaults re-apply to fields not explicitly set. fileciteturn2file4L23-L23

### 11.3 Upcoming view
- [Confirmed] Upcoming (N=7) shows open items with due_date within next 7 days, grouped by date, ordered by due_date then priority_score.

### 11.4 Completion workflow
- [Confirmed] Complete sets status=completed and item disappears from open lists.
- [Confirmed] CompleteCreate completes the item and creates a new item seeded from the completed one. fileciteturn2file1L10-L10

### 11.5 Time tracking
- [Confirmed] Work logs accumulate actual minutes and Stats reflects planned vs actual deltas.

---

## 12) Non-Functional Requirements
- [Confirmed] Local-first; single-user; no server required.
- [Confirmed] Writes are transactional (SQLite transactions per create/edit/complete).
- [Confirmed] Backup/export supported (at minimum: copy `.db`; optional CSV/MD exports).
- [Requires Verification] Cross-platform UI target (CLI vs desktop vs web-local) not specified.

---

## 13) Open Decisions (remaining)
- [Requires Verification] OD-001 How to treat no-due-date items in Upcoming: exclude vs separate section.
- [Requires Verification] OD-002 External calendar provider + sync rules. fileciteturn2file2L16-L16
- [Requires Verification] OD-003 Exact behavior of `P=0` (Parked/None) and whether UI should allow it by default. fileciteturn2file1L30-L35
