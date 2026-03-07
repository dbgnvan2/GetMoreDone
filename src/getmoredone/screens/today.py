"""
Today view screen - shows items for today including completed ones.
"""

import customtkinter as ctk
from datetime import datetime, date
from typing import Optional, TYPE_CHECKING

from ..db_manager import DatabaseManager
from ..models import ActionItem
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from ..date_utils import increment_date
from .segment_color_utils import resolve_segment_color_for_item
from ..theme import apply_segment_accent, semantic_colors, button_style, list_row_font
from .inline_editors import InlineDateDialog, InlinePriorityDialog
from .title_format import (
    split_action_item_title,
    format_column_text,
    TITLE_COL_CHARS,
    CONTEXT_COL_CHARS,
    CONTACT_COL_CHARS,
)

if TYPE_CHECKING:
    from ..app import GetMoreDoneApp


class TodayScreen(ctk.CTkFrame):
    """Screen showing today's items (start <= today), including completed items."""

    def __init__(self, parent, db_manager: DatabaseManager, app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.settings = AppSettings.load()
        self.segment_colors_by_id = {}
        self.segment_colors_by_name = {}
        self._parent_segment_cache = {}
        self._ape_segment_cache = {}
        self._week_action_segment_cache = {}
        # Track column visibility state (use setting)
        self.columns_expanded = self.settings.default_columns_expanded
        self.show_top_3_only = False  # Track Top 3 mode
        self.search_query = ""  # Track search query
        self.palette = semantic_colors()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        header_frame.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="Today's Items",
            font=ctk.CTkFont(size=24, weight="bold")
        ).grid(row=0, column=0, sticky="w")

        # Search entry
        self.search_entry = ctk.CTkEntry(
            header_frame,
            placeholder_text="Search title, description, next action...",
            width=250
        )
        self.search_entry.grid(row=0, column=1, padx=5)
        self.search_entry.bind("<Return>", lambda e: self.perform_search())

        # Search button
        btn_search = ctk.CTkButton(
            header_frame,
            text="Search",
            width=80,
            **button_style("secondary"),
            command=self.perform_search
        )
        btn_search.grid(row=0, column=2, padx=5)

        # Expand/Collapse button
        self.expand_collapse_btn = ctk.CTkButton(
            header_frame,
            text="Collapse" if self.columns_expanded else "Expand",
            width=100,
            **button_style("secondary"),
            command=self.toggle_columns
        )
        self.expand_collapse_btn.grid(row=0, column=3, padx=5)

        # Top 3 toggle button
        self.top3_btn = ctk.CTkButton(
            header_frame,
            text="Top 3",
            width=100,
            **button_style("secondary"),
            command=self.toggle_top3
        )
        self.top3_btn.grid(row=0, column=4, padx=5)

        # New Item button
        btn_new = ctk.CTkButton(
            header_frame,
            text="+ New Item",
            width=100,
            **button_style("primary"),
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=6, padx=5)

        # Refresh button
        btn_refresh = ctk.CTkButton(
            header_frame,
            text="Refresh",
            width=100,
            **button_style("secondary"),
            command=self.refresh
        )
        btn_refresh.grid(row=0, column=7, padx=5)

        # Scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(
            row=1, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load items
        self.load_items()

    def perform_search(self):
        """Perform search and update the view."""
        self.search_query = self.search_entry.get().strip()
        self.load_items()

    def toggle_columns(self):
        """Toggle between expanded and collapsed column view."""
        self.columns_expanded = not self.columns_expanded
        self.expand_collapse_btn.configure(
            text="Expand" if not self.columns_expanded else "Collapse")
        self.load_items()

    def toggle_top3(self):
        """Toggle between showing all items and showing only top 3 by priority."""
        self.show_top_3_only = not self.show_top_3_only
        self.top3_btn.configure(
            text="Show All" if self.show_top_3_only else "Top 3")
        self.top3_btn.configure(
            **button_style("primary" if self.show_top_3_only else "secondary")
        )
        self.load_items()

    def refresh(self):
        """Refresh the view."""
        self.settings = AppSettings.load()  # Reload settings for icon changes
        self.load_items()

    def load_items(self):
        """Load and display today's items."""
        self.palette = semantic_colors()
        # Temporarily remove scroll_frame from grid to prevent flickering during rebuild
        grid_info = self.scroll_frame.grid_info()
        self.scroll_frame.grid_remove()

        try:
            # Clear existing items
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()

            # Get today's items (start_date <= today, includes completed)
            items = self.get_todays_items()

            # Refresh VPS color caches
            self.segment_colors_by_id = self.app.vps_manager.get_segment_colors_by_id()
            self.segment_colors_by_name = self.app.vps_manager.get_segment_color_map()
            self._parent_segment_cache = {}
            self._ape_segment_cache = {}
            self._week_action_segment_cache = {}

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
            completed_items = [
                item for item in items if item.status == "completed"]

            # Filter to top 3 by priority if toggle is on
            # Items are already sorted by priority_score DESC in the query
            if self.show_top_3_only and len(open_items) > 3:
                # Sort open items by priority_score descending to ensure top 3
                open_items_sorted = sorted(
                    open_items, key=lambda x: x.priority_score, reverse=True)
                open_items = open_items_sorted[:3]

            row = 0

            # Open items section
            if open_items:
                open_header = ctk.CTkFrame(
                    self.scroll_frame, fg_color=self.palette["surface_subtle"])
                open_header.grid(row=row, column=0,
                                 sticky="ew", pady=(10, 0), padx=5)
                ctk.CTkLabel(
                    open_header,
                    text=f"To Do ({len(open_items)} items)",
                    font=ctk.CTkFont(size=14, weight="bold")
                ).pack(padx=10, pady=5, anchor="w")
                row += 1

                for item in open_items:
                    item_frame = self.create_item_row(item)
                    item_frame.grid(row=row, column=0,
                                    sticky="ew", pady=2, padx=5)
                    row += 1

            # Completed items section
            if completed_items:
                # Calculate total time for completed items
                total_minutes = sum(
                    item.planned_minutes for item in completed_items if item.planned_minutes)

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

                completed_header = ctk.CTkFrame(
                    self.scroll_frame, fg_color=self.palette["success_strong"])
                completed_header.grid(
                    row=row, column=0, sticky="ew", pady=(20, 0), padx=5)
                ctk.CTkLabel(
                    completed_header,
                    text=f"Completed ({len(completed_items)} items | Time: {time_str})",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=self.palette["on_strong"]
                ).pack(padx=10, pady=5, anchor="w")
                row += 1

                for item in completed_items:
                    item_frame = self.create_item_row(item, is_completed=True)
                    item_frame.grid(row=row, column=0,
                                    sticky="ew", pady=2, padx=5)
                    row += 1
        finally:
            # Restore scroll_frame to grid - this ensures it's shown even if an error occurs
            self.scroll_frame.grid(**grid_info)

    def get_todays_items(self):
        """Get items for today (start_date <= today for open items, completed_at = today for completed items)."""
        today = datetime.now().date().isoformat()

        # If search query exists, use search instead
        if self.search_query:
            all_items = self.db_manager.search_items(self.search_query)
            # Filter to today's items
            todays_items = []
            for item in all_items:
                # Include open items where start/due date <= today
                if item.status == "open":
                    if item.start_date and item.start_date <= today:
                        todays_items.append(item)
                    elif not item.start_date and item.due_date and item.due_date <= today:
                        todays_items.append(item)
                # Include completed items completed today
                elif item.status == "completed" and item.completed_at:
                    if item.completed_at.startswith(today):
                        todays_items.append(item)
            return todays_items

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

        rows = self.db_manager.db.conn.execute(
            query, (today, today)).fetchall()
        return [self.db_manager._row_to_action_item(row) for row in rows]

    def create_item_row(self, item: ActionItem, is_completed: bool = False) -> ctk.CTkFrame:
        """Create a row for an action item."""
        palette = self.palette
        segment_color = resolve_segment_color_for_item(
            item,
            self.segment_colors_by_id,
            self.segment_colors_by_name,
            self.db_manager,
            self._parent_segment_cache,
            self._ape_segment_cache,
            self._week_action_segment_cache,
        )
        is_critical = (item.importance == 20 or item.urgency == 20)
        if segment_color:
            bg_color = segment_color
        elif is_completed:
            bg_color = palette["success_tint"]
        elif is_critical:
            bg_color = palette["critical_tint"]
        else:
            bg_color = None

        frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
        apply_segment_accent(frame, segment_color)
        frame.grid_columnconfigure(1, weight=1)
        parsed = split_action_item_title(item.title)

        # Completion indicator
        if is_completed:
            # Show custom completion icon
            completion_text = self.settings.completion_icon
            ctk.CTkLabel(
                frame,
                text=completion_text,
                font=ctk.CTkFont(size=16),
                text_color="black",
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

        title_cell = ctk.CTkFrame(frame, fg_color="transparent")
        title_cell.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        if item.item_type == "week":
            ctk.CTkLabel(
                title_cell,
                text="WT",
                width=28,
                corner_radius=6,
                fg_color=palette["success_strong"],
                text_color=palette["on_strong"],
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="left", padx=(0, 6))
        title_label = ctk.CTkLabel(
            title_cell,
            text=format_column_text(parsed.title, TITLE_COL_CHARS),
            width=300,
            font=list_row_font(),
            anchor="w",
            text_color="black"
        )
        title_label.pack(side="left")
        title_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_item(item_id))

        # Context
        ctk.CTkLabel(
            frame,
            text=format_column_text(parsed.context, CONTEXT_COL_CHARS),
            width=140,
            anchor="w",
            text_color="black",
            font=list_row_font(),
        ).grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # Who
        ctk.CTkLabel(
            frame,
            text=format_column_text(item.who, CONTACT_COL_CHARS),
            width=100,
            anchor="w",
            text_color="black",
            font=list_row_font(),
        ).grid(row=0, column=3, padx=5, pady=5, sticky="w")

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
            text_color="black",
            font=list_row_font()
        )
        start_label.grid(row=0, column=4, padx=5, pady=5)
        start_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_start_date_inline(item_id))

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
            text_color="black",
            font=list_row_font()
        )
        due_label.grid(row=0, column=5, padx=5, pady=5)
        due_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_due_date_inline(item_id))

        # Priority score
        is_priority_critical = item.importance == 20 or item.urgency == 20
        score_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=60,
            fg_color=palette["danger"] if is_priority_critical else "transparent",
            text_color=pick_text_color(palette["danger"]) if is_priority_critical else "black",
            corner_radius=6 if is_priority_critical else 0,
            font=list_row_font(),
        )
        score_label.grid(row=0, column=6, padx=5, pady=5)
        score_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_priority_inline(item_id))

        # Estimated time (planned_minutes) - ALWAYS shown (not collapsed)
        time_text = f"{item.planned_minutes}m" if item.planned_minutes else "-"
        time_label = ctk.CTkLabel(
            frame,
            text=time_text,
            width=50,
            anchor="w",
            text_color="black",
            font=list_row_font()
        )
        time_label.grid(row=0, column=7, padx=5, pady=5)

        # Factor chips (I, U, E, V) - only shown when expanded
        factors_frame = ctk.CTkFrame(frame, fg_color="transparent")
        if self.columns_expanded:
            factors_frame.grid(row=0, column=8, padx=5, pady=5)
            columns = [
                ("G", item.group, 120),
                ("C", item.category, 120),
                ("I", item.importance, 40),
                ("U", item.urgency, 40),
                ("E", item.size, 40),
                ("V", item.value, 40),
            ]
            for col, (label, value, width) in enumerate(columns):
                text = f"{label}:{value}" if value not in (None, "") else ""
                label_kwargs = {
                    "text": text,
                    "width": width,
                    "anchor": "w",
                    "font": list_row_font(),
                    "text_color": "black",
                }
                if label in ("I", "U") and str(value).strip() == "20":
                    label_kwargs["fg_color"] = palette["danger"]
                    label_kwargs["text_color"] = pick_text_color(palette["danger"])
                    label_kwargs["corner_radius"] = 6
                ctk.CTkLabel(factors_frame, **label_kwargs).grid(
                    row=0, column=col, padx=2)

        # Action buttons (only for open items)
        # Column positions shift based on whether factors are shown
        btn_col_start = 9 if self.columns_expanded else 8
        if not is_completed:
            btn_timer = ctk.CTkButton(
                frame,
                text="⏱ Timer",
                width=70,
                **button_style("secondary"),
                command=lambda: self.start_timer(item.id)
            )
            btn_timer.grid(row=0, column=btn_col_start, padx=(0, 2), pady=5)

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

    def edit_item(self, item_id: str, focus_tab: str | None = None):
        """Open item editor."""
        from .item_editor import ItemEditorDialog
        ItemEditorDialog(self, self.db_manager, item_id,
                         vps_manager=self.app.vps_manager, on_close_callback=self.refresh,
                         focus_tab=focus_tab)

    def edit_start_date_inline(self, item_id: str):
        """Edit item start date in place."""
        item = self.db_manager.get_action_item(item_id)
        if not item:
            return
        dialog = InlineDateDialog(self, "Edit Start Date", item.start_date)
        self.wait_window(dialog)
        if dialog.result == "__cancel__":
            return
        new_start = dialog.result
        new_due = item.due_date
        if new_start and new_due and new_due < new_start:
            new_due = new_start
        self.db_manager.reschedule_item(item_id, new_start, new_due, reason="inline_start_edit")
        self.refresh()

    def edit_priority_inline(self, item_id: str):
        """Edit item priority score in place."""
        item = self.db_manager.get_action_item(item_id)
        if not item:
            return
        dialog = InlinePriorityDialog(self, item)
        self.wait_window(dialog)
        if dialog.result == "__cancel__":
            return
        item.importance = dialog.result["importance"]
        item.urgency = dialog.result["urgency"]
        item.size = dialog.result["size"]
        item.value = dialog.result["value"]
        self.db_manager.update_action_item(item, normalize_week_dates=False)
        self.refresh()

    def edit_due_date_inline(self, item_id: str):
        """Edit item due date in place."""
        item = self.db_manager.get_action_item(item_id)
        if not item:
            return
        dialog = InlineDateDialog(self, "Edit Due Date", item.due_date)
        self.wait_window(dialog)
        if dialog.result == "__cancel__":
            return
        new_due = dialog.result
        new_start = item.start_date
        if new_start and new_due and new_due < new_start:
            new_due = new_start
        self.db_manager.reschedule_item(item_id, new_start, new_due, reason="inline_due_edit")
        self.refresh()

    def create_new_item(self):
        """Open item editor for new item."""
        from .item_editor import ItemEditorDialog
        ItemEditorDialog(self, self.db_manager,
                         vps_manager=self.app.vps_manager, on_close_callback=self.refresh)

    def push_item(self, item_id: str):
        """Push item to next day without showing dialog, using weekend-aware logic."""
        # Get the item
        item = self.db_manager.get_action_item(item_id)
        if not item:
            return

        # Load settings for weekend handling
        settings = AppSettings.load()
        next_day = increment_date(
            date.today(), 1, settings.include_saturday, settings.include_sunday
        ).isoformat()

        # Calculate new dates (add 1 day using weekend-aware logic)
        new_start = item.start_date
        new_due = item.due_date

        if item.start_date:
            try:
                start_dt = date.fromisoformat(item.start_date)
                new_start_dt = increment_date(
                    start_dt, 1, settings.include_saturday, settings.include_sunday)
                new_start = new_start_dt.isoformat()
            except ValueError:
                new_start = item.start_date

        if item.due_date:
            try:
                due_dt = date.fromisoformat(item.due_date)
                new_due_dt = increment_date(
                    due_dt, 1, settings.include_saturday, settings.include_sunday)
                new_due = new_due_dt.isoformat()
            except ValueError:
                new_due = item.due_date

        # If item has no dates yet, assign next business day to both.
        if not item.start_date and not item.due_date:
            new_start = next_day
            new_due = next_day

        # Push to next day directly (no dialog, no reason)
        self.db_manager.reschedule_item(
            item_id, new_start, new_due, reason=None)
        self.refresh()
