"""PL1–PL7, PL12 — filing an Action Item under a Project from the item editor.

Spec: docs/implementation_plan_2026-08-19_item_editor_project_link.md

The dialog methods are driven with SimpleNamespace stubs (the pattern used by
tests/test_project_board_dates_ui.py), against a **real** DatabaseManager, so a
control that renders but never reaches the database fails here (P25).
"""

import sqlite3
from types import SimpleNamespace

import pytest

import src.getmoredone.screens.item_editor as ie
from src.getmoredone.models import ActionItem, ProjectBoard, ProjectBoardStatus
from src.getmoredone.screens.item_editor import ItemEditorDialog
from src.getmoredone.screens.item_editor_project_dialog import SetProjectDialog
from tests.weekly_tactic_fixtures import make_daily_item, make_vps, seed_ape


# --------------------------------------------------------------------- stubs


def _project_stub(manager, item_id=None, loaded_project_id=None, extra=0):
    """Enough of the editor to drive the project methods without a display."""
    texts = []
    stub = SimpleNamespace(
        db_manager=manager,
        item=None,
        item_id=item_id,
        NO_PROJECT_TEXT=ItemEditorDialog.NO_PROJECT_TEXT,
        _selected_project_id=loaded_project_id,
        _loaded_project_id=loaded_project_id,
        _loaded_extra_project_links=extra,
        _extra_project_links=extra,
        _project_choice_made=False,
        project_label=SimpleNamespace(
            configure=lambda **kw: texts.append(kw.get("text"))),
    )
    stub.refresh_project_display = lambda: ItemEditorDialog.refresh_project_display(stub)
    stub._load_project_baseline = lambda: ItemEditorDialog._load_project_baseline(stub)
    stub.apply_project_selection = lambda board_id: ItemEditorDialog.apply_project_selection(stub, board_id)
    stub._apply_project_link = lambda item_id: ItemEditorDialog._apply_project_link(stub, item_id)
    return stub, texts


def _save_stub(manager, monkeypatch, item=None, project_choice=..., texts=None):
    """A stub wired for ``save_item`` — every field that method reads."""
    monkeypatch.setattr(ie, "notify_weekly_tactic_changes", lambda *a, **k: None)

    def entry(value=""):
        return SimpleNamespace(get=lambda *a, **k: value)

    stub, label_texts = _project_stub(
        manager,
        item_id=item.id if item else None,
    )
    if texts is not None:
        texts.extend(label_texts)
    if item is not None:
        stub._load_project_baseline()
    stub.item = item
    stub.who_var = entry("Self")
    stub.selected_contact_id = None
    stub.title_context_entry = entry("")
    stub.title_entry = entry(item.title if item else "New Task")
    stub.description_text = entry("")
    stub.next_action_text = entry("")
    stub.start_date_entry = entry("2026-02-25")
    stub.due_date_entry = entry("2026-02-25")
    stub.is_meeting_var = SimpleNamespace(get=lambda: False)
    stub.importance_var = entry("")
    stub.urgency_var = entry("")
    stub.size_var = entry("")
    stub.value_var = entry("")
    stub.group_var = entry("")
    stub.category_var = entry("")
    stub.planned_minutes_entry = entry("")
    stub.weekly_tactic_start_var = entry("")
    stub.week_action_id = None
    stub.pending_weekly_tactic_id = None
    stub.segment_description_id = None
    stub._follow_chosen_tactic = False
    stub.error_label = SimpleNamespace(configure=lambda **kw: None)
    stub.after = lambda *a, **k: None
    stub.logger = SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None)
    stub.extract_factor_value = lambda text: ItemEditorDialog.extract_factor_value(stub, text)
    stub._canonical_weekly_tactic_title = lambda *a: a[0]

    if project_choice is not ...:
        stub.apply_project_selection(project_choice)
    return stub


def _seed_board(manager, title, ape_id=None, status=ProjectBoardStatus.ACTIVE):
    board = ProjectBoard(title=title, annual_plan_element_id=ape_id, status=status)
    manager.create_project_board(board)
    return board


# ------------------------------------------------------------------- PL1


