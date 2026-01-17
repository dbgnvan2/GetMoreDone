"""
Today view screen - shows items for today including completed ones.
"""

import customtkinter as ctk
from datetime import datetime, date
from typing import Optional

from ..db_manager import DatabaseManager
from ..models import ActionItem
from ..app_settings import AppSettings
from ..date_utils import increment_date


class TodayScreen(ctk.CTkFrame):
    """Screen showing today's items (start <= today), including completed items."""

    def __init__(self, parent, db_manager: DatabaseManager):
        super().__init__(parent)
        self.db_manager = db_manager
        self.settings = AppSettings.load()
        self.columns_expanded = True  # Track column visibility state

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="Today's Items",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        # Expand/Collapse button
        self.expand_collapse_btn = ctk.CTkButton(
            header_frame,
            text="Collapse",
            width=100,
            command=self.toggle_columns
        )
        self.expand_collapse_btn.grid(row=0, column=1, padx=5)

        # New Item button
        btn_new = ctk.CTkButton(
            header_frame,
            text="+ New Item",
            width=100,
            fg_color="green",
            hover_color="darkgreen",
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=2, padx=5)

        # Refresh button
        btn_refresh = ctk.CTkButton(
            header_frame,
            text="Refresh",
            width=100,
            command=self.refresh
        )
        btn_refresh.grid(row=0, column=3, padx=5)

        # Scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load items
        self.load_items()

    def toggle_columns(self):
        """Toggle between expanded and collapsed column view."""
        self.columns_expanded = not self.columns_expanded
        self.expand_collapse_btn.configure(text="Expand" if not self.columns_expanded else "Collapse")
        self.load_items()

    def refresh(self):
        """Refresh the view."""
        self.settings = AppSettings.load()  # Reload settings for icon changes
        self.load_items()

    def load_items(self):
        """Load and display today's items."""
        # Clear existing items
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get today's items (start_date <= today, includes completed)
        items = self.get_todays_items()

        if not items:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No items for today",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Separate open and completed items
        open_items = [item for item in items if item.status == "open"]
        completed_items = [item for item in items if item.status == "completed"]

        row = 0

        # Open items section
        if open_items:
            open_header = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
            open_header.grid(row=row, column=0, sticky="ew", pady=(10, 0), padx=5)
            ctk.CTkLabel(
                open_header,
                text=f"To Do ({len(open_items)} items)",
                font=ctk.CTkFont(size=14, weight="bold")
            ).pack(padx=10, pady=5, anchor="w")
            row += 1

            for item in open_items:
                item_frame = self.create_item_row(item)
                item_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
                row += 1

        # Completed items section
        if completed_items:
            # Calculate total time for completed items
            total_minutes = sum(item.planned_minutes for item in completed_items if item.planned_minutes)

            # Format time
            if total_minutes >= 60:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                if minutes > 0:
                    time_str = f"{hours}h {minutes}m"
                else:
                    time_str = f"{hours}h"
            else:
                time_str = f"{total_minutes}m" if total_minutes > 0 else "0m"

            completed_header = ctk.CTkFrame(self.scroll_frame, fg_color="darkgreen")
            completed_header.grid(row=row, column=0, sticky="ew", pady=(20, 0), padx=5)
            ctk.CTkLabel(
                completed_header,
                text=f"Completed ({len(completed_items)} items | Time: {time_str})",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color="lightgreen"
            ).pack(padx=10, pady=5, anchor="w")
            row += 1

            for item in completed_items:
                item_frame = self.create_item_row(item, is_completed=True)
                item_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
                row += 1

    def get_todays_items(self):
        """Get items for today (start_date <= today for open items, completed_at = today for completed items)."""
        today = datetime.now().date().isoformat()

        # Get open items where start date <= today (or due date if no start date)
        # AND completed items where completed_at is today
        query = """
            SELECT * FROM action_items
            WHERE (
                -- Open items: start/due date <= today
                (status = 'open'
                 AND (start_date IS NOT NULL OR due_date IS NOT NULL)
                 AND COALESCE(start_date, due_date) <= ?)
                OR
                -- Completed items: completed today (date part of completed_at matches today)
                (status = 'completed'
                 AND completed_at IS NOT NULL
                 AND DATE(completed_at) = ?)
            )
            ORDER BY status ASC, COALESCE(start_date, due_date) ASC, priority_score DESC
        """

        rows = self.db_manager.db.conn.execute(query, (today, today)).fetchall()
        return [self.db_manager._row_to_action_item(row) for row in rows]

    def create_item_row(self, item: ActionItem, is_completed: bool = False) -> ctk.CTkFrame:
        """Create a row for an action item."""
        # Determine background color: RED for critical items, gray for completed, default otherwise
        is_critical = (item.importance == 20 or item.urgency == 20)
        if is_critical and not is_completed:
            bg_color = "darkred"
        elif is_completed:
            bg_color = "gray20"
        else:
            bg_color = None

        frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
        frame.grid_columnconfigure(1, weight=1)

        # Completion indicator
        if is_completed:
            # Show custom completion icon
            completion_text = self.settings.completion_icon
            ctk.CTkLabel(
                frame,
                text=completion_text,
                font=ctk.CTkFont(size=16),
                text_color="lightgreen",
                width=30
            ).grid(row=0, column=0, padx=5, pady=5)
        else:
            # Complete checkbox for open items
            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(
                frame,
                text="",
                variable=var,
                width=30,
                command=lambda: self.complete_item(item.id)
            )
            checkbox.grid(row=0, column=0, padx=5, pady=5)

        # Title and info
        info_text = f"{item.title}"
        if item.who:
            info_text += f" ({item.who})"

        title_label = ctk.CTkLabel(
            frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color="gray60" if is_completed else None
        )
        title_label.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Start Date
        start_date_text = item.start_date if item.start_date else "-"
        if item.start_date:
            try:
                dt = datetime.fromisoformat(item.start_date)
                start_date_text = dt.strftime("%m/%d")
            except:
                pass
        start_label = ctk.CTkLabel(
            frame,
            text=f"S:{start_date_text}",
            width=60,
            anchor="w",
            text_color="lightblue"
        )
        start_label.grid(row=0, column=2, padx=5, pady=5)

        # Due Date
        due_date_text = item.due_date if item.due_date else "-"
        if item.due_date:
            try:
                dt = datetime.fromisoformat(item.due_date)
                due_date_text = dt.strftime("%m/%d")
            except:
                pass
        due_label = ctk.CTkLabel(
            frame,
            text=f"D:{due_date_text}",
            width=60,
            anchor="w",
            text_color="orange"
        )
        due_label.grid(row=0, column=3, padx=5, pady=5)

        # Priority score
        score_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=60,
            fg_color="gray30"
        )
        score_label.grid(row=0, column=4, padx=5, pady=5)

        # Factor chips (I, U, E, V) - only shown when expanded
        factors_frame = ctk.CTkFrame(frame, fg_color="transparent")
        if self.columns_expanded:
            factors_frame.grid(row=0, column=5, padx=5, pady=5)
            col = 0
            if item.importance:
                ctk.CTkLabel(factors_frame, text=f"I:{item.importance}", width=40).grid(row=0, column=col, padx=2)
                col += 1
            if item.urgency:
                ctk.CTkLabel(factors_frame, text=f"U:{item.urgency}", width=40).grid(row=0, column=col, padx=2)
                col += 1
            if item.size:
                ctk.CTkLabel(factors_frame, text=f"E:{item.size}", width=40).grid(row=0, column=col, padx=2)
                col += 1
            if item.value:
                ctk.CTkLabel(factors_frame, text=f"V:{item.value}", width=40).grid(row=0, column=col, padx=2)
                col += 1

        # Action buttons (only for open items)
        # Column positions shift based on whether factors are shown
        btn_col_start = 6 if self.columns_expanded else 5
        if not is_completed:
            btn_timer = ctk.CTkButton(
                frame,
                text="⏱ Timer",
                width=70,
                fg_color="darkgreen",
                hover_color="green",
                command=lambda: self.start_timer(item.id)
            )
            btn_timer.grid(row=0, column=btn_col_start, padx=2, pady=5)

            btn_edit = ctk.CTkButton(
                frame,
                text="Edit",
                width=60,
                command=lambda: self.edit_item(item.id)
            )
            btn_edit.grid(row=0, column=btn_col_start+1, padx=2, pady=5)

            btn_push = ctk.CTkButton(
                frame,
                text="Push",
                width=60,
                fg_color="orange",
                hover_color="darkorange",
                command=lambda item_id=item.id: self.push_item(item_id)
            )
            btn_push.grid(row=0, column=btn_col_start+2, padx=2, pady=5)

        return frame

    def complete_item(self, item_id: str):
        """Mark item as complete."""
        self.db_manager.complete_action_item(item_id)
        self.refresh()

    def start_timer(self, item_id: str):
        """Start timer for an action item."""
        # Get the action item
        item = self.db_manager.get_action_item(item_id)
        if not item:
            return

        # Open timer window
        from .timer_window import TimerWindow
        timer = TimerWindow(self, self.db_manager, item, on_close=self.refresh)

    def edit_item(self, item_id: str):
        """Open item editor."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager, item_id)
        dialog.wait_window()
        self.refresh()

    def create_new_item(self):
        """Open item editor for new item."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager)
        dialog.wait_window()
        self.refresh()

    def push_item(self, item_id: str):
        """Push item to next day without showing dialog, using weekend-aware logic."""
        # Get the item
        item = self.db_manager.get_action_item(item_id)
        if not item:
            return

        # Load settings for weekend handling
        settings = AppSettings.load()

        # Calculate new dates (add 1 day using weekend-aware logic)
        new_start = None
        new_due = None

        if item.start_date:
            try:
                start_dt = date.fromisoformat(item.start_date)
                new_start_dt = increment_date(start_dt, 1, settings.include_saturday, settings.include_sunday)
                new_start = new_start_dt.isoformat()
            except ValueError:
                pass

        if item.due_date:
            try:
                due_dt = date.fromisoformat(item.due_date)
                new_due_dt = increment_date(due_dt, 1, settings.include_saturday, settings.include_sunday)
                new_due = new_due_dt.isoformat()
            except ValueError:
                pass

        # Push to next day directly (no dialog, no reason)
        self.db_manager.reschedule_item(item_id, new_start, new_due, reason=None)
        self.refresh()
