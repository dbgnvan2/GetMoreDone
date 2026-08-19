# Implementation plan — Project link + Action Item editor layout rework

Date: 2026-08-19 (revised after review feedback)
Status: **implemented** — see [`docs/spec_coverage_2026-08-19_item_editor_project_link.md`](spec_coverage_2026-08-19_item_editor_project_link.md)

## Goal

Two things in one change to the Action Item **Create/Edit** screen
(`ItemEditorDialog`):

**A. Project linking.** The user can see which Project the item is filed under,
pick a different one, clear it, or **create a brand-new Project without leaving
the editor** — so a new Action Item can be created and filed to a new Project
from one screen.

**B. Layout rework.** The weekly-tactic fields leave the Organization tab, a new
**Action Plan** block in the top-left shows the item's Project and Weekly Tactic,
and the action buttons are re-paired.

"Project" here is a `ProjectBoard` row; the item↔project relation is the
`project_board_items` table.

> The screenshot supplied with the review confirmed this reading; it changed
> nothing in the plan beyond making Timer half-width so Cancel can sit beside it.

---

## What already exists (no new DB work needed)

| Piece | Location |
|---|---|
| `project_board_items` link table | `database.py` schema |
| `link_item_to_project_exclusive(board_id, item_id)` — clears prior links, adds one, **copies the board's APE onto the item** | `db_manager_project_boards.py:177` |
| `clear_item_project_links(item_id)` — removes links **and nulls the item's `annual_plan_element_id`** | `db_manager_project_boards.py:220` |
| `get_project_board_ids_for_item(item_id)` | `db_manager_project_boards.py:230` |
| `get_project_boards(show_pending, show_completed)` | `db_manager_project_boards.py:81` |
| `create_project_board(board)` | `db_manager_project_boards.py:13` |
| `ProjectBoardEditorDialog` — full New/Edit Project dialog, sets `.result`, caller persists | `screens/project_boards.py:25` |
| `SetWeeklyTacticDialog` — the picker the "Set Wk Tactic" button already opens | `screens/item_editor_weekly_tactic_dialog.py` |

The only precedent for setting the link outside the Projects screen is the
Scheduler drag-drop (`screens/drag_schedule.py:1266`), which uses exactly the
exclusive/clear pair above. This change follows that same contract, so the two
surfaces cannot drift.

---

## B. Layout rework — the six points

### 1. Weekly fields off the Organization tab
`_setup_org_tab` keeps **Group** and **Category** only. The `Wk Tactic:` label
and the `Orig. Week:` entry move to the new Action Plan block (point 6).
`refresh_weekly_tactic_display()` keeps its name and contract — only the widget
it writes to moves — so the existing tests and the
`apply_weekly_tactic_selection` caller keep working.

### 6. New "Action Plan" block, top-left
A titled block in the left column, directly under the Title row and above
Description:

```
Action Plan
  Project:     Website Rebuild                 (read-only label)
  Wk Tactic:   Ship v2 | W34 (2026-08-17 to 2026-08-23)   (read-only label)
  Orig. Week:  [2026-08-10]                    (editable entry, unchanged behaviour)
```

Both values are set through the **Set Project** / **Set Wk Tactic** buttons, so
the labels are read-only — same treatment the Wk Tactic already had. `Orig. Week`
stays an editable entry because `save_item` reads it (WT-M6.A.3); it has nowhere
else to live once it leaves the Org tab.

### 2–5. Button block

Current (right column, `create_form`) → proposed:

| | Left | Right |
|---|---|---|
| primary | **Save & Close** | **Save** |
| new items only | **Save + New** | **Cancel** |
| existing items | **⏱ Timer** | **Cancel** |
| existing items | **Add Follow-up** | **Add Subtasks** |
| existing items | **Set Parent** | **Show Related** |
| **both** | **Set Wk Tactic** | **Set Project** |
| existing items | **Complete** | **Delete** |

