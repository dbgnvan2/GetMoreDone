"""Obsidian note support for ItemEditorDialog."""

from __future__ import annotations

import customtkinter as ctk
from datetime import datetime

from ..models import ActionItem, ItemLink
from ..theme import button_style, status_text_color
from ..validation import Validator
from .item_editor_dialogs import CreateNoteDialog, LinkNoteDialog
from .week_collision_notice import notify_weekly_tactic_changes


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
        """
        if self.item_id:
            # Already has an ID, nothing to do
            return True

        try:
            # Create new item
            item = ActionItem(who="", title="")

            # Set fields
            item.who = self.who_var.get().strip()
            item.contact_id = self.selected_contact_id
            item.title = self.title_entry.get().strip()
            if item.item_type == "week":
                item.title = self._canonical_weekly_tactic_title(
                    item.title,
                    item.annual_plan_element_id,
                    item.start_date,
                )
            item.description = self.description_text.get(
                "1.0", "end").strip() or None
            item.next_action = self.next_action_text.get(
                "1.0", "end").strip() or None
            item.start_date = self.start_date_entry.get().strip() or None
            item.due_date = self.due_date_entry.get().strip() or None
            item.is_meeting = self.is_meeting_var.get()

            # Priority factors
            item.importance = self.extract_factor_value(
                self.importance_var.get())
            item.urgency = self.extract_factor_value(self.urgency_var.get())
            item.size = self.extract_factor_value(self.size_var.get())
            item.value = self.extract_factor_value(self.value_var.get())

            # Organization
            item.group = self.group_var.get().strip() or None
            item.category = self.category_var.get().strip() or None

            # Planned minutes
            planned_text = self.planned_minutes_entry.get().strip()
            item.planned_minutes = int(planned_text) if planned_text else None

            # Validate dates
            if item.start_date and item.due_date:
                try:
                    start = datetime.strptime(
                        item.start_date, "%Y-%m-%d").date()
                    due = datetime.strptime(item.due_date, "%Y-%m-%d").date()
                    if due < start:
                        self.error_label.configure(
                            text="Error: Due date cannot be before Start date")
                        return False
                except ValueError:
                    pass

            # Validate
            errors = Validator.validate_action_item(item)
            if errors:
                self.error_label.configure(text=errors[0].message)
                return False

            # Save and get the ID
            self.db_manager.create_action_item(item, apply_defaults=True)
            self.item_id = item.id
            self.item = item

            # The second insert path for a new item. Everything chosen before
            # the first save has to be applied here too, or clicking "Create
            # Note" instead of "Save" silently drops it while the Action Plan
            # block goes on displaying the choice (P5: the sibling call was not
            # hardened; P6: a label with no row behind it).
            if self._apply_project_link(item.id):
                self.item = self.db_manager.get_action_item(item.id) or item
            self.refresh_project_display()
            if getattr(self, "pending_weekly_tactic_id", None):
                self.item.weekly_tactic_id = self.pending_weekly_tactic_id
                self.db_manager.update_action_item(self.item, follow_tactic=True)
                self.pending_weekly_tactic_id = None
                # WT-M6.B.5 — follow_tactic moves the item's dates, so whatever
                # the cascade built has to be said out loud here too (P25).
                notify_weekly_tactic_changes(self.db_manager, self)

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
