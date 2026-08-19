"""The Who field's contact autocomplete.

Regression: typing in Who did nothing at all. ``on_who_search`` opens with
``if self.suggestions_hide_job``, an attribute nothing ever initialised, so the
first keystroke raised AttributeError inside a Tk callback — which Tk prints to
stderr and swallows. No dropdown, no error on screen, a field that looked dead.
``selected_contact_id`` had the same hole and broke saving a new item.

Driven through a real dialog against a real DatabaseManager: a stub would have
supplied the very attributes whose absence was the bug.
"""

import customtkinter as ctk
import pytest

from src.getmoredone.models import ActionItem, Contact
from src.getmoredone.screens.item_editor import ItemEditorDialog
from src.getmoredone.screens.item_editor_contacts import ItemEditorContactsMixin
from src.getmoredone.vps_manager import VPSManager


@pytest.fixture
def vps(tmp_path):
    manager = VPSManager(str(tmp_path / "contacts.db"))
    yield manager
    manager.close()


@pytest.fixture
def root():
    window = ctk.CTk()
    window.withdraw()
    yield window
    window.destroy()


def _seed_contacts(manager):
    manager.create_contact(Contact(name="Acme Corp", contact_type="Client"))
    manager.create_contact(Contact(name="Alice Baker", contact_type="Contact"))
    manager.create_contact(Contact(name="Zeta Ltd", contact_type="Client"))


def test_who_autocomplete_state_is_declared_on_the_mixin():
    """The attributes on_who_search reads exist before any dialog is built."""
    assert ItemEditorContactsMixin.suggestions_hide_job is None
    assert ItemEditorContactsMixin.contact_suggestions_frame is None
    assert ItemEditorContactsMixin.selected_contact_id is None


def test_typing_in_who_opens_the_suggestions_dropdown(root, vps):
    """The actual reported symptom: type in Who, get matching contacts."""
    _seed_contacts(vps.db_manager)
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)

    dialog.who_var.set("Ac")
    dialog.on_who_search()

    assert dialog.contact_suggestions_frame is not None, "no dropdown appeared"
    labels = [
        child.cget("text")
        for child in dialog.contact_suggestions_frame.winfo_children()
    ]
    # search_contacts matches anywhere in the name, so "Ac" reaches Acme Corp
    # but not the other two.
    assert any("Acme Corp" in text for text in labels)
    assert not any("Alice Baker" in text for text in labels)
    assert not any("Zeta Ltd" in text for text in labels)


def test_clearing_who_hides_the_dropdown(root, vps):
    _seed_contacts(vps.db_manager)
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)

    dialog.who_var.set("A")
    dialog.on_who_search()
    assert dialog.contact_suggestions_frame is not None

    dialog.who_var.set("")
    dialog.on_who_search()

    assert dialog.contact_suggestions_frame is None
    assert dialog.selected_contact_id is None


def test_selecting_a_contact_fills_who_and_links_the_contact(root, vps):
    _seed_contacts(vps.db_manager)
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)
    contact = vps.db_manager.search_contacts("Acme", active_only=True)[0]

    dialog.select_contact(contact)

    assert dialog.who_var.get() == "Acme Corp"
    assert dialog.selected_contact_id == contact.id
    assert dialog.contact_suggestions_frame is None


def test_a_new_item_has_no_contact_until_one_is_chosen(root, vps):
    """selected_contact_id is readable on a brand-new item.

    Reading it is the first thing save_item does with the Who field; when the
    attribute was missing, the save died and surfaced only as a generic error
    message in the dialog.
    """
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)

    assert dialog.selected_contact_id is None


def test_saving_a_new_item_without_a_contact_succeeds(root, vps):
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)
    dialog.who_var.set("Self")
    dialog.title_entry.insert(0, "A task with no contact")

    assert dialog.save_item() is True, dialog.error_label.cget("text")

    stored = vps.db_manager.get_action_item(dialog.item_id)
    assert stored is not None
    assert stored.contact_id is None


def test_saving_a_new_item_carries_the_chosen_contact(root, vps):
    _seed_contacts(vps.db_manager)
    dialog = ItemEditorDialog(root, vps.db_manager, vps_manager=vps)
    contact = vps.db_manager.search_contacts("Acme", active_only=True)[0]

    dialog.select_contact(contact)
    dialog.title_entry.insert(0, "A task for Acme")

    assert dialog.save_item() is True, dialog.error_label.cget("text")

    stored = vps.db_manager.get_action_item(dialog.item_id)
    assert stored.who == "Acme Corp"
    assert stored.contact_id == contact.id
