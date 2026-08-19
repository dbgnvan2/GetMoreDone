"""The Context field is gone from the editor, and its column from the lists.

Context was never a field of its own — only the front half of the stored title,
rejoined on save. It also only read back out of a title whose prefix ended in a
week marker (``W8``), so most items showed an empty Context box while their
title still carried the prefix.

The risk in removing it is data loss: if Title shows only the split *body* while
save writes Title verbatim, every prefixed title is silently truncated on the
next save. The round-trip tests below are the ones that matter.
"""

from pathlib import Path

import customtkinter as ctk
import pytest

from src.getmoredone.models import ActionItem
from src.getmoredone.screens.item_editor import ItemEditorDialog
from src.getmoredone.vps_manager import VPSManager

SCREENS = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"

LIST_VIEWS = ["today.py", "upcoming.py", "all_items.py", "completed.py", "hierarchical.py"]

PREFIXED_TITLE = "PW|LS|Blog - W8 - write blog 3"


@pytest.fixture
def vps(tmp_path):
    manager = VPSManager(str(tmp_path / "no_context.db"))
    yield manager
    manager.close()


@pytest.fixture
def root():
    window = ctk.CTk()
    window.withdraw()
    yield window
    window.destroy()


def _make_item(manager, title=PREFIXED_TITLE):
    item = ActionItem(who="Self", title=title,
                      start_date="2026-02-25", due_date="2026-02-25")
    manager.create_action_item(item, apply_defaults=False)
    return item


def test_the_editor_has_no_context_widgets(root, vps):
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)

    assert not hasattr(dialog, "title_context_entry")
    assert not hasattr(dialog, "context_label")


def test_title_field_shows_the_whole_stored_title(root, vps):
    """Including a prefix the old splitter would have moved into Context."""
    item = _make_item(vps.db_manager)

    dialog = ItemEditorDialog(root, vps.db_manager, item_id=item.id, vps_manager=vps)

    assert dialog.title_entry.get() == PREFIXED_TITLE


def test_saving_an_untouched_prefixed_title_does_not_truncate_it(root, vps):
    """The data-loss case: open a prefixed item, hit Save, title unchanged."""
    item = _make_item(vps.db_manager)
    dialog = ItemEditorDialog(root, vps.db_manager, item_id=item.id, vps_manager=vps)

    assert dialog.save_item() is True, dialog.error_label.cget("text")

    assert vps.db_manager.get_action_item(item.id).title == PREFIXED_TITLE


def test_an_edited_title_is_stored_verbatim(root, vps):
    item = _make_item(vps.db_manager)
    dialog = ItemEditorDialog(root, vps.db_manager, item_id=item.id, vps_manager=vps)

    dialog.title_entry.delete(0, "end")
    dialog.title_entry.insert(0, "PW|LS|Blog - W9 - write blog 4")

    assert dialog.save_item() is True, dialog.error_label.cget("text")

    assert vps.db_manager.get_action_item(item.id).title == "PW|LS|Blog - W9 - write blog 4"


def test_a_plain_title_round_trips_unchanged(root, vps):
    """A title with no prefix — the ordinary case — is untouched either way."""
    item = _make_item(vps.db_manager, title="Just a task")
    dialog = ItemEditorDialog(root, vps.db_manager, item_id=item.id, vps_manager=vps)

    assert dialog.title_entry.get() == "Just a task"
    assert dialog.save_item() is True
    assert vps.db_manager.get_action_item(item.id).title == "Just a task"


def test_a_new_item_saves_its_title_verbatim(root, vps):
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)
    dialog.who_var.set("Self")
    dialog.title_entry.insert(0, "PW|LS|Blog - W8 - brand new")

    assert dialog.save_item() is True, dialog.error_label.cget("text")

    assert vps.db_manager.get_action_item(dialog.item_id).title == "PW|LS|Blog - W8 - brand new"


@pytest.mark.parametrize("module", LIST_VIEWS)
def test_no_list_view_renders_a_context_column(module):
    """No list view reads parsed.context or budgets a context column."""
    source = (SCREENS / module).read_text(encoding="utf-8")

    assert "parsed.context" not in source, f"{module} still renders a Context cell"
    assert 'limits["context"]' not in source, f"{module} still budgets a Context column"
    assert '"Context"' not in source, f"{module} still has a Context header"


def test_the_title_splitter_survives_for_lineage_colours():
    """Deliberately kept: the Scheduler colours rows from the title prefix."""
    from src.getmoredone.screens.title_format import split_action_item_title

    parsed = split_action_item_title(PREFIXED_TITLE)

    assert parsed.context == "PW|LS|Blog - W8"
    assert parsed.title == "write blog 3"
    assert "parsed.context" in (SCREENS / "item_lineage.py").read_text(encoding="utf-8")
