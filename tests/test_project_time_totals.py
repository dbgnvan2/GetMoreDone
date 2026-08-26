"""Session count and total time on the Project record.

Purpose: PT1-PT3 — how many timer sessions a project has absorbed and how long
         they came to. Both derived from work_logs rather than stored, because a
         counter column is a status field that can disagree with the rows it
         summarises (P6).
Spec:    docs/implementation_plan_2026-08-25_project_time_totals.md#acceptance-criteria
Tests:   this file

ProjectBoard.savor_count is a different quantity — completed deliverables, used
only to pick the reward phase — and carries no time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, ProjectBoard, WorkLog
from src.getmoredone.utils.duration import format_minutes


@pytest.fixture
def manager(tmp_path):
    db = DatabaseManager(str(tmp_path / "project_time.db"))
    yield db
    db.close()


def _board(manager, title="Website Rebuild"):
    board = ProjectBoard(title=title)
    manager.create_project_board(board)
    return board


def _item_on(manager, board, title="A task", status="open"):
    item = ActionItem(who="Self", title=title, status=status)
    manager.create_action_item(item)
    manager.link_action_item_to_project_board(board.id, item.id)
    return item


def _log(manager, item, minutes):
    started = datetime.now() - timedelta(minutes=minutes)
    manager.create_work_log(WorkLog(
        item_id=item.id,
        started_at=started.isoformat(),
        ended_at=datetime.now().isoformat(),
        minutes=minutes,
    ))


def _row_for(manager, board):
    rows = manager.get_project_boards()
    return next(r for r in rows if r["id"] == board.id)


# --- PT1 : the numbers ------------------------------------------------------

def test_pt11_a_board_reports_its_sessions_and_minutes(manager):
    """PT1.1 — the two values the Project record needs, per board."""
    board = _board(manager)
    item = _item_on(manager, board)
    _log(manager, item, 25)
    _log(manager, item, 50)

    row = _row_for(manager, board)
    assert row["session_count"] == 2
    assert row["total_minutes"] == 75


def test_pt12_a_board_with_no_sessions_reports_zero(manager):
    """PT1.2 — zero, never NULL, or the UI has to guess what None means."""
    board = _board(manager)
    _item_on(manager, board)

    row = _row_for(manager, board)
    assert row["session_count"] == 0
    assert row["total_minutes"] == 0, (
        "SUM over no rows is NULL in SQL; the COALESCE is what makes this 0"
    )


def test_pt13_only_this_boards_items_count(manager):
    """PT1.3 — a project's total is its own work, not everyone's."""
    mine = _board(manager, "Website Rebuild")
    theirs = _board(manager, "Something Else")
    _log(manager, _item_on(manager, mine), 30)
    _log(manager, _item_on(manager, theirs, title="Their task"), 90)

    mine_row, theirs_row = _row_for(manager, mine), _row_for(manager, theirs)
    # Both columns: asserting only the minutes left the count's board filter
    # uncovered, and dropping it kept every test green.
    assert (mine_row["session_count"], mine_row["total_minutes"]) == (1, 30)
    assert (theirs_row["session_count"], theirs_row["total_minutes"]) == (1, 90)


def test_pt14_the_existing_counts_survive_multiple_sessions_per_item(manager):
    """PT1.4 — the trap this feature could have set, and the reason for
    subqueries instead of another JOIN.

    get_project_boards is grouped per board and already joins
    project_board_items and action_items. A LEFT JOIN on work_logs would give
    one row per session per item: COUNT(DISTINCT pbi.item_id) survives it, but
    the two SUM(CASE WHEN ai.status ...) counts do not — an open item with
    three sessions would be counted three times, on numbers already on screen.

    One session per item hides it completely, so this uses three.
    """
    board = _board(manager)
    busy = _item_on(manager, board, title="Open, worked on three times")
    for minutes in (25, 25, 10):
        _log(manager, busy, minutes)
    done = _item_on(manager, board, title="Finished", status="completed")
    _log(manager, done, 40)

    row = _row_for(manager, board)
    assert row["linked_item_count"] == 2
    assert row["open_item_count"] == 1, (
        f"the open-item count was inflated to {row['open_item_count']} by the "
        "sessions logged against it"
    )
    assert row["completed_item_count"] == 1
    assert row["session_count"] == 4
    assert row["total_minutes"] == 100


def test_pt15_completed_items_and_follow_ups_still_count(manager):
    """PT1.5 — time spent does not stop counting when the task closes.

    A follow-up inherits its project link, so work continued across days
    accumulates against the project it belongs to rather than vanishing.
    """
    board = _board(manager)
    original = _item_on(manager, board, title="Draft the report")
    _log(manager, original, 45)

    follow_up_id = manager.create_followup_item(original.id)
    assert follow_up_id, "precondition: the follow-up was created"
    assert board.id in manager.get_project_board_ids_for_item(follow_up_id), (
        "precondition: the follow-up inherited the project link"
    )
    _log(manager, manager.get_action_item(follow_up_id), 30)

    manager.complete_action_item(original.id)

    row = _row_for(manager, board)
    assert row["session_count"] == 2
    assert row["total_minutes"] == 75, (
        "closing the task or continuing it elsewhere lost the time it took"
    )


# --- PT2 : how it reads -----------------------------------------------------

@pytest.mark.parametrize("minutes,expected", [
    (None, "0m"),
    (0, "0m"),
    (45, "45m"),
    (60, "1h"),
    (120, "2h"),
    (75, "1h 15m"),
    (750, "12h 30m"),
])
def test_pt21_minutes_render_the_way_a_person_reads_them(minutes, expected):
    """PT2.1 — 750 is not a number anyone reads as twelve and a half hours."""
    assert format_minutes(minutes) == expected


# --- PT3 : on the Project record --------------------------------------------

def test_pt31_the_time_line_renders_the_boards_own_numbers(manager):
    """PT3.1 — the pane's own function, on a real row from the real query.

    The first version of this rebuilt the pane's f-string inside the test and
    asserted against its own arithmetic. Mutation-proved worthless: inverting
    the pluralisation in production, and rendering linked_item_count instead of
    total_minutes, both left all fourteen tests green (P27).
    """
    from src.getmoredone.screens.project_boards import project_time_line

    board = _board(manager)
    item = _item_on(manager, board)
    _log(manager, item, 45)
    _log(manager, item, 30)

    assert project_time_line(_row_for(manager, board)) == "Time: 2 sessions | 1h 15m"


def test_pt32_one_session_is_not_pluralised(manager):
    """PT3.1 — "1 sessions" is the kind of thing people notice."""
    from src.getmoredone.screens.project_boards import project_time_line

    board = _board(manager)
    _log(manager, _item_on(manager, board), 20)

    assert project_time_line(_row_for(manager, board)) == "Time: 1 session | 20m"


def test_pt33_absent_numbers_render_no_line_rather_than_zero(manager):
    """PT3.1 — absent is not zero.

    The detail pane has a fallback that fetches a board with SELECT *, which
    has neither aggregate. Rendering "0 sessions | 0m" there asserted a number
    the row could not support, on the one line of that pane that claims a real
    figure while every other field degrades to blank (P6).
    """
    from src.getmoredone.screens.project_boards import project_time_line

    board = _board(manager)
    _log(manager, _item_on(manager, board), 60)

    bare = dict(manager.db.conn.execute(
        "SELECT * FROM project_boards WHERE id = ?", (board.id,)).fetchone())
    assert "session_count" not in bare, "precondition: the fallback row lacks them"
    assert project_time_line(bare) is None, (
        "a row with no aggregates rendered a number anyway"
    )

    # And the fallback fills them in, so the line does not simply vanish.
    bare.update(manager.get_project_time_totals(board.id))
    assert project_time_line(bare) == "Time: 1 session | 1h"


def test_pt34_the_detail_pane_uses_that_function(manager):
    """PT3.1 — a line nothing renders is the same as no line (P25).

    Parsed, not grepped: the call has to be on the renderer's path, and a
    substring search would match the import or a comment.
    """
    import ast
    import pathlib

    from src.getmoredone.screens import project_boards as pb

    tree = ast.parse(pathlib.Path(pb.__file__).read_text())
    render = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_render_detail")
    called = {n.func.id for n in ast.walk(render)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "project_time_line" in called, (
        "_render_detail does not build the Time line, so the query's "
        "session_count and total_minutes reach nothing the user can see"
    )


def test_pt41_the_single_board_totals_agree_with_the_grouped_query(manager):
    """PT1 — two ways to compute one quantity is how they drift (P5)."""
    board = _board(manager)
    busy = _item_on(manager, board, title="Worked on repeatedly")
    for minutes in (25, 25, 10):
        _log(manager, busy, minutes)
    _log(manager, _item_on(manager, board, title="Second task"), 40)

    grouped = _row_for(manager, board)
    single = manager.get_project_time_totals(board.id)

    assert single == {"session_count": grouped["session_count"],
                      "total_minutes": grouped["total_minutes"]}
    assert single == {"session_count": 4, "total_minutes": 100}


def test_pt35_the_fallback_path_asks_for_the_totals(manager):
    """PT3.1 — pt33 proves the helper works, not that the pane calls it.

    Deleting the fallback's `row.update(get_project_time_totals(...))` left
    every test green: the Time line simply vanished on that path, silently.
    """
    import ast
    import pathlib

    from src.getmoredone.screens import project_boards as pb

    tree = ast.parse(pathlib.Path(pb.__file__).read_text())
    render = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == "_render_detail")
    called = {n.func.attr for n in ast.walk(render)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "get_project_time_totals" in called, (
        "the direct-fetch fallback does not ask for the aggregates, so the "
        "Time line disappears whenever a board is shown from that path"
    )