The Set row renders on a **new** item too (PL10.4). Filing a not-yet-saved item
under a Project is the headline case — a button available only after "save it
first" would leave it unreachable from the screen it was asked for (P25). Both
pickers already hold the choice for an unsaved item and apply it on insert.

- **2.** Cancel leaves the primary row and pairs with Timer. On a *new* item
  there is no Timer button, so Cancel pairs with **Save + New** — Cancel must
  exist on every state of the dialog (P25: don't lose a control on one path).
- **2.** **Duplicate is removed.** `duplicate_item()` and `create_followup()`
  merge into one method: save first, create the derived item, open it in an
  offset window. The surviving button is **Add Follow-up**, backed by
  `create_followup_item`.
  - Two real consequences, both improvements: `create_followup` currently does
    **not** save pending edits first (only `duplicate_item` did) — the merged
    method always saves first, so the P5 sibling gap closes. And
    `create_followup_item` carries the weekly lineage (`_inherit_weekly_lineage`,
    WT-M5.C.1) that plain `duplicate_action_item` drops.
  - `db_manager.duplicate_action_item` **stays** — `complete_and_create` and
    `create_followup_item` both call it. Only the editor's button and its
    wrapper method go.
- **3.** "Add Sub-tasks" is relabelled **Add Subtasks** (no hyphen) and pairs
  with Add Follow-up.
- **4.** Set Parent and Show Related pair on one row.
- **5.** New **Set Project** button beside Set Wk Tactic.

### Set Project dialog

Rather than a combo on a tab, point 5 makes Project a *button-driven* picker,
matching Set Wk Tactic. New `SetProjectDialog` in a new module
`screens/item_editor_project_dialog.py`:

- A searchable list of projects (active + pending; a completed project already
  linked to this item is still listed so it can't vanish).
- **Clear Project** button → `(none)`.
- **+ New Project** button → opens the existing `ProjectBoardEditorDialog`,
  persists via `create_project_board`, selects the new project and returns.
- On choose, calls back into the editor exactly like
  `apply_weekly_tactic_selection` does: for a saved item the link is written
  immediately; for an unsaved new item the choice is held and applied on insert.
  Implemented as a single deferred path — the choice is recorded in
  `_selected_project_id` and written by `save_item` for saved and new items
  alike, so Cancel really cancels and there is one place the link is written.

---

## Design decisions (call these out before approving)

- **D1 — One project per item (exclusive).** Matches the Scheduler and
  `link_item_to_project_exclusive`.
- **D2 — Linking overwrites the item's Annual Plan Element.** Existing behaviour
  of `link_item_to_project_exclusive`, not new. Clearing the project to `(none)`
  nulls the item's APE. Guarded per D3.
- **D3 — Apply only on change.** `save_item` compares against the value loaded
  when the dialog opened. Unchanged ⇒ no link/clear call at all, so an ordinary
  Save on an item that has an APE but no project cannot wipe the APE (P13).
- **D4 — Weekly Tactic records:** Set Project is disabled for `item_type ==
  'week'` in `_apply_record_type_ui()`, where Context is already disabled. A week
  item's title derives from its APE, so letting a project re-stamp the APE would
  silently rewrite the title.
- **D5 — Pre-existing multi-links preserved.** The Projects screen's "link
  existing items" dialog is *not* exclusive, so an item may already hold several
  links. The Action Plan label shows the first plus `+N more`; because of D3,
  saving without touching Set Project leaves all of them intact (P2).

---

## Acceptance criteria → tests

New file `tests/test_item_editor_project_link.py` (PL1–PL7) and
`tests/test_item_editor_layout.py` (PL8–PL12), driven with `SimpleNamespace`
stubs — the pattern already used by `tests/test_project_board_dates_ui.py` and
`tests/test_item_editor_weekly_tactic_ui.py`.

### A. Project linking

| ID | Criterion | Verified by |
|---|---|---|
| **PL1** | `SetProjectDialog` lists active + pending projects, plus any completed project already linked to this item. | `test_pl1_dialog_lists_projects` |
| **PL2** | Opening the editor on a linked item shows that project in the Action Plan block; an unlinked item shows `(none)`. | `test_pl2_action_plan_shows_current_project`, `test_pl2_1_unlinked_shows_none` |
| **PL2.2** | An item with two pre-existing links shows the first labelled `+1 more`. | `test_pl2_2_multi_link_is_surfaced_not_hidden` |
| **PL3** | **New item:** choosing a project then saving creates the item *and* the link, and stamps the board's APE. | `test_pl3_new_item_saves_and_links` — drives `save_item` on a stub with no `item_id`. |
| **PL4** | **Edit item:** choosing a different project re-links exclusively (old link gone, exactly one new link). | `test_pl4_edit_item_relinks_exclusively` |
| **PL4.1** | Clear Project removes the link. | `test_pl4_1_clear_removes_link` |
| **PL4.2** | Saving **without** touching Set Project makes **no** link/clear call — an item with an APE and no project keeps its APE. | `test_pl4_2_untouched_selection_never_clears` — intercepts both manager methods, asserts zero calls. **Written first** (highest-risk, P10). |
| **PL4.3** | Saving without touching Set Project leaves a pre-existing multi-link intact. | `test_pl4_3_untouched_selection_preserves_multi_link` |
| **PL5** | **+ New Project** opens `ProjectBoardEditorDialog`, persists the result via `create_project_board`, and selects it. Cancel creates nothing. | `test_pl5_new_project_creates_and_selects`, `test_pl5_1_cancel_creates_nothing` — dialog class monkeypatched, patch restored in `finally`. |
| **PL6** | Set Project is disabled for an `item_type == 'week'` record. | `test_pl6_week_record_disables_set_project` |
| **PL7** | The link round-trips through the real `DatabaseManager` and survives a re-read. | `test_pl7_link_round_trips_through_db` |

### B. Layout

| ID | Criterion | Verified by |
|---|---|---|
| **PL8** | `_setup_org_tab` creates Group and Category only — no `weekly_tactic_label`, no `weekly_tactic_start_entry`. | `test_pl8_org_tab_has_no_weekly_widgets` |
| **PL9** | The Action Plan block exists and `refresh_weekly_tactic_display` writes into it; `Orig. Week` still round-trips through `save_item`. | `test_pl9_action_plan_block_shows_project_and_tactic`, `test_pl9_1_orig_week_still_saves` |
| **PL10** | Button pairings: Cancel with Timer (existing item) / with Save + New (new item); Add Follow-up with Add Subtasks; Set Parent with Show Related; Set Wk Tactic with Set Project. Verified by grid row/column, not by "the widget exists". | `test_pl10_button_pairs_share_a_row` |
| **PL10.1** | No Duplicate button on any path; label reads exactly `Add Subtasks`. | `test_pl10_1_duplicate_button_is_gone` |
| **PL11** | The merged follow-up method saves before creating, and aborts entirely when the save fails. | `test_pl11_followup_saves_first`, `test_pl11_1_followup_aborts_on_save_failure` (rewrites of the existing `test_duplicate_item_*` pair in `tests/test_item_editor.py`, which target the removed method). |
| **PL12** | *(optional — needs your call, see below)* A follow-up inherits the original's project link. | `test_pl12_followup_inherits_project_link` |

**Not code-testable — flagged for human review:** the visual result of the
rework (Action Plan block spacing, button grid fit inside the scrollable
container at the default 920×550 and when the sash is dragged). Proposed human
check: launch under the venv, open a new item and an existing one, screenshot the
left column and the button block, confirm `app.log` is clean — per
`~/.claude/standards/ui-regression.md`.

---

## Implementation order

1. `tests/` — PL4.2 first, then PL3/PL4, then the layout tests.
2. `screens/item_editor_project_dialog.py` — new `SetProjectDialog`.
3. `screens/item_editor.py` — `_setup_org_tab` stripped to Group/Category (PL8).
4. `screens/item_editor.py` — Action Plan block in `create_form`; move
   `weekly_tactic_label` / `weekly_tactic_start_entry` there; add
   `project_label`; `refresh_project_display()` (PL9, PL2).
5. `screens/item_editor.py` — button block re-pairing, Cancel move, Duplicate
   removal, `Add Subtasks` relabel, `Set Project` button (PL10).
6. `screens/item_editor.py` — merge `duplicate_item` + `create_followup` into
   one method; update the two existing tests (PL11).
7. `screens/item_editor.py` — `set_project()` + `apply_project_selection()`;
   `save_item` applies the pending/changed link after create/update, both
   branches in the same change (P5) (PL3–PL4.3).
8. `_apply_record_type_ui` — disable Set Project for week records (PL6).
9. Full suite; then launch the app for the manual check.
10. Docs: `docs/changes/2026-08-19-item-editor-project-link.md` handoff note,
    `CHANGELOG.md`, `docs/USER_GUIDE.md`, `docs/spec_coverage.md`.

Steps 4→7 are sequential (7 needs the baseline stored in 4). No schema
migration, no `requirements.txt` change.

---

## Needs your call

- **PL12 — should a follow-up inherit the project link?** Today a follow-up
  inherits the weekly lineage and APE (`_inherit_weekly_lineage`) but nothing
  copies `project_board_items`, so a follow-up of a project task lands with no
  project. Coherent to fix while we're here; it is a behaviour change outside
  the six points, so I'm not folding it in silently. Include, or leave for later?

## Adjacent issues found, not fixed (rule 10)

- `LinkProjectActionItemsDialog._link` (`project_boards.py:374`) uses the
  **non**-exclusive `link_action_item_to_project_board` while the Scheduler uses
  the exclusive one. The two surfaces disagree about whether an item may belong
  to several projects. This change tolerates both (D5) but does not reconcile
  them.
- `get_unlinked_action_items` has no `LIMIT`, so the Projects screen's link
  dialog loads every open unlinked item.

---
---

# Phase C — Create a Weekly Tactic from the editor

Added 2026-08-19, after A and B shipped in `cfd7a66`.
Status: **awaiting approval — no implementation code written.**

## Goal

A user starting a new piece of work needs several Action Items under a Weekly
Tactic that does not exist yet. Today that means leaving the editor, going to the
Weekly Items screen, picking the APE and the week, creating the tactic, coming
back, and linking it.

**`+ New Weekly Tactic` on `SetWeeklyTacticDialog`**, mirroring the
`+ New Project` button phase A just put on `SetProjectDialog`. Same button pair,
same shape, same place.

## What already exists (no DB work, no new manager methods)

| Piece | Location |
|---|---|
| `WeeklyTacticEngine.ensure_tactic(ape_row, week_start, report)` — get-or-create the week item for an APE and week | `weekly_tactic.py` |
| `_ensure_quarter_and_month(ape_row, target, report)` — creates the Quarter Initiative and Month Tactic when missing, and sets the APE's `qN`/`mN` flags | `weekly_tactic.py` |
| `db_manager.weekly_tactic_engine` — the engine, its calendar already bound to `first_day_of_week` + `first_week_of_year_rule` | `db_manager.py` |
| `db_manager.transaction()` — one all-or-nothing unit (WT-M4.D) | `db_manager.py` |
| `list_annual_plan_element_catalog()` — the APE list `SetProjectDialog` already uses | `db_manager.py` |
| `CascadeReport` + `notify_weekly_tactic_changes` — the "here is what got created" summary, already wired into the editor | `weekly_tactic.py`, `screens/week_collision_notice.py` |
| `SetWeeklyTacticDialog` — the select-only picker to extend | `screens/item_editor_weekly_tactic_dialog.py` |
| `SetProjectDialog.create_new_project()` — the pattern to mirror | `screens/item_editor_project_dialog.py` |

**Verified, not assumed.** Starting from an APE with nothing built under it:

```
before: {quarter_initiatives: 0, month_tactics: 0}
  engine._ensure_quarter_and_month(ape, week_start, report)
  engine.ensure_tactic(ape, week_start, report)
after:  {quarter_initiatives: 1, month_tactics: 1}
created: quarter_initiative=Q2 2026, month_tactic=M5 2026, weekly_tactic=H|LS|Blog - W21
tactic:  H|LS|Blog - W21   2026-05-18 -> 2026-05-24
   filed: New work 0/1/2   start=2026-05-21  stamp=2026-05-18
APE flags set: q2=1 m5=1
```

So this is a dialog change. The engine underneath it is the WT-M4 cascade,
already built and tested.

**It also settles the mid-quarter question.** Every FK from `tl_visions` down to
`week_actions` is `NOT NULL`, and none of the seven `update_*` functions accepts
an FK — so a parent is fixed at creation and an orphan can never be adopted.
Backfill by re-parenting is not possible and is not needed: the chain is built
*downward* from the APE at the moment the tactic is created, with the editorial
text left blank. Creating a tactic for a May week on a bare APE creates Q2 and
May with it.

## Design decisions (call these out before approving)

- **WTC-D1 — "Create" is get-or-create.** WT-INV5 allows one Weekly Tactic per
  (APE, week), and `ensure_tactic` returns the existing row rather than raising.
  That is the right behaviour, but the button must not promise a new record when
  it may hand back an existing one — label and confirmation wording follow from
  this.
- **WTC-D2 — Which APE.** Default to the item's own `annual_plan_element_id`,
  which phase A's project link now stamps (D2). When the item has none, the
  dialog offers the `list_annual_plan_element_catalog()` picker. A Weekly Tactic
  cannot exist without an APE — enforced since WT-M1.C.4 — so with neither, the
  create control is disabled **with the reason shown**, not silently absent.
- **WTC-D3 — Which week.** Default to the week containing the item's start date,
  via `weekly_tactic_engine.calendar`, so it honours `first_day_of_week` and the
  first-week-of-year rule. Changeable in the dialog.
- **WTC-D4 — The title is derived, not typed.** `load_item_data` rewrites a week
  record's title to canonical **every time the editor opens it**
  (`item_editor.py:769`), so a hand-typed name would not survive. Either accept
  derived naming (`H|LS|Blog - W21`) and offer no title field, or carve out that
  rewrite. **Needs your call — see below.**
- **WTC-D5 — One transaction.** The create runs inside
  `db_manager.transaction()`. A failure part-way leaves no Quarter or Month
  behind, which is what WT-M4.D exists for.
- **WTC-D6 — Say what was built.** Creating a tactic can also create a Quarter
  Initiative and a Month Tactic and flip two flags on the APE. That is a
  side effect the user should see. The dialog returns the `CascadeReport` and the
  editor reports it through `notify_weekly_tactic_changes`, which already
  interrupts for rollover stubs and stays quiet otherwise (WT-M6.B.5).

## Acceptance criteria → tests

New file `tests/test_item_editor_weekly_tactic_create.py`, `SimpleNamespace`
stubs, same pattern as `tests/test_item_editor_weekly_tactic_ui.py`.

| ID | Criterion | Verified by |
|---|---|---|
| **WTC1** | `+ New Weekly Tactic` creates the tactic for the chosen APE and week, and selecting it files the item under it. | `test_wtc1_create_and_select` |
| **WTC2** | Creating for a week whose Quarter and Month do not exist creates both, and sets the APE's `qN`/`mN` flags — the mid-quarter start. | `test_wtc2_creates_quarter_and_month_when_missing` |
| **WTC3** | Creating for a week that already has a tactic returns **that** tactic and creates nothing (WTC-D1). | `test_wtc3_create_is_get_or_create` |
| **WTC4** | The week defaults to the week containing the item's start date, under the configured first-day-of-week. | `test_wtc4_week_defaults_to_the_items_week` |
| **WTC5** | With no APE on the item and none chosen, the create control is disabled **and states why**. | `test_wtc5_no_ape_disables_create_with_a_reason` |
| **WTC6** | A failure part-way leaves no Quarter, Month or week item behind, and the item unchanged (WTC-D5). | `test_wtc6_failed_create_rolls_back` — injects at `ensure_tactic`, mirroring `test_wt_m4d2_failure_at_last_row_rolls_back_everything`. **Written first** (highest-risk, P10). |
| **WTC7** | What was created reaches the user: the report names the Quarter and Month, not only the tactic (WTC-D6). | `test_wtc7_created_records_are_reported` |
| **WTC8** | Cancelling the create dialog creates nothing. | `test_wtc8_cancel_creates_nothing` |

**Not code-testable — flagged for human review:** whether the create panel reads
as *"make a new week bucket for work I already have"* rather than as VSP
planning. That is the whole point of the feature and no assertion covers it.
Proposed check: launch under the venv, create an item, use `+ New Weekly
Tactic`, confirm `app.log` is clean — per `~/.claude/standards/ui-regression.md`.

## Implementation order

1. `tests/` — WTC6 first, then WTC1–WTC3.
2. `screens/item_editor_weekly_tactic_dialog.py` — APE + week selection panel and
   the `+ New Weekly Tactic` button.
3. The create call itself: `transaction()` → `_ensure_quarter_and_month` →
   `ensure_tactic`, returning the `CascadeReport` with the chosen tactic.
4. `screens/item_editor.py` — pass the report to `notify_weekly_tactic_changes`
   on the existing `apply_weekly_tactic_selection` path (WTC-D6, WTC7).
5. Disabled-state and reason text (WTC5).
6. Full suite; then launch for the manual check.
7. Docs: handoff note, `CHANGELOG.md`, `docs/USER_GUIDE.md`, and the WTC rows in
   `docs/spec_coverage_2026-08-19_item_editor_project_link.md`.

No schema migration, no `requirements.txt` change, no new manager method.

## Needs your call

- **WTC-D4 — derived title, or an editable one?** Deriving it is free and
  consistent with every tactic the app already makes. Making it editable means
  changing the load-time canonical rewrite, which exists so a tactic's name
  always matches its APE and week. My recommendation: derived, no title field.
- **WTC-D2 — is defaulting the APE from the item's project the behaviour you
  want?** It means "new Weekly Tactic" quietly inherits the project's plan
  element. That is almost always right and occasionally surprising.

## Adjacent issue this feature makes more reachable (rule 10)

`_find_annual_initiative_for_ape` matches an APE to its Annual Initiative by
**string equality on the key field** (`LOWER(ai.title) = LOWER(ape.key_field)`),
not by a foreign key. Renaming a vision element updates the APE's `key_field` and
its mirror rows but **not** the initiative's title, so the link silently breaks
and the next assignment builds a second Annual Initiative and a second Quarter
Initiative for the same APE and quarter. Reproduced:

```
rename "Blog" -> "Newsletter"
  APE key_field: Health|Living Systems|Newsletter
  AI  title:     Health|Living Systems|Blog        <- not updated
next assign -> annual_initiatives: 2, quarter_initiatives: 2
```

Pre-existing, and spec §9 of the weekly-tactic spec deliberately left the
quarter/month/annual levels without the uniqueness protection WT-D8 gave weekly
tactics — so nothing dedupes it and nothing warns. This feature does not cause
it, but it puts a "create the scaffolding" button in front of many more users.

**Now specced separately:** `docs/spec_2026-08-19_rename_safe_links.md` (RN)
covers this and the rest of the class — a rename at any level from Vision to
Weekly Tactic must not break a link. A wider audit found the segment case is
worse than this one: renaming a segment makes an ordinary date change on a filed
Action Item raise `ValueError: Segment '...' not found`, because
`vision_segments` and `segment_descriptions` are joined by name and
`rename_vision_segment` updates only one of them. Project → Action Item and
Weekly Tactic → Action Item are id-based and already safe.

Phase C does not depend on RN, but the two touch the same create path
(`_ensure_quarter_and_month` → `_find_annual_initiative_for_ape`), so RN should
land first if both are approved.
