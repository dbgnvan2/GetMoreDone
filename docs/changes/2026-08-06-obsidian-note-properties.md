# Handoff Note

- Date: 2026-08-06
- Agent: Code
- Topic: obsidian-note-properties (Notes-table "Create Note" export frontmatter)

## Summary
The "Create Note" export under the Notes table now writes an Obsidian note whose
frontmatter contains **only** the requested properties, in this order:

```
Prev / Next / tags / title / entity_id / created / Summary
```

Before, `create_obsidian_note` wrote `type`, `entity_id`, `title`, `created`,
`PREV`, `NEXT`, `TAG`, `Summary`, plus `who` / `due_date` / `priority_score` for
action items. Changes:

- Frontmatter is now exactly the 7 properties above. `type`, `who`, `due_date`,
  `priority_score` removed; `PREV`/`NEXT`/`TAG` renamed to `Prev`/`Next`/`tags`
  (lower/camel case per the spec image); `Prev`/`Next`/`tags` written empty,
  `Summary` empty, `title`/`entity_id`/`created` populated.
- `create_obsidian_note` signature slimmed: removed now-unused `entity_type`,
  `who`, `due_date`, `priority_score` params (they only fed removed fields).
- Caller `CreateNoteDialog.create_note` no longer gathers/passes that metadata.
- Side effect (improvement): the note-search `tag:` prefix reads `tags:` from
  frontmatter; the old writer emitted `TAG:`, which never matched. Producer and
  consumer are now aligned (P19).

## Files changed
- src/getmoredone/obsidian_utils.py                        (frontmatter + signature)
- src/getmoredone/screens/item_editor_note_dialogs.py      (drop dead metadata gathering + args)
- tests/test_obsidian_integration.py                       (updated calls + assertions; new property-set guard)
- tests/test_project_notes.py                              (drop entity_type from calls/asserts)

## Verification
- Command: `pytest -q`  → PASS (425 passed, 1 skipped)
- Command: `pytest tests/test_obsidian_integration.py tests/test_project_notes.py tests/test_note_search.py -v` → PASS (66)
- Real dialog end-to-end: drove `CreateNoteDialog.create_note()` (action_item)
  against a temp vault + temp DB — wrote a note with exactly the 7 properties in
  order, no legacy keys, and created the `obsidian_note` DB link.
- Sample output frontmatter:
  `---\nPrev:\nNext:\ntags:\ntitle: "..."\nentity_id: ...\ncreated: YYYY-MM-DD HH:MM\nSummary:\n---`

## Risks / Known gaps
- Prev/Next/tags are written empty (bare `key:`), matching how Obsidian
  serialises empty List/Tags properties. They render as List/Tags in a vault
  where those types are registered (as in the spec image). In a brand-new vault
  with no type registry, an empty property defaults to Text until its type is
  set once. If guaranteed List typing in fresh vaults is needed, emit `[]`.
- Pre-existing: `title: "{title}"` is not YAML-escaped; a title containing a
  double quote would break the frontmatter. Out of scope for this change.

## Next agent actions
- None required. If Docs Agent documents note format anywhere, use the 7-property list.
