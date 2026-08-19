"""Obsidian integration — the pieces the note dialogs depend on.

BC3. Converted from a standalone script whose tests returned bools inside
``except Exception: return False``, so pytest ignored the verdict entirely.

One of them did more than lie about its result: ``test_database`` constructed
``DatabaseManager()`` **with no path**, which resolves to the user's real
application database and runs ``initialize_schema()`` on it — schema
migrations, the Weekly Tactic dedupe (which deletes rows) and the invariant
repair (which moves dates). A test suite must never touch production data.
Every database here is a temporary one.

Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#batch-1
"""

import inspect

import pytest

from src.getmoredone.app_settings import AppSettings
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.models import ContactLink, ItemLink
from src.getmoredone.obsidian_utils import (
    create_obsidian_note,
    open_in_obsidian,
    validate_obsidian_setup,
)
from src.getmoredone.screens.item_editor import (
    CreateNoteDialog,
    ItemEditorDialog,
    LinkNoteDialog,
)


@pytest.fixture
def manager(tmp_path):
    """A DatabaseManager on a throwaway file, never the real one."""
    db = DatabaseManager(str(tmp_path / "obsidian.db"))
    yield db
    db.close()


def test_bc3_the_obsidian_helpers_are_importable_and_callable():
    """A broken import fails this test by raising, as it should."""
    assert callable(create_obsidian_note)
    assert callable(open_in_obsidian)
    assert callable(validate_obsidian_setup)


@pytest.mark.parametrize("table", ["item_links", "contact_links"])
def test_bc3_the_link_tables_exist(manager, table):
    row = manager.db.conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()

    assert row is not None, f"{table} is missing — note links cannot be stored"


def test_bc3_an_item_link_round_trips(manager):
    """The table existing is not the same as the link surviving a write."""
    from src.getmoredone.models import ActionItem

    item = ActionItem(who="Self", title="With a note")
    manager.create_action_item(item, apply_defaults=False)
    manager.add_item_link(ItemLink(
        item_id=item.id, url="/vault/note.md", label="note",
        link_type="obsidian_note"))

    links = manager.get_item_links(item.id)

    assert [link.url for link in links] == ["/vault/note.md"]
    assert links[0].link_type == "obsidian_note"


def test_bc3_a_contact_link_round_trips(manager):
    from src.getmoredone.models import Contact

    contact = Contact(name="Acme Corp", contact_type="Client")
    contact_id = manager.create_contact(contact)
    manager.add_contact_link(ContactLink(
        contact_id=contact_id, url="/vault/acme.md", label="acme",
        link_type="obsidian_note"))

    links = manager.get_contact_links(contact_id)

    assert [link.url for link in links] == ["/vault/acme.md"]


@pytest.mark.parametrize("method", ["create_note", "link_existing_note", "load_notes"])
def test_bc3_the_item_editor_exposes_its_note_actions(method):
    assert callable(getattr(ItemEditorDialog, method, None)), (
        f"ItemEditorDialog.{method} is gone — the Notes tab lost a control")


def test_bc3_the_note_dialog_classes_exist():
    assert inspect.isclass(CreateNoteDialog)
    assert inspect.isclass(LinkNoteDialog)


def test_bc3_settings_expose_the_obsidian_fields():
    """Read the dataclass, not the user's saved settings file.

    The original called ``AppSettings.load()`` and printed whatever the machine
    happened to have configured, so it asserted nothing and behaved differently
    on every machine.
    """
    fields = AppSettings.__dataclass_fields__

    assert "obsidian_vault_path" in fields
    assert "obsidian_notes_subfolder" in fields


def test_bc3_validate_obsidian_setup_rejects_a_missing_vault(tmp_path):
    is_valid, message = validate_obsidian_setup(
        str(tmp_path / "no-such-vault"), "GetMoreDone")

    assert is_valid is False
    assert message, "the failure came back with nothing to show the user"


def test_bc3_validate_obsidian_setup_accepts_a_real_vault(tmp_path):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)

    is_valid, message = validate_obsidian_setup(str(vault), "GetMoreDone")

    assert is_valid is True, message
