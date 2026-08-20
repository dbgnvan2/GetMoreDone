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

import pathlib
from types import SimpleNamespace

import pytest

import src.getmoredone.screens.project_boards as pb
from src.getmoredone.models import ProjectBoard
from src.getmoredone.screens.project_boards import LinkProjectActionItemsDialog
from src.getmoredone.screens.project_link_notice import (
    describe_bulk_clear,
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


def _banner_stub(manager, texts):
    """Enough of the Projects screen to drive the multi-link banner."""
    label = SimpleNamespace(
        configure=lambda **kw: texts.append(kw.get("text")),
        grid=lambda *a, **k: None,
        grid_remove=lambda *a, **k: None,
    )
    stub = SimpleNamespace(db_manager=manager, multi_link_label=label)
    stub._show_multi_link_text = lambda text: pb.ProjectBoardsScreen._show_multi_link_text(
        stub, text)
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
        assert "2 of the selected items:" in answers["messages"][0], answers["messages"][0]
        assert "2 already filed under another project" in answers["messages"][0]
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
        stub = _banner_stub(manager, texts)
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
        elsewhere = _board(manager, "Somewhere Else", None)

        answers["reply"] = False
        _dialog_stub(manager, elsewhere.id)._link(item.id)

        message = answers["messages"][0]
        # Three other projects, three links removed — the number in the
        # sentence is the number of links the write deletes.
        assert "filed under 3 other projects" in message, message
        assert "Somewhere Else" in message
        assert "removes those 3 links" in message, message
    finally:
        vps.close()


def test_p10_the_target_board_is_not_counted_as_a_link_being_lost(tmp_path, answers):
    """Filing an item under a board it is already on removes nothing.

    ``classify_losses`` excludes the target; the count beside it did not, so an
    item whose only board *is* the target reached "already filed under another
    project … removes that link" — where no link is removed at all, the row
    being deleted and re-inserted under the same board (P19: two halves of one
    decision measuring different things).
    """
    from tests.weekly_tactic_fixtures import seed_second_ape

    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)

        answers["reply"] = False
        _dialog_stub(manager, boards[0].id)._link(item.id)

        message = answers["messages"][0]
        # The target is one of the three, so two links go — and the sentence
        # says two, not "the other 1".
        assert "filed under 2 other projects" in message, message
        assert "removes those 2 links" in message, message

        # And an item whose ONLY board is the target loses no link at all.
        answers["messages"].clear()
        ape_b = seed_second_ape(vps)
        solo_board = _board(manager, "Solo", ape_b)
        solo = make_daily_item(vps, "Solo task")
        manager.link_item_to_project_exclusive(solo_board.id, solo.id)
        stored = manager.get_action_item(solo.id)
        stored.annual_plan_element_id = seed_ape(
            vps, subsegment="Third", key_field="Third")
        manager.update_action_item(stored)

        _dialog_stub(manager, solo_board.id)._link(solo.id)
        if answers["messages"]:
            assert "removes that link" not in answers["messages"][0], (
                answers["messages"][0])
    finally:
        vps.close()


# ----------------------------------------------------- shared wording


def test_bp1_every_surface_uses_the_same_sentence():
    """The editor and the Projects dialog must not word this differently."""
    single = describe_single_relink(3, "Website Rebuild")
    assert "filed under 3 other projects" in single
    assert "Website Rebuild" in single
    assert "removes those 3 links" in single

    cleared = describe_single_relink(2, None)
    assert "unfiles it from all of them" in cleared
    assert "Annual Plan Element is not affected" in cleared

    # One existing link is the Projects screen's ordinary case, and the plural
    # form got it wrong in both halves of the sentence.
    one = describe_single_relink(1, "Website Rebuild")
    assert "already filed under another project" in one
    assert "removes that link" in one
    assert "1 projects" not in one and "the other 0" not in one
    assert "unfiles it" in describe_single_relink(1, None)

    # Two *other* projects means two links go.
    two = describe_single_relink(2, "Website Rebuild")
    assert "removes those 2 links" in two, two

    assert "1 of the selected item:" in describe_bulk_relink(
        1, "Website Rebuild", batch_size=1)
    assert "4 of the selected items:" in describe_bulk_relink(
        4, None, batch_size=4)
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


def test_f1_dropping_onto_no_project_keeps_the_plan_element(tmp_path, answers):
    """Detaching removes the link and nothing else.

    Taking an item off a project is one action, not two: the user may be about
    to file it under a different one, and losing its place in the plan in
    between is a loss they never asked for. The Projects screen's own "Unlink"
    button always behaved this way; the other two paths now match it.
    """
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
        assert "not affected" in answers["messages"][0], answers["messages"][0]

        answers["reply"] = True
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")
        assert manager.get_project_board_ids_for_item(item.id) == []
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id, (
            "unfiling destroyed the item's place in the plan")
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
        stub = _banner_stub(manager, texts)
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