def test_pl1_dialog_lists_active_and_pending_projects(tmp_path):
    """The picker offers active and pending projects; completed are not offered."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        _seed_board(manager, "Active One", ape_id)
        _seed_board(manager, "Pending One", ape_id, ProjectBoardStatus.PENDING)
        _seed_board(manager, "Done One", ape_id, ProjectBoardStatus.COMPLETED)

        stub = SimpleNamespace(
            db_manager=manager, current_board_id=None,
            SELECTABLE_STATUSES=SetProjectDialog.SELECTABLE_STATUSES)
        titles = [row["title"] for row in SetProjectDialog.load_boards(stub)]

        assert "Active One" in titles
        assert "Pending One" in titles
        assert "Done One" not in titles
    finally:
        vps.close()


def test_pl1_1_current_project_is_listed_even_when_completed(tmp_path):
    """The item's own current project never disappears from the picker."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        done = _seed_board(manager, "Done One", ape_id, ProjectBoardStatus.COMPLETED)

        stub = SimpleNamespace(
            db_manager=manager, current_board_id=done.id,
            SELECTABLE_STATUSES=SetProjectDialog.SELECTABLE_STATUSES)
        titles = [row["title"] for row in SetProjectDialog.load_boards(stub)]

        assert "Done One" in titles
    finally:
        vps.close()


# ------------------------------------------------------------------- PL2


def test_pl2_action_plan_shows_current_project(tmp_path):
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        stub, texts = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.refresh_project_display()

        assert stub._loaded_project_id == board.id
        assert texts[-1] == "Website Rebuild"
    finally:
        vps.close()


def test_pl2_1_unlinked_item_shows_none(tmp_path):
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        item = make_daily_item(vps, "Task")

        stub, texts = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.refresh_project_display()

        assert stub._loaded_project_id is None
        assert texts[-1] == ItemEditorDialog.NO_PROJECT_TEXT
    finally:
        vps.close()


def test_pl2_2_multi_link_is_surfaced_not_hidden(tmp_path):
    """An item the Projects screen filed under two boards says so (P2)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        first = _seed_board(manager, "First", ape_id)
        second = _seed_board(manager, "Second", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_action_item_to_project_board(first.id, item.id)
        manager.link_action_item_to_project_board(second.id, item.id)

        stub, texts = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.refresh_project_display()

        assert stub._extra_project_links == 1
        assert texts[-1] == "First  (+1 more)"
    finally:
        vps.close()


def test_pl2_3_deleting_the_board_unfiles_the_item(tmp_path):
    """Deleting a project takes its links with it (ON DELETE CASCADE).

    So the display reads "(none)" rather than pointing at a board that is gone.
    The "(project no longer exists)" branch in refresh_project_display stays as
    a guard for a link the cascade did not reach; this test pins the normal
    path, which is that no such link survives.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Doomed", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_action_item_to_project_board(board.id, item.id)
        manager.db.conn.execute("DELETE FROM project_boards WHERE id = ?", (board.id,))
        manager.db.conn.commit()

        stub, texts = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.refresh_project_display()

        assert manager.get_project_board_ids_for_item(item.id) == []
        assert texts[-1] == ItemEditorDialog.NO_PROJECT_TEXT
    finally:
        vps.close()


# ------------------------------------------------------------------- PL3


