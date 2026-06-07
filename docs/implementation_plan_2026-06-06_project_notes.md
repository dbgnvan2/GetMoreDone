# Implementation Plan: Project Notes as First-Class List in Project Detail Panel

**Date:** 2026-06-06
**Feature:** Split the Project detail right panel into two equal sections — **Project Notes** and **Action Items** — both rendered as visible lists with checkboxes and Status. Replaces the current "N notes linked to this project." count-only summary with the same kind of list users already get for Action Items.

## Background — current state (from existing screenshots)

Right panel today (when a project is selected) renders, top-to-bottom:
1. Project title + meta line
2. Toolbar of 7 buttons
3. **One line of text** — `"N notes linked to this project."` (no list, only a count)
4. `Action Items` header + `Show Completed` + `Select All` + count
5. Action item rows: checkbox, title, status/start/due meta, Edit/Complete/Unlink

So today **Notes are invisible** in the panel — you have to click `Open Notes` to see them as a separate dialog. Per the user's direction, Notes should be a real list in the panel, parallel to Action Items.

## User's conceptual model (locked in chat)

- **Action Items** = tasks → Priority, Start/Due dates, Status
- **Notes** = always Obsidian notes (this is the only meaning of "Notes" going forward)
- **Project Notes** = Obsidian notes linked to a project → Status only, **no** Priority, **no** dates
- Clicking a project shows **all OPEN Project Notes AND OPEN Action Items**

## Decisions locked in chat

| # | Decision | Choice |
|---|---|---|
| D1 | Identity of a Project Note | Existing `ProjectBoardLink` row + a new `status` column. Status is per-link (same Obsidian doc linked to two projects can have independent statuses). |
| D2 | Project Note status values | `open` / `completed` (mirrors Action Items). |
| D3 | Layout | Two stacked sections: Project Notes on top, Action Items below. |
| D4 | "Show Completed" | **One shared toggle** at the top of the items area. Default **OFF** → open-only on first view (supersedes the prior default-on choice for Action Items). |

## Acceptance Criteria & Verification

### M1 — Data model: Status on Project Notes

| ID | Description | Test |
|---|---|---|
| **M1.A.1** | `ProjectBoardLink` dataclass has a `status: str = "open"` field. | `tests/test_project_notes.py::test_project_board_link_has_status_field` — instantiates `ProjectBoardLink(...)`, asserts `link.status == "open"`. |
| **M1.A.2** | `project_board_links` SQLite table has a `status TEXT NOT NULL DEFAULT 'open'` column. | `tests/test_project_notes.py::test_project_board_links_table_has_status_column` — runs `PRAGMA table_info(project_board_links)`, asserts row for `status` exists with `dflt_value='open'`. |
| **M1.A.3** | A migration runs at startup that adds the column to existing DBs without data loss. | `tests/test_project_notes.py::test_migration_adds_status_to_existing_db` — opens a DB with the old schema (no status), inserts a link, calls `initialize_schema()` again, asserts new column exists and the existing link's status is `'open'`. |
| **M1.A.4** | `add_project_board_link`, `get_project_board_links` round-trip the new status. | `tests/test_project_notes.py::test_link_status_roundtrip` — insert with `status='completed'`, fetch, assert. |

### M2 — DB methods for note status