def test_unlinking_keeps_the_plan_element(tmp_path, answers):
    """Detaching removes the link and nothing else.

    An item with an Annual Plan Element and no project row therefore loses
    nothing at all when dropped on "No Project", so it is not interrupted —
    and its place in the plan survives, ready for the project it is on its way
    to.
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
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")

        assert answers["messages"] == [], (
            f"interrupted for a change that does not happen: {answers['messages']}")
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id
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
        # A filing, not a clear: the plan element is *replaced* by the board's,
        # never "cleared", and the fallback target names a project.
        assert "Clearing" not in message, message
        assert "clears the item's Annual Plan Element" not in message, message
        assert "the selected project" in message, message
    finally:
        vps.close()


# ---------------------------------------------- sweep, third pass



def test_a_bulk_unlink_counts_only_the_items_that_are_filed(tmp_path, answers):
    """Items with nothing to unfile are not counted and not mentioned."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        filed = make_daily_item(vps, "Filed")
        manager.link_item_to_project_exclusive(board.id, filed.id)
        loose = make_daily_item(vps, "Loose")

        stub = SimpleNamespace(db_manager=manager, drag_items=[filed, loose])
        stub.refresh = lambda: None
        answers["reply"] = False
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")

        message = answers["messages"][0]
        assert "1 of the dragged items is filed under a project" in message, message
        assert "not affected" in message, message
    finally:
        vps.close()



def test_the_single_message_only_promises_what_this_write_does(tmp_path, answers):
    """Filing names the plan element only when it actually moves."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        same = _board(manager, "Same plan element", ape_id)
        other = _board(manager, "Other", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(same.id, item.id)

        stub = SimpleNamespace(db_manager=manager, drag_items=[item])
        stub.refresh = lambda: None
        answers["reply"] = False
        ds.DragScheduleScreen._drop_onto_project(stub, other.id)

        message = answers["messages"][0]
        # Both boards share a plan element, so nothing about it changes.
        assert "Annual Plan Element" not in message, message
        assert "removes that link" in message, message
    finally:
        vps.close()


def test_s3_2_an_unselected_no_project_box_says_its_number_is_unfiltered(tmp_path):
    """The box count is not segment-filtered; every other box on the row is.

    Sweep pass 3. S2-3 made the number honest on the selected path and left the
    unselected one reporting a different population with the same words (P5).
    """
    from types import SimpleNamespace
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    def box(lineage_filtered):
        stub = SimpleNamespace(unlinked_shown=None, unlinked_total=None)
        stub._lineage_filter_active = lambda: lineage_filtered
        return stub

    assert DragScheduleScreen._unlinked_box_text(box(True), 30) == (
        "30 unlinked items (before the segment filter)")
    assert DragScheduleScreen._unlinked_box_text(box(False), 30) == "30 unlinked items"


# --------------------------------------------- sweep, fourth pass



def test_s4_1_the_editor_warns_a_multi_filed_item_when_the_plan_element_moves(
        tmp_path, monkeypatch):
    """Adding a parameter with a default silently disarmed this call site once.

    The editor's multi-filed dialog is the only one such an item ever gets, so
    a defaulted flag there is a warning nobody sees (P22).
    """
    import tkinter.messagebox as messagebox
    from src.getmoredone.screens.item_editor import ItemEditorDialog
    from tests.weekly_tactic_fixtures import seed_second_ape

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_a = seed_ape(vps)
        ape_b = seed_second_ape(vps)
        first = _board(manager, "First", ape_a)
        second = _board(manager, "Second", ape_a)
        target = _board(manager, "Target", ape_b)
        item = make_daily_item(vps, "Task")
        manager.link_action_item_to_project_board(first.id, item.id)
        manager.link_action_item_to_project_board(second.id, item.id)
        stored = manager.get_action_item(item.id)
        stored.annual_plan_element_id = ape_a
        manager.update_action_item(stored)

        asked = []
        monkeypatch.setattr(messagebox, "askyesno",
                            lambda title, message, **kw: asked.append(message) or True)

        stub = SimpleNamespace(db_manager=manager, _loaded_extra_project_links=1,
                               item_id=item.id, item=manager.get_action_item(item.id))
        ItemEditorDialog._confirm_dropping_extra_project_links(stub, target.id)
        assert "Annual Plan Element" in asked[0], asked[0]

        # ...and filing under a board with the same plan element does not
        # claim it moves.
        asked.clear()
        ItemEditorDialog._confirm_dropping_extra_project_links(stub, second.id)
        assert "Annual Plan Element" not in asked[0], asked[0]
    finally:
        vps.close()



def test_the_bulk_unlink_sentence_says_what_it_does_and_what_it_does_not():
    """One loss, named; and the one it does not take, named too.

    The sentence had to describe two losses and got that wrong three times in
    a row. Removing the second loss removed the second half of the problem —
    but it has to say so, or a user who remembers the old behaviour has no way
    to tell.
    """
    assert describe_bulk_clear(0) == ""
    one = describe_bulk_clear(1, batch_size=1)
    assert "1 of the dragged item is filed under a project" in one, one
    assert "Annual Plan Element is not affected" in one, one

    many = describe_bulk_clear(3, batch_size=5, verb="selected")
    assert "3 of the selected items are filed under a project" in many, many
    assert "Annual Plan Element is not affected" in many, many



def test_the_bulk_unlink_plural_reads_as_english():
    """The noun follows the batch, the verb follows the affected count."""
    assert "1 of the dragged item is filed" in describe_bulk_clear(1, batch_size=1)
    assert "1 of the dragged items is filed" in describe_bulk_clear(1, batch_size=3)
    assert "2 of the dragged items are filed" in describe_bulk_clear(2, batch_size=3)



def test_p6_the_batch_noun_is_pluralised_from_the_batch_not_the_affected_count():
    """"1 of the dragged item" — two dragged, one affected (sweep pass 6)."""
    one_of_two = describe_bulk_clear(1, batch_size=2)
    assert "1 of the dragged items" in one_of_two, one_of_two
    one_of_one = describe_bulk_clear(1, batch_size=1)
    assert "1 of the dragged item " in one_of_one, one_of_one

    # The relink sibling was given the same shape only in pass 10.
    assert "2 of the selected items" in describe_bulk_relink(2, "Alpha", batch_size=5)
    assert "1 of the dragged items" in describe_bulk_relink(
        1, "Alpha", verb="dragged", batch_size=2)



def test_p6_each_surface_names_the_action_the_user_took():
    """A drag is not a selection, and the Projects dialog has no drag."""
    dragged = describe_bulk_relink(2, "Alpha", verb="dragged", batch_size=2)
    assert "2 of the dragged items" in dragged, dragged
    selected = describe_bulk_relink(2, "Alpha", batch_size=2)
    assert "2 of the selected items" in selected, selected
    assert "of the selected items" in describe_bulk_clear(
        2, batch_size=2, verb="selected")


def test_s4_6_both_who_branches_read_a_blank_filter_the_same_way(tmp_path):
    """The same screen must not list rows one way and count them another.

    Sweep pass 4: the unlinked branch returned nothing for a whitespace-only
    filter while the project-board branch listed the rows whose owner was also
    whitespace (P5).
    """
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen
    from src.getmoredone.models import ActionItem

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        # The row has to exist, or the SQL half of this test returns [] under
        # any implementation and proves only that the fixture is empty (sweep
        # pass 5, P10).
        blank_owner = ActionItem(who="   ", title="Whitespace owner")
        manager.create_action_item(blank_owner, apply_defaults=False)
        named = ActionItem(who="Ana", title="Named")
        manager.create_action_item(named, apply_defaults=False)

        assert DragScheduleScreen._matches_who(blank_owner, "   ") is False
        assert DragScheduleScreen._matches_who(blank_owner, None) is True

        listed = manager.get_unlinked_action_items(who_filter="   ")
        assert listed == [], f"a blank filter listed {[i.title for i in listed]}"
        assert {i.title for i in manager.get_unlinked_action_items(who_filter=None)} == {
            "Whitespace owner", "Named"}, "the row is not in the fixture at all"

        # An *empty* filter is the same answer as a whitespace one. It used to
        # fall past `if who_filter:` and drop the filter entirely, so the
        # unlinked list returned everything while _matches_who returned nothing.
        assert DragScheduleScreen._matches_who(blank_owner, "") is False
        assert manager.get_unlinked_action_items(who_filter="") == []
        assert manager.count_unlinked_action_items(who_filter="") == 0

        assert DragScheduleScreen._matches_who(named, "ana") is True
        assert DragScheduleScreen._matches_who(named, "Bob") is False
    finally:
        vps.close()



def test_a_bulk_unlink_leaves_every_plan_element_intact(tmp_path, answers):
    """Two items filed under an Annual Plan Element keep it when unfiled."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        items = [make_daily_item(vps, f"Task {i}") for i in range(2)]
        for item in items:
            manager.link_item_to_project_exclusive(board.id, item.id)
        assert all(manager.get_action_item(i.id).annual_plan_element_id == ape_id
                   for i in items)

        stub = SimpleNamespace(db_manager=manager, drag_items=items)
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")

        for item in items:
            assert manager.get_project_board_ids_for_item(item.id) == []
            assert manager.get_action_item(item.id).annual_plan_element_id == ape_id
    finally:
        vps.close()



