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
            self.title(f"Edit Item: {self.item.title if self.item else 'Unknown'}")
        else:
            self.title("New Action Item")

        self.geometry("700x800")
        self.grid_columnconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load item data if editing
        if self.item:
            self.load_item_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        # Scrollable frame
        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(1, weight=1)

        row = 0

        # Title
        ctk.CTkLabel(scroll, text="* Who:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        who_values = self.db_manager.get_distinct_who_values()
        if not who_values:
            who_values = ["Self"]
        self.who_var = ctk.StringVar(value=who_values[0] if who_values else "Self")
        self.who_combo = ctk.CTkComboBox(scroll, values=who_values, variable=self.who_var, width=300)
        self.who_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Title
        ctk.CTkLabel(scroll, text="* Title:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.title_entry = ctk.CTkEntry(scroll, width=400)
        self.title_entry.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Description
        ctk.CTkLabel(scroll, text="Description:").grid(row=row, column=0, sticky="nw", padx=10, pady=5)
        self.description_text = ctk.CTkTextbox(scroll, width=400, height=100)
        self.description_text.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
        row += 1

        # Dates
        ctk.CTkLabel(scroll, text="Start Date:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.start_date_entry = ctk.CTkEntry(scroll, width=200, placeholder_text="YYYY-MM-DD")
        self.start_date_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        ctk.CTkLabel(scroll, text="Due Date:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.due_date_entry = ctk.CTkEntry(scroll, width=200, placeholder_text="YYYY-MM-DD")
        self.due_date_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Priority factors
        ctk.CTkLabel(
            scroll,
            text="Priority Factors",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # Importance
        ctk.CTkLabel(scroll, text="Importance:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        importance_values = [f"{k} ({v})" for k, v in PriorityFactors.IMPORTANCE.items()]
        self.importance_var = ctk.StringVar(value="")
        self.importance_combo = ctk.CTkComboBox(scroll, values=importance_values, variable=self.importance_var, width=200)
        self.importance_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Urgency
        ctk.CTkLabel(scroll, text="Urgency:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        urgency_values = [f"{k} ({v})" for k, v in PriorityFactors.URGENCY.items()]
        self.urgency_var = ctk.StringVar(value="")
        self.urgency_combo = ctk.CTkComboBox(scroll, values=urgency_values, variable=self.urgency_var, width=200)
        self.urgency_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Size
        ctk.CTkLabel(scroll, text="Size:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        size_values = [f"{k} ({v})" for k, v in PriorityFactors.SIZE.items()]
        self.size_var = ctk.StringVar(value="")
        self.size_combo = ctk.CTkComboBox(scroll, values=size_values, variable=self.size_var, width=200)
        self.size_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Value
        ctk.CTkLabel(scroll, text="Value:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        value_values = [f"{k} ({v})" for k, v in PriorityFactors.VALUE.items()]
        self.value_var = ctk.StringVar(value="")
        self.value_combo = ctk.CTkComboBox(scroll, values=value_values, variable=self.value_var, width=200)
        self.value_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Organization
        ctk.CTkLabel(
            scroll,
            text="Organization",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # Group
        ctk.CTkLabel(scroll, text="Group:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        groups = self.db_manager.get_distinct_groups()
        self.group_var = ctk.StringVar(value="")
        self.group_combo = ctk.CTkComboBox(scroll, values=groups if groups else [""], variable=self.group_var, width=200)
        self.group_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Category
        ctk.CTkLabel(scroll, text="Category:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        categories = self.db_manager.get_distinct_categories()
        self.category_var = ctk.StringVar(value="")
        self.category_combo = ctk.CTkComboBox(scroll, values=categories if categories else [""], variable=self.category_var, width=200)
        self.category_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Planned minutes
        ctk.CTkLabel(scroll, text="Planned Minutes:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.planned_minutes_entry = ctk.CTkEntry(scroll, width=100, placeholder_text="0")
        self.planned_minutes_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Priority score display
        self.priority_label = ctk.CTkLabel(
            scroll,
            text="Priority Score: 0",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.priority_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # Validation errors
        self.error_label = ctk.CTkLabel(scroll, text="", text_color="red")
        self.error_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)
        row += 1

        # Buttons
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=10)

        btn_save = ctk.CTkButton(btn_frame, text="Save", command=self.save_item)
        btn_save.pack(side="left", padx=5)

        if not self.item_id:
            btn_save_new = ctk.CTkButton(btn_frame, text="Save + New", command=self.save_and_new)
            btn_save_new.pack(side="left", padx=5)

        if self.item_id:
            btn_duplicate = ctk.CTkButton(btn_frame, text="Duplicate", command=self.duplicate_item)
            btn_duplicate.pack(side="left", padx=5)

            btn_complete = ctk.CTkButton(btn_frame, text="Complete", command=self.complete_item)
            btn_complete.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy)
        btn_cancel.pack(side="right", padx=5)

    def load_item_data(self):
        """Load item data into form fields."""
        if not self.item:
            return

        self.who_var.set(self.item.who)
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
            text=f"Priority Score: {score} ({importance} × {urgency} × {size} × {value})"
        )