| ID | Description | Test |
|---|---|---|
| **M2.A.1** | `DatabaseManager.complete_project_note(link_id)` sets status='completed'. | `tests/test_project_notes.py::test_complete_project_note` |
| **M2.A.2** | `DatabaseManager.reopen_project_note(link_id)` sets status='open'. | `tests/test_project_notes.py::test_reopen_project_note` |
| **M2.A.3** | `get_project_board_links(board_id, include_completed=True)` returns all; `include_completed=False` returns only open. (Default = True so existing callers don't break.) | `tests/test_project_notes.py::test_get_links_filters_by_status` |

### M3 — UI: Project Notes section

| ID | Description | Test |
|---|---|---|
| **M3.A.1** | Right panel shows a `Project Notes` header (bold) **above** the `Action Items` header. | `tests/test_project_notes.py::test_project_notes_header_rendered` — uses the `gui_screen` fixture pattern, asserts a CTkLabel with text `"Project Notes"` exists in `screen.items_frame`. |
| **M3.A.2** | Each linked note renders as a row with: link label/url, status, `Open` button, `Complete` (if open) / `Reopen` (if completed) button, `Unlink` button. **No** checkbox, **no** Priority, **no** dates. | `tests/test_project_notes.py::test_project_note_row_has_status_buttons_no_checkbox` — asserts the row contains `Complete`/`Reopen` and `Unlink` buttons but no `CTkCheckBox`. |
| **M3.A.3** | `Complete` on a note moves it to completed status; UI refreshes. | `tests/test_project_notes.py::test_complete_button_updates_status` — click handler, assert DB row updated and screen re-rendered. |
| **M3.A.4** | A count label reads `"N note(s) shown"` (open-only) or `"N shown • M completed hidden"` when filter is on. | `tests/test_project_notes.py::test_notes_count_label` |

### M4 — Shared "Show Completed" toggle

| ID | Description | Test |
|---|---|---|
| **M4.A.1** | A single `Show Completed` checkbox sits in a shared header above both sections, default **off**. | `tests/test_project_notes.py::test_show_completed_default_off` — assert `screen.show_completed_items_var.get() is False` (default flipped from earlier). |
| **M4.A.2** | Toggling it affects BOTH the Notes list and the Action Items list. | `tests/test_project_notes.py::test_show_completed_filters_both_lists` — set up open+completed in both lists, assert both are filtered together. |
| **M4.A.3** | `Select All` (Action Items) only selects visible (open) items when filter is off. | Already covered by `TestShowCompletedToggle::test_select_all_respects_filter` (passes today). |

### M5 — Obsoleted UI elements removed cleanly

| ID | Description | Test |
|---|---|---|
| **M5.A.1** | The old `"N notes linked to this project."` count-only line is removed (replaced by the new Notes section + its own count label). | `tests/test_project_notes.py::test_old_count_only_label_removed` — assert no label with that exact text exists. |
| **M5.A.2** | The toolbar buttons `Create Note`, `Link Note`, `Open Notes` are **kept** (still useful — Create/Link add notes, Open jumps to Obsidian). No behavior change to those handlers. | Visual check + no test changes for those handlers. |

### M6 — Spec traceability & docstrings

| ID | Description | Test |
|---|---|---|
| **M6.A.1** | Every new method/function has a docstring with `Purpose:` / `Spec:` / `Tests:` referencing this file and the test name. | Manual review (cannot automate cheaply). Will be visible in the diff. |
| **M6.A.2** | `docs/spec_coverage.md` is updated with a section for this plan: spec ID → impl location → test → status. | `tests/test_project_notes.py::test_spec_coverage_doc_mentions_m1_through_m5` — open `docs/spec_coverage.md`, assert each top-level ID (`M1.A.1`…`M5.A.2`) appears. |

## Implementation Order

1. **M1 (Data model)** — change `ProjectBoardLink`, add column + migration. **Verify M1 tests pass before touching anything else.** Migration is the riskiest piece; it must be solid before code depends on it.
2. **M2 (DB methods)** — add complete/reopen and filtered get.
3. **M3 (Notes section UI)** — build the list rows + handlers. Use the existing Action Items row pattern as a template, but strip checkbox/date fields.
4. **M4 (Shared Show Completed)** — flip default to off; rewire the existing var to filter both lists; update `_render_detail`.
5. **M5 (Cleanup)** — remove the old count-only line.
6. **M6 (Docs)** — write `docs/spec_coverage.md` section, add docstrings.

## Files to Modify

| File | Change |
|---|---|
| `src/getmoredone/models.py` | Add `status` field to `ProjectBoardLink`. |
| `src/getmoredone/database.py` | New table column + idempotent migration. |
| `src/getmoredone/db_manager_project_boards.py` | Round-trip status in SQL; new `complete_project_note` / `reopen_project_note`; add `include_completed` to `get_project_board_links`. |
| `src/getmoredone/screens/project_boards.py` | New Notes section, shared `Show Completed` rewiring, remove old count-only label. |
| `tests/test_project_notes.py` | New test file, all M1–M5 tests. |
| `docs/spec_coverage.md` | New (or appended) coverage table. |

## Risks & "Adjacent issues found, not fixed" (per CLAUDE.md §8)

While reading the project-detail code I noticed:

1. **`open_note_picker` does its own dialog** that duplicates note-row rendering. Once notes are in the panel as first-class rows, that dialog becomes redundant — but **I will not remove or refactor it in this change** (out of scope). Flagging for follow-up.
2. **`load_notes()` will still be called from outside the new section** in a few places (e.g. `delete_note_link`). It should be safe to leave it because it now renders into the new Notes section frame, but I'll double-check during M3.
3. **The Obsidian "open" path** (`_open_note_path`) is unchanged. If the user later wants completed Project Notes to remain openable, the existing handler already works for both statuses.
4. The `ProjectBoard.notes` field (a freeform text blurb on the project card itself) is **not** the same as Project Notes. It's the small text shown on the card in the left panel. I will not touch it. Flagging because the naming overlap is a long-term debt.

## Open question for the user

**Default ordering of Project Notes in the section** — alphabetical by label, or most-recently-linked first? My default will be **most-recently-linked first** (matches typical "newest first" expectations and is what `created_at DESC` gives us essentially for free), unless you prefer alphabetical.

## Status

**Plan ready for approval.** No code changed yet. Awaiting your sign-off before starting M1.
