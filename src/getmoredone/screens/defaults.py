"""
Defaults screen - manage system and who-specific defaults.
"""

import customtkinter as ctk
from typing import Optional, TYPE_CHECKING

from ..models import Defaults, PriorityFactors

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class DefaultsScreen(ctk.CTkFrame):
    """Screen for managing default values."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create form area
        self.create_form()

        # Load system defaults
        self.load_system_defaults()

    def create_header(self):
        """Create header."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        title = ctk.CTkLabel(
            header,
            text="Defaults Configuration",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=10, pady=10)

    def create_form(self):
        """Create form area."""
        scroll = ctk.CTkScrollableFrame(self)
        scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(1, weight=1)

        row = 0

        # Scope selector
        ctk.CTkLabel(
            scroll,
            text="Defaults For:",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=row, column=0, sticky="w", padx=10, pady=(0, 5))
        row += 1

        scope_frame = ctk.CTkFrame(scroll)
        scope_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=5)
        row += 1

        self.scope_var = ctk.StringVar(value="system")
        ctk.CTkRadioButton(
            scope_frame,
            text="System Defaults",
            variable=self.scope_var,
            value="system",
            command=self.on_scope_change
        ).pack(side="left", padx=10)

        ctk.CTkRadioButton(
            scope_frame,
            text="Who-specific:",
            variable=self.scope_var,
            value="who",
            command=self.on_scope_change
        ).pack(side="left", padx=10)

        who_values = self.db_manager.get_distinct_who_values()
        if not who_values:
            who_values = ["Self"]

        self.who_var = ctk.StringVar(value=who_values[0] if who_values else "Self")
        self.who_combo = ctk.CTkComboBox(
            scope_frame,
            values=who_values,
            variable=self.who_var,
            width=150,
            command=lambda _: self.load_defaults()
        )
        self.who_combo.pack(side="left", padx=5)

        # Default Who section
        ctk.CTkLabel(
            scroll,
            text="Default Who",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # WHO field
        ctk.CTkLabel(scroll, text="WHO:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        who_field_values = self.db_manager.get_distinct_who_values()
        if not who_field_values:
            who_field_values = ["Self"]
        self.who_field_var = ctk.StringVar(value="")
        self.who_field_combo = ctk.CTkComboBox(scroll, values=[""] + who_field_values, variable=self.who_field_var, width=200)
        self.who_field_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Priority factors section
        ctk.CTkLabel(
            scroll,
            text="Priority Factors",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # Importance
        ctk.CTkLabel(scroll, text="Importance:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        importance_values = [""] + [f"{k} ({v})" for k, v in PriorityFactors.IMPORTANCE.items()]
        self.importance_var = ctk.StringVar(value="")
        self.importance_combo = ctk.CTkComboBox(scroll, values=importance_values, variable=self.importance_var, width=200)
        self.importance_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Urgency
        ctk.CTkLabel(scroll, text="Urgency:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        urgency_values = [""] + [f"{k} ({v})" for k, v in PriorityFactors.URGENCY.items()]
        self.urgency_var = ctk.StringVar(value="")
        self.urgency_combo = ctk.CTkComboBox(scroll, values=urgency_values, variable=self.urgency_var, width=200)
        self.urgency_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Effort-Cost (Size internally)
        ctk.CTkLabel(scroll, text="Effort-Cost:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        size_values = [""] + [f"{k} ({v})" for k, v in PriorityFactors.SIZE.items()]
        self.size_var = ctk.StringVar(value="")
        self.size_combo = ctk.CTkComboBox(scroll, values=size_values, variable=self.size_var, width=200)
        self.size_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Value
        ctk.CTkLabel(scroll, text="Value:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        value_values = [""] + [f"{k} ({v})" for k, v in PriorityFactors.VALUE.items()]
        self.value_var = ctk.StringVar(value="")
        self.value_combo = ctk.CTkComboBox(scroll, values=value_values, variable=self.value_var, width=200)
        self.value_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Organization Factors section
        ctk.CTkLabel(
            scroll,
            text="Organization Factors",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # Group
        ctk.CTkLabel(scroll, text="Group:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        group_values = self.db_manager.get_distinct_groups()
        self.group_var = ctk.StringVar(value="")
        self.group_combo = ctk.CTkComboBox(scroll, values=[""] + group_values, variable=self.group_var, width=200)
        self.group_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Category
        ctk.CTkLabel(scroll, text="Category:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        category_values = self.db_manager.get_distinct_categories()
        self.category_var = ctk.StringVar(value="")
        self.category_combo = ctk.CTkComboBox(scroll, values=[""] + category_values, variable=self.category_var, width=200)
        self.category_combo.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Planned minutes
        ctk.CTkLabel(scroll, text="Planned Minutes:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        self.planned_minutes_entry = ctk.CTkEntry(scroll, width=100)
        self.planned_minutes_entry.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        row += 1

        # Date Offsets Section
        ctk.CTkLabel(
            scroll,
            text="Date Offsets (Days from Today)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(15, 5))
        row += 1

        # Start Date Offset
        ctk.CTkLabel(scroll, text="Start Date Offset:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        offset_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        offset_frame.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        self.start_offset_entry = ctk.CTkEntry(offset_frame, width=60, placeholder_text="0")
        self.start_offset_entry.pack(side="left")
        ctk.CTkLabel(offset_frame, text="(0=today, 1=tomorrow, etc.)", font=ctk.CTkFont(size=10)).pack(side="left", padx=5)
        row += 1

        # Due Date Offset
        ctk.CTkLabel(scroll, text="Due Date Offset:").grid(row=row, column=0, sticky="w", padx=10, pady=5)
        due_offset_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        due_offset_frame.grid(row=row, column=1, sticky="w", padx=10, pady=5)
        self.due_offset_entry = ctk.CTkEntry(due_offset_frame, width=60, placeholder_text="0")
        self.due_offset_entry.pack(side="left")
        ctk.CTkLabel(due_offset_frame, text="(0=today, 1=tomorrow, etc.)", font=ctk.CTkFont(size=10)).pack(side="left", padx=5)
        row += 1

        # Buttons
        btn_frame = ctk.CTkFrame(scroll)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", padx=10, pady=(20, 10))
        row += 1

        btn_save = ctk.CTkButton(btn_frame, text="Save Defaults", command=self.save_defaults)
        btn_save.pack(side="left", padx=5)

        btn_clear = ctk.CTkButton(btn_frame, text="Clear Form", command=self.clear_form)
        btn_clear.pack(side="left", padx=5)

        # Status label
        self.status_label = ctk.CTkLabel(scroll, text="", text_color="green")
        self.status_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=10, pady=5)

    def on_scope_change(self):
        """Handle scope change."""
        self.load_defaults()

    def load_defaults(self):
        """Load defaults based on current scope."""
        self.clear_form()

        scope_type = self.scope_var.get()
        scope_key = self.who_var.get() if scope_type == "who" else None

        defaults = self.db_manager.get_defaults(scope_type, scope_key)
        if not defaults:
            return

        # Load values
        if defaults.importance is not None:
            for k, v in PriorityFactors.IMPORTANCE.items():
                if v == defaults.importance:
                    self.importance_var.set(f"{k} ({v})")
                    break

        if defaults.urgency is not None:
            for k, v in PriorityFactors.URGENCY.items():
                if v == defaults.urgency:
                    self.urgency_var.set(f"{k} ({v})")
                    break

        if defaults.size is not None:
            for k, v in PriorityFactors.SIZE.items():
                if v == defaults.size:
                    self.size_var.set(f"{k} ({v})")
                    break

        if defaults.value is not None:
            for k, v in PriorityFactors.VALUE.items():
                if v == defaults.value:
                    self.value_var.set(f"{k} ({v})")
                    break

        if defaults.who:
            self.who_field_var.set(defaults.who)

        if defaults.group:
            self.group_var.set(defaults.group)

        if defaults.category:
            self.category_var.set(defaults.category)

        if defaults.planned_minutes is not None:
            self.planned_minutes_entry.insert(0, str(defaults.planned_minutes))

        if defaults.start_offset_days is not None:
            self.start_offset_entry.insert(0, str(defaults.start_offset_days))

        if defaults.due_offset_days is not None:
            self.due_offset_entry.insert(0, str(defaults.due_offset_days))

    def load_system_defaults(self):
        """Load system defaults initially."""
        self.load_defaults()

    def clear_form(self):
        """Clear all form fields."""
        self.importance_var.set("")
        self.urgency_var.set("")
        self.size_var.set("")
        self.value_var.set("")
        self.who_field_var.set("")
        self.group_var.set("")
        self.category_var.set("")
        self.planned_minutes_entry.delete(0, "end")
        self.start_offset_entry.delete(0, "end")
        self.due_offset_entry.delete(0, "end")
        self.status_label.configure(text="")

    def extract_factor_value(self, text: str) -> Optional[int]:
        """Extract numeric value from factor string."""
        if not text:
            return None
        try:
            return int(text.split("(")[1].split(")")[0])
        except Exception:
            return None

    def save_defaults(self):
        """Save defaults."""
        try:
            scope_type = self.scope_var.get()
            scope_key = self.who_var.get() if scope_type == "who" else None

            # Parse date offsets
            start_offset_text = self.start_offset_entry.get().strip()
            start_offset = int(start_offset_text) if start_offset_text else None

            due_offset_text = self.due_offset_entry.get().strip()
            due_offset = int(due_offset_text) if due_offset_text else None

            defaults = Defaults(
                scope_type=scope_type,
                scope_key=scope_key,
                who=self.who_field_var.get().strip() or None,
                importance=self.extract_factor_value(self.importance_var.get()),
                urgency=self.extract_factor_value(self.urgency_var.get()),
                size=self.extract_factor_value(self.size_var.get()),
                value=self.extract_factor_value(self.value_var.get()),
                group=self.group_var.get().strip() or None,
                category=self.category_var.get().strip() or None,
                planned_minutes=int(self.planned_minutes_entry.get()) if self.planned_minutes_entry.get().strip() else None,
                start_offset_days=start_offset,
                due_offset_days=due_offset
            )

            self.db_manager.save_defaults(defaults)
            self.status_label.configure(text="Defaults saved successfully!")
            # Refresh form to show saved values
            self.load_defaults()

        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}", text_color="red")
