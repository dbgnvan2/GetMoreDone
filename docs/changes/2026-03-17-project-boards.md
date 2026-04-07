# Handoff Note

- Date: 2026-03-17
- Agent: Code
- Topic: project-boards

## Summary
Added a new Project Boards feature with persistent project cards linked to Annual Plan Elements and action items. The implementation includes schema/model support, database CRUD and linking methods, a new sidebar screen with square color-coded project cards, Add/Edit/Delete/Complete/Pending flows, pending/completed visibility filters, action-item-style Obsidian note create/link/open support, and a Create Action Item flow that seeds and links a task back to the selected board.

Adjusted the initial design to follow existing app patterns instead of board-specific ones:
- each APE now auto-creates exactly one Project Board
- Project Boards use `importance` for priority instead of a custom icon field
- Project Board notes use a proper link table and the same create/link note dialogs as action items
- opening the Project Board now backfills missing project items for older existing APEs
- the board now supports drag/drop note reordering, a draggable split pane, density controls, and shared note resizing from any note grip
- note gutters were tightened so more project notes fit across the board
- the board now uses a top-panel size slider to resize all notes together, and note titles use a smaller regular-weight font

## Files changed
- src/getmoredone/models.py
- src/getmoredone/database.py
- src/getmoredone/db_manager.py
- src/getmoredone/app.py
- src/getmoredone/screens/project_boards.py
- tests/test_database.py
- docs/changes/2026-03-17-project-boards.md

## Verification
- Command: `python3 -m py_compile src/getmoredone/models.py src/getmoredone/database.py src/getmoredone/db_manager.py src/getmoredone/app.py src/getmoredone/screens/project_boards.py`
- Result: PASS
- Command: `pytest -q tests/test_database.py -q`
- Result: PASS
- Command: `python3 -m py_compile src/getmoredone/screens/project_boards.py`
- Result: PASS
- Command: `pytest -q tests/test_database.py -q`
- Result: PASS
- Command: `python3 -m py_compile src/getmoredone/models.py src/getmoredone/database.py src/getmoredone/db_manager.py src/getmoredone/vps_manager.py src/getmoredone/screens/item_editor.py src/getmoredone/screens/project_boards.py tests/test_database.py`
- Result: PASS
- Command: `pytest -q tests/test_database.py tests/test_vps_hub_crud.py -q`
- Result: PASS
- Command: `python3 -m py_compile src/getmoredone/screens/project_boards.py`
- Result: PASS
- Command: `pytest -q tests/test_database.py -q`
- Result: PASS

## Risks / Known gaps
- Project board task linking is currently driven by creating a new action item from the board or unlinking an existing linked task in the board view; there is not yet a picker to attach arbitrary existing items from elsewhere.
- UI behavior was verified by compile/tests, but not by an automated screen test.
- Shared note sizing is session-scoped UI state; it is not yet persisted as a saved user preference.

## Next agent actions
- Add user-facing docs for the new Project Boards screen and sidebar entry.
- Decide whether project boards need multiple Obsidian links or a generic attachments model.
- If desired, extend the board UI with drag/drop linking of existing action items onto a project card.
