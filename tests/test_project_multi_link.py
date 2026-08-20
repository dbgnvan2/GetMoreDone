"""BP1/BP2 — an Action Item belongs to exactly one Project.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#bp1

The Projects screen's "link existing items" dialog was the last additive
surface. Making it exclusive means it can now *delete* links, so the tests here
are as much about what must **not** happen without consent as about the link
that is written (P2 — never silently drop).

The dialog methods are driven with SimpleNamespace stubs against a **real**
DatabaseManager, the pattern used by tests/test_item_editor_project_link.py, so
a control that renders but never reaches the database fails here (P25).
"""

from types import SimpleNamespace

import pytest

import src.getmoredone.screens.project_boards as pb
from src.getmoredone.models import ProjectBoard
from src.getmoredone.screens.project_boards import LinkProjectActionItemsDialog
from src.getmoredone.screens.project_link_notice import (
    describe_bulk_relink,
    describe_outstanding_multi_links,
    describe_single_relink,
)
from tests.weekly_tactic_fixtures import make_daily_item, make_vps, seed_ape


def _dialog_stub(manager, board_id, checked=()):
    """Enough of LinkProjectActionItemsDialog to drive its link methods."""
    stub = SimpleNamespace(
        db_manager=manager,
        board_id=board_id,
        checked_items=set(checked),
        on_linked=None,
        refreshed=0,
    )
    stub.refresh_results = lambda: setattr(stub, "refreshed", stub.refreshed + 1)
    for name in ("_link", "_link_selected_items", "_confirm_relink"):
        method = getattr(LinkProjectActionItemsDialog, name)
        setattr(stub, name, (lambda m: lambda *a, **kw: m(stub, *a, **kw))(method))
    return stub


def _board(manager, title, ape_id=None):
    board = ProjectBoard(title=title, annual_plan_element_id=ape_id)
    manager.create_project_board(board)
    return board


@pytest.fixture
def answers(monkeypatch):
    """Capture (and script) every messagebox.askyesno the dialog raises."""
    seen = {"messages": [], "reply": True}

    def _ask(title, message, **kwargs):
        seen["messages"].append(message)
        return seen["reply"]

    monkeypatch.setattr(pb.messagebox, "askyesno", _ask)
    return seen


# ----------------------------------------------------------------- BP1


def test_bp1_linking_moves_an_item_between_boards(tmp_path, answers):
    """Linking an item already on another board moves it rather than adding."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        _dialog_stub(manager, new.id)._link(item.id)

        assert manager.get_project_board_ids_for_item(item.id) == [new.id], (
            "the Projects dialog is still additive — the item is on two boards")
    finally:
        vps.close()


def test_bp1_linking_an_unfiled_item_asks_nothing(tmp_path, answers):
    """The ordinary case must not be interrupted by a confirmation."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")

        _dialog_stub(manager, board.id)._link(item.id)

        assert answers["messages"] == []
        assert manager.get_project_board_ids_for_item(item.id) == [board.id]
    finally:
        vps.close()


def test_bp1_relinking_to_the_same_board_asks_nothing(tmp_path, answers):
    """An item already on this board loses nothing, so nothing is asked."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        _dialog_stub(manager, board.id)._link(item.id)

        assert answers["messages"] == []
        assert manager.get_project_board_ids_for_item(item.id) == [board.id]
    finally:
        vps.close()


def test_bp1_declining_the_confirmation_changes_nothing(tmp_path, answers):
    """"No" must leave every existing link exactly where it was."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        answers["reply"] = False
        stub = _dialog_stub(manager, new.id)
        stub._link(item.id)

        assert manager.get_project_board_ids_for_item(item.id) == [old.id]
        assert answers["messages"], "the item was unfiled without being asked about"
        message = answers["messages"][0]
        assert "New Project" in message
        # The ordinary case: exactly one existing link. The plural form reads
        # "filed under 1 projects ... removes it from the other 0", which says
        # nothing is at stake when a link is about to be deleted.
        assert "1 projects" not in message, message
        assert "the other 0" not in message, message
        assert "already filed under another project" in message, message
    finally:
        vps.close()


