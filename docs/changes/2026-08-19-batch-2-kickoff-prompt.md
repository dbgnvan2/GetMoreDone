# Batch 2 kickoff prompt

Paste the block below into a fresh conversation.

---

Start Batch 2 of the backlog clearance in `~/ProjectsLocal/GetMoreDone`.

**State:** on `main`, everything pushed (HEAD `56702cd`), suite green at 960
passed / 2 skipped. The only untracked file is `visact_rebrand_prompt.md` —
not mine, leave it alone. Another Claude session also commits to `main` in this
repo, so pull before you start and expect commits you didn't write.

**The plan:** `docs/implementation_plan_2026-08-19_backlog_clearance.md`. Batch 1
is done and ticked off. Batch 2 is six items, BP1–BP6, listed there. Read that
file first, plus `docs/changes/2026-08-19-backlog-batch-1.md` for what Batch 1
actually found.

**Decisions already taken — don't re-open them:**
- An Action Item belongs to **exactly one Project**. BP1 makes the Projects
  screen's "link existing items" dialog exclusive, matching the Scheduler and
  the item editor.
- `complete_and_create` and `RescheduleDialog` get **deleted**, not wired (BP4).
- BP6's recommendation is to stop `weekly_items.py` prefixing new titles, but
  confirm that one with me before doing it — it changes what titles get created.

**Order:** do BP3 first (factor the new-item field assembly out of `save_item` /
`save_item_if_needed`). Those two paths drifted twice in one session — the
project link, then the Annual Plan Element ordering — and BP1/BP2 touch the same
area, so the shared builder makes the rest smaller.

**BP2 is the one with teeth.** Existing items can already sit on several project
boards. Making linking exclusive must not silently delete those links: report the
count, and keep the editor's `(+N more)` label and its confirmation dialog as the
visible path until the count is zero. A dirty-state test with a 3-linked item is
required.

## Things a fresh context will get wrong

- **Never construct a production object with default arguments in a test.**
  `DatabaseManager()` with no path opens the user's real database and runs
  migrations on it; `AppSettings.load()/.save()` writes the real settings file.
  `conftest.py` now redirects both and fingerprints the real files — if a run
  ends with `GUARD:` in the output, a test escaped the isolation. Pass
  `tmp_path` explicitly.
- **Two module identities.** The repo supports both `import getmoredone.x` and
  `import src.getmoredone.x`, and Python loads those as *different* modules with
  different class objects. Patching one does not patch the other. Prefer
  `src.getmoredone.*` in tests.
- **CustomTkinter hangs** when a full screen is built after other tests in the
  same interpreter have created and destroyed CTk roots. Dialogs are fine;
  screens are not. See `tests/render_list_screen.py` for the subprocess pattern
  used to get around it.
- **A test that returns a value is a test that does not assert.** pytest ignores
  the return; `PytestReturnNotNoneWarning` is currently at 0 and should stay
  there.
- The running app serves code from memory — restart GetMoreDone to see any
  change, and don't conclude an edit didn't work until you have.

## How to finish

Finish with `/csdp`. Expect the sweep to find real things: on Batch 1 it found
9, then 8 on the fixes, then 11 on those — each pass found a defect inside the
previous pass's fix. Two passes is the working minimum; fix every finding with a
test, and prove each test fails without its fix.

`LEARNINGS.md` and `BACKLOG.md` are both current. Don't touch `LICENSE` (needs a
lawyer) or refactor `item_editor.py` / `db_manager.py` (its own batch, later).
