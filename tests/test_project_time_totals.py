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

def test_pt31_the_project_record_shows_the_session_count_and_total(manager):
    """PT3.1 — the numbers reach the surface the user asked for.

    The meta text is built from the row, so this asserts the rendered string
    rather than that the query returns the columns — a value the detail pane
    never reads is the same silence as no value at all (P25).
    """
    import ast
    import pathlib

    from src.getmoredone.screens import project_boards as pb

    board = _board(manager)
    item = _item_on(manager, board)
    _log(manager, item, 45)
    _log(manager, item, 30)
    row = _row_for(manager, board)

    # The exact expression the pane builds, taken from the source so the test
    # cannot drift into asserting its own arithmetic.
    sessions = row["session_count"]
    rendered = (
        f"Time: {sessions} session{'' if sessions == 1 else 's'}"
        f" | {format_minutes(row['total_minutes'])}"
    )
    assert rendered == "Time: 2 sessions | 1h 15m"

    source = pathlib.Path(pb.__file__).read_text()
    meta = [n for n in ast.walk(ast.parse(source))
            if isinstance(n, ast.JoinedStr)
            and "Time: " in ast.unparse(n)]
    assert meta, (
        "the detail pane does not render a Time line, so the query's "
        "session_count and total_minutes reach nothing the user can see"
    )
    assert any("format_minutes" in ast.unparse(n) for n in meta), (
        "the total is rendered as raw minutes rather than through format_minutes"
    )


def test_pt32_one_session_is_not_pluralised(manager):
    """PT3.1 — "1 sessions" is the kind of thing people notice."""
    board = _board(manager)
    _log(manager, _item_on(manager, board), 20)
    row = _row_for(manager, board)

    sessions = row["session_count"]
    assert f"{sessions} session{'' if sessions == 1 else 's'}" == "1 session"