def test_bp1_bulk_link_asks_once_before_dropping_links(tmp_path, answers):
    """One question for the batch, naming only the items that would lose a link."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        filed = [make_daily_item(vps, f"Filed {i}") for i in range(2)]
        unfiled = make_daily_item(vps, "Unfiled")
        for item in filed:
            manager.link_item_to_project_exclusive(old.id, item.id)

        selected = [item.id for item in filed] + [unfiled.id]
        _dialog_stub(manager, new.id, checked=selected)._link_selected_items()

        assert len(answers["messages"]) == 1, "one question per batch, not per item"
        assert "2 selected items are" in answers["messages"][0], answers["messages"][0]
        for item_id in selected:
            assert manager.get_project_board_ids_for_item(item_id) == [new.id]
    finally:
        vps.close()


def test_bp1_declining_the_bulk_confirmation_links_nothing(tmp_path, answers):
    """"No" on the batch must not link the items that had nothing to lose either.

    Half-applying a batch the user declined is worse than doing nothing: the
    selection is gone and only some of it landed.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        filed = make_daily_item(vps, "Filed")
        unfiled = make_daily_item(vps, "Unfiled")
        manager.link_item_to_project_exclusive(old.id, filed.id)

        answers["reply"] = False
        stub = _dialog_stub(manager, new.id, checked=[filed.id, unfiled.id])
        stub._link_selected_items()

        assert manager.get_project_board_ids_for_item(filed.id) == [old.id]
        assert manager.get_project_board_ids_for_item(unfiled.id) == []
        assert stub.checked_items == {filed.id, unfiled.id}, "the selection was consumed"
    finally:
        vps.close()


def test_bp1_bulk_link_of_unfiled_items_asks_nothing(tmp_path, answers):
    """The ordinary bulk case: nothing to lose, no interruption."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        items = [make_daily_item(vps, f"Task {i}") for i in range(3)]

        stub = _dialog_stub(manager, board.id, checked=[i.id for i in items])
        stub._link_selected_items()

        assert answers["messages"] == []
        assert stub.checked_items == set()
        for item in items:
            assert manager.get_project_board_ids_for_item(item.id) == [board.id]
    finally:
        vps.close()


# ----------------------------------------------------------------- BP2


def _three_linked(vps):
    """A database in the pre-exclusive state: one item on three boards."""
    manager = vps.db_manager
    ape_id = seed_ape(vps)
    boards = [_board(manager, f"Board {i}", ape_id) for i in range(3)]
    item = make_daily_item(vps, "Legacy multi-filed task")
    for board in boards:
        manager.link_action_item_to_project_board(board.id, item.id)
    return manager, item, boards


def test_bp2_the_count_finds_a_three_linked_item(tmp_path):
    """Dirty state (P8): a database written before filing became exclusive."""
    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)

        assert len(manager.get_items_on_multiple_project_boards()) == 1
        reported = manager.get_items_on_multiple_project_boards()
        assert [(row["id"], row["board_count"]) for row in reported] == [(item.id, 3)]

        # Reporting is read-only: nothing was resolved behind the user's back.
        assert sorted(manager.get_project_board_ids_for_item(item.id)) == sorted(
            b.id for b in boards)
    finally:
        vps.close()


def test_bp2_singly_filed_items_are_not_reported(tmp_path):
    """A count that also counts the healthy rows tells nobody anything."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        filed = make_daily_item(vps, "Filed")
        make_daily_item(vps, "Unfiled")
        manager.link_item_to_project_exclusive(board.id, filed.id)

        assert len(manager.get_items_on_multiple_project_boards()) == 0
        assert manager.get_items_on_multiple_project_boards() == []
        assert describe_outstanding_multi_links(0) == ""
    finally:
        vps.close()


def test_bp2_the_projects_screen_reports_the_outstanding_count(tmp_path):
    """The count reaches a label, not only a log line (P25)."""
    vps = make_vps(tmp_path)
    try:
        manager, item, _ = _three_linked(vps)

        texts = []
        stub = SimpleNamespace(
            db_manager=manager,
            multi_link_label=SimpleNamespace(
                configure=lambda **kw: texts.append(kw.get("text"))),
        )
        pb.ProjectBoardsScreen._refresh_multi_link_notice(stub)

        assert texts and "1 action item is" in texts[0], texts
        assert "more than one project" in texts[0]
    finally:
        vps.close()


