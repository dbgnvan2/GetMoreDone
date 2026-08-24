"""
Tests for Item Editor dialog functionality.
"""

import pytest
import tempfile
import os
from datetime import date, timedelta
from types import SimpleNamespace

from src.getmoredone.database import Database
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ActionItem, Defaults, PriorityFactors
from src.getmoredone.screens.item_editor import ItemEditorDialog
from src.getmoredone.screens.vps_editors import _show_dialog_after_layout


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()

    db_manager = DatabaseManager(temp_file.name)
    yield db_manager

    db_manager.close()
    os.unlink(temp_file.name)


def test_date_offset_application(temp_db):
    """Test that date offsets are correctly applied from defaults."""
    # Create system defaults with date offsets
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=0,  # Today
        due_offset_days=7     # One week from today
    )
    temp_db.save_defaults(system_defaults)

    # Create a new item (simulating form submission with defaults applied)
    item = ActionItem(who="TestUser", title="Test Task")

    # Simulate what the item editor does: apply defaults including date offsets
    retrieved_defaults = temp_db.get_defaults("system")

    # Calculate expected dates
    today = date.today()
    expected_start = today + \
        timedelta(days=retrieved_defaults.start_offset_days)
    expected_due = today + timedelta(days=retrieved_defaults.due_offset_days)

    # Apply date offsets as the form would
    item.start_date = expected_start.strftime("%Y-%m-%d")
    item.due_date = expected_due.strftime("%Y-%m-%d")

    assert item.start_date == today.strftime("%Y-%m-%d")
    assert item.due_date == (today + timedelta(days=7)).strftime("%Y-%m-%d")


def test_who_specific_date_offsets(temp_db):
    """Test that who-specific date offsets override system defaults."""
    # Create system defaults
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=0,
        due_offset_days=7
    )
    temp_db.save_defaults(system_defaults)

    # Create who-specific defaults with different offsets
    who_defaults = Defaults(
        scope_type="who",
        scope_key="UrgentClient",
        start_offset_days=0,
        due_offset_days=1  # Tomorrow instead of 7 days
    )
    temp_db.save_defaults(who_defaults)

    # Retrieve who defaults
    retrieved_who_defaults = temp_db.get_defaults("who", "UrgentClient")

    assert retrieved_who_defaults.due_offset_days == 1
    assert retrieved_who_defaults.start_offset_days == 0


def test_date_offset_none_handling(temp_db):
    """Test that None date offsets are handled correctly."""
    # Create defaults with no date offsets
    system_defaults = Defaults(
        scope_type="system",
        importance=PriorityFactors.IMPORTANCE["Medium"],
        start_offset_days=None,
        due_offset_days=None
    )
    temp_db.save_defaults(system_defaults)

    retrieved = temp_db.get_defaults("system")
    assert retrieved.start_offset_days is None
    assert retrieved.due_offset_days is None
    assert retrieved.importance == PriorityFactors.IMPORTANCE["Medium"]


def test_negative_date_offsets(temp_db):
    """Test that negative date offsets work (dates in the past)."""
    # Create defaults with negative offsets
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=-7,  # One week ago
        due_offset_days=0      # Today
    )
    temp_db.save_defaults(system_defaults)

    retrieved = temp_db.get_defaults("system")

    # Calculate expected dates
    today = date.today()
    expected_start = today + timedelta(days=-7)
    expected_due = today

    assert retrieved.start_offset_days == -7
    assert retrieved.due_offset_days == 0


def test_defaults_precedence_with_offsets(temp_db):
    """Test precedence: who defaults override system defaults for date offsets."""
    # Create both types of defaults
    system_defaults = Defaults(
        scope_type="system",
        start_offset_days=0,
        due_offset_days=7,
        importance=PriorityFactors.IMPORTANCE["Low"]
    )
    temp_db.save_defaults(system_defaults)

    who_defaults = Defaults(
        scope_type="who",
        scope_key="HighPriorityClient",
        due_offset_days=1,  # Override due date
        importance=PriorityFactors.IMPORTANCE["Critical"]
    )
    temp_db.save_defaults(who_defaults)

    # Simulate defaults application logic
    system = temp_db.get_defaults("system")
    who = temp_db.get_defaults("who", "HighPriorityClient")

    # Who defaults should override
    final_due_offset = who.due_offset_days if who and who.due_offset_days is not None else system.due_offset_days
    final_start_offset = who.start_offset_days if who and who.start_offset_days is not None else system.start_offset_days
    final_importance = who.importance if who and who.importance is not None else system.importance

    assert final_due_offset == 1  # From who defaults
    # From system defaults (who didn't override)
    assert final_start_offset == 0
    assert final_importance == PriorityFactors.IMPORTANCE["Critical"]