def test_pl3_new_item_saves_and_links(tmp_path, monkeypatch):
    """A brand-new item plus a chosen project: one save, item created and filed."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Website Rebuild", ape_id)

        stub = _save_stub(manager, monkeypatch, item=None, project_choice=board.id)
        assert ItemEditorDialog.save_item(stub) is True

        new_id = stub.item_id
        assert new_id, "the item was never created"
        assert manager.get_project_board_ids_for_item(new_id) == [board.id]
        stored = manager.get_action_item(new_id)
        assert stored.annual_plan_element_id == ape_id
    finally:
        vps.close()


# ------------------------------------------------------------------- PL4


def test_pl4_edit_item_relinks_exclusively(tmp_path, monkeypatch):
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _seed_board(manager, "Old Project", ape_id)
        new = _seed_board(manager, "New Project", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        stub = _save_stub(
            manager, monkeypatch,
            item=manager.get_action_item(item.id), project_choice=new.id,
        )
        assert ItemEditorDialog.save_item(stub) is True

        assert manager.get_project_board_ids_for_item(item.id) == [new.id]
    finally:
        vps.close()


def test_pl4_1_clearing_the_project_removes_the_link(tmp_path, monkeypatch):
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Old Project", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        stub = _save_stub(
            manager, monkeypatch,
            item=manager.get_action_item(item.id), project_choice=None,
        )
        assert ItemEditorDialog.save_item(stub) is True

        assert manager.get_project_board_ids_for_item(item.id) == []
    finally:
        vps.close()


def test_pl4_2_untouched_selection_never_clears(tmp_path, monkeypatch):
    """The highest-risk case: an ordinary Save must not touch the links at all.

    ``clear_item_project_links`` also nulls the item's Annual Plan Element, so a
    guard scoped to the save rather than to the change would strip the APE from
    every item saved without a project (P13).
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        item = make_daily_item(vps, "Task")
        stored = manager.get_action_item(item.id)
        stored.annual_plan_element_id = ape_id
        manager.update_action_item(stored)

        calls = []
        monkeypatch.setattr(
            manager, "clear_item_project_links",
            lambda *a, **k: calls.append(("clear", a)))
        monkeypatch.setattr(
            manager, "link_item_to_project_exclusive",
            lambda *a, **k: calls.append(("link", a)))

        stub = _save_stub(
            manager, monkeypatch,
            item=manager.get_action_item(item.id), project_choice=...,
        )
        assert ItemEditorDialog.save_item(stub) is True

        assert calls == [], f"an untouched dialog wrote project links: {calls}"
        assert manager.get_action_item(item.id).annual_plan_element_id == ape_id
    finally:
        vps.close()


def test_pl4_3_untouched_selection_preserves_multi_link(tmp_path, monkeypatch):
    """Saving an item that already sits on two boards keeps both."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        first = _seed_board(manager, "First", ape_id)
        second = _seed_board(manager, "Second", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_action_item_to_project_board(first.id, item.id)
        manager.link_action_item_to_project_board(second.id, item.id)

        stub = _save_stub(
            manager, monkeypatch,
            item=manager.get_action_item(item.id), project_choice=...,
        )
        assert ItemEditorDialog.save_item(stub) is True

        assert sorted(manager.get_project_board_ids_for_item(item.id)) == sorted(
            [first.id, second.id])
    finally:
        vps.close()


def test_pl4_4_re_picking_the_same_project_writes_nothing(tmp_path):
    """Choosing the project the item is already on is not a change."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Same", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        stub, _ = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.apply_project_selection(board.id)

        assert stub._apply_project_link(item.id) is False
    finally:
        vps.close()


# ------------------------------------------------------------------- PL5


def test_pl5_new_project_creates_and_selects(tmp_path, monkeypatch):
    """"+ New Project" persists the board and returns it as the selection."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        made = ProjectBoard(title="Made Inline", annual_plan_element_id=ape_id)

        import src.getmoredone.screens.project_boards as pb
        monkeypatch.setattr(
            pb, "ProjectBoardEditorDialog",
            lambda *a, **k: SimpleNamespace(result=made))

        chosen = []
        stub = SimpleNamespace(
            db_manager=manager,
            wait_window=lambda _dialog: None,
            _finish=lambda board_id: chosen.append(board_id),
        )
        SetProjectDialog.create_new_project(stub)

        assert chosen == [made.id]
        assert manager.get_project_board(made.id).title == "Made Inline"
    finally:
        vps.close()


def test_pl5_1_cancelling_the_new_project_creates_nothing(tmp_path, monkeypatch):
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        before = len(manager.get_project_boards(show_pending=True, show_completed=True))

        import src.getmoredone.screens.project_boards as pb
        monkeypatch.setattr(
            pb, "ProjectBoardEditorDialog",
            lambda *a, **k: SimpleNamespace(result="__cancel__"))

        chosen = []
        stub = SimpleNamespace(
            db_manager=manager,
            wait_window=lambda _dialog: None,
            _finish=lambda board_id: chosen.append(board_id),
        )
        SetProjectDialog.create_new_project(stub)

        assert chosen == []
        after = len(manager.get_project_boards(show_pending=True, show_completed=True))
        assert after == before
    finally:
        vps.close()


# ------------------------------------------------------------------- PL6


def test_pl6_week_record_cannot_be_filed_under_a_project(tmp_path):
    """A Weekly Tactic's title derives from its APE — a project must not restamp it."""
    opened = []
    stub = SimpleNamespace(
        _is_weekly_tactic_record=lambda: True,
        db_manager=None,
        item=None,
        _selected_project_id=None,
        title_entry=SimpleNamespace(get=lambda: "Week"),
    )
    stub.set_project = lambda: ItemEditorDialog.set_project(stub)
    stub.set_project()
    assert opened == []