def test_bp2_the_editor_stays_the_visible_path_until_the_count_is_zero(tmp_path, answers):
    """Resolving a 3-linked item happens through the editor's confirmation.

    Nothing deletes those links on its own — the item is re-filed when the
    user picks a project for it, and the count falls to zero only then.
    """
    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)
        assert len(manager.get_items_on_multiple_project_boards()) == 1

        # Declining leaves all three links in place.
        answers["reply"] = False
        _dialog_stub(manager, boards[0].id)._link(item.id)
        assert len(manager.get_items_on_multiple_project_boards()) == 1
        assert len(manager.get_project_board_ids_for_item(item.id)) == 3

        # Accepting resolves this item, and only this item.
        answers["reply"] = True
        _dialog_stub(manager, boards[0].id)._link(item.id)
        assert manager.get_project_board_ids_for_item(item.id) == [boards[0].id]
        assert len(manager.get_items_on_multiple_project_boards()) == 0
    finally:
        vps.close()


def test_bp2_the_confirmation_names_what_is_being_lost(tmp_path, answers):
    """A 3-linked item's confirmation says three, not "some"."""
    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)

        answers["reply"] = False
        _dialog_stub(manager, boards[0].id)._link(item.id)

        message = answers["messages"][0]
        assert "filed under 3 projects" in message, message
        assert "Board 0" in message
        assert "the other 2 projects" in message, message
    finally:
        vps.close()


# ----------------------------------------------------- shared wording


def test_bp1_every_surface_uses_the_same_sentence():
    """The editor and the Projects dialog must not word this differently."""
    single = describe_single_relink(3, "Website Rebuild")
    assert "filed under 3 projects" in single
    assert "Website Rebuild" in single
    assert "the other 2 projects" in single

    cleared = describe_single_relink(2, None)
    assert "Clearing the project removes all of them" in cleared

    # One existing link is the Projects screen's ordinary case, and the plural
    # form got it wrong in both halves of the sentence.
    one = describe_single_relink(1, "Website Rebuild")
    assert "already filed under another project" in one
    assert "removes that link" in one
    assert "1 projects" not in one and "the other 0" not in one
    assert "removes that link" in describe_single_relink(1, None)

    # Two projects means one *other* project, not "1 projects".
    two = describe_single_relink(2, "Website Rebuild")
    assert "the other 1 project." in two, two

    assert "1 selected item is" in describe_bulk_relink(1, "Website Rebuild")
    assert "4 selected items are" in describe_bulk_relink(4, None)
    assert "this project" in describe_bulk_relink(4, None)


# ------------------------------------------------- the real dialog


def test_bp1_the_real_dialog_moves_an_item_and_says_so(tmp_path, monkeypatch, answers):
    """Build the actual Toplevel, not a stub of it.

    The stub tests above all passed while the confirmation read "This item is
    filed under 1 projects ... removes it from the other 0" — they asserted the
    target board's name was present and never read the rest of the sentence.
    Driving the real dialog is what showed it (P25: test the surface the user
    touches, and read what it actually says).
    """
    import customtkinter as ctk
    from src.getmoredone.models import ActionItem

    # grab_set() makes a modal window that a headless run never releases.
    monkeypatch.setattr(LinkProjectActionItemsDialog, "grab_set", lambda self: None)

    vps = make_vps(tmp_path)
    root = ctk.CTk()
    root.withdraw()
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        item = ActionItem(who="Self", title="Movable task")
        manager.create_action_item(item, apply_defaults=False)
        manager.link_action_item_to_project_board(old.id, item.id)

        dialog = LinkProjectActionItemsDialog(root, manager, new.id, on_linked=lambda: None)
        try:
            assert len(dialog.results.winfo_children()) == 1, "the item is not listed"
            dialog._link(item.id)
        finally:
            dialog.destroy()

        assert manager.get_project_board_ids_for_item(item.id) == [new.id]
        message = answers["messages"][0]
        assert "New Project" in message
        assert "1 projects" not in message, message
        assert "the other 0" not in message, message
    finally:
        root.destroy()
        vps.close()


# --------------------------------------------------- sweep findings


