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

        self.geometry("600x1000")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Bind resize event
        self.bind("<Configure>", self.on_resize)
        self.last_width = 600  # Track width for responsive layout

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

        # Center on parent window
        self.center_on_parent()

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

        # Parent Item Info (if this is a sub-item)
        if self.item and self.item.parent_id:
            parent_item = self.db_manager.get_action_item(self.item.parent_id)
            if parent_item:
                parent_frame = ctk.CTkFrame(left_col, fg_color="gray25", corner_radius=8)
                parent_frame.grid(row=row_l, column=0, columnspan=2, sticky="ew", padx=10, pady=(5, 10))

                ctk.CTkLabel(
                    parent_frame,
                    text=f"Sub-item of: {parent_item.title}",
                    font=ctk.CTkFont(size=12),
                    text_color="lightblue"
                ).pack(side="left", padx=10, pady=5)

                btn_view_parent = ctk.CTkButton(
                    parent_frame,
                    text="View Parent",
                    width=80,
                    height=24,
                    command=lambda: self.view_parent_item(parent_item.id)
                )
                btn_view_parent.pack(side="right", padx=10, pady=5)

                row_l += 1

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
        self.who_entry.bind('<Button-1>', self.on_who_click)  # Show on click
        self.who_entry.bind('<Tab>', lambda e: self.hide_contact_suggestions())
        self.who_entry.bind('<Escape>', lambda e: self.hide_contact_suggestions())

        # Dropdown for contact suggestions
        self.contact_suggestions_frame = None
        self.selected_contact_id = None
        self.suggestions_hide_job = None  # Track scheduled hide job

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

        # Is Meeting checkbox
        ctk.CTkLabel(left_col, text="Is Meeting:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        self.is_meeting_var = ctk.BooleanVar(value=False)
        self.is_meeting_checkbox = ctk.CTkCheckBox(
            left_col,
            text="",
            variable=self.is_meeting_var,
            onvalue=True,
            offvalue=False
        )
        self.is_meeting_checkbox.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
        row_l += 1

        # Original Due Date (read-only display)
        ctk.CTkLabel(left_col, text="Original Due Date:").grid(row=row_l, column=0, sticky="w", padx=10, pady=5)
        self.original_due_date_label = ctk.CTkLabel(
            left_col,
            text="-",
            anchor="w",
            text_color="gray"
        )
        self.original_due_date_label.grid(row=row_l, column=1, sticky="w", padx=10, pady=5)
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

        # Obsidian Notes Section (only for existing items)
        if self.item_id:
            ctk.CTkLabel(
                right_col,
                text="Obsidian Notes",
                font=ctk.CTkFont(size=14, weight="bold")
            ).grid(row=row_r, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
            row_r += 1

            # Notes list frame
            self.notes_frame = ctk.CTkScrollableFrame(right_col, height=150)
            self.notes_frame.grid(row=row_r, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
            self.notes_frame.grid_columnconfigure(0, weight=1)
            row_r += 1

            # Notes buttons
            notes_btn_frame = ctk.CTkFrame(right_col, fg_color="transparent")
            notes_btn_frame.grid(row=row_r, column=0, columnspan=2, sticky="w", padx=10, pady=5)

            btn_create_note = ctk.CTkButton(
                notes_btn_frame,
                text="+ Create Note",
                width=110,
                command=self.create_note
            )
            btn_create_note.pack(side="left", padx=2)

            btn_link_note = ctk.CTkButton(
                notes_btn_frame,
                text="+ Link Note",
                width=100,
                command=self.link_existing_note
            )
            btn_link_note.pack(side="left", padx=2)
            row_r += 1

            # Load notes
            self.load_notes()

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

            btn_create_sub = ctk.CTkButton(btn_frame, text="+ Create Sub-Item", command=self.create_sub_item, width=120)
            btn_create_sub.pack(side="left", padx=5)

            btn_show_children = ctk.CTkButton(btn_frame, text="Show Children", command=self.show_children, width=110)
            btn_show_children.pack(side="left", padx=5)

            btn_set_parent = ctk.CTkButton(btn_frame, text="Set Parent", command=self.set_parent, width=100)
            btn_set_parent.pack(side="left", padx=5)

        # Error label in the center between buttons
        self.error_label = ctk.CTkLabel(btn_frame, text="", text_color="red", wraplength=600)
        self.error_label.pack(side="left", expand=True, padx=10)

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

        # Is Meeting
        self.is_meeting_var.set(self.item.is_meeting)

        # Original Due Date (read-only display)
        if self.item.original_due_date:
            self.original_due_date_label.configure(text=self.item.original_due_date)
        else:
            self.original_due_date_label.configure(text="-")

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

        # If adjusting start date, also adjust due date by the same amount
        if entry_widget == self.start_date_entry:
            due_text = self.due_date_entry.get().strip()
            if due_text:
                try:
                    due_base = datetime.strptime(due_text, "%Y-%m-%d").date()
                    new_due = due_base + timedelta(days=days_delta)
                    self.due_date_entry.delete(0, "end")
                    self.due_date_entry.insert(0, new_due.strftime("%Y-%m-%d"))
                except ValueError:
                    # If due date is invalid, don't adjust it
                    pass

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
            contacts = self.db_manager.search_contacts(current_text, active_only=True)
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
        contacts = self.db_manager.search_contacts(search_term, active_only=True)

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
            fg_color="gray20",
            width=318,
            height=min(len(contacts[:10]) * 35 + 10, 360)  # Height for up to 10 items
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
                text=f"{contact.name}" + (f" ({contact.contact_type})" if contact.contact_type else ""),
                anchor="w",
                fg_color="transparent",
                hover_color="gray30",
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
        self.suggestions_hide_job = self.after(300, self.hide_contact_suggestions)

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
            item.is_meeting = self.is_meeting_var.get()

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

            # Validate dates: due date must be >= start date
            if item.start_date and item.due_date:
                try:
                    start = datetime.strptime(item.start_date, "%Y-%m-%d").date()
                    due = datetime.strptime(item.due_date, "%Y-%m-%d").date()
                    if due < start:
                        self.error_label.configure(text="Error: Due date cannot be before Start date")
                        return
                except ValueError:
                    # Let the validator handle invalid date formats
                    pass

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

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        # Schedule centering after dialog is fully rendered
        self.after(10, self._do_center)

    def _do_center(self):
        """Actually perform the centering after dialog is rendered."""
        # Use fixed dimensions from geometry call
        dialog_width = 600
        dialog_height = 1000

        # Force complete update of both windows
        self.master.update()
        self.update()

        # Get parent window position and size using rootx/rooty for absolute screen coordinates
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure dialog is not positioned off-screen
        x = max(0, x)
        y = max(0, y)

        # Set geometry with position
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Final update to apply positioning
        self.update_idletasks()

    def view_parent_item(self, parent_id: str):
        """Open the parent item in a new editor dialog."""
        self.destroy()
        ItemEditorDialog(self.master, self.db_manager, parent_id)

    def create_sub_item(self):
        """Create a new sub-item linked to this item."""
        if not self.item_id:
            return

        # Close this dialog and open a new one for the sub-item
        # Create a new action item with parent_id set
        from ..models import ActionItem

        sub_item = ActionItem(
            who=self.who_var.get(),
            title="",
            parent_id=self.item_id
        )

        # Save the sub-item
        sub_item_id = self.db_manager.create_action_item(sub_item, apply_defaults=True)

        # Close this dialog
        self.destroy()

        # Open editor for the new sub-item
        ItemEditorDialog(self.master, self.db_manager, sub_item_id)

    def show_children(self):
        """Show list of child items in a new dialog."""
        if not self.item_id:
            return

        # Open children list dialog
        ShowChildrenDialog(self, self.db_manager, self.item_id, self.item.title if self.item else "Item")

    def set_parent(self):
        """Open dialog to set/change the parent item."""
        if not self.item_id:
            return

        # Open set parent dialog
        SetParentDialog(self, self.db_manager, self.item_id, self.item.title if self.item else "Item")

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
                text_color="gray"
            ).pack(pady=10)
            return

        # Display each note
        for note in notes:
            self.create_note_row(note)

    def create_note_row(self, note: ItemLink):
        """Create a row for a note link."""
        frame = ctk.CTkFrame(self.notes_frame)
        frame.pack(fill="x", pady=2, padx=5)

        # Note icon and label
        label_text = note.label or "Untitled Note"
        ctk.CTkLabel(frame, text=f"📝 {label_text}", anchor="w").pack(side="left", fill="x", expand=True, padx=5)

        # Open button
        btn_open = ctk.CTkButton(
            frame,
            text="Open",
            width=60,
            command=lambda: self.open_note(note)
        )
        btn_open.pack(side="left", padx=2)

        # Delete button
        btn_delete = ctk.CTkButton(
            frame,
            text="×",
            width=30,
            fg_color="darkred",
            hover_color="red",
            command=lambda: self.delete_note(note.id)
        )
        btn_delete.pack(side="left", padx=2)

    def create_note(self):
        """Open dialog to create a new Obsidian note."""
        if not self.item_id:
            return

        # Check if Obsidian is configured
        from ..app_settings import AppSettings
        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(text="Error: Please configure Obsidian vault in Settings first")
            return

        try:
            CreateNoteDialog(self, self.db_manager, "action_item", self.item_id, self.item.title if self.item else "Item")
        except Exception as e:
            self.error_label.configure(text=f"Error opening note dialog: {str(e)}")

    def link_existing_note(self):
        """Open dialog to link an existing note file."""
        if not self.item_id:
            return

        LinkNoteDialog(self, self.db_manager, "action_item", self.item_id)

    def open_note(self, note: ItemLink):
        """Open note in Obsidian."""
        from ..app_settings import AppSettings
        from ..obsidian_utils import open_in_obsidian

        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(text="Error: Obsidian vault not configured in Settings")
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


class ShowChildrenDialog(ctk.CTkToplevel):
    """Dialog for showing list of child items."""

    def __init__(self, parent, db_manager: 'DatabaseManager', parent_item_id: str, parent_title: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.parent_item_id = parent_item_id
        self.parent_title = parent_title

        self.title(f"Children of: {parent_title}")
        self.geometry("900x600")

        # Create UI
        self.create_ui()

        # Load children
        self.refresh()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.center_on_parent()

    def create_ui(self):
        """Create the UI components."""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text=f"Child Items of: {self.parent_title}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10, pady=10)

        # Scrollable frame for children list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        btn_close = ctk.CTkButton(btn_frame, text="Close", command=self.destroy, width=100)
        btn_close.pack(side="right", padx=5)

    def refresh(self):
        """Refresh the list of children."""
        # Clear current list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get children
        children = self.db_manager.get_children(self.parent_item_id)

        if not children:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No child items found",
                font=ctk.CTkFont(size=14)
            ).grid(row=0, column=0, pady=20)
            return

        # Create header row
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Title (Who)", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkLabel(header_frame, text="Priority", width=70, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Due Date", width=110, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=2, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Status", width=80, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Actions", width=80, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=4, padx=5, pady=5
        )

        # Display each child
        for idx, child in enumerate(children):
            self.create_child_row(child, idx + 1)

    def create_child_row(self, item: ActionItem, row: int):
        """Create a row for a child item."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        frame.grid_columnconfigure(0, weight=1)

        # Title and who
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Priority
        priority_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=70,
            fg_color="gray30"
        )
        priority_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        due_text = item.due_date if item.due_date else "-"
        due_label = ctk.CTkLabel(frame, text=due_text, width=110)
        due_label.grid(row=0, column=2, padx=5, pady=5)

        # Status
        status_label = ctk.CTkLabel(
            frame,
            text=item.status.capitalize(),
            width=80,
            text_color="green" if item.status == "completed" else "white"
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Edit button
        btn_edit = ctk.CTkButton(
            frame,
            text="Edit",
            width=80,
            command=lambda: self.edit_child(item.id)
        )
        btn_edit.grid(row=0, column=4, padx=5, pady=5)

    def edit_child(self, child_id: str):
        """Open editor for a child item."""
        # Close this dialog
        self.destroy()
        # Open editor for the child
        ItemEditorDialog(self.master, self.db_manager, child_id)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 900
        dialog_height = 600

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class SetParentDialog(ctk.CTkToplevel):
    """Dialog for selecting a parent item."""

    def __init__(self, parent, db_manager: 'DatabaseManager', current_item_id: str, current_item_title: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.current_item_id = current_item_id
        self.current_item_title = current_item_title
        self.parent_dialog = parent

        self.title(f"Set Parent for: {current_item_title}")
        self.geometry("900x600")

        # Create UI
        self.create_ui()

        # Load available parents
        self.refresh()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.center_on_parent()

    def create_ui(self):
        """Create the UI components."""
        # Header
        header_frame = ctk.CTkFrame(self)
        header_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            header_frame,
            text=f"Select Parent for: {self.current_item_title}",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10, pady=10)

        # Scrollable frame for item list
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Button frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=10)

        btn_close = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_close.pack(side="right", padx=5)

    def refresh(self):
        """Refresh the list of available parent items."""
        # Clear current list
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get all items
        all_items = self.db_manager.get_all_items(sort_by="priority_score", sort_desc=True)

        # Get descendants of current item (to prevent circular references)
        descendants = self.db_manager.get_subtree(self.current_item_id)
        descendant_ids = {item.id for item in descendants}

        # Filter out current item and its descendants
        available_items = [
            item for item in all_items
            if item.id != self.current_item_id and item.id not in descendant_ids
        ]

        # Create header row
        header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5), padx=5)
        header_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header_frame, text="Title (Who)", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=10, pady=5
        )
        ctk.CTkLabel(header_frame, text="Priority", width=70, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Due Date", width=110, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=2, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Status", width=80, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(header_frame, text="Actions", width=100, font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=4, padx=5, pady=5
        )

        # Add "No Parent" option as first row
        row = 1
        no_parent_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray20")
        no_parent_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        no_parent_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            no_parent_frame,
            text="[No Parent - Make this a root item]",
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="lightblue"
        ).grid(row=0, column=0, sticky="w", padx=10, pady=5, columnspan=4)

        btn_clear = ctk.CTkButton(
            no_parent_frame,
            text="Clear Parent",
            width=100,
            command=self.clear_parent,
            fg_color="darkred",
            hover_color="red"
        )
        btn_clear.grid(row=0, column=4, padx=5, pady=5)
        row += 1

        # Display each available item
        if not available_items:
            ctk.CTkLabel(
                self.scroll_frame,
                text="No available parent items found",
                font=ctk.CTkFont(size=14)
            ).grid(row=row, column=0, pady=20)
            return

        for item in available_items:
            self.create_item_row(item, row)
            row += 1

    def create_item_row(self, item: ActionItem, row: int):
        """Create a row for a potential parent item."""
        frame = ctk.CTkFrame(self.scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
        frame.grid_columnconfigure(0, weight=1)

        # Title and who
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            anchor="w",
            font=ctk.CTkFont(size=12)
        )
        title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        # Priority
        priority_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=70,
            fg_color="gray30"
        )
        priority_label.grid(row=0, column=1, padx=5, pady=5)

        # Due date
        due_text = item.due_date if item.due_date else "-"
        due_label = ctk.CTkLabel(frame, text=due_text, width=110)
        due_label.grid(row=0, column=2, padx=5, pady=5)

        # Status
        status_label = ctk.CTkLabel(
            frame,
            text=item.status.capitalize(),
            width=80,
            text_color="green" if item.status == "completed" else "white"
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Select button
        btn_select = ctk.CTkButton(
            frame,
            text="Select",
            width=100,
            command=lambda: self.select_parent(item.id),
            fg_color="darkgreen",
            hover_color="green"
        )
        btn_select.grid(row=0, column=4, padx=5, pady=5)

    def select_parent(self, parent_id: str):
        """Set the selected item as parent."""
        # Get the current item and update its parent_id
        current_item = self.db_manager.get_action_item(self.current_item_id)
        if current_item:
            current_item.parent_id = parent_id
            self.db_manager.update_action_item(current_item)

        # Close this dialog
        self.destroy()

        # Close and reopen the parent editor to show updated parent info
        self.parent_dialog.destroy()
        ItemEditorDialog(self.parent_dialog.master, self.db_manager, self.current_item_id)

    def clear_parent(self):
        """Clear the parent (make this a root item)."""
        # Get the current item and clear its parent_id
        current_item = self.db_manager.get_action_item(self.current_item_id)
        if current_item:
            current_item.parent_id = None
            self.db_manager.update_action_item(current_item)

        # Close this dialog
        self.destroy()

        # Close and reopen the parent editor to show updated parent info
        self.parent_dialog.destroy()
        ItemEditorDialog(self.parent_dialog.master, self.db_manager, self.current_item_id)

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 900
        dialog_height = 600

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

class CreateNoteDialog(ctk.CTkToplevel):
    """Dialog for creating a new Obsidian note."""

    def __init__(self, parent, db_manager, entity_type: str, entity_id: str, entity_title: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.entity_title = entity_title
        self.parent_window = parent

        self.title(f"Create Note for: {entity_title}")
        self.geometry("500x300")

        self.create_form()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Ensure dialog is visible and on top
        self.lift()
        self.focus_force()

        # Center on parent
        self.center_on_parent()

    def create_form(self):
        """Create the form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Note title
        ctk.CTkLabel(main_frame, text="Note Title:").pack(pady=(0, 5))
        self.title_var = ctk.StringVar(value=f"{self.entity_title} Notes")
        self.title_entry = ctk.CTkEntry(main_frame, textvariable=self.title_var, width=400)
        self.title_entry.pack(pady=(0, 15))

        # Initial content (optional)
        ctk.CTkLabel(main_frame, text="Initial Content (optional):").pack(pady=(0, 5))
        self.content_text = ctk.CTkTextbox(main_frame, width=400, height=100)
        self.content_text.pack(pady=(0, 15))

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))

        btn_create = ctk.CTkButton(
            btn_frame,
            text="Create & Open",
            command=self.create_note,
            fg_color="darkgreen",
            hover_color="green",
            width=120
        )
        btn_create.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_cancel.pack(side="left", padx=5)

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red", wraplength=400)
        self.error_label.pack(pady=(10, 0))

    def create_note(self):
        """Create the note file and link it."""
        from ..app_settings import AppSettings
        from ..obsidian_utils import create_obsidian_note, open_in_obsidian
        from ..models import ItemLink, ContactLink

        title = self.title_var.get().strip()
        if not title:
            self.error_label.configure(text="Error: Note title is required")
            return

        content = self.content_text.get("1.0", "end-1c").strip()

        # Load settings
        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(text="Error: Obsidian vault not configured in Settings")
            return

        try:
            # Get additional metadata based on entity type
            who = None
            due_date = None
            priority_score = None

            if self.entity_type == "action_item":
                item = self.db_manager.get_action_item(self.entity_id)
                if item:
                    who = item.who
                    due_date = item.due_date
                    priority_score = item.priority_score

            # Create note file
            file_path = create_obsidian_note(
                vault_path=settings.obsidian_vault_path,
                subfolder=settings.obsidian_notes_subfolder,
                entity_type=self.entity_type,
                entity_id=self.entity_id,
                title=title,
                initial_content=content,
                who=who,
                due_date=due_date,
                priority_score=priority_score
            )

            # Create link in database
            if self.entity_type == "action_item":
                link = ItemLink(
                    item_id=self.entity_id,
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_item_link(link)
            elif self.entity_type == "contact":
                link = ContactLink(
                    contact_id=int(self.entity_id),
                    url=file_path,
                    label=title,
                    link_type="obsidian_note"
                )
                self.db_manager.add_contact_link(link)

            # Open in Obsidian
            open_in_obsidian(file_path, settings.obsidian_vault_path)

            # Close dialog and refresh parent
            self.destroy()
            if hasattr(self.parent_window, 'load_notes'):
                self.parent_window.load_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def center_on_parent(self):
        """Center the dialog on the parent window."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 500
        dialog_height = 300

        # Get parent window position
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()

        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2

        # Ensure not off-screen
        x = max(0, x)
        y = max(0, y)

        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")


class LinkNoteDialog(ctk.CTkToplevel):
    """Dialog for linking an existing note file."""

    def __init__(self, parent, db_manager, entity_type: str, entity_id: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.parent_window = parent
        self.available_notes = []

        self.title("Link Existing Note")
        self.geometry("600x500")

        self.create_form()
        self.load_available_notes()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Search/filter by note title
        ctk.CTkLabel(main_frame, text="Search Notes:", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(0, 5))

        self.search_var = ctk.StringVar()
        self.search_var.trace_add('write', lambda *args: self.filter_notes())
        self.search_entry = ctk.CTkEntry(main_frame, textvariable=self.search_var, width=500,
                                        placeholder_text="Search by title, or use file:name or tag:tagname")
        self.search_entry.pack(pady=(0, 10))

        # Display label
        ctk.CTkLabel(main_frame, text="Display Label (optional):").pack(pady=(0, 5))
        self.label_var = ctk.StringVar()
        self.label_entry = ctk.CTkEntry(main_frame, textvariable=self.label_var, width=500)
        self.label_entry.pack(pady=(0, 15))

        # Available notes list
        ctk.CTkLabel(main_frame, text="Available Notes:", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(0, 5))

        self.notes_frame = ctk.CTkScrollableFrame(main_frame, height=200)
        self.notes_frame.pack(fill="both", expand=True, pady=(0, 15))
        self.notes_frame.grid_columnconfigure(0, weight=1)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_frame.pack(pady=(10, 0))

        btn_browse = ctk.CTkButton(
            btn_frame,
            text="Browse Files...",
            command=self.browse_file,
            width=120
        )
        btn_browse.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_cancel.pack(side="left", padx=5)

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red", wraplength=500)
        self.error_label.pack(pady=(10, 0))

    def load_available_notes(self):
        """Load all markdown files from vault (searches entire vault)."""
        from ..app_settings import AppSettings
        from pathlib import Path
        import re

        settings = AppSettings.load()

        if not settings.obsidian_vault_path:
            self.error_label.configure(text="Error: Obsidian vault not configured in Settings")
            return

        vault_path = Path(settings.obsidian_vault_path)
        if not vault_path.exists():
            self.error_label.configure(text="Error: Vault path does not exist")
            return

        # Search entire vault, not just GetMoreDone subfolder
        search_path = vault_path

        # Find all .md files
        try:
            self.available_notes = []
            for md_file in search_path.rglob("*.md"):
                # Extract tags from frontmatter
                tags = []
                try:
                    content = md_file.read_text(encoding='utf-8')
                    # Look for YAML frontmatter
                    frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
                    if frontmatter_match:
                        frontmatter = frontmatter_match.group(1)
                        # Extract tags (supports: tags: [tag1, tag2] or tags:\n- tag1\n- tag2)
                        tags_match = re.search(r'tags:\s*\[(.*?)\]', frontmatter)
                        if tags_match:
                            tags = [t.strip().strip('"\'') for t in tags_match.group(1).split(',')]
                        else:
                            # Look for YAML list format
                            tags_lines = re.findall(r'^\s*-\s*(.+)$', frontmatter, re.MULTILINE)
                            if 'tags:' in frontmatter:
                                tags = [t.strip() for t in tags_lines if t.strip()]

                    # Also look for inline tags (#tag format)
                    inline_tags = re.findall(r'#(\w+)', content)
                    tags.extend(inline_tags)
                    tags = list(set(tags))  # Remove duplicates
                except Exception:
                    pass  # If we can't read tags, continue anyway

                self.available_notes.append({
                    'path': str(md_file),
                    'title': md_file.stem,
                    'relative': str(md_file.relative_to(vault_path)),
                    'tags': tags
                })

            # Sort by title
            self.available_notes.sort(key=lambda x: x['title'].lower())

            # Display notes
            self.filter_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error loading notes: {str(e)}")

    def filter_notes(self):
        """Filter notes based on search text with support for file: and tag: prefixes."""
        # Clear current list
        for widget in self.notes_frame.winfo_children():
            widget.destroy()

        search_text = self.search_var.get().strip()

        if not search_text:
            # No search text - show all notes (up to 50)
            filtered = self.available_notes[:50]
        else:
            # Parse search prefixes (Obsidian-style)
            search_lower = search_text.lower()

            if search_lower.startswith("file:"):
                # Search by filename only
                query = search_text[5:].strip().lower()
                filtered = [n for n in self.available_notes if query in n['title'].lower()]
            elif search_lower.startswith("tag:"):
                # Search by tags
                query = search_text[4:].strip().lower()
                filtered = [n for n in self.available_notes
                           if any(query in tag.lower() for tag in n.get('tags', []))]
            else:
                # Default: search in title (case-insensitive contains)
                query = search_text.lower()
                filtered = [n for n in self.available_notes if query in n['title'].lower()]

        if not filtered:
            ctk.CTkLabel(
                self.notes_frame,
                text="No notes found" if search_text else "No notes in vault",
                text_color="gray"
            ).pack(pady=20)
            return

        # Display filtered notes
        for note in filtered[:50]:  # Limit to 50 results
            self.create_note_row(note)

    def create_note_row(self, note: dict):
        """Create a row for a note."""
        frame = ctk.CTkFrame(self.notes_frame)
        frame.pack(fill="x", pady=2, padx=5)

        # Note info
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            info_frame,
            text=note['title'],
            anchor="w",
            font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", padx=5)

        ctk.CTkLabel(
            info_frame,
            text=note['relative'],
            anchor="w",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        ).pack(anchor="w", padx=5)

        # Display tags if present
        if note.get('tags'):
            tags_text = " ".join([f"#{tag}" for tag in note['tags'][:5]])  # Show first 5 tags
            ctk.CTkLabel(
                info_frame,
                text=tags_text,
                anchor="w",
                font=ctk.CTkFont(size=9),
                text_color="#6B7280"
            ).pack(anchor="w", padx=5)

        # Select button
        btn_select = ctk.CTkButton(
            frame,
            text="Link This",
            width=80,
            command=lambda: self.link_note_file(note['path'], note['title']),
            fg_color="darkgreen",
            hover_color="green"
        )
        btn_select.pack(side="right", padx=5)

    def link_note_file(self, file_path: str, default_label: str):
        """Link the selected note file."""
        from ..models import ItemLink, ContactLink
        from pathlib import Path

        # Get label (use custom if provided, otherwise use note title)
        label = self.label_var.get().strip() or default_label

        try:
            # Create link in database
            if self.entity_type == "action_item":
                link = ItemLink(
                    item_id=self.entity_id,
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_item_link(link)
            elif self.entity_type == "contact":
                link = ContactLink(
                    contact_id=int(self.entity_id),
                    url=file_path,
                    label=label,
                    link_type="obsidian_note"
                )
                self.db_manager.add_contact_link(link)

            # Close dialog and refresh parent
            self.destroy()
            if hasattr(self.parent_window, 'load_notes'):
                self.parent_window.load_notes()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")

    def browse_file(self):
        """Browse for a markdown file (fallback option)."""
        from tkinter import filedialog
        from ..app_settings import AppSettings
        from pathlib import Path

        settings = AppSettings.load()

        # Start in vault folder if configured
        initial_dir = None
        if settings.obsidian_vault_path:
            notes_folder = settings.get_notes_folder()
            if notes_folder and notes_folder.exists():
                initial_dir = str(notes_folder)
            else:
                initial_dir = settings.obsidian_vault_path

        file_path = filedialog.askopenfilename(
            title="Select Markdown Note",
            initialdir=initial_dir,
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")]
        )

        if file_path:
            # Get title from filename
            title = Path(file_path).stem

            # Link the file
            self.link_note_file(file_path, title)