def test_a_batch_with_nothing_filed_is_not_interrupted(tmp_path, answers):
    """Nothing to unfile means nothing to consent to."""
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        items = [make_daily_item(vps, f"Loose {i}") for i in range(2)]

        stub = SimpleNamespace(db_manager=manager, drag_items=items)
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")

        assert answers["messages"] == []
    finally:
        vps.close()


# ------------------------------- cold sweep (no prior context) findings


def test_c1_a_search_cannot_leave_invisible_items_selected(tmp_path, monkeypatch, answers):
    """Ticks must match the rows on screen, because Link Selected now deletes.

    The result list is rebuilt on every keystroke in Search and on every filter
    toggle, with the checkboxes recreated blank while ``checked_items`` kept
    its contents. Ticking three rows, typing one character and pressing "Link
    Selected" re-filed three items the user could no longer see — survivable
    while linking was additive, destructive once BP1 made it exclusive.
    """
    import customtkinter as ctk
    from src.getmoredone.models import ActionItem

    monkeypatch.setattr(LinkProjectActionItemsDialog, "grab_set", lambda self: None)

    vps = make_vps(tmp_path)
    root = ctk.CTk()
    root.withdraw()
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        new = _board(manager, "New Project", ape_id)
        hidden = ActionItem(who="Self", title="Zebra report")
        manager.create_action_item(hidden, apply_defaults=False)
        manager.link_item_to_project_exclusive(old.id, hidden.id)
        shown = ActionItem(who="Self", title="Alpha report")
        manager.create_action_item(shown, apply_defaults=False)

        dialog = LinkProjectActionItemsDialog(root, manager, new.id, on_linked=lambda: None)
        try:
            dialog._on_item_checkbox_toggled(hidden.id)
            assert dialog.checked_items == {hidden.id}

            # The user types, and "Zebra report" leaves the list.
            dialog.search_var.set("Alpha")
            assert hidden.id not in dialog.checked_items, (
                "an item the user can no longer see is still selected")

            dialog._link_selected_items()
        finally:
            dialog.destroy()

        assert manager.get_project_board_ids_for_item(hidden.id) == [old.id], (
            "an invisible item was re-filed, losing its project link")
    finally:
        root.destroy()
        vps.close()


