# Handoff Note: Project Drag-and-Drop Scheduling

**Date:** 2026-04-03
**Topic:** Project Drag-and-Drop in Scheduler

## Description
Added a new "Projects" tab to the `DragScheduleScreen` (Scheduler) to allow organizing action items by project via drag-and-drop.

## Key Changes
- **Database/Logic:**
    - Added `link_item_to_project_exclusive(board_id, item_id)` to `DBManagerProjectBoardsMixin`.
    - This method ensures an action item is linked to *exactly one* project board (clears previous project links) and synchronizes the item's `annual_plan_element_id` with the project's APE.
- **UI (DragScheduleScreen):**
    - Added a 3rd tab "Projects" to the right-hand panel.
    - Implemented `build_project_boxes` to render active projects as wide rows, consistent with date boxes.
    - Added a special "Unlinked (No Project)" box at the top of the project list to filter for unlinked items and serve as a drop target for unlinking items.
    - Added a "Sort Projects by" dropdown to the Projects tab to sort the list by Title, Subsegment, or Category.
    - Project row height is 50% larger than date boxes for better readability.
    - Improved vertical centering in both Project boxes and Date boxes using grid row weights and refined sticky/padding settings.
    - The main "Refresh" button now correctly clears both date and project filters.
    - Project boxes show the project title, lineage (Segment | SubSegment | Category), and open item counts.
    - Clicking a project box filters the "Action Items" list to show items already linked to that project.
    - Dragging an action item onto a project box links the item to that project and refreshes the view.
    - Hover effects and selection styling are consistent with the date-based scheduling view.

## Verification Results
- Ran `pytest tests/test_drag_schedule_support.py`: **PASSED**
- Created and ran `tests/test_project_drag_linking.py` to verify exclusive linking and APE synchronization: **PASSED** (Test file removed after verification).