def test_f1_dragging_onto_a_project_asks_before_unfiling(tmp_path, answers):
    """The Scheduler deleted links with no confirmation while this dialog asked.

    Sweep F1: BP1's own docstring justified itself with "the Scheduler already
    relinks exclusively", which was true of the link and false of the consent
    (P5 — the sibling call was not hardened).
    """
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        stub = SimpleNamespace(db_manager=manager, drag_items=[item], refreshed=0)
        stub.refresh = lambda: setattr(stub, "refreshed", stub.refreshed + 1)

        answers["reply"] = False
        ds.DragScheduleScreen._drop_onto_project(stub, new.id)
        assert manager.get_project_board_ids_for_item(item.id) == [old.id], (
            "the drag unfiled the item after the user said no")
        assert answers["messages"], "the drag deleted a link without asking"

        answers["reply"] = True
        ds.DragScheduleScreen._drop_onto_project(stub, new.id)
        assert manager.get_project_board_ids_for_item(item.id) == [new.id]
    finally:
        vps.close()


def test_f1_dragging_an_unfiled_item_asks_nothing(tmp_path, answers):
    """The Scheduler's ordinary gesture — filing loose work — is not interrupted."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        items = [make_daily_item(vps, f"Task {i}") for i in range(3)]

        stub = SimpleNamespace(db_manager=manager, drag_items=items)
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, board.id)

        assert answers["messages"] == []
        for item in items:
            assert manager.get_project_board_ids_for_item(item.id) == [board.id]
    finally:
        vps.close()


def test_f1_dropping_onto_no_project_asks_before_clearing_the_ape(tmp_path, answers):
    """The worse of the two drops: it also nulls the Annual Plan Element."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id

        stub = SimpleNamespace(db_manager=manager, drag_items=[item])
        stub.refresh = lambda: None

        answers["reply"] = False
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")
        assert manager.get_project_board_ids_for_item(item.id) == [board.id]
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id
        assert "Annual Plan Element" in answers["messages"][0], answers["messages"][0]

        answers["reply"] = True
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")
        assert manager.get_project_board_ids_for_item(item.id) == []
        assert manager.get_action_item(item.id).annual_plan_element_id is None
    finally:
        vps.close()


def test_f4_the_banner_names_the_items_not_only_the_count(tmp_path):
    """A number with no way to find what it refers to is not actionable.

    Sweep F4: ``get_items_on_multiple_project_boards`` had no caller in src/ —
    the same "built but not wired" class this batch deletes elsewhere (P21).
    """
    vps = make_vps(tmp_path)
    try:
        manager, item, _ = _three_linked(vps)

        texts = []
        stub = SimpleNamespace(
            db_manager=manager,
            multi_link_label=SimpleNamespace(
                configure=lambda **kw: texts.append(kw.get("text"))),
        )
        pb.ProjectBoardsScreen._refresh_multi_link_notice(stub)

        assert "Legacy multi-filed task" in texts[0], texts[0]
        assert "3 projects" in texts[0], texts[0]
    finally:
        vps.close()


def test_f4_the_banner_caps_the_names_and_says_how_many_it_left_out(tmp_path):
    """Naming 200 items in a header label is its own failure (P9)."""
    from src.getmoredone.screens.project_link_notice import MULTI_LINK_NAMES_SHOWN

    rows = [{"id": str(i), "title": f"Item {i}", "board_count": 2} for i in range(12)]
    text = describe_outstanding_multi_links(len(rows), rows)

    assert text.count("Item ") == MULTI_LINK_NAMES_SHOWN
    assert f"and {12 - MULTI_LINK_NAMES_SHOWN} more" in text, text


def test_f5_a_failed_bulk_link_moves_nothing(tmp_path, monkeypatch, answers):
    """Half a batch applied is worse than none: the selection is gone either way.

    Sweep F5. Each exclusive link opened its own transaction, so a failure on
    item three left the first two moved off their old boards and the exception
    escaping a Tk callback, where this repo has already lost one.
    """
    import sqlite3

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        items = [make_daily_item(vps, f"Task {i}") for i in range(3)]
        for item in items:
            manager.link_item_to_project_exclusive(old.id, item.id)

        real = manager.link_item_to_project_exclusive
        calls = {"n": 0}

        def explode_on_the_third(board_id, item_id):
            calls["n"] += 1
            if calls["n"] == 3:
                raise sqlite3.OperationalError("simulated failure mid-batch")
            return real(board_id, item_id)

        monkeypatch.setattr(manager, "link_item_to_project_exclusive", explode_on_the_third)
        errors = []
        monkeypatch.setattr(pb.messagebox, "showerror",
                            lambda title, message, **kw: errors.append(message))

        stub = _dialog_stub(manager, new.id, checked=[i.id for i in items])
        stub._link_selected_items()

        for item in items:
            assert manager.get_project_board_ids_for_item(item.id) == [old.id], (
                "the batch was half-applied — some items moved, some did not")
        assert errors, "the failure reached nobody"
        assert stub.checked_items == {i.id for i in items}, "the selection was consumed"
    finally:
        vps.close()


