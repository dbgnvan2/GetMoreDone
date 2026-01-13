"""
Item editor dialog for creating and editing action items.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from ..models import ActionItem, PriorityFactors, ItemLink
from ..validation import Validator

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager


class ItemEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing action items."""

    def __init__(self, parent, db_manager: 'DatabaseManager', item_id: Optional[str] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item_id = item_id
        self.item: Optional[ActionItem] = None

        # Load item if editing
        if item_id:
            self.item = db_manager.get_action_item(item_id)
            self.title("Edit Action Item")
        else:
            self.title("New Action Item")

        self.geometry("1100x700")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Bind resize event
        self.bind("<Configure>", self.on_resize)
        self.last_width = 1100

        # Create form
        self.create_form()

        # Load item data if editing, or apply defaults if new
        if self.item:
            self.load_item_data()
        else:
            # Apply defaults for new items
            self.apply_defaults_to_form()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout with responsive two-column design."""
        # Main container frame
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_columnconfigure(0, weight=1)  # Left column
        main_frame.grid_columnconfigure(1, weight=0)  # Right column - fixed width
        main_frame.grid_rowconfigure(0, weight=1)

        # Left column
        left_col = ctk.CTkFrame(main_frame)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        left_col.grid_columnconfigure(1, weight=1)

        # Right column
        right_col = ctk.CTkFrame(main_frame)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        right_col.grid_columnconfigure(1, weight=1)

        # === LEFT COLUMN ===
        row_l = 0

        # Basic Info Section
        ctk.CTkLabel(
            left_col,
            text="Basic Information",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row_l, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 10))
        row_l += 1

        # Who (with contact lookup)
        who_label_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        who_label_frame.grid(row=row_l, column=0, sticky="w", padx=10, pady=5)

        ctk.CTkLabel(who_label_frame, text="* Who:").pack(side="left")

        # Add contact button
        btn_add_contact = ctk.CTkButton(
            who_label_frame,
            text="+",
            width=30,
            height=24,
            command=self.add_new_contact
        )
        btn_add_contact.pack(side="left", padx=(5, 0))

        # Who entry with autocomplete
        who_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        who_frame.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)

        self.who_var = ctk.StringVar()
        self.who_entry = ctk.CTkEntry(who_frame, textvariable=self.who_var, width=320)
        self.who_entry.pack()
        self.who_entry.bind('<KeyRelease>', self.on_who_search)
        self.who_entry.bind('<FocusIn>', lambda e: self.show_contact_suggestions())
        self.who_entry.bind('<FocusOut>', lambda e: self.after(200, self.hide_contact_suggestions))

        # Dropdown for contact suggestions
        self.contact_suggestions_frame = None
        self.selected_contact_id = None

        # Try to auto-select contact if who name matches a contact
        if not self.item_id:
            # Set default who value
            contacts = self.db_manager.get_all_contacts(active_only=True)
            if contacts:
                self.who_var.set(contacts[0].name)
                self.selected_contact_id = contacts[0].id
            else:
                self.who_var.set("Self")

        row_l += 1

        # Title
        ctk.CTkLabel(left_col, text="* Title:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        self.title_entry = ctk.CTkEntry(left_col, width=320)
        self.title_entry.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Description
        ctk.CTkLabel(left_col, text="Description:").grid(row=row_l, column=0, sticky="nw", padx=10, pady=5)
        self.description_text = ctk.CTkTextbox(left_col, height=100, width=320)
        self.description_text.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Dates Section
        ctk.CTkLabel(
            left_col,
            text="Dates",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row_l, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 10))
        row_l += 1

        # Start Date
        ctk.CTkLabel(left_col, text="Start Date:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)

        start_date_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        start_date_frame.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)

        self.start_date_entry = ctk.CTkEntry(start_date_frame, placeholder_text="YYYY-MM-DD", width=150)
        self.start_date_entry.pack(side="left", padx=(0, 5))

        btn_start_today = ctk.CTkButton(start_date_frame, text="Today", width=50,
                                        command=lambda: self.set_date(self.start_date_entry, 0))
        btn_start_today.pack(side="left", padx=2)

        btn_start_minus = ctk.CTkButton(start_date_frame, text="-1", width=40,
                                        command=lambda: self.adjust_date(self.start_date_entry, -1))
        btn_start_minus.pack(side="left", padx=2)

        btn_start_plus = ctk.CTkButton(start_date_frame, text="+1", width=40,
                                       command=lambda: self.adjust_date(self.start_date_entry, 1))
        btn_start_plus.pack(side="left", padx=2)

        btn_start_clear = ctk.CTkButton(start_date_frame, text="Clear", width=50,
                                       command=lambda: self.start_date_entry.delete(0, "end"))
        btn_start_clear.pack(side="left", padx=2)
        row_l += 1

        # Due Date
        ctk.CTkLabel(left_col, text="Due Date:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)

        due_date_frame = ctk.CTkFrame(left_col, fg_color="transparent")
        due_date_frame.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)

        self.due_date_entry = ctk.CTkEntry(due_date_frame, placeholder_text="YYYY-MM-DD", width=150)
        self.due_date_entry.pack(side="left", padx=(0, 5))

        btn_due_today = ctk.CTkButton(due_date_frame, text="Today", width=50,
                                      command=lambda: self.set_date(self.due_date_entry, 0))
        btn_due_today.pack(side="left", padx=2)

        btn_due_minus = ctk.CTkButton(due_date_frame, text="-1", width=40,
                                      command=lambda: self.adjust_date(self.due_date_entry, -1))
        btn_due_minus.pack(side="left", padx=2)

        btn_due_plus = ctk.CTkButton(due_date_frame, text="+1", width=40,
                                     command=lambda: self.adjust_date(self.due_date_entry, 1))
        btn_due_plus.pack(side="left", padx=2)

        btn_due_clear = ctk.CTkButton(due_date_frame, text="Clear", width=50,
                                      command=lambda: self.due_date_entry.delete(0, "end"))
        btn_due_clear.pack(side="left", padx=2)
        row_l += 1

        # Organization Section
        ctk.CTkLabel(
            left_col,
            text="Organization",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row_l, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 10))
        row_l += 1

        # Group
        ctk.CTkLabel(left_col, text="Group:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        groups = self.db_manager.get_distinct_groups()
        self.group_var = ctk.StringVar(value="")
        self.group_combo = ctk.CTkComboBox(left_col, values=groups if groups else [""], variable=self.group_var, width=320)
        self.group_combo.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Category
        ctk.CTkLabel(left_col, text="Category:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        categories = self.db_manager.get_distinct_categories()
        self.category_var = ctk.StringVar(value="")
        self.category_combo = ctk.CTkComboBox(left_col, values=categories if categories else [""], variable=self.category_var, width=320)
        self.category_combo.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Planned Minutes
        ctk.CTkLabel(left_col, text="Planned Minutes:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        self.planned_minutes_entry = ctk.CTkEntry(left_col, placeholder_text="0", width=320)
        self.planned_minutes_entry.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # === RIGHT COLUMN ===
        row_r = 0

        # Priority Factors Section
        ctk.CTkLabel(
            right_col,
            text="Priority Factors",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row_r, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 10))
        row_r += 1

        # Importance
        ctk.CTkLabel(right_col, text="Importance:").grid(row=row_r, column=0, sticky="w", padx=10, pady=5)
        importance_values = [f"{k} ({v})" for k, v in PriorityFactors.IMPORTANCE.items()]
        self.importance_var = ctk.StringVar(value="")
        self.importance_combo = ctk.CTkComboBox(
            right_col, values=importance_values, variable=self.importance_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.importance_combo.grid(row=row_r, column=1, sticky="w", padx=10, pady=5)
        row_r += 1

        # Urgency
        ctk.CTkLabel(right_col, text="Urgency:").grid(row=row_r, column=0, sticky="w", padx=10, pady=5)
        urgency_values = [f"{k} ({v})" for k, v in PriorityFactors.URGENCY.items()]
        self.urgency_var = ctk.StringVar(value="")
        self.urgency_combo = ctk.CTkComboBox(
            right_col, values=urgency_values, variable=self.urgency_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.urgency_combo.grid(row=row_r, column=1, sticky="w", padx=10, pady=5)
        row_r += 1

        # Size
        ctk.CTkLabel(right_col, text="Size:").grid(row=row_r, column=0, sticky="w", padx=10, pady=5)
        size_values = [f"{k} ({v})" for k, v in PriorityFactors.SIZE.items()]
        self.size_var = ctk.StringVar(value="")
        self.size_combo = ctk.CTkComboBox(
            right_col, values=size_values, variable=self.size_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.size_combo.grid(row=row_r, column=1, sticky="w", padx=10, pady=5)
        row_r += 1

        # Value
        ctk.CTkLabel(right_col, text="Value:").grid(row=row_r, column=0, sticky="w", padx=10, pady=5)
        value_values = [f"{k} ({v})" for k, v in PriorityFactors.VALUE.items()]
        self.value_var = ctk.StringVar(value="")
        self.value_combo = ctk.CTkComboBox(
            right_col, values=value_values, variable=self.value_var, width=180,
            command=lambda _: self.update_priority_display()
        )
        self.value_combo.grid(row=row_r, column=1, sticky="w", padx=10, pady=5)
        row_r += 1

        # Priority Score Display (more compact)
        score_frame = ctk.CTkFrame(right_col, fg_color="gray25", corner_radius=8)
        score_frame.grid(row=row_r, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))

        ctk.CTkLabel(
            score_frame,
            text="Priority Score:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(side="left", padx=10, pady=8)

        self.priority_label = ctk.CTkLabel(
            score_frame,
            text="0 (0×0×0×0)",
            font=ctk.CTkFont(size=12)
        )
        self.priority_label.pack(side="left", padx=10, pady=8)
        row_r += 1

        # === BOTTOM: Validation Errors ===
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red", wraplength=1000)
        self.error_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 0))

        # === BUTTONS ===
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        btn_save = ctk.CTkButton(btn_frame, text="Save", command=self.save_item, width=100)
        btn_save.pack(side="left", padx=5)

        if not self.item_id:
            btn_save_new = ctk.CTkButton(btn_frame, text="Save + New", command=self.save_and_new, width=100)
            btn_save_new.pack(side="left", padx=5)

        if self.item_id:
            btn_duplicate = ctk.CTkButton(btn_frame, text="Duplicate", command=self.duplicate_item, width=100)
            btn_duplicate.pack(side="left", padx=5)

            btn_complete = ctk.CTkButton(btn_frame, text="Complete", command=self.complete_item, width=100)
            btn_complete.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_cancel.pack(side="right", padx=5)

        # Store references for responsive layout
        self.left_col = left_col
        self.right_col = right_col
        self.main_frame = main_frame

    def load_item_data(self):
        """Load item data into form fields."""
        if not self.item:
            return

        self.who_var.set(self.item.who)
        self.selected_contact_id = self.item.contact_id
        self.title_entry.insert(0, self.item.title)

        if self.item.description:
            self.description_text.insert("1.0", self.item.description)

        if self.item.start_date:
            self.start_date_entry.insert(0, self.item.start_date)

        if self.item.due_date:
            self.due_date_entry.insert(0, self.item.due_date)

        # Priority factors
        if self.item.importance is not None:
            for k, v in PriorityFactors.IMPORTANCE.items():
                if v == self.item.importance:
                    self.importance_var.set(f"{k} ({v})")
                    break

        if self.item.urgency is not None:
            for k, v in PriorityFactors.URGENCY.items():
                if v == self.item.urgency:
                    self.urgency_var.set(f"{k} ({v})")
                    break

        if self.item.size is not None:
            for k, v in PriorityFactors.SIZE.items():
                if v == self.item.size:
                    self.size_var.set(f"{k} ({v})")
                    break

        if self.item.value is not None:
            for k, v in PriorityFactors.VALUE.items():
                if v == self.item.value:
                    self.value_var.set(f"{k} ({v})")
                    break

        if self.item.group:
            self.group_var.set(self.item.group)

        if self.item.category:
            self.category_var.set(self.item.category)

        if self.item.planned_minutes is not None:
            self.planned_minutes_entry.insert(0, str(self.item.planned_minutes))

        self.update_priority_display()

    def set_date(self, entry_widget, offset_days: int):
        """Set date field to today + offset_days."""
        from datetime import date, timedelta
        target_date = date.today() + timedelta(days=offset_days)
        entry_widget.delete(0, "end")
        entry_widget.insert(0, target_date.strftime("%Y-%m-%d"))

    def adjust_date(self, entry_widget, days_delta: int):
        """Add or subtract days from the current date in the field."""
        from datetime import datetime, timedelta

        current_text = entry_widget.get().strip()
        if not current_text:
            # If field is empty, use today as base
            base_date = datetime.now().date()
        else:
            # Parse the current date
            try:
                base_date = datetime.strptime(current_text, "%Y-%m-%d").date()
            except ValueError:
                # If invalid format, use today
                base_date = datetime.now().date()

        new_date = base_date + timedelta(days=days_delta)
        entry_widget.delete(0, "end")
        entry_widget.insert(0, new_date.strftime("%Y-%m-%d"))

    def apply_defaults_to_form(self):
        """Apply system and who-specific defaults to form fields for new items."""
        who = self.who_var.get()

        # Get defaults
        system_defaults = self.db_manager.get_defaults("system")
        who_defaults = self.db_manager.get_defaults("who", who)

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

        # Apply priority factor defaults
        importance = get_default("importance")
        if importance is not None:
            for k, v in PriorityFactors.IMPORTANCE.items():
                if v == importance:
                    self.importance_var.set(f"{k} ({v})")
                    break

        urgency = get_default("urgency")
        if urgency is not None:
            for k, v in PriorityFactors.URGENCY.items():
                if v == urgency:
                    self.urgency_var.set(f"{k} ({v})")
                    break

        size = get_default("size")
        if size is not None:
            for k, v in PriorityFactors.SIZE.items():
                if v == size:
                    self.size_var.set(f"{k} ({v})")
                    break

        value = get_default("value")
        if value is not None:
            for k, v in PriorityFactors.VALUE.items():
                if v == value:
                    self.value_var.set(f"{k} ({v})")
                    break

        # Apply organization defaults
        group = get_default("group")
        if group:
            self.group_var.set(group)

        category = get_default("category")
        if category:
            self.category_var.set(category)

        planned_minutes = get_default("planned_minutes")
        if planned_minutes is not None:
            self.planned_minutes_entry.delete(0, "end")
            self.planned_minutes_entry.insert(0, str(planned_minutes))

        # Apply date offsets if set
        start_offset = get_default("start_offset_days")
        if start_offset is not None:
            self.set_date(self.start_date_entry, start_offset)

        due_offset = get_default("due_offset_days")
        if due_offset is not None:
            self.set_date(self.due_date_entry, due_offset)

        self.update_priority_display()

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

    def on_who_search(self, event=None):
        """Handle typing in Who field - show matching contacts."""
        search_term = self.who_var.get().strip()

        # Hide suggestions if field is empty
        if not search_term:
            self.hide_contact_suggestions()
            self.selected_contact_id = None
            return

        # Search contacts
        contacts = self.db_manager.search_contacts(search_term, active_only=True)

        # Also check if exact match exists in distinct who values (for non-contact entries)
        all_who = self.db_manager.get_distinct_who_values()

        self.show_contact_suggestions(contacts)

    def show_contact_suggestions(self, contacts=None):
        """Show dropdown with contact suggestions."""
        # Hide existing suggestions
        self.hide_contact_suggestions()

        # Get all contacts if none provided
        if contacts is None:
            contacts = self.db_manager.get_all_contacts(active_only=True)

        if not contacts:
            return

        # Create suggestions frame
        self.contact_suggestions_frame = ctk.CTkFrame(self.who_entry.master, fg_color="gray20")
        self.contact_suggestions_frame.place(
            x=0,
            y=self.who_entry.winfo_height(),
            width=320
        )

        # Limit to 10 suggestions
        for idx, contact in enumerate(contacts[:10]):
            btn = ctk.CTkButton(
                self.contact_suggestions_frame,
                text=f"{contact.name}" + (f" ({contact.contact_type})" if contact.contact_type else ""),
                anchor="w",
                fg_color="transparent",
                hover_color="gray30",
                command=lambda c=contact: self.select_contact(c)
            )
            btn.pack(fill="x", padx=2, pady=1)

    def hide_contact_suggestions(self):
        """Hide contact suggestions dropdown."""
        if self.contact_suggestions_frame:
            self.contact_suggestions_frame.destroy()
            self.contact_suggestions_frame = None

    def select_contact(self, contact):
        """Select a contact from the suggestions."""
        self.who_var.set(contact.name)
        self.selected_contact_id = contact.id
        self.hide_contact_suggestions()

        # Re-apply defaults for this contact
        self.on_who_changed()

    def add_new_contact(self):
        """Open dialog to add a new contact and select it."""
        from .edit_contact import EditContactDialog

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

    def extract_factor_value(self, text: str) -> Optional[int]:
        """Extract numeric value from factor string like 'High (10)'."""
        if not text:
            return None
        try:
            return int(text.split("(")[1].split(")")[0])
        except Exception:
            return None

    def save_item(self):
        """Save the item."""
        try:
            # Create or update item
            if self.item_id:
                item = self.item
            else:
                item = ActionItem(who="", title="")

            # Set fields
            item.who = self.who_var.get().strip()
            item.contact_id = self.selected_contact_id
            item.title = self.title_entry.get().strip()
            item.description = self.description_text.get("1.0", "end").strip() or None
            item.start_date = self.start_date_entry.get().strip() or None
            item.due_date = self.due_date_entry.get().strip() or None

            # Priority factors
            item.importance = self.extract_factor_value(self.importance_var.get())
            item.urgency = self.extract_factor_value(self.urgency_var.get())
            item.size = self.extract_factor_value(self.size_var.get())
            item.value = self.extract_factor_value(self.value_var.get())

            # Organization
            item.group = self.group_var.get().strip() or None
            item.category = self.category_var.get().strip() or None

            # Planned minutes
            planned_text = self.planned_minutes_entry.get().strip()
            item.planned_minutes = int(planned_text) if planned_text else None

            # Validate
            errors = Validator.validate_action_item(item)
            if errors:
                self.error_label.configure(text=errors[0].message)
                return

            # Save
            if self.item_id:
                self.db_manager.update_action_item(item)
            else:
                self.db_manager.create_action_item(item, apply_defaults=True)

            self.destroy()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def save_and_new(self):
        """Save and open a new item editor."""
        self.save_item()
        if not self.winfo_exists():
            ItemEditorDialog(self.master, self.db_manager)

    def duplicate_item(self):
        """Duplicate the current item."""
        if self.item_id:
            new_id = self.db_manager.duplicate_action_item(self.item_id)
            self.destroy()
            if new_id:
                ItemEditorDialog(self.master, self.db_manager, new_id)

    def complete_item(self):
        """Mark item as complete."""
        if self.item_id:
            self.db_manager.complete_action_item(self.item_id)
            self.destroy()

    def update_priority_display(self):
        """Update the priority score display."""
        importance = self.extract_factor_value(self.importance_var.get()) or 0
        urgency = self.extract_factor_value(self.urgency_var.get()) or 0
        size = self.extract_factor_value(self.size_var.get()) or 0
        value = self.extract_factor_value(self.value_var.get()) or 0

        if any(f == 0 for f in [importance, urgency, size, value]):
            score = 0
        else:
            score = importance * urgency * size * value

        self.priority_label.configure(
            text=f"{score} ({importance}×{urgency}×{size}×{value})"
        )

    def on_resize(self, event):
        """Handle window resize to switch between 2-column and 1-column layout."""
        if event.widget != self:
            return

        width = event.width
        # Only update if width changed significantly (avoid flickering)
        if abs(width - self.last_width) < 50:
            return

        self.last_width = width

        # Switch to single column if window is narrow
        if width < 900:
            # Single column layout
            self.left_col.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=0, pady=(0, 5))
            self.right_col.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=0, pady=(5, 0))
        else:
            # Two column layout
            self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 5), pady=0)
            self.right_col.grid(row=0, column=1, sticky="nsew", padx=(5, 0), pady=0)
