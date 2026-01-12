"""
Plan screen - time blocks and daily planning.
"""

import customtkinter as ctk
from datetime import datetime, date
from typing import TYPE_CHECKING

from ..models import TimeBlock

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class PlanScreen(ctk.CTkFrame):
    """Screen for planning time blocks."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Left: Backlog
        self.create_backlog()

        # Right: Day planner
        self.create_day_planner()

        # Load data
        self.refresh()

    def create_header(self):
        """Create header."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 0))

        title = ctk.CTkLabel(
            header,
            text="Plan - Time Blocks",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.pack(side="left", padx=10, pady=10)

    def create_backlog(self):
        """Create backlog panel."""
        backlog_frame = ctk.CTkFrame(self)
        backlog_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=10)
        backlog_frame.grid_columnconfigure(0, weight=1)
        backlog_frame.grid_rowconfigure(1, weight=1)

        # Header
        ctk.CTkLabel(
            backlog_frame,
            text="Open Items",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=10, pady=10, sticky="w")

        # Scrollable list
        self.backlog_scroll = ctk.CTkScrollableFrame(backlog_frame)
        self.backlog_scroll.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.backlog_scroll.grid_columnconfigure(0, weight=1)

    def create_day_planner(self):
        """Create day planner panel."""
        planner_frame = ctk.CTkFrame(self)
        planner_frame.grid(row=1, column=1, sticky="nsew", padx=(5, 10), pady=10)
        planner_frame.grid_columnconfigure(0, weight=1)
        planner_frame.grid_rowconfigure(2, weight=1)

        # Date selector
        date_frame = ctk.CTkFrame(planner_frame)
        date_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(date_frame, text="Date:").pack(side="left", padx=5)

        today = date.today().strftime("%Y-%m-%d")
        self.date_var = ctk.StringVar(value=today)
        self.date_entry = ctk.CTkEntry(date_frame, textvariable=self.date_var, width=150)
        self.date_entry.pack(side="left", padx=5)

        btn_refresh = ctk.CTkButton(
            date_frame,
            text="Load",
            width=80,
            command=self.load_time_blocks
        )
        btn_refresh.pack(side="left", padx=5)

        btn_add = ctk.CTkButton(
            date_frame,
            text="+ Add Block",
            command=self.add_time_block
        )
        btn_add.pack(side="left", padx=5)

        # Time blocks header
        ctk.CTkLabel(
            planner_frame,
            text="Time Blocks",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=1, column=0, padx=10, pady=(10, 5), sticky="w")

        # Scrollable blocks
        self.blocks_scroll = ctk.CTkScrollableFrame(planner_frame)
        self.blocks_scroll.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)
        self.blocks_scroll.grid_columnconfigure(0, weight=1)

    def refresh(self):
        """Refresh backlog and time blocks."""
        self.load_backlog()
        self.load_time_blocks()

    def load_backlog(self):
        """Load open items into backlog."""
        for widget in self.backlog_scroll.winfo_children():
            widget.destroy()

        items = self.db_manager.get_all_items(
            status_filter="open",
            sort_by="priority_score",
            sort_desc=True
        )

        for item in items[:50]:  # Limit to 50 items
            frame = ctk.CTkFrame(self.backlog_scroll)
            frame.grid(sticky="ew", pady=2)
            frame.grid_columnconfigure(0, weight=1)

            info_text = f"{item.title} (P:{item.priority_score})"
            if item.planned_minutes:
                info_text += f" - {item.planned_minutes}m"

            ctk.CTkLabel(frame, text=info_text, anchor="w").grid(
                row=0, column=0, sticky="w", padx=5, pady=5
            )

    def load_time_blocks(self):
        """Load time blocks for selected date."""
        for widget in self.blocks_scroll.winfo_children():
            widget.destroy()

        selected_date = self.date_var.get()
        blocks = self.db_manager.get_time_blocks(selected_date)

        if not blocks:
            ctk.CTkLabel(
                self.blocks_scroll,
                text="No time blocks for this date"
            ).grid(row=0, column=0, pady=20)
            return

        for block in blocks:
            frame = ctk.CTkFrame(self.blocks_scroll)
            frame.grid(sticky="ew", pady=2, padx=5)
            frame.grid_columnconfigure(1, weight=1)

            # Time
            ctk.CTkLabel(
                frame,
                text=f"{block.start_time} - {block.end_time}",
                width=120
            ).grid(row=0, column=0, padx=5, pady=5)

            # Label/item
            label_text = block.label or "Unassigned"
            ctk.CTkLabel(frame, text=label_text, anchor="w").grid(
                row=0, column=1, sticky="w", padx=5, pady=5
            )

            # Minutes
            ctk.CTkLabel(frame, text=f"{block.planned_minutes}m", width=60).grid(
                row=0, column=2, padx=5, pady=5
            )

            # Delete button
            btn_delete = ctk.CTkButton(
                frame,
                text="Delete",
                width=60,
                command=lambda b=block.id: self.delete_block(b)
            )
            btn_delete.grid(row=0, column=3, padx=5, pady=5)

    def add_time_block(self):
        """Add a new time block."""
        dialog = AddTimeBlockDialog(self, self.db_manager, self.date_var.get())
        dialog.wait_window()
        self.load_time_blocks()

    def delete_block(self, block_id: str):
        """Delete a time block."""
        self.db_manager.delete_time_block(block_id)
        self.load_time_blocks()


class AddTimeBlockDialog(ctk.CTkToplevel):
    """Dialog for adding a time block."""

    def __init__(self, parent, db_manager, block_date: str):
        super().__init__(parent)
        self.db_manager = db_manager
        self.block_date = block_date

        self.title("Add Time Block")
        self.geometry("400x300")

        self.create_form()
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create form."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Start time
        ctk.CTkLabel(main_frame, text="Start Time (HH:MM):").pack(pady=(0, 5))
        self.start_entry = ctk.CTkEntry(main_frame, placeholder_text="09:00")
        self.start_entry.pack(pady=(0, 10))

        # End time
        ctk.CTkLabel(main_frame, text="End Time (HH:MM):").pack(pady=(0, 5))
        self.end_entry = ctk.CTkEntry(main_frame, placeholder_text="10:00")
        self.end_entry.pack(pady=(0, 10))

        # Label
        ctk.CTkLabel(main_frame, text="Label:").pack(pady=(0, 5))
        self.label_entry = ctk.CTkEntry(main_frame)
        self.label_entry.pack(pady=(0, 10))

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.pack(pady=(20, 0))

        btn_save = ctk.CTkButton(btn_frame, text="Save", command=self.save)
        btn_save.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy)
        btn_cancel.pack(side="left", padx=5)

    def save(self):
        """Save time block."""
        try:
            start_time = self.start_entry.get().strip()
            end_time = self.end_entry.get().strip()
            label = self.label_entry.get().strip() or None

            # Calculate minutes
            start_hour, start_min = map(int, start_time.split(":"))
            end_hour, end_min = map(int, end_time.split(":"))
            minutes = (end_hour * 60 + end_min) - (start_hour * 60 + start_min)

            block = TimeBlock(
                block_date=self.block_date,
                start_time=start_time,
                end_time=end_time,
                planned_minutes=minutes,
                label=label
            )

            self.db_manager.create_time_block(block)
            self.destroy()

        except Exception as e:
            print(f"Error: {e}")