def test_c1_a_row_that_survives_the_rebuild_keeps_its_tick(tmp_path, monkeypatch, answers):
    """...and the fix must not silently drop a selection the user can still see."""
    import customtkinter as ctk
    from src.getmoredone.models import ActionItem

    monkeypatch.setattr(LinkProjectActionItemsDialog, "grab_set", lambda self: None)

    vps = make_vps(tmp_path)
    root = ctk.CTk()
    root.withdraw()
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        keeper = ActionItem(who="Self", title="Alpha report")
        manager.create_action_item(keeper, apply_defaults=False)

        dialog = LinkProjectActionItemsDialog(root, manager, board.id, on_linked=lambda: None)
        try:
            dialog._on_item_checkbox_toggled(keeper.id)
            dialog.search_var.set("Alpha")          # still matches
            assert dialog.checked_items == {keeper.id}
            dialog._link_selected_items()
        finally:
            dialog.destroy()

        assert manager.get_project_board_ids_for_item(keeper.id) == [board.id]
    finally:
        root.destroy()
        vps.close()


def test_c2_filing_asks_before_replacing_an_items_own_plan_element(tmp_path, answers):
    """Filing overwrites the item's Annual Plan Element; that is a loss too.

    ``classify_losses`` counted an APE as at stake only when clearing, so an
    item carrying its own plan element and no board row was classified as
    losing nothing and had it destroyed with no dialog (P5 — the class closed
    for clearing and left open for filing).
    """
    from tests.weekly_tactic_fixtures import seed_second_ape

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        own_ape = seed_ape(vps)
        board_ape = seed_second_ape(vps)
        board = _board(manager, "Website Rebuild", board_ape)
        item = make_daily_item(vps, "Task")
        stored = manager.get_action_item(item.id)
        stored.annual_plan_element_id = own_ape
        manager.update_action_item(stored)

        answers["reply"] = False
        _dialog_stub(manager, board.id)._link(item.id)

        assert answers["messages"], "the item's plan element went without a word"
        assert "Annual Plan Element" in answers["messages"][0], answers["messages"][0]
        assert manager.get_action_item(item.id).annual_plan_element_id == own_ape

        answers["reply"] = True
        _dialog_stub(manager, board.id)._link(item.id)
        assert manager.get_action_item(item.id).annual_plan_element_id == board_ape
    finally:
        vps.close()


def test_c2_filing_an_item_with_no_plan_element_asks_nothing(tmp_path, answers):
    """The ordinary case stays uninterrupted."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")
        assert manager.get_action_item(item.id).annual_plan_element_id is None

        _dialog_stub(manager, board.id)._link(item.id)

        assert answers["messages"] == []
        assert manager.get_project_board_ids_for_item(item.id) == [board.id]
    finally:
        vps.close()


def test_c3_a_board_with_no_plan_element_clears_the_items(tmp_path):
    """Moving to a board with none must not leave the previous board's behind.

    The APE sync was `if board and board.annual_plan_element_id:` with no else,
    so the row went on claiming a plan element belonging to a project it was no
    longer on — and every reader downstream took that as ground truth.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        with_ape = _board(manager, "Has a plan element", ape_id)
        without = _board(manager, "No plan element", None)
        item = make_daily_item(vps, "Task")

        manager.link_item_to_project_exclusive(with_ape.id, item.id)
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id

        manager.link_item_to_project_exclusive(without.id, item.id)
        assert manager.get_project_board_ids_for_item(item.id) == [without.id]
        assert manager.get_action_item(item.id).annual_plan_element_id is None, (
            "the item still claims the previous board's plan element")
    finally:
        vps.close()


def test_c5_a_failed_banner_check_says_so_rather_than_showing_nothing(tmp_path):
    """"The check failed" must not look identical to "nothing to report"."""
    class Exploding:
        def get_items_on_multiple_project_boards(self):
            raise RuntimeError("simulated query failure")

    texts = []
    stub = _banner_stub(Exploding(), texts)
    pb.ProjectBoardsScreen._refresh_multi_link_notice(stub)

    assert texts, "the banner was never configured at all"
    assert "Could not check" in texts[0], texts
    assert texts[0] != "", "a failed check was shown as an empty banner"