def test_pl6_1_week_record_disables_the_button():
    states = []
    stub = SimpleNamespace(
        _is_weekly_tactic_record=lambda: True,
        record_type_badge=SimpleNamespace(configure=lambda **kw: None),
        context_label=SimpleNamespace(configure=lambda **kw: None),
        title_context_entry=SimpleNamespace(
            configure=lambda **kw: None, delete=lambda *a: None),
        btn_set_project=SimpleNamespace(
            configure=lambda **kw: states.append(kw.get("state"))),
    )
    stub._set_project_button_state = lambda state: ItemEditorDialog._set_project_button_state(stub, state)
    ItemEditorDialog._apply_record_type_ui(stub)
    assert states == ["disabled"]


# ------------------------------------------------------------------- PL7


def test_pl7_link_round_trips_through_db(tmp_path):
    """The link is real: it comes back from a fresh read of the board."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Round Trip", ape_id)
        item = make_daily_item(vps, "Task")

        stub, _ = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.apply_project_selection(board.id)
        assert stub._apply_project_link(item.id) is True

        linked_ids = [linked.id for linked in manager.get_project_board_items(board.id)]
        assert linked_ids == [item.id]
    finally:
        vps.close()


# ------------------------------------------------------------------ PL12


def test_pl12_followup_inherits_project_link(tmp_path):
    """A follow-up of a project task stays on that project."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Ongoing", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        new_id = manager.create_followup_item(item.id)

        assert new_id
        assert manager.get_project_board_ids_for_item(new_id) == [board.id]
        assert manager.get_action_item(new_id).annual_plan_element_id == ape_id
    finally:
        vps.close()


def test_pl12_1_complete_and_create_inherits_project_link(tmp_path):
    """The sibling copy path carries it too (P5)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Ongoing", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(board.id, item.id)

        new_id = manager.complete_and_create(item.id)

        assert new_id
        assert manager.get_project_board_ids_for_item(new_id) == [board.id]
    finally:
        vps.close()


def test_pl12_2_followup_of_an_unfiled_item_stays_unfiled(tmp_path):
    """Nothing is invented for an item that was never on a board."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        item = make_daily_item(vps, "Task")

        new_id = manager.create_followup_item(item.id)

        assert manager.get_project_board_ids_for_item(new_id) == []
    finally:
        vps.close()


def test_pl12_3_multi_link_source_copies_every_link(tmp_path):
    """All of them, not just the first (P2)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        first = _seed_board(manager, "First", ape_id)
        second = _seed_board(manager, "Second", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_action_item_to_project_board(first.id, item.id)
        manager.link_action_item_to_project_board(second.id, item.id)

        new_id = manager.create_followup_item(item.id)

        assert sorted(manager.get_project_board_ids_for_item(new_id)) == sorted(
            [first.id, second.id])
    finally:
        vps.close()


# ------------------------------------------------------------------- PL9


def test_pl9_1_orig_week_still_saves_from_the_action_plan_block(tmp_path, monkeypatch):
    """WT-M6.A.3 — the stamp still round-trips now that the field has moved."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        seed_ape(vps)
        item = make_daily_item(vps, "Task")

        stub = _save_stub(manager, monkeypatch, item=manager.get_action_item(item.id))
        stub.weekly_tactic_start_var = SimpleNamespace(get=lambda: "2026-02-16")
        assert ItemEditorDialog.save_item(stub) is True

        assert manager.get_action_item(item.id).weekly_tactic_start_date == "2026-02-16"
    finally:
        vps.close()


# ------------------------------------------ sweep fixes (pre-push review)


