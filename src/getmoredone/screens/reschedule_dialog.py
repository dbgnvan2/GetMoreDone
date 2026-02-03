"""
Push dialog for moving item to next day.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager


class RescheduleDialog(ctk.CTkToplevel):
    """Dialog for pushing an action item to the next day."""

    def __init__(self, parent, db_manager: 'DatabaseManager', item_id: str):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item_id = item_id
        self.item = db_manager.get_action_item(item_id)

        if not self.item:
            self.destroy()
            return

        self.title(f"Push to Next Day: {self.item.title}")
        self.geometry("500x300")

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

        # Calculate new dates (add 1 day)
        new_start = None
        new_due = None

        if self.item.start_date:
            try:
                start_dt = datetime.strptime(self.item.start_date, "%Y-%m-%d")
                new_start_dt = start_dt + timedelta(days=1)
                new_start = new_start_dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        if self.item.due_date:
            try:
                due_dt = datetime.strptime(self.item.due_date, "%Y-%m-%d")
                new_due_dt = due_dt + timedelta(days=1)
                new_due = new_due_dt.strftime("%Y-%m-%d")
            except ValueError:
                pass

        self.new_start = new_start
        self.new_due = new_due

        # New dates (auto-calculated)
        ctk.CTkLabel(
            main_frame,
            text="New Dates (after +1 day)",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(0, 10))

        new_text = f"Start: {new_start or 'None'}\nDue: {new_due or 'None'}"
        ctk.CTkLabel(
            main_frame,
            text=new_text,
            font=ctk.CTkFont(size=12),
            text_color="lightblue"
        ).pack(pady=(0, 20))

        # Reason
        ctk.CTkLabel(main_frame, text="Reason (optional):").pack(pady=(10, 5))
        self.reason_text = ctk.CTkTextbox(main_frame, height=60)
        self.reason_text.pack(fill="x", pady=5)

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")
        self.error_label.pack(pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.pack(pady=(15, 0))

        btn_save = ctk.CTkButton(btn_frame, text="Push to Next Day", command=self.save, fg_color="darkgreen", hover_color="green")
        btn_save.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy)
        btn_cancel.pack(side="left", padx=5)

    def save(self):
        """Save the pushed dates."""
        try:
            reason = self.reason_text.get("1.0", "end").strip() or None

            # Save with new dates
            self.db_manager.reschedule_item(self.item_id, self.new_start, self.new_due, reason)
            self.destroy()

        except Exception as e:
            self.error_label.configure(text=f"Error: {str(e)}")