def test_c6_creating_an_item_from_a_board_files_it_exclusively(tmp_path, monkeypatch):
    """The item a board creates is filed under that board, exclusively.

    This asserted the *absence of a string* in the source, which passes just as
    happily when the link call is deleted outright — a guard that cannot fail
    for the thing it names (P24). It drives the real method now.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)

        # An error here would be swallowed by the method's own try/except and
        # reported as a messagebox, so make that loud instead of silent.
        errors = []
        monkeypatch.setattr(pb.messagebox, "showerror",
                            lambda *a, **k: errors.append(a))

        opened = []
        stub = SimpleNamespace(
            db_manager=manager,
            board_rows=[{"id": board.id, "segment_name": "Health"}],
            selected_board_id=None,
            refresh=lambda: None,
            edit_item=lambda item_id: opened.append(item_id),
        )
        # Exclusive and additive are indistinguishable by *outcome* here — the
        # item is brand new with the board's plan element already on it — so
        # the call itself is what has to be asserted. The earlier version of
        # this test passed with the additive call restored, and the one before
        # that passed with the call deleted outright (P24).
        additive = []
        monkeypatch.setattr(
            manager, "link_action_item_to_project_board",
            lambda *a, **k: additive.append(a))
        exclusive = []
        real_exclusive = manager.link_item_to_project_exclusive
        monkeypatch.setattr(
            manager, "link_item_to_project_exclusive",
            lambda b, i: (exclusive.append((b, i)), real_exclusive(b, i))[1])

        pb.ProjectBoardsScreen.create_action_item(stub, board.id)
        assert not errors, errors
        assert not additive, "the additive link call is back"
        assert exclusive, "nothing was filed exclusively"

        assert opened, "no item was created"
        new_id = opened[0]
        assert manager.get_project_board_ids_for_item(new_id) == [board.id], (
            "an item created from a board was not filed under it")
        assert manager.get_action_item(new_id).annual_plan_element_id == ape_id
    finally:
        vps.close()


def test_c2_2_no_combination_of_arguments_produces_a_false_sentence():
    """Walk every branch of the two relink sentences, not just the live ones.

    The Annual Plan Element clause went wrong three times in a row — promised
    unconditionally, then only for clearing, then "replaces" for a board with
    nothing to replace it with. Each was found by reading one live message. An
    exhaustive walk finds the combinations no caller produces *today*, which is
    what the next caller turns into a live one.
    """
    from src.getmoredone.screens.project_link_notice import (
        APE_CLEARED, APE_REPLACED, APE_UNCHANGED)

    outcomes = (APE_UNCHANGED, APE_CLEARED, APE_REPLACED)
    for count in (0, 1, 2, 5):
        for title in ("Website Rebuild", None):
            for outcome in outcomes:
                text = describe_single_relink(count, title, ape_outcome=outcome)
                assert text and text.endswith("Continue?"), (count, title, outcome)
                if title:
                    assert "Clearing the project" not in text, text
                else:
                    # Nothing to take a plan element from, so nothing to replace.
                    assert "replaces" not in text, text
                if outcome is APE_UNCHANGED and count:
                    # The clearing sentence names the plan element only to say
                    # it is untouched — that is not a claim of loss.
                    assert ("Annual Plan Element" not in text
                            or "not affected" in text), text

    # affected == 0 is what a batch of loose items each carrying their own
    # plan element actually produces, and the walk that "covered everything"
    # started at 1 — so it never saw the case the live caller hits (P24).
    for affected in (0, 1, 2, 5):
        for title in ("Website Rebuild", None):
            for outcome in outcomes:
                for ape_only in (0, 1, 3):
                    text = describe_bulk_relink(
                        affected, title, ape_outcome=outcome,
                        ape_only_count=ape_only, batch_size=affected + ape_only)
                    if affected + ape_only == 0:
                        assert text == "", text
                        continue
                    if not affected and outcome is APE_UNCHANGED:
                        # Nothing is unfiled and no plan element moves, so
                        # there is nothing to consent to and no sentence to
                        # show — rather than "…filing under “X” . Continue?".
                        assert text == "", text
                        continue
                    assert text.endswith("Continue?")
                    if not title:
                        assert "replaces" not in text, text
                    if outcome is APE_UNCHANGED and not ape_only:
                        assert "Annual Plan Element" not in text, text
                    # The total heads the sentence, and each bucket is
                    # named against the clause it is actually true of — the
                    # earlier version demanded only the total, which is how the
                    # mixed batch came to say "N already filed under another
                    # project" about items filed under nothing.
                    assert text.startswith(f"{affected + ape_only} "), text
                    if affected:
                        assert f"{affected} already filed under another project" in text, text
                    else:
                        assert "already filed under another project" not in text, text
                    if ape_only:
                        assert f"{ape_only} carrying" in text, text
                    else:
                        assert "carrying" not in text, text


# ------------------------------------------------- eighth pass (cold)


def test_f1_a_batch_that_only_loses_plan_elements_is_counted_and_named(tmp_path, answers):
    """"0 selected items … removes the existing links" while three APEs went.

    ``classify_losses`` returns two buckets; the bulk *filing* sentence used
    only the first. A batch of loose items each carrying their own Annual Plan
    Element put every one of them in the second bucket, so the message counted
    zero and dropped the plan-element clause as well — both halves false, and
    the same defect the single-item path had fixed one commit earlier.
    """
    from tests.weekly_tactic_fixtures import seed_second_ape

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        own_ape = seed_ape(vps)
        board_ape = seed_second_ape(vps)
        board = _board(manager, "Website Rebuild", board_ape)

        items = []
        for i in range(3):
            item = make_daily_item(vps, f"Loose {i}")
            stored = manager.get_action_item(item.id)
            stored.annual_plan_element_id = own_ape
            manager.update_action_item(stored)
            items.append(item)

        answers["reply"] = False
        stub = _dialog_stub(manager, board.id, checked=[i.id for i in items])
        stub._link_selected_items()

        message = answers["messages"][0]
        assert "0 " not in message, message
        assert "3 of the selected items" in message, message
        assert "Annual Plan Element" in message, message
        for item in items:
            assert manager.get_action_item(item.id).annual_plan_element_id == own_ape
    finally:
        vps.close()


def test_f2_filing_never_strips_a_weekly_tactics_plan_element(tmp_path):
    """A Weekly Tactic with no Annual Plan Element is a row the app cannot save.

    The APE sync writes raw SQL, so it bypasses ``update_action_item``'s
    validation. Making it unconditional meant filing a tactic under a project
    with no plan element produced an ``item_type='week'`` row whose own writer
    then raised ValueError on it — a value no supported path can create,
    written by a supported path.
    """
    import pytest as _pytest
    from tests.weekly_tactic_fixtures import make_week_item

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)
        bare = _board(manager, "No plan element", None)

        # Filing is refused outright, not merely when it would null the APE:
        # a board with a *different* plan element would re-stamp the tactic and
        # leave a perfectly valid-looking row in the wrong lineage.
        with _pytest.raises(ValueError, match="Weekly Tactic"):
            manager.link_item_to_project_exclusive(bare.id, tactic.id)
        other = _board(manager, "Different plan element", seed_ape(
            vps, subsegment="Elsewhere", key_field="Other"))
        with _pytest.raises(ValueError, match="Weekly Tactic"):
            manager.link_item_to_project_exclusive(other.id, tactic.id)

        after = manager.get_action_item(tactic.id)
        assert after.annual_plan_element_id == ape_id, (
            "the Weekly Tactic lost the plan element it is required to have")
        assert manager.get_project_board_ids_for_item(tactic.id) == []
        # ...and the row is still saveable through the ordinary path.
        manager.update_action_item(after)

        # The same applies to clearing.
        manager.clear_item_project_links(tactic.id)
        assert manager.get_action_item(tactic.id).annual_plan_element_id == ape_id

        # An ordinary daily item is unaffected by the guard.
        daily = make_daily_item(vps, "Daily")
        manager.link_item_to_project_exclusive(_board(manager, "Has one", ape_id).id, daily.id)
        assert manager.get_action_item(daily.id).annual_plan_element_id == ape_id
        manager.link_item_to_project_exclusive(bare.id, daily.id)
        assert manager.get_action_item(daily.id).annual_plan_element_id is None
    finally:
        vps.close()


def test_f2_the_link_dialog_does_not_offer_weekly_tactics(tmp_path, monkeypatch):
    """PL6 — a Weekly Tactic cannot be filed under a project, on any surface.

    The item editor disables its Set Project button for one; this dialog was
    listing tactics with a working Link button.
    """
    import customtkinter as ctk
    from tests.weekly_tactic_fixtures import make_week_item

    monkeypatch.setattr(LinkProjectActionItemsDialog, "grab_set", lambda self: None)

    vps = make_vps(tmp_path)
    root = ctk.CTk()
    root.withdraw()
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        make_week_item(vps, ape_id)
        daily = make_daily_item(vps, "An ordinary task")

        dialog = LinkProjectActionItemsDialog(root, manager, board.id, on_linked=lambda: None)
        try:
            listed = {item.id for item in manager.get_all_items()}
            assert any(manager.get_action_item(i).item_type == "week" for i in listed), (
                "the fixture has no Weekly Tactic, so this proves nothing")
            # One row rendered: the daily item, not the tactic.
            assert len(dialog.results.winfo_children()) == 1
            dialog._link(daily.id)
        finally:
            dialog.destroy()
        assert manager.get_project_board_ids_for_item(daily.id) == [board.id]
    finally:
        root.destroy()
        vps.close()


def test_f5_one_implementation_of_what_happens_to_the_plan_element(tmp_path):
    """The editor had a third copy that lacked the unreadable-board guard."""
    from src.getmoredone.screens.item_editor import ItemEditorDialog
    from src.getmoredone.screens.project_link_notice import (
        ape_outcome_for_change, APE_CLEARED, APE_REPLACED, APE_UNCHANGED)
    from tests.weekly_tactic_fixtures import seed_second_ape

    assert not hasattr(ItemEditorDialog, "_project_change_moves_the_ape"), (
        "the editor-local copy of the rule is back")

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_a = seed_ape(vps)
        ape_b = seed_second_ape(vps)
        with_a = _board(manager, "Has A", ape_a)
        with_b = _board(manager, "Has B", ape_b)
        bare = _board(manager, "Has none", None)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(with_a.id, item.id)

        assert ape_outcome_for_change(manager, item.id, with_a.id) is APE_UNCHANGED
        assert ape_outcome_for_change(manager, item.id, with_b.id) == APE_REPLACED
        assert ape_outcome_for_change(manager, item.id, bare.id) == APE_CLEARED
        assert ape_outcome_for_change(manager, item.id, None) == APE_CLEARED
        assert ape_outcome_for_change(manager, None, with_b.id) is APE_UNCHANGED
        # An unreadable board: the write skips the APE, so the answer is
        # "unchanged", not "cleared".
        assert ape_outcome_for_change(manager, item.id, "no-such-board") is APE_UNCHANGED
    finally:
        vps.close()


def test_f2_dragging_a_tactic_onto_a_project_is_refused(tmp_path, monkeypatch, answers):
    """The Scheduler lists Weekly Tactics; it must not file them under a board.

    `drag_schedule` had no `item_type` check at all, so a tactic dropped on a
    project box was re-stamped with that board's Annual Plan Element — the
    exact thing PL6 forbids, and it left a perfectly valid-looking row in the
    wrong lineage, so nothing downstream ever caught it.
    """
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds
    from tests.weekly_tactic_fixtures import make_week_item

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        other_ape = seed_ape(vps, subsegment="Elsewhere", key_field="Other")
        board = _board(manager, "Website Rebuild", other_ape)
        tactic = make_week_item(vps, ape_id)
        daily = make_daily_item(vps, "An ordinary task")

        told = []
        monkeypatch.setattr(ds.messagebox, "showinfo",
                            lambda title, msg, **kw: told.append(msg))

        stub = SimpleNamespace(db_manager=manager, drag_items=[tactic, daily])
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, board.id)

        assert told, "the tactic was silently left behind with no word"
        assert "Weekly Tactic" in told[0], told[0]
        assert manager.get_project_board_ids_for_item(tactic.id) == []
        assert manager.get_action_item(tactic.id).annual_plan_element_id == ape_id
        # ...and the rest of the drag still went through.
        assert manager.get_project_board_ids_for_item(daily.id) == [board.id]
    finally:
        vps.close()


def test_f1_clearing_a_tactics_project_promises_nothing_it_will_not_do(tmp_path, answers):
    """A tactic keeps its plan element, so there is nothing to confirm.

    The writer learned that and the describer did not, so dragging a tactic
    onto "No Project" showed "Removing the project also clears it" over a write
    that changed nothing — an affirmative confirmation in front of a no-op.
    """
    from types import SimpleNamespace
    import src.getmoredone.screens.drag_schedule as ds
    from tests.weekly_tactic_fixtures import make_week_item

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        tactic = make_week_item(vps, ape_id)

        stub = SimpleNamespace(db_manager=manager, drag_items=[tactic])
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, "__none__")

        assert answers["messages"] == [], (
            f"asked about a change that will not happen: {answers['messages']}")
        assert manager.get_action_item(tactic.id).annual_plan_element_id == ape_id
    finally:
        vps.close()


def test_p10_a_refused_link_reports_instead_of_escaping_a_tk_callback(tmp_path, monkeypatch, answers):
    """`link_item_to_project_exclusive` raises for a tactic; `_link` must catch it.

    The dialog no longer lists Weekly Tactics, so this is unreachable through
    the UI — but the bulk path beside it was guarded and this one was not, and
    an unguarded raise in a Tk callback is invisible in a double-clicked app.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")

        def explode(board_id, item_id):
            raise ValueError("simulated refusal")

        monkeypatch.setattr(manager, "link_item_to_project_exclusive", explode)
        errors = []
        monkeypatch.setattr(pb.messagebox, "showerror",
                            lambda title, msg, **kw: errors.append(msg))

        _dialog_stub(manager, board.id)._link(item.id)

        assert errors and "simulated refusal" in errors[0], errors
    finally:
        vps.close()


