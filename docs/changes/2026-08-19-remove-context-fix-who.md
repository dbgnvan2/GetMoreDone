# Handoff Note

- Date: 2026-08-19
- Agent: Code
- Topic: remove-context-fix-who

## Summary

**1. The Who field was dead — fixed.** Typing in Who did nothing at all.
`ItemEditorContactsMixin.on_who_search` opens with `if self.suggestions_hide_job:`,
and nothing ever initialised `suggestions_hide_job`,
`contact_suggestions_frame` or `selected_contact_id` — the mixin read state its
host dialog was silently expected to create. The first keystroke raised
`AttributeError` inside a Tk callback, which Tk prints to stderr and swallows, so
a hard failure presented as an inert widget. The same hole could break saving a
brand-new item, surfacing only as the editor's generic "Error: …" label. The three
attributes are now class-level defaults on the mixin that reads them.

**2. Context removed** — the editor box and the list-view column, per the scope
chosen: Title now holds and saves the whole stored title verbatim, and the
Context column is gone from Today, Upcoming, All Items, Completed and
Hierarchical. `split_action_item_title` is deliberately kept: list views still
show the short task body, and the Scheduler and item lineage derive
segment/subsegment colours from the title prefix.

No stored title changes. The round-trip is the risk this carried — showing only
the split body in Title while saving Title verbatim would truncate every prefixed
title on the next save — and it is covered by three tests.

## Files changed

- `src/getmoredone/screens/item_editor_contacts.py` — mixin state declared
- `src/getmoredone/screens/item_editor.py` — Context widgets removed; Title shows
  and saves the whole title; `_apply_record_type_ui` no longer touches Context
- `src/getmoredone/screens/item_editor_notes.py` — same title composition on the
  sub-item path
- `src/getmoredone/screens/{today,upcoming,all_items,completed,hierarchical}.py` —
  Context cell and header removed, remaining grid columns renumbered
- `src/getmoredone/screens/title_format.py` — `CONTEXT_COL_CHARS` and the
  `"context"` column budget removed; splitter kept with a note on why
- `tests/test_item_editor_contacts.py` (new, 7 tests)
- `tests/test_item_editor_no_context.py` (new, 12 tests)
- `tests/test_ui_presence.py` — screen contract inverted for Context
- `tests/test_vision_planning_regressions.py` — no context column budget
- `LEARNINGS.md`, `CHANGELOG.md`, `docs/USER_GUIDE.md`

## Verification

- Command: `venv/bin/python -m pytest -q`
- Result: PASS — 885 passed, 2 skipped, exit code 0
- Bug reproduced first, against a real dialog, before any fix: the traceback is in
  the LEARNINGS entry.
- Real widgets: editor rebuilt under the venv with a prefixed title and the Who
  dropdown driven open; screenshot confirms the dropdown lists the matching
  contact and Title carries the full `PW|LS|Blog - W8 - …` string.
- Real widgets: Today and All Items rendered against a seeded database — headers
  read Title / SubSegment / Category / Who / Start / Due / Pri / Time with no
  Context column, cells still line up under their headers, titles still display
  the short body, and SubSegment / Category are still derived from the prefix.

## Risks / Known gaps

- `weekly_items.py` still composes new titles as `<tactic context> - <title>`
  using `build_action_item_title`, so prefixed titles can still be *created*
  while no screen offers a Context field. Measured on the real path rather than
  assumed: with a **canonical** tactic title (`PW|LS|Blog - W34`) the splitter
  finds no context — there is nothing after the week number — so the new item is
  stored with exactly what the user typed, unprefixed. It only prefixes when the
  tactic's own title carries a body after the week number
  (`PW|LS|Blog - W34 - ship v2` → `PW|LS|Blog - W34 - draft the intro`), which is
  the legacy/hand-edited shape. Narrower than it first looked.
- Existing titles keep their prefixes. Nothing migrates them, and nothing needs
  to: list views still strip the prefix for display.
- The title prefix is the **third** source of lineage, not the first. Both
  `item_lineage.lineage_for_item` and the Scheduler's `_lineage_for_item` resolve
  in the order: the item's Annual Plan Element → the parent item's lineage (depth
  2) → the structured title prefix → the week action. Items created from a Weekly
  Tactic carry both an APE and a parent, so they never reach the prefix. Keeping
  `split_action_item_title` matters for items that have neither — the prefix is
  their only lineage — but the phrase "the Scheduler colours from the prefix"
  overstates it.
- The list views' grid columns were renumbered by script. Today and All Items were
  rendered and checked; Upcoming, Completed and Hierarchical were not opened —
  they share the same edit shape and the suite is green, but their alignment has
  not been seen.

## Next agent actions

- Restart GetMoreDone to pick this up.
- Consider whether `weekly_items.py` should stop prefixing new titles now that
  Context is not an editable concept.
