"""
Upcoming screen - shows items due in next N days.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from ..models import ActionItem

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class UpcomingScreen(ctk.CTkFrame):
    """Screen showing upcoming items grouped by due date."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load items
        self.refresh()

    def create_header(self):
        """Create header with controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(3, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="Upcoming Items",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # N-days selector
        ctk.CTkLabel(header, text="Next").grid(row=0, column=1, padx=(20, 5), pady=10)

        self.days_var = ctk.StringVar(value="7")
        self.days_combo = ctk.CTkComboBox(
            header,
            values=["1", "3", "7", "14", "30"],
            variable=self.days_var,
            width=80,
            command=lambda _: self.refresh()
        )
        self.days_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkLabel(header, text="days").grid(row=0, column=3, sticky="w", padx=5, pady=10)

        # Who filter
        ctk.CTkLabel(header, text="Who:").grid(row=0, column=4, padx=(20, 5), pady=10)

        who_values = ["All"] + self.db_manager.get_distinct_who_values()
        self.who_var = ctk.StringVar(value="All")
        self.who_combo = ctk.CTkComboBox(
            header,
            values=who_values,
            variable=self.who_var,
            width=150,
            command=lambda _: self.refresh()
        )
        self.who_combo.grid(row=0, column=5, padx=5, pady=10)

        # New Item button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Item",
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=6, padx=10, pady=10)

    def refresh(self):
        """Refresh the list of upcoming items."""
        # Clear current items
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get filters
        n_days = int(self.days_var.get())
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()

        # Get items
        items = self.db_manager.get_upcoming_items(n_days, who_filter)

        if not items:
            label = ctk.CTkLabel(
                self.scroll_frame,
                text="No upcoming items",
                font=ctk.CTkFont(size=14)
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Group by start date (or due date if no start date)
        grouped = {}
        for item in items:
            date_key = item.start_date or item.due_date or "No start date"
            if date_key not in grouped:
                grouped[date_key] = []
            grouped[date_key].append(item)

        # Display grouped items
        row = 0
        for start_date in sorted(grouped.keys()):
            items_for_date = grouped[start_date]

            # Date header
            total_planned = sum(item.planned_minutes or 0 for item in items_for_date)
            date_label = self.format_date_header(start_date, len(items_for_date), total_planned)

            header_frame = ctk.CTkFrame(self.scroll_frame, fg_color="gray25")
            header_frame.grid(row=row, column=0, sticky="ew", pady=(10, 0), padx=5)
            header_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                header_frame,
                text=date_label,
                font=ctk.CTkFont(size=14, weight="bold")
            ).grid(row=0, column=0, sticky="w", padx=10, pady=5)

            row += 1

            # Items for this date
            for item in items_for_date:
                item_frame = self.create_item_row(item)
                item_frame.grid(row=row, column=0, sticky="ew", pady=2, padx=5)
                row += 1

    def create_item_row(self, item: ActionItem) -> ctk.CTkFrame:
        """Create a row for an action item."""
        # RED background for critical items
        is_critical = (item.importance == 20 or item.urgency == 20)
        bg_color = "darkred" if is_critical else None
        frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
        frame.grid_columnconfigure(1, weight=1)

        # Complete checkbox
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
            anchor="w"
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

        # Group
        group_label = ctk.CTkLabel(
            frame,
            text=item.group or "",
            width=80,
            anchor="w"
        )
        group_label.grid(row=0, column=4, padx=5, pady=5)

        # Category
        category_label = ctk.CTkLabel(
            frame,
            text=item.category or "",
            width=80,
            anchor="w"
        )
        category_label.grid(row=0, column=5, padx=5, pady=5)

        # Priority score
        score_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=60,
            fg_color="gray30"
        )
        score_label.grid(row=0, column=6, padx=5, pady=5)

        # Factor chips
        factors_frame = ctk.CTkFrame(frame, fg_color="transparent")
        factors_frame.grid(row=0, column=7, padx=5, pady=5)

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

        # Planned minutes
        if item.planned_minutes:
            minutes_label = ctk.CTkLabel(
                frame,
                text=f"{item.planned_minutes}m",
                width=50
            )
            minutes_label.grid(row=0, column=8, padx=5, pady=5)

        # Action buttons
        btn_timer = ctk.CTkButton(
            frame,
            text="⏱ Timer",
            width=70,
            fg_color="darkgreen",
            hover_color="green",
            command=lambda: self.start_timer(item.id)
        )
        btn_timer.grid(row=0, column=9, padx=2, pady=5)

        btn_edit = ctk.CTkButton(
            frame,
            text="Edit",
            width=60,
            command=lambda: self.edit_item(item.id)
        )
        btn_edit.grid(row=0, column=10, padx=2, pady=5)

        btn_push = ctk.CTkButton(
            frame,
            text="Push",
            width=60,
            fg_color="orange",
            hover_color="darkorange",
            command=lambda: self.push_item(item.id)
        )
        btn_push.grid(row=0, column=11, padx=2, pady=5)

        return frame

    def format_date_header(self, start_date: str, count: int, total_minutes: int) -> str:
        """Format date header text."""
        if start_date == "No start date":
            return f"{start_date} ({count} items)"

        try:
            dt = datetime.fromisoformat(start_date)
            day_name = dt.strftime("%A, %B %d, %Y")

            # Check if today, tomorrow, etc.
            today = datetime.now().date()
            item_date = dt.date()
            days_diff = (item_date - today).days

            if days_diff == 0:
                day_name = f"Today - {day_name}"
            elif days_diff == 1:
                day_name = f"Tomorrow - {day_name}"
            elif days_diff < 7:
                day_name = f"This {dt.strftime('%A')} - {day_name}"

            header = f"{day_name} ({count} items"
            if total_minutes > 0:
                hours = total_minutes // 60
                mins = total_minutes % 60
                if hours > 0:
                    header += f", {hours}h {mins}m"
                else:
                    header += f", {mins}m"
            header += ")"

            return header
        except Exception:
            return f"{due_date} ({count} items)"

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

    def push_item(self, item_id: str):
        """Push item to today (set both start and due to today)."""
        from datetime import datetime
        today = datetime.now().date().strftime("%Y-%m-%d")

        # Set both start and due dates to today
        self.db_manager.reschedule_item(item_id, today, today, "Pushed to today")
        self.refresh()

    def create_new_item(self):
        """Open item editor for new item."""
        from .item_editor import ItemEditorDialog
        dialog = ItemEditorDialog(self, self.db_manager)
        dialog.wait_window()
        self.refresh()