def test_p10_a_blank_board_title_is_still_a_filing(tmp_path, answers):
    """A board saved with an empty title must not read as a clear.

    Every branch treats a falsy title as "this is a clear", so an empty one
    turned filing into "Clearing the project…". The fallback is a phrase, not a
    name, so it is not wrapped in quotation marks either.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _board(manager, "Old Project", ape_id)
        blank = _board(manager, "", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        answers["reply"] = False
        _dialog_stub(manager, blank.id)._link(item.id)

        message = answers["messages"][0]
        assert "Clearing" not in message, message
        assert "unfiles" not in message, message
        assert "the selected project" in message, message
        assert "“the selected project”" not in message, (
            "a stand-in phrase is quoted as though it were a project name")
    finally:
        vps.close()


def test_p10_a_tactic_in_a_batch_is_not_counted_as_a_loss(tmp_path, answers):
    """`classify_losses` skips tactics, because filing one is refused.

    Without the skip the dialog counts a loss for an item the write will
    refuse to touch, and a batch of nothing but tactics raises a dialog for an
    operation that does nothing at all.
    """
    from src.getmoredone.screens.project_link_notice import classify_losses
    from tests.weekly_tactic_fixtures import make_week_item

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _board(manager, "Website Rebuild", ape_id)
        tactic = make_week_item(vps, ape_id)
        manager.link_action_item_to_project_board(board.id, tactic.id)
        other = _board(manager, "Elsewhere", None)

        with_links, ape_only = classify_losses(manager, [tactic.id], other.id)
        assert (with_links, ape_only) == ([], []), (
            "a Weekly Tactic was counted as losing something to a write that "
            "is refused")
    finally:
        vps.close()


def test_p11_the_number_in_the_sentence_is_the_number_of_links_removed(tmp_path, monkeypatch):
    """Count the rows the write actually deletes and compare with the sentence.

    ``count`` was changed to exclude the target board while the sentence went
    on saying "the other count - 1", so every multi-filed item was told one
    fewer link would go than actually went (P19). Reading one message could not
    show that; counting the deleted rows can.
    """
    import src.getmoredone.screens.project_link_notice as notice
    from src.getmoredone.models import ProjectBoard

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        boards = []
        for i in range(4):
            board = ProjectBoard(title=f"Board {i}", annual_plan_element_id=ape_id)
            manager.create_project_board(board)
            boards.append(board)

        said = []
        monkeypatch.setattr(notice.messagebox, "askyesno",
                            lambda title, message, **kw: said.append(message) or True)

        for on, target_index in ((3, 0), (3, 3), (2, 0), (4, 1)):
            item = make_daily_item(vps, f"Task {on}-{target_index}")
            for board in boards[:on]:
                manager.link_action_item_to_project_board(board.id, item.id)

            before = set(manager.get_project_board_ids_for_item(item.id))
            said.clear()
            notice.confirm_exclusive_relink(None, manager, [item.id],
                                            boards[target_index].id)
            manager.link_item_to_project_exclusive(boards[target_index].id, item.id)
            removed = len(before - set(manager.get_project_board_ids_for_item(item.id)))

            message = said[0]
            if removed == 1:
                assert "removes that link" in message, (on, target_index, message)
            else:
                assert f"removes those {removed} links" in message, (
                    on, target_index, removed, message)
                assert f"filed under {removed} other projects" in message, (
                    on, target_index, removed, message)
    finally:
        vps.close()


def test_p11_all_three_surfaces_say_the_same_number(tmp_path, monkeypatch):
    """The module exists so one write has one wording. It has to hold."""
    import tkinter.messagebox as messagebox
    import src.getmoredone.screens.drag_schedule as ds
    import src.getmoredone.screens.project_link_notice as notice
    from src.getmoredone.screens.item_editor import ItemEditorDialog

    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)
        target = boards[0]

        said = []
        for module in (notice.messagebox, messagebox):
            monkeypatch.setattr(module, "askyesno",
                                lambda title, message, **kw: said.append(message) or False)

        _dialog_stub(manager, target.id)._link(item.id)
        dialog_message = said[-1]

        stub = SimpleNamespace(db_manager=manager, drag_items=[item])
        stub.refresh = lambda: None
        ds.DragScheduleScreen._drop_onto_project(stub, target.id)
        drag_message = said[-1]

        editor = SimpleNamespace(db_manager=manager, item_id=item.id,
                                 item=manager.get_action_item(item.id),
                                 _loaded_extra_project_links=2)
        ItemEditorDialog._confirm_dropping_extra_project_links(editor, target.id)
        editor_message = said[-1]

        assert dialog_message == drag_message, (dialog_message, drag_message)
        assert dialog_message == editor_message, (dialog_message, editor_message)
        assert "filed under 2 other projects" in dialog_message, dialog_message
    finally:
        vps.close()


def test_p12_a_blank_board_title_is_a_filing_on_the_editor_too(tmp_path, monkeypatch):
    """The editor resolved the target's name itself and got the blank case wrong.

    An empty board title is falsy, and every branch of ``describe_single_relink``
    reads a falsy title as "this is a clear" — so the editor showed "Removing
    the project unfiles it from all of them" over a write that files the item
    and overwrites its Annual Plan Element. ``confirm_exclusive_relink`` carries
    the guard for exactly this; the editor's second copy of the same resolution
    did not (P5).
    """
    import tkinter.messagebox as messagebox
    from src.getmoredone.screens.item_editor import ItemEditorDialog

    vps = make_vps(tmp_path)
    try:
        manager, item, boards = _three_linked(vps)
        blank = _board(manager, "", None)

        asked = []
        monkeypatch.setattr(messagebox, "askyesno",
                            lambda title, message, **kw: asked.append(message) or False)

        stub = SimpleNamespace(db_manager=manager, item_id=item.id,
                               item=manager.get_action_item(item.id),
                               _loaded_extra_project_links=2)
        ItemEditorDialog._confirm_dropping_extra_project_links(stub, blank.id)

        message = asked[0]
        assert "Removing the project" not in message, message
        assert "Filing it under" in message, message
        assert "the selected project" in message, message
        assert "“the selected project”" not in message, message
    finally:
        vps.close()