def test_date_calculation_edge_cases(temp_db):
    """Test date calculation with various offsets."""
    today = date.today()

    # Test various offsets
    offsets_to_test = [0, 1, 7, 14, 30, 365, -1, -7]

    for offset in offsets_to_test:
        expected = today + timedelta(days=offset)
        assert expected == today + timedelta(days=offset)


def test_item_creation_with_all_defaults(temp_db):
    """Test creating an item with all defaults including date offsets."""
    # Create comprehensive defaults
    defaults = Defaults(
        scope_type="system",
        importance=PriorityFactors.IMPORTANCE["High"],
        urgency=PriorityFactors.URGENCY["High"],
        size=PriorityFactors.SIZE["M"],
        value=PriorityFactors.VALUE["L"],
        group="DefaultGroup",
        category="DefaultCategory",
        planned_minutes=60,
        start_offset_days=0,
        due_offset_days=3
    )
    temp_db.save_defaults(defaults)

    # Create item with defaults applied
    item = ActionItem(who="TestUser", title="Comprehensive Test")
    item_id = temp_db.create_action_item(item, apply_defaults=True)

    # Retrieve and verify
    retrieved = temp_db.get_action_item(item_id)
    assert retrieved.importance == PriorityFactors.IMPORTANCE["High"]
    assert retrieved.urgency == PriorityFactors.URGENCY["High"]
    assert retrieved.size == PriorityFactors.SIZE["M"]
    assert retrieved.value == PriorityFactors.VALUE["L"]
    assert retrieved.group == "DefaultGroup"
    assert retrieved.category == "DefaultCategory"
    assert retrieved.planned_minutes == 60


def test_priority_score_calculation_with_defaults(temp_db):
    """Test that priority score is calculated correctly with defaulted factors."""
    defaults = Defaults(
        scope_type="system",
        importance=10,  # High
        urgency=5,      # Medium
        size=4,         # M
        value=8         # L
    )
    temp_db.save_defaults(defaults)

    item = ActionItem(who="User", title="Test")
    item_id = temp_db.create_action_item(item, apply_defaults=True)

    retrieved = temp_db.get_action_item(item_id)
    expected_score = 10 * 5 * 4 * 8  # 1600
    assert retrieved.priority_score == expected_score


def test_item_editor_do_center_uses_requested_dialog_size():
    calls = []

    dialog = SimpleNamespace(
        master=SimpleNamespace(
            update_idletasks=lambda: calls.append("parent_update"),
            winfo_rootx=lambda: 100,
            winfo_rooty=lambda: 50,
            winfo_width=lambda: 1200,
            winfo_height=lambda: 800,
        ),
        winfo_reqwidth=lambda: 920,
        winfo_reqheight=lambda: 550,
        winfo_width=lambda: 1,
        winfo_height=lambda: 1,
        geometry=lambda value: calls.append(("geometry", value)),
        update_idletasks=lambda: calls.append("dialog_update"),
        specified_x=None,
        specified_y=None,
    )

    ItemEditorDialog._do_center(dialog)

    assert ("geometry", "920x680+240+110") in calls
    assert "parent_update" in calls
    assert "dialog_update" in calls


def test_item_editor_finalize_reveals_after_centering():
    calls = []

    dialog = SimpleNamespace(
        update_idletasks=lambda: calls.append("update"),
        _do_center=lambda: calls.append("center"),
        deiconify=lambda: calls.append("show"),
        after_idle=lambda callback: (calls.append("after_idle"), callback()),
        _show_dialog_contents=lambda: calls.append("finish"),
    )

    ItemEditorDialog._finalize_dialog_window(dialog)

    assert calls == ["update", "center", "show", "after_idle", "finish"]


