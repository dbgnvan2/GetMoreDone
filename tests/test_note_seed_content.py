"""
Regression tests for seeding a new Obsidian note with an Action Item's
Description and Next Action (create-note-from-item flow).
"""

from src.getmoredone.screens.item_editor_notes import ItemEditorNotesMixin


class _FakeTextbox:
    """Minimal stand-in for a CTkTextbox exposing .get(start, end)."""

    def __init__(self, text: str):
        self._text = text

    def get(self, _start, _end):
        return self._text


class _Holder(ItemEditorNotesMixin):
    """Bare host object so we can exercise the mixin method in isolation."""


def test_seed_includes_description_and_next_action():
    h = _Holder()
    h.description_text = _FakeTextbox("From: someone@example.com\nInvitation details\n")
    h.next_action_text = _FakeTextbox("Accept the invitation\n")

    out = h._build_note_seed_content()

    assert "## Description" in out
    assert "Invitation details" in out
    assert "## Next Action" in out
    assert "Accept the invitation" in out
    # Description section comes before Next Action section.
    assert out.index("## Description") < out.index("## Next Action")


def test_seed_omits_empty_sections():
    h = _Holder()
    h.description_text = _FakeTextbox("Only a description here\n")
    h.next_action_text = _FakeTextbox("   \n")  # whitespace only

    out = h._build_note_seed_content()

    assert "## Description" in out
    assert "Only a description here" in out
    assert "## Next Action" not in out


def test_seed_empty_when_both_blank():
    h = _Holder()
    h.description_text = _FakeTextbox("\n")
    h.next_action_text = _FakeTextbox("")

    assert h._build_note_seed_content() == ""