def test_f6_the_dead_title_builder_is_gone():
    """BP6 removed its last caller; it is the same class as the BP4 deletions."""
    from src.getmoredone.screens import title_format

    assert not hasattr(title_format, "build_action_item_title")


# --------------------------------------------- sweep, second pass


def test_s2_2_dropping_onto_no_project_asks_even_with_no_board_link(tmp_path, answers):
    """The Annual Plan Element is destroyed whether or not a link exists.

    Sweep pass 2. ``items_losing_links`` read only project links, so an item
    with an APE set from the editor's Annual Plan field — and no board row —
    had it nulled with nothing asked (P13: the guard measured the wrong thing).
    """
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        item = make_daily_item(vps, "Task")
        stored = manager.get_action_item(item.id)
        stored.annual_plan_element_id = ape_id
        manager.update_action_item(stored)
        assert manager.get_project_board_ids_for_item(item.id) == []

        stub = SimpleNamespace(db_manager=manager, drag_items=[item])
        stub.refresh = lambda: None

        answers["reply"] = False
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")
        assert answers["messages"], "the Annual Plan Element went without a question"
        assert "Annual Plan Element" in answers["messages"][0], answers["messages"][0]
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id

        answers["reply"] = True
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")
        assert manager.get_action_item(item.id).annual_plan_element_id is None
    finally:
        vps.close()


def test_s2_2_an_item_with_nothing_to_lose_is_still_not_interrupted(tmp_path, answers):
    """No link, no Annual Plan Element — nothing at stake, so no dialog."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        item = make_daily_item(vps, "Task")
        stored = manager.get_action_item(item.id)
        assert stored.annual_plan_element_id is None

        stub = SimpleNamespace(db_manager=manager, drag_items=[item])
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")

        assert answers["messages"] == []
    finally:
        vps.close()


def test_s2_6_a_dropped_inherited_link_is_logged(tmp_path, caplog):
    """F2 drops N-1 links on a copy; a silent drop is the bug it was fixing."""
    import logging

    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)

        with caplog.at_level(logging.WARNING,
                             logger="src.getmoredone.db_manager_project_boards"):
            new_id = manager.create_followup_item(item.id)

        assert len(manager.get_project_board_ids_for_item(new_id)) == 1
        messages = [record.getMessage() for record in caplog.records]
        assert any("inherits" in message for message in messages), (
            f"two project links were dropped without a word; log said {messages}")
    finally:
        vps.close()


def test_s2_6_a_single_inherited_link_is_not_logged(tmp_path, caplog):
    """Nothing was dropped, so there is nothing to say — a log per copy is noise."""
    import logging

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Only", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        with caplog.at_level(logging.WARNING,
                             logger="src.getmoredone.db_manager_project_boards"):
            new_id = manager.create_followup_item(item.id)

        assert manager.get_project_board_ids_for_item(new_id) == [board.id]
        assert not [r for r in caplog.records if "inherits" in r.getMessage()]
    finally:
        vps.close()


def test_s2_8_an_unreadable_board_is_still_a_filing_not_a_clear(tmp_path, monkeypatch,
                                                               answers):
    """The message branched on the board *title*, not on what is happening.

    Sweep pass 2. A board row that cannot be read left ``title = None``, and
    ``describe_single_relink`` then told the user their Annual Plan Element was
    about to be cleared — which filing does not do (P14: an error state read as
    content).
    """
    from src.getmoredone.screens.project_link_notice import confirm_exclusive_relink

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        monkeypatch.setattr(manager, "get_project_board", lambda board_id: None)
        confirm_exclusive_relink(None, manager, [item.id], new.id)

        message = answers["messages"][0]
        assert "Annual Plan Element" not in message, message
        assert "Clearing" not in message, message
        assert "the selected project" in message, message
    finally:
        vps.close()