def test_vps_editor_show_dialog_after_layout_centers_then_reveals():
    calls = []

    dialog = SimpleNamespace(
        transient=lambda parent: calls.append(("transient", parent)),
        grab_set=lambda: calls.append("grab"),
        update_idletasks=lambda: calls.append("dialog_update"),
        winfo_reqwidth=lambda: 700,
        winfo_reqheight=lambda: 900,
        winfo_width=lambda: 1,
        winfo_height=lambda: 1,
        geometry=lambda value: calls.append(("geometry", value)),
        deiconify=lambda: calls.append("show"),
        after_idle=lambda callback: (calls.append("after_idle"), callback()),
        lift=lambda: calls.append("lift"),
        focus_force=lambda: calls.append("focus"),
    )
    parent = SimpleNamespace(
        update_idletasks=lambda: calls.append("parent_update"),
        winfo_rootx=lambda: 100,
        winfo_rooty=lambda: 50,
        winfo_width=lambda: 1200,
        winfo_height=lambda: 1000,
    )

    _show_dialog_after_layout(dialog, parent)

    assert ("geometry", "700x900+350+100") in calls
    assert calls[:4] == [("transient", parent), "grab", "dialog_update", "parent_update"]
    assert "show" in calls
    assert "after_idle" in calls
    assert "lift" in calls
    assert "focus" in calls
    assert calls.index("show") < calls.index("after_idle") < calls.index("lift") < calls.index("focus")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


def test_create_tasks_from_next_action(temp_db):
    """Test creating child tasks from Next Action field lines."""
    # Create parent item
    parent = ActionItem(
        who="TestUser",
        title="Launch Website",
        description="Main launch project",
        next_action="Design homepage\nWrite product copy\nSet up payment system\nTest checkout flow",
        start_date="2024-01-15",
        due_date="2024-01-20",
        importance=10,
        urgency=10,
        size=8,
        value=8,
        group="Projects",
        category="Development"
    )
    parent_id = temp_db.create_action_item(parent)

    # Simulate the create_tasks functionality
    next_action_text = "Design homepage\nWrite product copy\nSet up payment system\nTest checkout flow"
    lines = [line.strip()
             for line in next_action_text.split('\n') if line.strip()]

    created_items = []
    for line in lines:
        child_item = ActionItem(
            who=parent.who,
            title=f"{parent.title} - {line}",
            description=line,
            parent_id=parent_id,
            start_date=parent.start_date,
            due_date=parent.due_date,
            importance=parent.importance,
            urgency=parent.urgency,
            size=parent.size,
            value=parent.value,
            group=parent.group,
            category=parent.category,
            status="open"
        )
        child_id = temp_db.create_action_item(child_item, apply_defaults=False)
        created_items.append(child_id)

    # Verify all children were created
    assert len(created_items) == 4

    # Verify children have correct properties
    children = temp_db.get_children(parent_id)
    assert len(children) == 4

    # Check first child
    first_child = temp_db.get_action_item(created_items[0])
    assert first_child.title == "Launch Website - Design homepage"
    assert first_child.description == "Design homepage"
    assert first_child.parent_id == parent_id
    assert first_child.start_date == parent.start_date
    assert first_child.due_date == parent.due_date
    assert first_child.who == parent.who

    # Check last child
    last_child = temp_db.get_action_item(created_items[3])
    assert last_child.title == "Launch Website - Test checkout flow"
    assert last_child.description == "Test checkout flow"


def test_create_tasks_with_empty_lines(temp_db):
    """Test create tasks handles empty lines correctly."""
    parent = ActionItem(
        who="TestUser",
        title="Test Project",
        next_action="Task 1\n\nTask 2\n  \nTask 3",
        start_date="2024-01-15",
        due_date="2024-01-20"
    )
    parent_id = temp_db.create_action_item(parent)

    # Simulate filtering empty lines
    next_action_text = "Task 1\n\nTask 2\n  \nTask 3"
    lines = [line.strip()
             for line in next_action_text.split('\n') if line.strip()]

    # Should only have 3 tasks (empty lines filtered out)
    assert len(lines) == 3
    assert lines == ["Task 1", "Task 2", "Task 3"]


