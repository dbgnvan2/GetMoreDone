"""The editor must not report success for a row that no longer exists.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#bp3

`ItemEditorDialog.__init__` does `self.item = db_manager.get_action_item(item_id)`
and leaves `item_id` set when that returns None — the row was deleted from a
list, or from a second editor window, while this one was open.

Before BP3 that state raised `AttributeError` inside `save_item`, which the
`except` turned into a visible "Error: …". BP3's shared builder fabricates a
brand-new `ActionItem` when handed `None`, the save then took the *update*
branch, and `update_action_item` returns True for a row it did not match — so
the editor said "Saved", closed, and discarded every edit (P2: a failure that
reports success; P12: a refactor that turned a loud failure into a silent one).
"""

from types import SimpleNamespace

import pytest

from src.getmoredone.models import ActionItem
from src.getmoredone.screens.item_editor import ItemEditorDialog
from tests.weekly_tactic_fixtures import make_vps, seed_ape


def _entry(value=""):
    return SimpleNamespace(get=lambda *a, **k: value)


def _stub(manager, item_id, item, texts):
    stub = SimpleNamespace(
        db_manager=manager,
        item=item,
        item_id=item_id,
        who_var=_entry("Self"),
        selected_contact_id=None,
        title_entry=_entry("Edited title"),
        description_text=_entry(""),
        next_action_text=_entry(""),
        start_date_entry=_entry("2026-02-25"),
        due_date_entry=_entry("2026-02-25"),
        is_meeting_var=SimpleNamespace(get=lambda: False),
        importance_var=_entry(""),
        urgency_var=_entry(""),
        size_var=_entry(""),
        value_var=_entry(""),
        group_var=_entry(""),
        category_var=_entry(""),
        planned_minutes_entry=_entry(""),
        weekly_tactic_start_var=_entry(""),
        week_action_id=None,
        pending_weekly_tactic_id=None,
        segment_description_id=None,
        _follow_chosen_tactic=False,
        _project_choice_made=False,
        _selected_project_id=None,
        _loaded_project_id=None,
        _extra_project_links=0,
        _loaded_extra_project_links=0,
        NO_PROJECT_TEXT=ItemEditorDialog.NO_PROJECT_TEXT,
        project_label=SimpleNamespace(configure=lambda **kw: None),
        notes_frame=SimpleNamespace(winfo_children=lambda: []),
        error_label=SimpleNamespace(configure=lambda **kw: texts.append(kw.get("text"))),
        after=lambda *a, **k: None,
        logger=SimpleNamespace(warning=lambda *a, **k: None, info=lambda *a, **k: None),
        title=lambda *a, **k: None,
        load_notes=lambda: None,
    )
    for name in ("build_item_from_form", "apply_new_item_fields",
                 "validate_item_for_save", "insert_new_item", "_warn",
                 "extract_factor_value", "_apply_project_link",
                 "refresh_project_display", "save_item", "save_item_if_needed"):
        method = getattr(ItemEditorDialog, name)
        setattr(stub, name, (lambda m: lambda *a, **kw: m(stub, *a, **kw))(method))
    stub._canonical_weekly_tactic_title = lambda *a: a[0]
    return stub


@pytest.fixture
def deleted_item(tmp_path, monkeypatch):
    """An editor holding an id whose row has been deleted underneath it."""
    import src.getmoredone.screens.item_editor as ie
    monkeypatch.setattr(ie, "notify_weekly_tactic_changes", lambda *a, **k: None)

    vps = make_vps(tmp_path)
    manager = vps.db_manager
    seed_ape(vps)
    item = ActionItem(who="Self", title="Doomed")
    manager.create_action_item(item, apply_defaults=False)
    manager.db.conn.execute("DELETE FROM action_items WHERE id = ?", (item.id,))
    manager.db.conn.commit()
    assert manager.get_action_item(item.id) is None
    try:
        yield manager, item.id
    finally:
        vps.close()


def test_save_refuses_when_the_row_is_gone(deleted_item):
    manager, gone_id = deleted_item
    texts = []
    stub = _stub(manager, gone_id, None, texts)

    assert stub.save_item() is False, "the editor reported a successful save"
    assert texts and "no longer exists" in texts[0], texts
    assert "✓ Saved" not in texts

    rows = manager.db.conn.execute(
        "SELECT COUNT(*) AS c FROM action_items").fetchone()["c"]
    assert rows == 0, "a row was written under a fabricated id"


def test_the_note_path_refuses_too(deleted_item):
    """"Create Note" would otherwise attach a note to an item that is gone."""
    manager, gone_id = deleted_item
    texts = []
    stub = _stub(manager, gone_id, None, texts)

    assert stub.save_item_if_needed() is False
    assert texts and "no longer exists" in texts[0], texts


def test_an_ordinary_edit_still_saves(deleted_item, tmp_path):
    """The guard must not fire on the path it shares with every normal save."""
    manager, _gone = deleted_item
    live = ActionItem(who="Self", title="Alive")
    manager.create_action_item(live, apply_defaults=False)
    texts = []
    stub = _stub(manager, live.id, manager.get_action_item(live.id), texts)

    assert stub.save_item() is True, texts
    assert manager.get_action_item(live.id).title == "Edited title"
