# Handoff Note

- Date: 2026-04-03
- Agent: Code
- Topic: Project Board UI Refresh (Pencil Icon & Content Display)

## Summary
- Updated the "pencil" edit icon on Project Boards to be a custom vertical graphic (yellow body, black pointy tip, red eraser).
- Expanded Project Board cards to show all "Next Step" text (bolded) and as much of the project "Notes" as possible.
- Increased default card height from 235px to 280px to accommodate expanded content.

## Files changed
- assets/icons/pencil_vertical.png (new icon)
- src/getmoredone/screens/project_boards.py (UI logic update)
- tests/test_project_boards_ui.py (test update)

## Verification
- Command: `./venv/bin/python -m pytest tests/test_project_boards_ui.py`
- Result: PASS

## Risks / Known gaps
- Large notes will be clipped if they exceed the new card height; user can still see them in the detail panel or edit dialog.

## Next agent actions
- None required.
