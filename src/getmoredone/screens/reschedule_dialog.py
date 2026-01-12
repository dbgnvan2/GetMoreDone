"""
Reschedule dialog for changing item dates.
"""

import customtkinter as ctk
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager


class RescheduleDialog(ctk.CTkToplevel):
    """Dialog for rescheduling an action item."""

    def __init__(self, parent, db_manager: 'DatabaseManager', item_id: str):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item_id = item_id
        self.item = db_manager.get_action_item(item_id)

        if not self.item:
            self.destroy()
            return

        self.title(f"Reschedule: {self.item.title}")
        self.geometry("500x350")

        self.create_form()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Current dates
        ctk.CTkLabel(
            main_frame,
            text="Current Dates",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(0, 10))

        current_text = f"Start: {self.item.start_date or 'None'}\nDue: {self.item.due_date or 'None'}"
        ctk.CTkLabel(main_frame, text=current_text).pack(pady=(0, 20))

        # New dates
        ctk.CTkLabel(
            main_frame,
            text="New Dates",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(0, 10))

        # Start date
        date_frame = ctk.CTkFrame(main_frame)
        date_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(date_frame, text="Start Date:").pack(side="left", padx=5)
        self.start_entry = ctk.CTkEntry(date_frame, width=200, placeholder_text="YYYY-MM-DD")
        self.start_entry.pack(side="left", padx=5)
        if self.item.start_date:
            self.start_entry.insert(0, self.item.start_date)

        # Due date
        due_frame = ctk.CTkFrame(main_frame)
        due_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(due_frame, text="Due Date:").pack(side="left", padx=5)
        self.due_entry = ctk.CTkEntry(due_frame, width=200, placeholder_text="YYYY-MM-DD")
        self.due_entry.pack(side="left", padx=5)
        if self.item.due_date:
            self.due_entry.insert(0, self.item.due_date)

        # Reason
        ctk.CTkLabel(main_frame, text="Reason (optional):").pack(pady=(20, 5))
        self.reason_text = ctk.CTkTextbox(main_frame, height=80)
        self.reason_text.pack(fill="x", pady=5)

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")
        self.error_label.pack(pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.pack(pady=(20, 0))

        btn_save = ctk.CTkButton(btn_frame, text="Reschedule", command=self.save)
        btn_save.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy)
        btn_cancel.pack(side="left", padx=5)

    def save(self):
        """Save the rescheduled dates."""
        try:
            new_start = self.start_entry.get().strip() or None
            new_due = self.due_entry.get().strip() or None
            reason = self.reason_text.get("1.0", "end").strip() or None

            # Validate dates if both present
            if new_start and new_due:
                if new_due < new_start:
                    self.error_label.configure(text="Due date cannot be earlier than start date")
                    return

            # Save
            self.db_manager.reschedule_item(self.item_id, new_start, new_due, reason)
            self.destroy()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")
