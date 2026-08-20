"""Obsidian note support for ItemEditorDialog."""

from __future__ import annotations

import customtkinter as ctk

from ..models import ItemLink
from ..theme import button_style, status_text_color
from .item_editor_dialogs import CreateNoteDialog, LinkNoteDialog


class ItemEditorNotesMixin:
    def load_notes(self):
        """Load and display Obsidian notes for this item."""
        if not self.item_id:
            return

        # Clear current notes
        for widget in self.notes_frame.winfo_children():
            widget.destroy()

        # Get notes (obsidian_note type links)
        links = self.db_manager.get_item_links(self.item_id)
        notes = [link for link in links if link.link_type == "obsidian_note"]

        if not notes:
            ctk.CTkLabel(
                self.notes_frame,
                text="No notes yet",
                text_color=status_text_color("muted")
            ).pack(pady=10)
            return

        # Display each note
        for note in notes:
            self.create_note_row(note)

    def create_note_row(self, note: ItemLink):
        """Create a row for a note link."""
        frame = ctk.CTkFrame(self.notes_frame)
        frame.pack(fill="x", pady=2, padx=5)

        # Pack the action buttons FIRST (side="right") so a long note title can
        # never push them off the edge of the (narrow) notes panel.
        btn_delete = ctk.CTkButton(
            frame,
            text="×",
            width=30,
            **button_style("danger"),
            command=lambda: self.delete_note(note.id)
        )
        btn_delete.pack(side="right", padx=2)

        btn_open = ctk.CTkButton(
            frame,
            text="Open",
            width=60,
            command=lambda: self.open_note(note)
        )
        btn_open.pack(side="right", padx=2)

        # Note icon and label fill the remaining space. Double-clicking the
        # title opens the note as well.
        label_text = note.label or "Untitled Note"
        label = ctk.CTkLabel(frame, text=f"📝 {label_text}", anchor="w", justify="left")
        label.pack(side="left", fill="x", expand=True, padx=5)
        label.bind("<Double-Button-1>", lambda e: self.open_note(note))

    def save_item_if_needed(self) -> bool:
        """
        Save the item if it's new (no item_id yet).
        Returns True if successful or already has ID, False if validation fails.

        The second insert path for a new item: "Create Note", "Link Note" and
        the calendar dialog all come through here rather than through Save.
        Every field is assembled by the one shared builder (BP3) so the two
        paths cannot store different rows for the same form.
        """
        if self.item_id:
            # Already has an ID, nothing to do — unless the row behind it is
            # gone, in which case the caller is about to attach a note to an
            # item that does not exist (P6: a status with no artifact).
            if self.item is None:
                self.error_label.configure(
                    text="Error: this item no longer exists — it was deleted elsewhere")
                return False
            return True

        try:
            item = self.build_item_from_form()
            self.apply_new_item_fields(item)

            error = self.validate_item_for_save(item)
            if error:
                self.error_label.configure(text=error)
                return False

            self.insert_new_item(item)

            # Clear the notes frame and reload to show it's ready for notes
            for widget in self.notes_frame.winfo_children():
                widget.destroy()
            self.load_notes()

            # Update window title
            self.title("Edit Action Item")

            return True

        except Exception as e:
            self.error_label.configure(text=f"Error saving item: {str(e)}")
            return False

    def _build_note_seed_content(self) -> str:
        """Assemble the item's Description and Next Action as initial note content.

        Reads the live form fields (not the last-saved item) so the note
        captures whatever the user currently has on screen.
        """
        sections = []
        try:
            description = self.description_text.get("1.0", "end").strip()
        except Exception:
            description = ""
        try:
            next_action = self.next_action_text.get("1.0", "end").strip()
        except Exception:
            next_action = ""

        if description:
            sections.append(f"## Description\n\n{description}")
        if next_action:
            sections.append(f"## Next Action\n\n{next_action}")
        return "\n\n".join(sections)

    def create_note(self):
        """Open dialog to create a new Obsidian note."""
        # Save item first if it's new
        if not self.save_item_if_needed():
            return

        # Check if Obsidian is configured
        from ..app_settings import AppSettings
        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Please configure Obsidian vault in Settings first")
            return

        try:
            CreateNoteDialog(self, self.db_manager, "action_item",
                             self.item_id, self.item.title if self.item else "Item",
                             initial_content=self._build_note_seed_content())
        except Exception as e:
            self.error_label.configure(
                text=f"Error opening note dialog: {str(e)}")

    def link_existing_note(self):
        """Open dialog to link an existing note file."""
        # Save item first if it's new
        if not self.save_item_if_needed():
            return

        LinkNoteDialog(self, self.db_manager, "action_item", self.item_id)

    def open_note(self, note: ItemLink):
        """Open note in Obsidian."""
        from ..app_settings import AppSettings
        from ..obsidian_utils import open_in_obsidian

        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(
                text="Error: Obsidian vault not configured in Settings")
            return

        try:
            open_in_obsidian(note.url, settings.obsidian_vault_path)
        except Exception as e:
            self.error_label.configure(text=f"Error opening note: {str(e)}")

    def delete_note(self, note_id: str):
        """Delete a note link."""
        # Ask for confirmation
        # For simplicity, just delete without confirmation for now
        self.db_manager.delete_item_link(note_id)
        self.load_notes()
