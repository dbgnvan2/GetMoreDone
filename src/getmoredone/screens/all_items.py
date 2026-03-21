"""
All Items screen - table view of all action items.
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

from ..models import Status
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from .segment_color_utils import resolve_segment_color_for_item
from .item_lineage import lineage_for_item, LINEAGE_COL_CHARS
from ..theme import apply_segment_accent, semantic_colors, button_style, combo_box_style, list_row_font
from .inline_editors import InlineDateDialog, InlinePriorityDialog
from .title_format import (
    split_action_item_title,
    format_column_text,
    responsive_column_chars,
    CONTEXT_COL_CHARS,
    CONTACT_COL_CHARS,
)

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class AllItemsScreen(ctk.CTkFrame):
    """Screen showing all items in a table format."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.settings = AppSettings.load()
        self.segment_colors_by_id = {}
        self.segment_colors_by_name = {}
        self._parent_segment_cache = {}
        self._ape_segment_cache = {}
        self._ape_lineage_cache = {}
        self._week_action_segment_cache = {}
        self._item_lineage_cache = {}
        # Track column visibility state (use setting)
        self.columns_expanded = self.settings.default_columns_expanded
        self.search_query = ""  # Track search query
        self.palette = semantic_colors()

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(
            row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load items
        self.refresh()

    def create_header(self):
        """Create header with filters and controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(7, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="All Items",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Search entry
        self.search_entry = ctk.CTkEntry(
            header,
            placeholder_text="Search title, description, next action...",
            width=200
        )
        self.search_entry.grid(row=0, column=1, padx=5, pady=10)
        self.search_entry.bind("<Return>", lambda e: self.perform_search())

        # Search button
        btn_search = ctk.CTkButton(
            header,
            text="Search",
            width=80,
            **button_style("secondary"),
            command=self.perform_search
        )
        btn_search.grid(row=0, column=2, padx=5, pady=10)

        # Status filter
        ctk.CTkLabel(header, text="Status:").grid(
            row=0, column=3, padx=(20, 5), pady=10)
        self.status_var = ctk.StringVar(value="open")
        self.status_combo = ctk.CTkComboBox(
            header,
            values=["open", "completed", "canceled", "all"],
            variable=self.status_var,
            width=120,
            command=lambda _: self.refresh()
        )
        self.status_combo.grid(row=0, column=4, padx=5, pady=10)

        # Who filter
        ctk.CTkLabel(header, text="Who:").grid(
            row=0, column=5, padx=(20, 5), pady=10)
        who_values = ["All"] + self.db_manager.get_distinct_who_values()
        self.who_var = ctk.StringVar(value="All")
        self.who_combo = ctk.CTkComboBox(
            header,
            values=who_values,
            variable=self.who_var,
            width=150,
            **combo_box_style(),
            command=lambda _: self.refresh()
        )
        self.who_combo.grid(row=0, column=6, padx=5, pady=10)

        # Expand/Collapse button
        self.expand_collapse_btn = ctk.CTkButton(
            header,
            text="Collapse" if self.columns_expanded else "Expand",
            width=100,
            **button_style("secondary"),
            command=self.toggle_columns
        )
        self.expand_collapse_btn.grid(row=0, column=8, padx=5, pady=10)

        # New Item button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Item",
            **button_style("primary"),
            command=self.create_new_item
        )
        btn_new.grid(row=0, column=9, padx=10, pady=10)

    def perform_search(self):
        """Perform search and update the view."""
        self.search_query = self.search_entry.get().strip()
        self.refresh()

    def toggle_columns(self):
        """Toggle between expanded and collapsed column view."""
        self.columns_expanded = not self.columns_expanded
        self.expand_collapse_btn.configure(
            text="Expand" if not self.columns_expanded else "Collapse")
        self.refresh()

    def refresh(self):
        """Refresh the list of items."""
        self.palette = semantic_colors()
        # Temporarily remove scroll_frame from grid to prevent flickering during rebuild
        grid_info = self.scroll_frame.grid_info()
        self.scroll_frame.grid_remove()

        try:
            # Clear current items
            for widget in self.scroll_frame.winfo_children():
                widget.destroy()

            # Refresh VSP segment color cache
            self.segment_colors_by_id = self.app.vps_manager.get_segment_colors_by_id()
            self.segment_colors_by_name = self.app.vps_manager.get_segment_color_map()
            self._parent_segment_cache = {}
            self._ape_segment_cache = {}
            self._ape_lineage_cache = {}
            self._week_action_segment_cache = {}
            self._item_lineage_cache = {}
            row_text = self.palette["row_text"]

            # Get filters
            status_filter = None if self.status_var.get() == "all" else self.status_var.get()
            who_filter = None if self.who_var.get() == "All" else self.who_var.get()

            # Get items (use search if query exists, otherwise get all)
            if self.search_query:
                items = self.db_manager.search_items(self.search_query)
                # Apply filters to search results
                if status_filter:
                    items = [
                        item for item in items if item.status == status_filter]
                if who_filter:
                    items = [item for item in items if item.who == who_filter]
            else:
                items = self.db_manager.get_all_items(
                    status_filter=status_filter,
                    who_filter=who_filter,
                    sort_by="start_date",
                    sort_desc=False
                )

            if not items:
                label = ctk.CTkLabel(
                    self.scroll_frame,
                    text="No items found",
                    font=ctk.CTkFont(size=14)
                )
                label.grid(row=0, column=0, pady=20)
                return

            # Create table header
            header_frame = ctk.CTkFrame(self.scroll_frame, fg_color=self.palette["surface_subtle"])
            header_frame.grid(row=0, column=0, sticky="ew",
                              pady=(0, 5), padx=5)
            header_frame.grid_columnconfigure(1, weight=1)

            headers = ["✓", "Immediate Step", "SubSegment", "Category", "Context", "Who", "Start", "Due",
                       "Priority", "Est. Time", "Status", "Actions"]
            col_weights = [0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

            for col, (header_text, weight) in enumerate(zip(headers, col_weights)):
                header_frame.grid_columnconfigure(col, weight=weight)
                ctk.CTkLabel(
                    header_frame,
                    text=header_text,
                    font=ctk.CTkFont(weight="bold")
                ).grid(row=0, column=col, padx=5, pady=5, sticky="w")

            # Create item rows
            palette = self.palette
            for idx, item in enumerate(items, start=1):
                segment_color = resolve_segment_color_for_item(
                    item,
                    self.segment_colors_by_id,
                    self.segment_colors_by_name,
                    self.db_manager,
                    self._parent_segment_cache,
                    self._ape_segment_cache,
                    self._week_action_segment_cache,
                )
                if segment_color:
                    bg_color = segment_color
                elif item.status == Status.COMPLETED:
                    bg_color = palette["success_tint"]
                elif item.importance == 20 or item.urgency == 20:
                    bg_color = palette["critical_tint"]
                else:
                    bg_color = None
                item_frame = ctk.CTkFrame(self.scroll_frame, fg_color=bg_color)
                apply_segment_accent(item_frame, segment_color)
                item_frame.grid(row=idx, column=0, sticky="ew", pady=2, padx=5)
                item_frame.grid_columnconfigure(1, weight=1)
                limits = responsive_column_chars(max(self.winfo_width(), self.scroll_frame.winfo_width()))
                parsed = split_action_item_title(item.title)
                _segment_name, subsegment_name, category_name = lineage_for_item(
                    item,
                    self.db_manager,
                    self._item_lineage_cache,
                    self._ape_lineage_cache,
                    self._week_action_segment_cache,
                )

                # Checkbox
                if item.status == Status.OPEN:
                    var = ctk.BooleanVar(value=False)
                    checkbox = ctk.CTkCheckBox(
                        item_frame,
                        text="",
                        variable=var,
                        width=30,
                        command=lambda i=item.id: self.complete_item(i)
                    )
                    checkbox.grid(row=0, column=0, padx=5, pady=5)
                else:
                    ctk.CTkLabel(item_frame, text="✓").grid(
                        row=0, column=0, padx=5, pady=5)

                # Context
                title_cell = ctk.CTkFrame(item_frame, fg_color="transparent")
                title_cell.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
                title_cell.grid_columnconfigure(1, weight=1)
                if item.item_type == "week":
                    ctk.CTkLabel(
                        title_cell,
                        text="WT",
                        width=28,
                        corner_radius=6,
                        fg_color=palette["success_strong"],
                        text_color=palette["on_strong"],
                        font=ctk.CTkFont(size=11, weight="bold"),
                    ).grid(row=0, column=0, padx=(0, 6), sticky="w")
                title_label = ctk.CTkLabel(
                    title_cell,
                    text=parsed.title,
                    anchor="w",
                    text_color=row_text,
                    font=list_row_font()
                )
                title_label.grid(row=0, column=1, sticky="ew")
                title_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_item(item_id))

                ctk.CTkLabel(
                    item_frame,
                    text=format_column_text(subsegment_name or "-", limits["subsegment"]),
                    width=max(56, limits["subsegment"] * 8),
                    anchor="w",
                    text_color=row_text,
                    font=list_row_font()
                ).grid(row=0, column=2, padx=5, pady=5, sticky="w")

                ctk.CTkLabel(
                    item_frame,
                    text=format_column_text(category_name or "-", limits["category"]),
                    width=max(56, limits["category"] * 8),
                    anchor="w",
                    text_color=row_text,
                    font=list_row_font()
                ).grid(row=0, column=3, padx=5, pady=5, sticky="w")

                # Context
                ctk.CTkLabel(
                    item_frame,
                    text=format_column_text(parsed.context, limits["context"]),
                    width=max(90, limits["context"] * 8),
                    anchor="w",
                    text_color=row_text,
                    font=list_row_font()
                ).grid(row=0, column=4, padx=5, pady=5, sticky="w")

                # Who
                ctk.CTkLabel(
                    item_frame,
                    text=format_column_text(item.who, limits["who"]),
                    width=max(52, limits["who"] * 8),
                    text_color=row_text,
                    font=list_row_font(),
                ).grid(
                    row=0, column=5, padx=5, pady=5)

                # Start date
                start_text = item.start_date or "-"
                if item.start_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(item.start_date)
                        start_text = dt.strftime("%m/%d")
                    except:
                        pass
                start_label = ctk.CTkLabel(
                    item_frame,
                    text=start_text,
                    width=60,
                    text_color=row_text,
                    font=list_row_font()
                )
                start_label.grid(row=0, column=6, padx=5, pady=5)
                start_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_start_date_inline(item_id))

                # Due date
                due_text = item.due_date or "-"
                if item.due_date:
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(item.due_date)
                        due_text = dt.strftime("%m/%d")
                    except:
                        pass
                due_label = ctk.CTkLabel(
                    item_frame,
                    text=due_text,
                    width=60,
                    text_color=row_text,
                    font=list_row_font()
                )
                due_label.grid(row=0, column=7, padx=5, pady=5)
                due_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_due_date_inline(item_id))

                # Priority
                is_priority_critical = item.importance == 20 or item.urgency == 20
                priority_label = ctk.CTkLabel(
                    item_frame,
                    text=str(item.priority_score),
                    width=80,
                    fg_color=palette["danger"] if is_priority_critical else "transparent",
                    text_color=pick_text_color(palette["danger"]) if is_priority_critical else row_text,
                    corner_radius=6 if is_priority_critical else 0,
                    font=list_row_font(),
                )
                priority_label.grid(row=0, column=8, padx=5, pady=5)
                priority_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_priority_inline(item_id))

                # Estimated time (planned_minutes) - ALWAYS shown (not collapsed)
                time_text = f"{item.planned_minutes}m" if item.planned_minutes else "-"
                ctk.CTkLabel(
                    item_frame,
                    text=time_text,
                    width=60,
                    text_color=row_text,
                    font=list_row_font()
                ).grid(row=0, column=9, padx=5, pady=5)

                # Factor chips (I, U, E, V) - only shown when expanded
                col_offset = 0
                if self.columns_expanded:
                    factors_frame = ctk.CTkFrame(
                        item_frame, fg_color="transparent")
                    factors_frame.grid(row=0, column=10, padx=5, pady=5)
                    columns = [
                        ("G", item.group, 120),
                        ("C", item.category, 120),
                        ("I", item.importance, 40),
                        ("U", item.urgency, 40),
                        ("E", item.size, 40),
                        ("V", item.value, 40),
                    ]
                    for factor_col, (label, value, width) in enumerate(columns):
                        text = f"{label}:{value}" if value not in (None, "") else ""
                        label_kwargs = {
                            "text": text,
                            "width": width,
                            "anchor": "w",
                            "font": list_row_font(),
                            "text_color": row_text,
                        }
                        if label in ("I", "U") and str(value).strip() == "20":
                            label_kwargs["fg_color"] = palette["danger"]
                            label_kwargs["text_color"] = pick_text_color(palette["danger"])
                            label_kwargs["corner_radius"] = 6
                        ctk.CTkLabel(factors_frame, **label_kwargs).grid(
                            row=0, column=factor_col, padx=2)
                    col_offset = 1

                # Status
                ctk.CTkLabel(item_frame, text=item.status, width=80, font=list_row_font(), text_color=row_text).grid(
                    row=0, column=10 + col_offset, padx=5, pady=5)

                # Action buttons
                col = 11 + col_offset
                # Timer button (only for open items)
                if item.status == Status.OPEN:
                    btn_timer = ctk.CTkButton(
                        item_frame,
                        text="⏱ Timer",
                        width=70,
                        **button_style("secondary"),
                        command=lambda i=item.id: self.start_timer(i)
                    )
                    btn_timer.grid(row=0, column=col, padx=(0, 2), pady=5)
                    col += 1

        finally:
            # Restore scroll_frame to grid - this ensures it's shown even if an error occurs
            self.scroll_frame.grid(**grid_info)

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