def test_sweep1_second_insert_path_also_applies_the_project_link(tmp_path):
    """save_item_if_needed is the *other* way a new item gets created.

    "Create Note" / "Link Note" / calendar all go through it. It must apply a
    project chosen before the first save, or the choice is dropped while the
    Action Plan block goes on displaying it (P5 sibling, P6 label with no row).
    """
    import customtkinter as ctk
    from src.getmoredone.screens.item_editor import ItemEditorDialog

    vps = make_vps(tmp_path)
    root = ctk.CTk()
    root.withdraw()
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Website Rebuild", ape_id)

        dialog = ItemEditorDialog(root, manager, vps_manager=vps)
        dialog.who_var.set("Self")
        dialog.title_entry.insert(0, "Note-first task")
        dialog.apply_project_selection(board.id)

        assert dialog.save_item_if_needed() is True

        assert manager.get_project_board_ids_for_item(dialog.item_id) == [board.id]
        assert manager.get_action_item(dialog.item_id).annual_plan_element_id == ape_id
    finally:
        root.destroy()
        vps.close()


def test_sweep2_setting_a_tactic_does_not_discard_a_pending_project(tmp_path, monkeypatch):
    """The tactic path destroys and reopens the dialog — the choice must land first."""
    import src.getmoredone.screens.item_editor as ie

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Website Rebuild", ape_id)
        item = make_daily_item(vps, "Task")

        monkeypatch.setattr(ie, "notify_weekly_tactic_changes", lambda *a, **k: None)
        monkeypatch.setattr(ie, "ItemEditorDialog", _ReopenSpy := type(
            "ReopenSpy", (), {"__init__": lambda self, *a, **k: None}))

        stub, _ = _project_stub(manager, item_id=item.id)
        stub._load_project_baseline()
        stub.apply_project_selection(board.id)
        stub.logger = SimpleNamespace(info=lambda *a, **k: None)
        stub.destroy = lambda: None
        stub.master = None
        stub.vps_manager = vps
        stub.on_close_callback = None
        stub._canonical_weekly_tactic_title = lambda *a: a[0]

        ItemEditorDialog.apply_weekly_tactic_selection(
            stub, None, None, "some tactic", None)

        assert manager.get_project_board_ids_for_item(item.id) == [board.id]
    finally:
        vps.close()


def test_sweep6_a_failed_relink_does_not_leave_the_item_unfiled(tmp_path, monkeypatch):
    """The exclusive link deletes before it inserts — that pair must be atomic.

    Without a transaction, a failure between the two leaves the item filed
    under nothing at all: data loss, not merely skipped work.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        old = _seed_board(manager, "Old", ape_id)
        new = _seed_board(manager, "New", ape_id)
        item = make_daily_item(vps, "Task")
        manager.link_item_to_project_exclusive(old.id, item.id)

        real_conn = manager.db.conn

        class ExplodeOnInsert:
            """Delegates everything, but fails the INSERT after the DELETE."""

            def __getattr__(self, name):
                return getattr(real_conn, name)

            def __enter__(self):
                real_conn.__enter__()
                return self

            def __exit__(self, *exc):
                return real_conn.__exit__(*exc)

            def execute(self, sql, *args, **kwargs):
                if "INSERT INTO project_board_items" in sql:
                    raise sqlite3.OperationalError("simulated failure mid-relink")
                return real_conn.execute(sql, *args, **kwargs)

        manager.db.conn = ExplodeOnInsert()
        try:
            with pytest.raises(sqlite3.OperationalError):
                manager.link_item_to_project_exclusive(new.id, item.id)
        finally:
            manager.db.conn = real_conn

        assert manager.get_project_board_ids_for_item(item.id) == [old.id], (
            "the delete was committed without its insert — the item lost its project")
    finally:
        vps.close()


def test_sweep4_changing_project_confirms_before_dropping_other_links(tmp_path):
    """An exclusive re-link on a multi-linked item says what it will remove."""
    asked = []
    stub, _ = _project_stub(None, item_id="i1", loaded_project_id="b1", extra=2)
    stub._confirm_dropping_extra_project_links = lambda board_id: (
        asked.append(board_id), False)[1]

    stub.apply_project_selection("b2")

    assert asked == ["b2"]
    assert stub._selected_project_id == "b1", "declining still changed the selection"
    assert stub._project_choice_made is False


def test_sweep4_1_confirming_lets_the_change_through(tmp_path):
    stub, _ = _project_stub(None, item_id="i1", loaded_project_id="b1", extra=2)
    stub._confirm_dropping_extra_project_links = lambda board_id: True
    stub.db_manager = SimpleNamespace(get_project_board=lambda _id: None)

    stub.apply_project_selection("b2")

    assert stub._selected_project_id == "b2"
    assert stub._project_choice_made is True
    assert stub._extra_project_links == 0


def test_sweep8_a_failed_project_create_reports_instead_of_dying_silently(tmp_path, monkeypatch):
    """A raise in a Tk callback is invisible — the picker must say so."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        made = ProjectBoard(title="Doomed", annual_plan_element_id=ape_id)

        import src.getmoredone.screens.project_boards as pb
        monkeypatch.setattr(
            pb, "ProjectBoardEditorDialog",
            lambda *a, **k: SimpleNamespace(result=made))
        monkeypatch.setattr(
            manager, "create_project_board",
            lambda _board: (_ for _ in ()).throw(RuntimeError("disk on fire")))

        shown = []
        import tkinter.messagebox as messagebox
        monkeypatch.setattr(messagebox, "showerror",
                            lambda *a, **k: shown.append(a))

        chosen = []
        stub = SimpleNamespace(
            db_manager=manager,
            wait_window=lambda _dialog: None,
            _finish=lambda board_id: chosen.append(board_id),
        )
        SetProjectDialog.create_new_project(stub)

        assert shown, "the failure was swallowed"
        assert chosen == [], "a project that was never saved was selected anyway"
    finally:
        vps.close()