def test_duplicate_saves_current_changes(temp_db):
    """Test that duplicate button saves current changes before duplicating."""
    # Create original item
    original = ActionItem(
        who="TestUser",
        title="Original Task",
        description="Original description",
        importance=10,
        urgency=10
    )
    original_id = temp_db.create_action_item(original)

    # Simulate editing and duplicating
    # (In actual UI, save would be called, then duplicate)
    original_updated = temp_db.get_action_item(original_id)
    original_updated.description = "Updated description"
    temp_db.update_action_item(original_updated)

    # Now duplicate
    duplicate_id = temp_db.duplicate_action_item(original_id)

    # Verify duplicate has the UPDATED description
    duplicate = temp_db.get_action_item(duplicate_id)
    assert duplicate.description == "Updated description"
    assert duplicate.title == "Original Task"
    assert duplicate.id != original_id


# --- ⏱ Timer button on the editor (save-first, then open the working-mode timer) ---

def test_start_timer_aborts_when_save_fails(monkeypatch):
    """If the save-first step fails validation, the timer must not open."""
    import src.getmoredone.screens.timer_window as tw
    opened = []
    monkeypatch.setattr(tw, "TimerWindow", lambda *a, **k: opened.append((a, k)))

    dialog = SimpleNamespace(
        save_item=lambda: False,
        item=SimpleNamespace(id="x"),
        db_manager=object(),
        _on_timer_closed=lambda: None,
    )
    ItemEditorDialog.start_timer(dialog)

    assert opened == []


def test_start_timer_opens_timer_after_successful_save(monkeypatch):
    """A successful save opens the timer on the current (open) item with a callback."""
    import src.getmoredone.screens.timer_window as tw
    opened = []
    monkeypatch.setattr(tw, "TimerWindow", lambda *a, **k: opened.append((a, k)))

    item = SimpleNamespace(id="abc", status="open")
    db = object()
    def closer():
        return None
    dialog = SimpleNamespace(
        save_item=lambda: True,
        item=item,
        db_manager=db,
        _on_timer_closed=closer,
        _current_timer_field_values=lambda: {
            "description": "", "next_action": "", "planned_minutes": ""},
    )
    ItemEditorDialog.start_timer(dialog)

    assert len(opened) == 1
    args, kwargs = opened[0]
    assert args[0] is dialog          # parent
    assert args[1] is db              # db_manager
    assert args[2] is item           # the item being edited
    assert kwargs.get("on_close") is closer
    # A snapshot is captured so the on-close reload can avoid clobbering edits.
    assert hasattr(dialog, "_pre_timer_field_values")


def test_start_timer_aborts_on_completed_item(monkeypatch):
    """Even if save succeeds, a completed item must not open a timer."""
    import src.getmoredone.screens.timer_window as tw
    opened = []
    monkeypatch.setattr(tw, "TimerWindow", lambda *a, **k: opened.append((a, k)))
    dialog = SimpleNamespace(
        save_item=lambda: True,
        item=SimpleNamespace(id="x", status="completed"),
    )
    ItemEditorDialog.start_timer(dialog)
    assert opened == []


def test_on_timer_closed_reloads_notes_and_refreshes_parent():
    """Closing the timer reloads notes, refreshes the button state, then the parent."""
    calls = []
    dialog = SimpleNamespace(
        winfo_exists=lambda: True,
        _reload_editable_notes=lambda: calls.append("reload"),
        _refresh_timer_button_state=lambda: calls.append("btnstate"),
        on_close_callback=lambda: calls.append("refresh"),
    )
    ItemEditorDialog._on_timer_closed(dialog)
    assert calls == ["reload", "btnstate", "refresh"]


def test_refresh_timer_button_state_disables_when_completed():
    states = []
    dialog = SimpleNamespace(
        btn_timer=SimpleNamespace(configure=lambda **k: states.append(k)),
        item=SimpleNamespace(status="completed"),
    )
    ItemEditorDialog._refresh_timer_button_state(dialog)
    assert states == [{"state": "disabled"}]


def test_refresh_timer_button_state_noop_when_open():
    states = []
    dialog = SimpleNamespace(
        btn_timer=SimpleNamespace(configure=lambda **k: states.append(k)),
        item=SimpleNamespace(status="open"),
    )
    ItemEditorDialog._refresh_timer_button_state(dialog)
    assert states == []


