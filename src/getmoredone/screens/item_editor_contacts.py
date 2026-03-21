"""Contact autocomplete and who-default helpers for ItemEditorDialog."""

from __future__ import annotations

import customtkinter as ctk

from ..models import PriorityFactors
from ..theme import button_style


class ItemEditorContactsMixin:
    def on_who_changed(self):
        """Handle when Who field changes - re-apply defaults for fields that are empty."""
        if self.item_id:
            # Don't re-apply defaults when editing existing items
            return

        # Only re-apply to empty fields
        current_importance = self.importance_var.get()
        current_urgency = self.urgency_var.get()
        current_size = self.size_var.get()
        current_value = self.value_var.get()
        current_group = self.group_var.get()
        current_category = self.category_var.get()
        current_planned = self.planned_minutes_entry.get()

        # Get new who-specific defaults
        who = self.who_var.get()
        who_defaults = self.db_manager.get_defaults("who", who)
        system_defaults = self.db_manager.get_defaults("system")

        # Helper to get default value with precedence
        def get_default(field_name):
            if who_defaults:
                val = getattr(who_defaults, field_name, None)
                if val is not None:
                    return val
            if system_defaults:
                val = getattr(system_defaults, field_name, None)
                if val is not None:
                    return val
            return None

        # Re-apply defaults only to empty fields
        if not current_importance:
            importance = get_default("importance")
            if importance is not None:
                for k, v in PriorityFactors.IMPORTANCE.items():
                    if v == importance:
                        self.importance_var.set(f"{k} ({v})")
                        break

        if not current_urgency:
            urgency = get_default("urgency")
            if urgency is not None:
                for k, v in PriorityFactors.URGENCY.items():
                    if v == urgency:
                        self.urgency_var.set(f"{k} ({v})")
                        break

        if not current_size:
            size = get_default("size")
            if size is not None:
                for k, v in PriorityFactors.SIZE.items():
                    if v == size:
                        self.size_var.set(f"{k} ({v})")
                        break

        if not current_value:
            value = get_default("value")
            if value is not None:
                for k, v in PriorityFactors.VALUE.items():
                    if v == value:
                        self.value_var.set(f"{k} ({v})")
                        break

        if not current_group:
            group = get_default("group")
            if group:
                self.group_var.set(group)

        if not current_category:
            category = get_default("category")
            if category:
                self.category_var.set(category)

        if not current_planned:
            planned_minutes = get_default("planned_minutes")
            if planned_minutes is not None:
                self.planned_minutes_entry.delete(0, "end")
                self.planned_minutes_entry.insert(0, str(planned_minutes))

        # Apply date offsets if dates are empty
        if not self.start_date_entry.get():
            start_offset = get_default("start_offset_days")
            if start_offset is not None:
                self.set_date(self.start_date_entry, start_offset)

        if not self.due_date_entry.get():
            due_offset = get_default("due_offset_days")
            if due_offset is not None:
                self.set_date(self.due_date_entry, due_offset)

        self.update_priority_display()

    def on_who_click(self, event=None):
        """Handle click in Who field - show all contacts if field is empty or has selection."""
        # Wait a moment for click to complete
        self.after(50, self._show_contacts_on_click)

    def _show_contacts_on_click(self):
        """Show contacts after click delay."""
        current_text = self.who_var.get().strip()

        # If field is empty or user clicked, show all contacts
        if not current_text:
            self.show_contact_suggestions(None)
        else:
            # Show filtered contacts if there's text
            contacts = self.db_manager.search_contacts(
                current_text, active_only=True)
            if contacts:
                self.show_contact_suggestions(contacts)

    def on_who_search(self, event=None):
        """Handle typing in Who field - show matching contacts."""
        search_term = self.who_var.get().strip()

        # Cancel any pending hide job
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

        # Hide suggestions if field is empty
        if not search_term:
            self.hide_contact_suggestions()
            self.selected_contact_id = None
            return

        # Search contacts
        contacts = self.db_manager.search_contacts(
            search_term, active_only=True)

        # Show suggestions
        self.show_contact_suggestions(contacts)

    def show_contact_suggestions(self, contacts=None):
        """Show dropdown with contact suggestions."""
        # Cancel any pending hide job
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

        # Hide existing suggestions
        self.hide_contact_suggestions()

        # Get all contacts if none provided
        if contacts is None:
            contacts = self.db_manager.get_all_contacts(active_only=True)

        if not contacts:
            return

        # Update widget to get accurate positioning
        self.who_entry.update_idletasks()

        # Get absolute position of who_entry
        entry_x = self.who_entry.winfo_rootx() - self.winfo_rootx()
        entry_y = self.who_entry.winfo_rooty() - self.winfo_rooty()
        entry_height = self.who_entry.winfo_height()

        # Create suggestions frame positioned below the entry
        # Use regular frame (not scrollable) since we limit to 10 items
        # This prevents scrollbar interference with Title field navigation
        self.contact_suggestions_frame = ctk.CTkFrame(
            self,
            fg_color=self.palette["surface_subtle"],
            width=318,
            # Height for up to 10 items
            height=min(len(contacts[:10]) * 35 + 10, 360)
        )
        self.contact_suggestions_frame.place(
            x=entry_x,
            y=entry_y + entry_height + 2
        )

        # Bind click outside to hide dropdown
        self.bind('<Button-1>', self.on_click_outside_dropdown, add='+')

        # Limit to 10 suggestions
        for idx, contact in enumerate(contacts[:10]):
            btn = ctk.CTkButton(
                self.contact_suggestions_frame,
                text=f"{contact.name}" +
                (f" ({contact.contact_type})" if contact.contact_type else ""),
                anchor="w",
                **button_style("secondary"),
                height=30,
                command=lambda c=contact: self.select_contact(c)
            )
            btn.pack(fill="x", padx=2, pady=1)

        # Raise to top
        self.contact_suggestions_frame.lift()

    def cancel_hide_suggestions(self):
        """Cancel scheduled hide of suggestions."""
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

    def schedule_hide_suggestions(self):
        """Schedule hiding suggestions after a delay."""
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
        self.suggestions_hide_job = self.after(
            300, self.hide_contact_suggestions)

    def hide_contact_suggestions(self):
        """Hide contact suggestions dropdown."""
        if self.contact_suggestions_frame:
            self.contact_suggestions_frame.destroy()
            self.contact_suggestions_frame = None
        if self.suggestions_hide_job:
            self.after_cancel(self.suggestions_hide_job)
            self.suggestions_hide_job = None

    def on_click_outside_dropdown(self, event):
        """Hide dropdown when clicking outside of it."""
        if not self.contact_suggestions_frame:
            return

        # Get the widget that was clicked
        clicked_widget = event.widget

        # Check if click is inside the dropdown or the who_entry
        if clicked_widget == self.who_entry or clicked_widget == self.contact_suggestions_frame:
            return

        # Check if clicked widget is a child of the dropdown
        parent = clicked_widget
        while parent:
            if parent == self.contact_suggestions_frame:
                return
            parent = parent.master if hasattr(parent, 'master') else None

        # Click was outside - hide the dropdown
        self.hide_contact_suggestions()

    def select_contact(self, contact):
        """Select a contact from the suggestions."""
        self.who_var.set(contact.name)
        self.selected_contact_id = contact.id

        # Hide suggestions immediately
        self.hide_contact_suggestions()

        # Move focus to title field
        self.after(50, lambda: self.title_entry.focus_set())

        # Re-apply defaults for this contact
        self.on_who_changed()

    def add_new_contact(self):
        """Open dialog to add a new contact and select it."""
        from .edit_contact import EditContactDialog

        # Hide dropdown before opening dialog
        self.hide_contact_suggestions()

        # Get current text as suggested name
        suggested_name = self.who_var.get().strip()

        dialog = EditContactDialog(self, self.db_manager, contact_id=None)

        # Pre-fill name if provided
        if suggested_name:
            dialog.name_var.set(suggested_name)

        dialog.wait_window()

        # If a contact was created, search for it and select it
        if suggested_name:
            contact = self.db_manager.get_contact_by_name(suggested_name)
            if contact:
                self.select_contact(contact)