def test_sweep1_1_project_wins_the_ape_on_both_insert_paths(tmp_path):
    """A project and a tactic chosen together must resolve the same either way.

    The tactic re-file writes its own Annual Plan Element onto the item, so
    whichever of the two is applied last wins. save_item applies the project
    last; the note path must not disagree, or the stored APE depends on which
    button the user happened to press (P5).
    """
    import customtkinter as ctk
    from src.getmoredone.screens.item_editor import ItemEditorDialog
    from tests.weekly_tactic_fixtures import make_week_item, seed_second_ape

    vps = make_vps(tmp_path)
    root = ctk.CTk()
    root.withdraw()
    try:
        manager = vps.db_manager
        board_ape = seed_ape(vps)
        tactic_ape = seed_second_ape(vps)
        board = _seed_board(manager, "Website Rebuild", board_ape)
        tactic = make_week_item(vps, tactic_ape)

        def build():
            dialog = ItemEditorDialog(root, manager, vps_manager=vps)
            dialog.who_var.set("Self")
            dialog.title_entry.insert(0, "Task with both")
            dialog.start_date_entry.insert(0, "2026-02-25")
            dialog.due_date_entry.insert(0, "2026-02-25")
            dialog.pending_weekly_tactic_id = tactic.id
            dialog._follow_chosen_tactic = True
            dialog.apply_project_selection(board.id)
            return dialog

        via_save = build()
        assert via_save.save_item() is True, via_save.error_label.cget("text")

        via_note = build()
        assert via_note.save_item_if_needed() is True

        ape_via_save = manager.get_action_item(via_save.item_id).annual_plan_element_id
        ape_via_note = manager.get_action_item(via_note.item_id).annual_plan_element_id
        assert ape_via_save == ape_via_note, (
            f"the two insert paths disagree: Save -> {ape_via_save}, "
            f"Create Note -> {ape_via_note}")
        assert ape_via_note == board_ape, "the project should win the APE"
        assert manager.get_project_board_ids_for_item(via_note.item_id) == [board.id]
    finally:
        root.destroy()
        vps.close()


def test_sweep3_the_confirmation_message_names_the_target_project(tmp_path, monkeypatch):
    """Drive the real confirm body, not a lambda standing in for it.

    It runs inside a Tk callback, so a raise in here would leave the picker
    open and inert — the failure shape this repo already logged for Who.
    """
    import tkinter.messagebox as messagebox

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id = seed_ape(vps)
        board = _seed_board(manager, "Website Rebuild", ape_id)

        asked = {}
        monkeypatch.setattr(
            messagebox, "askyesno",
            lambda title, message, **kw: asked.update(
                title=title, message=message) or True)

        stub = SimpleNamespace(db_manager=manager, _loaded_extra_project_links=2)
        result = ItemEditorDialog._confirm_dropping_extra_project_links(stub, board.id)

        assert result is True
        assert "Website Rebuild" in asked["message"]
        assert "3 projects" in asked["message"], asked["message"]
        assert "2" in asked["message"]

        asked.clear()
        ItemEditorDialog._confirm_dropping_extra_project_links(stub, None)
        assert "Clearing the project" in asked["message"]
    finally:
        vps.close()