def test_refresh_timer_button_state_noop_without_button():
    """A completed item whose editor never built a Timer button.

    "Must not raise" was the whole test — an exception does fail it, but
    nothing said so, and nothing distinguished "handled the missing button"
    from "returned early for some other reason". Both are asserted now.
    """
    dialog = SimpleNamespace(item=SimpleNamespace(status="completed"))

    ItemEditorDialog._refresh_timer_button_state(dialog)

    assert not hasattr(dialog, "timer_button"), (
        "the method invented a timer button that the editor never built"
    )


class _FakeWidget:
    """Minimal stand-in for a CTk text/entry widget in reload tests."""
    def __init__(self, initial=""):
        self.content = initial
    def get(self, *args):
        return self.content
    def delete(self, *args):
        self.content = ""
    def insert(self, index, text):
        self.content = text


def _reload_dialog(fresh, snapshot, current):
    desc = _FakeWidget(current["description"])
    nxt = _FakeWidget(current["next_action"])
    pm = _FakeWidget(current["planned_minutes"])
    # RP-4.1: the timer's start dialog can write the deliverable, so it is one
    # of the fields the reload has to consider. Callers that predate it pass no
    # "deliverable" key and get an empty one.
    dlv = _FakeWidget(current.get("deliverable", ""))
    dialog = SimpleNamespace(
        item_id="id1",
        item=None,
        db_manager=SimpleNamespace(get_action_item=lambda i: fresh),
        description_text=desc,
        next_action_text=nxt,
        deliverable_entry=dlv,
        planned_minutes_entry=pm,
        _pre_timer_field_values=snapshot,
        _current_timer_field_values=lambda: {
            "description": desc.get().strip(),
            "next_action": nxt.get().strip(),
            "deliverable": dlv.get().strip(),
            "planned_minutes": pm.get().strip(),
        },
    )
    return dialog, desc, nxt, pm


def test_reload_refreshes_untouched_fields():
    """Dirty-state: the timer changed fields in the DB and the user touched none
    here; all reload (incl. planned_minutes, the P8/P12 revert fix)."""
    fresh = SimpleNamespace(
        description="notes from timer", next_action="do X", planned_minutes=60)
    snap = {"description": "orig", "next_action": "orig na", "planned_minutes": "30"}
    current = dict(snap)  # user left everything untouched -> current == snapshot

    dialog, desc, nxt, pm = _reload_dialog(fresh, snap, current)
    ItemEditorDialog._reload_editable_notes(dialog)

    assert desc.content == "notes from timer"
    assert nxt.content == "do X"
    assert pm.content == "60"
    assert dialog.item is fresh


def test_reload_preserves_field_user_edited_during_timer():
    """A field the user edited here while the timer was open must NOT be clobbered
    by the on-close reload; untouched fields still reload from the DB."""
    fresh = SimpleNamespace(
        description="timer note", next_action="timer na", planned_minutes=60)
    snap = {"description": "orig", "next_action": "orig na", "planned_minutes": "30"}
    # User edited description in the editor; left next_action / planned_minutes alone.
    current = {"description": "MY LIVE EDIT",
               "next_action": "orig na", "planned_minutes": "30"}

    dialog, desc, nxt, pm = _reload_dialog(fresh, snap, current)
    ItemEditorDialog._reload_editable_notes(dialog)

    assert desc.content == "MY LIVE EDIT"   # in-flight edit preserved
    assert nxt.content == "timer na"        # untouched -> reloaded
    assert pm.content == "60"               # untouched -> reloaded


def test_reload_handles_none_planned_minutes():
    """A cleared planned_minutes should blank the entry, not insert 'None'."""
    fresh = SimpleNamespace(description=None, next_action=None, planned_minutes=None)
    snap = {"description": "", "next_action": "", "planned_minutes": "30"}
    current = dict(snap)

    dialog, desc, nxt, pm = _reload_dialog(fresh, snap, current)
    ItemEditorDialog._reload_editable_notes(dialog)

    assert pm.content == ""              # blanked, never the string "None"


# --- save_item() bool return gates close / reopen / duplicate (validation errors) ---

def test_save_and_close_stays_open_on_save_failure():
    calls = []
    dialog = SimpleNamespace(
        save_item=lambda: False,
        on_dialog_close=lambda: calls.append("close"),
    )
    ItemEditorDialog.save_and_close(dialog)
    assert calls == []  # validation error -> dialog stays open


