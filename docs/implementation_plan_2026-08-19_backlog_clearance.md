# Implementation plan — Backlog clearance (2026-08-19)

Status: Batch 1 complete (2026-08-19). Batch 2 complete (2026-08-19). Batch 3 outstanding.
Source: [`BACKLOG.md`](../BACKLOG.md) open items, plus the two decisions taken today.

## Decisions taken

- **An Action Item belongs to exactly one Project.** The Projects screen's
  additive "link existing items" dialog becomes exclusive, matching the
  Scheduler and the item editor.
- **Delete rather than wire** `complete_and_create` and `RescheduleDialog`.

## Two backlog entries are wrong — checked before planning work on them

- **C1 "Today listing shows all completed items" is already fixed.** Both the
  SQL path and the Python fallback in `TodayScreen.get_todays_items` restrict
  completed items to `DATE(completed_at) = today`. Verified empirically against
  a real database: an item completed 9 days ago does not appear; one completed
  today does. **Action: tick it off with a regression test, not a fix.**
- **B1 is real but its stated cause has moved.** `repair_child_dates` *does* now
  consume `normalization["collisions"]` (`weekly_tactic_maintenance.py:476`) —
  but only to mark that tactic's *children* unrepairable. Nothing repairs the
  collided week item itself, and `dedupe_weekly_tactics` groups by exact
  `start_date` (`:372`), so a tactic left mid-week never groups with the one
  holding the week start. The WT-INV5 violation is still permanent.

One more correction: the backlog says A3's caller is the Projects screen. It is
not — `get_unlinked_action_items` is called from `drag_schedule.py:426` and
`:480`, and the second call loads every row only to take `len()` of it.

---

## Batch 1 — Bugs that bite (no decisions needed)

| ID | Work | Test |
|---|---|---|
| **BC1** | Tick C1 off. Add the regression test its absence allowed: an item completed today appears in Today, one completed earlier does not, an open item does. | `tests/test_today_completed_filter.py` — new, three cases through the real `get_todays_items` |
| **BC2** | B1: repair the collided week item instead of only reporting it. When `normalize_week_item_starts` cannot snap a tactic because another already holds that week start, hand both to `dedupe_weekly_tactics` as a duplicate group — they *are* duplicates, they just do not look like one while the loser's `start_date` is still mid-week. | `tests/test_weekly_tactic_dedupe.py` — seed the exact state (two tactics, same APE + week, one mid-week), assert one survivor on the week start, children repointed, and the run is idempotent (**dirty-state test, P8**) |
| **BC3** | D2: rewrite the tests in `tests/test_vps_segments.py` that `return True/False` instead of asserting. There are **six**, not two: `test_imports`, `test_settings_has_vps_tab`, `test_segment_editor_structure`, `test_color_validation`, `test_vps_manager_segment_methods`, `test_colorchooser_import` (+ `test_enhanced_deletion_protection`). Each becomes real assertions. | The tests themselves; confirm each **fails** when its subject is broken, or it has not been converted, only reformatted |

Risk: BC2 touches the migration that runs at every app start on a real database.
It gets a dirty-state test and a no-op-on-clean-database assertion before anything else.

## Batch 2 — The project-link model (decision applied) — **complete**

Handoff: [`docs/changes/2026-08-19-backlog-batch-2.md`](changes/2026-08-19-backlog-batch-2.md).
BP6 was confirmed with the user before doing it, as the plan required.

| ID | Work | Test |
|---|---|---|
| **BP1** | A1: make `LinkProjectActionItemsDialog._link` and `_link_selected_items` use `link_item_to_project_exclusive`. One rule on every surface. | `tests/test_project_boards_ui.py` — linking an item already on another board moves it rather than adding |
| **BP2** | A1 migration: existing multi-linked items. Report the count at start-up and offer to resolve, or resolve on next edit. **Never silently drop links** (P2) — the editor's `(+N more)` and its confirmation stay as the visible path until the count is zero. | A dirty-state test: a DB with a 3-linked item, assert the count is reported and nothing is deleted without consent |
| **BP3** | A5: factor the new-item field assembly out of `save_item` / `save_item_if_needed` into one builder. This has drifted twice in one session. | `tests/test_item_editor_project_link.py::test_sweep1_1...` already asserts the two paths agree; add one asserting they produce identical rows for a fully-populated form |
| **BP4** | A4 + B2: delete `complete_and_create`, `RescheduleDialog`, and `reschedule_dialog.py`, plus the tests that exist only to cover them. Check `duplicate_action_item` afterwards — `complete_and_create` was its only caller, so it may become dead too. | The suite; plus a grep-based assertion that neither name returns |
| **BP5** | A3: give the Scheduler a count query instead of `len(get_unlinked_action_items(...))`, and a `limit` on the list path with the drop announced ("showing N of M", P9). | `tests/test_db_project_drag.py` — a real-scale fixture big enough that the cap bites |
| **BP6** | A2: decide `weekly_items.py`. Recommendation: **stop prefixing** — build the title from what the user typed. Lineage already comes from the APE and parent, and the prefix is a third-choice fallback. | `tests/test_weekly_items_title.py` — an item created from a legacy-shaped tactic gets an unprefixed title, and its lineage still resolves |

## Batch 3 — Infra

| ID | Work | Test |
|---|---|---|
| **BI1** | D1: replace the two per-OS release calls with one `publish` job (`needs: [build-windows, build-macos]`) that downloads both artifacts and makes a single release call. | `tests/test_ci_contract.py` — assert exactly one job calls `action-gh-release`, and it needs both builds |
| **BI2** | D3: split `requirements-dev.txt` out of `requirements.txt`, and delete the hardcoded `TEST_ONLY_PACKAGES` set in `tests/test_release_licensing.py` that exists to compensate. | That test, rewritten to read the two files |
| **BI3** | D4: `GoogleCalendarManager.__init__` must read its arguments before touching the filesystem — only create the directory when it is actually going to use the default paths, and use `paths.app_data_dir_path()` for consistency with the rest of the app. | A test constructing it with explicit paths and asserting `~/.getmoredone` is not created (no `Path.home()` monkeypatching needed afterwards) |

## Not in this plan

- **D5 (LICENSE)** — needs a lawyer. When the review is done I delete the draft
  warning header and `test_rm2a_license_carries_the_unreviewed_draft_warning`
  together, and not before.
- **D6 (refactor `item_editor.py` 1797 / `db_manager.py` 2142)** — its own batch
  after these three land. Bundling a large mechanical refactor of the files we
  just reworked with functional changes would make any regression hard to
  isolate, in an app whose UI coverage is thin.
- Everything under Feature Requests, Enhancements, User Stories — product work,
  not debt.

## Sequencing

Batch 1 → 2 → 3, each ending in `/csdp` (commit, sweep, document, push) so each
batch is reviewed on its own. BP3 lands before BP1/BP2 if I hit any friction —
the shared builder makes the linking change smaller.

## Completion standard

Each ID gets `done` / `partial` / `not done` with the file path or test name
proving it, in a status report at the end of each batch.