def test_save_and_close_closes_on_success():
    calls = []
    dialog = SimpleNamespace(
        save_item=lambda: True,
        on_dialog_close=lambda: calls.append("close"),
    )
    ItemEditorDialog.save_and_close(dialog)
    assert calls == ["close"]


def test_save_and_new_does_not_reopen_on_failure(monkeypatch):
    import src.getmoredone.screens.item_editor as ie
    real = ie.ItemEditorDialog.save_and_new
    created, closed = [], []
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: created.append((a, k)))
    dialog = SimpleNamespace(
        on_close_callback="cb", save_item=lambda: False,
        on_dialog_close=lambda: closed.append(1),
        master="m", db_manager="db", vps_manager="vps",
    )
    real(dialog)
    assert created == [] and closed == []


def test_save_and_new_reopens_on_success(monkeypatch):
    import src.getmoredone.screens.item_editor as ie
    real = ie.ItemEditorDialog.save_and_new
    created, closed = [], []
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: created.append((a, k)))
    dialog = SimpleNamespace(
        on_close_callback="cb", save_item=lambda: True,
        on_dialog_close=lambda: closed.append(1),
        master="m", db_manager="db", vps_manager="vps",
    )
    real(dialog)
    assert closed == [1] and len(created) == 1


def test_pl11_1_followup_aborts_on_save_failure(monkeypatch):
    """PL11 — a failed save must not leave a follow-up behind.

    This guard used to live on the removed Duplicate button only; the merged
    path is the one that has to carry it now.
    Spec: docs/implementation_plan_2026-08-19_item_editor_project_link.md#pl11
    """
    import src.getmoredone.screens.item_editor as ie
    real = ie.ItemEditorDialog.create_followup
    created, made = [], []
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: created.append((a, k)))
    dialog = SimpleNamespace(
        item_id="id1", save_item=lambda: False,
        db_manager=SimpleNamespace(
            create_followup_item=lambda i: made.append(i) or "new"),
    )
    real(dialog)
    assert made == [] and created == []  # no save -> no follow-up


def test_pl11_followup_saves_first(monkeypatch):
    """PL11 — the merged path saves the on-screen edits, then copies."""
    import src.getmoredone.screens.item_editor as ie
    real = ie.ItemEditorDialog.create_followup
    created, made, order = [], [], []
    monkeypatch.setattr(ie, "ItemEditorDialog", lambda *a, **k: created.append((a, k)))
    dialog = SimpleNamespace(
        item_id="id1",
        save_item=lambda: order.append("save") or True,
        db_manager=SimpleNamespace(
            create_followup_item=lambda i: (order.append("copy"), made.append(i), "newid")[2]),
        winfo_x=lambda: 10, winfo_y=lambda: 20,
        master="m", vps_manager="vps", on_close_callback="cb",
    )
    real(dialog)
    assert made == ["id1"] and len(created) == 1
    assert order == ["save", "copy"], f"copied before saving: {order}"


def test_pl10_1_duplicate_editor_method_is_gone():
    """PL10.1 — one copy path, not two. The wrapper must not reappear."""
    import src.getmoredone.screens.item_editor as ie
    assert not hasattr(ie.ItemEditorDialog, "duplicate_item")


def test_reload_swallows_widget_teardown_error():
    """A widget-teardown error (window closing) during reload must be swallowed,
    not propagated out of the timer's on-close callback (narrowed except)."""
    def boom():
        raise AttributeError("widget gone")
    dialog = SimpleNamespace(
        item_id="id1", item=None,
        db_manager=SimpleNamespace(get_action_item=lambda i: SimpleNamespace(
            description="d", next_action="n", planned_minutes=1)),
        _pre_timer_field_values={},
        _current_timer_field_values=boom,
    )
    ItemEditorDialog._reload_editable_notes(dialog)

    # The point is that the AttributeError was swallowed and the reload still
    # did its job. "Must not raise" alone would also pass on a method that
    # returned immediately without reloading anything.
    assert dialog.item is not None, (
        "the reload swallowed the teardown error but also skipped the reload"
    )
    assert dialog.item.description == "d"
