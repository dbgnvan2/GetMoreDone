"""
Today view screen - shows items for today including completed ones.
"""

import customtkinter as ctk
from datetime import datetime, date
import random
import tkinter as tk
from typing import Optional, TYPE_CHECKING

from ..db_manager import DatabaseManager
from ..models import ActionItem
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from ..date_utils import increment_date
from .segment_color_utils import resolve_segment_color_for_item
from ..theme import apply_segment_accent, celebration_colors, semantic_colors, button_style, list_row_font
from .inline_editors import InlineDateDialog, InlinePriorityDialog
from .item_lineage import lineage_for_item, LINEAGE_COL_CHARS
from ..utils.icon_loader import IconLoader
from .title_format import (
    split_action_item_title,
    format_column_text,
    responsive_column_chars,
    CONTEXT_COL_CHARS,
    CONTACT_COL_CHARS,
)
from .column_resize import ColumnResizer, ColumnSpec

if TYPE_CHECKING:
    from ..app import GetMoreDoneApp


class TodayScreen(ctk.CTkFrame):
    """Screen showing today's items (start <= today), including completed items."""

    # Width of column 0 (drag grip + checkbox on open rows, badge on completed
    # rows). Header spacer and every row share this so columns stay aligned.
    COL0_WIDTH = 56

    # Minimum upward travel (pixels) of a grip drag that counts as "drag to top"
    # rather than an accidental click.
    PIN_DRAG_THRESHOLD = 12

    def __init__(self, parent, db_manager: DatabaseManager, app: 'GetMoreDoneApp'):
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
        self._completion_badge_image = None
        self._session_completed_count = 0
        self._confetti_overlay = None
        # Drag-to-top (pin) state for the Today list
        self._pin_drag_item_id = None
        self._pin_drag_start_y = None
        # Track column visibility state (use setting)
        self.columns_expanded = self.settings.default_columns_expanded
        self.show_top_3_only = False  # Track Top 3 mode
        self.search_query = ""  # Track search query
        self.palette = semantic_colors()
        # Resizable Title column (shared spreadsheet-style resizer). Today only
        # makes the Title column resizable; the rest keep responsive widths.
        self.resizer = ColumnResizer(
            owner=self,
            settings=self.settings,
            prefix="today",
            set_cell_width=False,  # title label sits inside a sub-frame
            specs=[ColumnSpec("title", grid_col=1, default_width=260, min_width=120)],
        )

        self.grid_columnconfigure(0, weight=1)
        # Row 0 = toolbar, row 1 = pinned column header, row 2 = scrolling list
        self.grid_rowconfigure(2, weight=1)

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

        # Pinned column-header row (does not scroll with the list)
        self.column_header = None
        self._header_title_label = None

        # Scrollable frame for items
        self.scroll_frame = ctk.CTkScrollableFrame(self)
        self.scroll_frame.grid(
            row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Build the pinned header, then load items
        self._build_column_header()
        self.load_items()

    def _build_column_header(self):
        """Build the pinned column-heading row with a draggable Title divider."""
        if self.column_header is not None:
            self.column_header.destroy()

        limits = responsive_column_chars(max(self.winfo_width(), 1))
        header_font = ctk.CTkFont(size=12, weight="bold")

        hdr = ctk.CTkFrame(self, fg_color=self.palette["surface_subtle"])
        # padx (25) ≈ scroll_frame outer padx (20) + per-row padx (5), so the
        # header columns line up over the scrolled rows below.
        hdr.grid(row=1, column=0, sticky="ew", padx=25, pady=(0, 4))
        hdr.grid_columnconfigure(0, minsize=self.COL0_WIDTH)
        self.resizer.apply_grid(hdr)  # Title column minsize
        hdr.grid_columnconfigure(99, weight=1)
        self.column_header = hdr

        # Column 0 (grip / checkbox / badge) spacer
        ctk.CTkLabel(hdr, text="", width=self.COL0_WIDTH).grid(
            row=0, column=0, padx=5, pady=4)

        # Title header cell + draggable divider (managed by the shared resizer)
        self._header_title_label = ctk.CTkLabel(
            hdr, text="Title", width=self.resizer.width("title"),
            anchor="w", font=header_font)
        self._header_title_label.grid(
            row=0, column=1, sticky="w", padx=5, pady=4)
        self.resizer.build_dividers(
            hdr, {"title": self._header_title_label},
            fg_color=self.palette["border"])

        # Remaining column headers — widths match create_item_row()
        header_cols = [
            ("SubSegment", max(56, limits["subsegment"] * 8)),
            ("Category", max(56, limits["category"] * 8)),
            ("Context", max(90, limits["context"] * 8)),
            ("Who", max(52, limits["who"] * 8)),
            ("Start", 60),
            ("Due", 60),
            ("Pri", 60),
            ("Time", 50),
        ]
        for idx, (text, width) in enumerate(header_cols, start=2):
            ctk.CTkLabel(
                hdr, text=text, width=width, anchor="w", font=header_font
            ).grid(row=0, column=idx, padx=5, pady=4, sticky="w")

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
        self._completion_badge_image = None
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
            self.resizer.clear_rows()

            # Get today's items (start_date <= today, includes completed)
            items = self.get_todays_items()

            # Refresh VSP color caches
            self.segment_colors_by_id = self.app.vps_manager.get_segment_colors_by_id()
            self.segment_colors_by_name = self.app.vps_manager.get_segment_color_map()
            self._parent_segment_cache = {}
            self._ape_segment_cache = {}
            self._ape_lineage_cache = {}
            self._week_action_segment_cache = {}
            self._item_lineage_cache = {}

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

            # Order open items: pinned rows first (drag-to-top), then the usual
            # date/priority ordering. Top-3 mode keeps its priority-only ranking
            # but still floats pinned rows to the front.
            if self.show_top_3_only and len(open_items) > 3:
                open_items = sorted(
                    open_items, key=self._today_top3_sort_key)[:3]
            else:
                open_items = sorted(
                    open_items, key=self._today_open_sort_key)

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

    @staticmethod
    def _pin_sort_prefix(item: ActionItem):
        """Ordering prefix that floats pinned rows to the top.

        Pinned items sort before unpinned ones; among pinned items a higher
        today_pin_rank (most recently dragged to top) comes first.
        """
        return (item.today_pin_rank is None, -(item.today_pin_rank or 0))

    @classmethod
    def _today_open_sort_key(cls, item: ActionItem):
        """Normal Today ordering: pinned first, then earliest start/due date,
        then higher priority score."""
        coalesced_date = item.start_date or item.due_date or "9999-12-31"
        return cls._pin_sort_prefix(item) + (coalesced_date, -item.priority_score)

    @classmethod
    def _today_top3_sort_key(cls, item: ActionItem):
        """Top-3 ordering: pinned first, then highest priority score."""
        return cls._pin_sort_prefix(item) + (-item.priority_score,)

    def _start_pin_drag(self, item_id: str, event):
        """Begin a drag-to-top gesture from an open row's grip handle.

        Records where the drag started (screen Y). The decision to pin is made
        purely from how far the grip is dragged upward by release time, so it
        does not depend on <B1-Motion> (which is unreliable on CTkLabel) or on
        polling the live cursor position.
        """
        self._pin_drag_item_id = item_id
        self._pin_drag_start_y = event.y_root

    def _finish_pin_drag(self, event):
        """Finish a drag-to-top gesture: dragging the grip upward pins the item
        above all other Today rows. A plain click (no upward travel) is ignored."""
        item_id = self._pin_drag_item_id
        start_y = self._pin_drag_start_y
        self._pin_drag_item_id = None
        self._pin_drag_start_y = None
        if not item_id or start_y is None:
            return
        # Upward travel (start higher Y number, release lower Y number).
        if start_y - event.y_root >= self.PIN_DRAG_THRESHOLD:
            if self.db_manager.pin_item_to_today_top(item_id):
                self.refresh()

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
        row_text = palette["row_text"]
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
        # Fixed, resizable Title column (col 1); slack goes to a trailing spacer
        # so the row still fills width and leading columns stay aligned.
        frame.grid_columnconfigure(0, minsize=self.COL0_WIDTH)
        frame.grid_columnconfigure(1, minsize=self.resizer.width("title"), weight=0)
        frame.grid_columnconfigure(99, weight=1)
        limits = responsive_column_chars(max(self.winfo_width(), self.scroll_frame.winfo_width()))
        parsed = split_action_item_title(item.title)
        _segment_name, subsegment_name, category_name = lineage_for_item(
            item,
            self.db_manager,
            self._item_lineage_cache,
            self._ape_lineage_cache,
            self._week_action_segment_cache,
        )

        # Completion indicator
        if is_completed:
            badge_image = self._get_completion_badge_image()
            if badge_image is not None:
                ctk.CTkLabel(
                    frame,
                    text="",
                    image=badge_image,
                    width=44,
                ).grid(row=0, column=0, padx=5, pady=5)
            else:
                completion_text = self.settings.completion_icon or "✓"
                ctk.CTkLabel(
                    frame,
                    text=completion_text,
                    font=ctk.CTkFont(size=28, weight="bold"),
                    text_color=palette["success_strong"],
                    width=44
                ).grid(row=0, column=0, padx=5, pady=5)
        else:
            # Drag grip + complete checkbox for open items. Dragging the grip
            # upward pins the item to the top of Today (see _start_pin_drag /
            # _finish_pin_drag). Release is bound on the grip itself: Tk's
            # implicit button grab keeps press/release on the grip for the whole
            # gesture, so no toplevel binding is needed.
            col0 = ctk.CTkFrame(frame, fg_color="transparent")
            col0.grid(row=0, column=0, padx=5, pady=5, sticky="w")
            grip = ctk.CTkLabel(
                col0,
                text="⣿",  # Braille dots — a compact drag handle
                width=14,
                cursor="fleur",
                text_color=palette["border"],
                font=list_row_font(),
            )
            grip.pack(side="left", padx=(0, 2))
            grip.bind("<ButtonPress-1>",
                      lambda e, iid=item.id: self._start_pin_drag(iid, e))
            grip.bind("<ButtonRelease-1>", self._finish_pin_drag)

            var = ctk.BooleanVar(value=False)
            checkbox = ctk.CTkCheckBox(
                col0,
                text="",
                variable=var,
                width=24,
                command=lambda: self.complete_item(item.id)
            )
            checkbox.pack(side="left")

        has_badge = item.item_type == "week"
        title_cell = ctk.CTkFrame(frame, fg_color="transparent")
        title_cell.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        title_cell.grid_columnconfigure(1, weight=1)
        if has_badge:
            ctk.CTkLabel(
                title_cell,
                text="WT",
                width=28,
                corner_radius=6,
                fg_color=palette["success_strong"],
                text_color=palette["on_strong"],
                font=ctk.CTkFont(size=11, weight="bold"),
            ).grid(row=0, column=0, padx=(0, 6), sticky="w")
        title_reserve = 4 if has_badge else 0
        title_label = ctk.CTkLabel(
            title_cell,
            text=self.resizer.cell_text("title", parsed.title, title_reserve),
            font=list_row_font(),
            anchor="w",
            text_color=row_text
        )
        title_label.grid(row=0, column=1, sticky="ew")
        title_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_item(item_id))

        # Register the title cell for live resizing (shared ColumnResizer)
        frame.item = item
        self.resizer.register_row(frame, [("title", title_label, parsed.title, title_reserve)])

        ctk.CTkLabel(
            frame,
            text=format_column_text(subsegment_name or "-", limits["subsegment"]),
            width=max(56, limits["subsegment"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=2, padx=5, pady=5, sticky="w")

        ctk.CTkLabel(
            frame,
            text=format_column_text(category_name or "-", limits["category"]),
            width=max(56, limits["category"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Context
        ctk.CTkLabel(
            frame,
            text=format_column_text(parsed.context, limits["context"]),
            width=max(90, limits["context"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=4, padx=5, pady=5, sticky="w")

        # Who
        ctk.CTkLabel(
            frame,
            text=format_column_text(item.who, limits["who"]),
            width=max(52, limits["who"] * 8),
            anchor="w",
            text_color=row_text,
            font=list_row_font(),
        ).grid(row=0, column=5, padx=5, pady=5, sticky="w")

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
            text_color=row_text,
            font=list_row_font()
        )
        start_label.grid(row=0, column=6, padx=5, pady=5)
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
            text_color=row_text,
            font=list_row_font()
        )
        due_label.grid(row=0, column=7, padx=5, pady=5)
        due_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_due_date_inline(item_id))

        # Priority score
        is_priority_critical = item.importance == 20 or item.urgency == 20
        score_label = ctk.CTkLabel(
            frame,
            text=f"P:{item.priority_score}",
            width=60,
            fg_color=palette["danger"] if is_priority_critical else "transparent",
            text_color=pick_text_color(palette["danger"]) if is_priority_critical else row_text,
            corner_radius=6 if is_priority_critical else 0,
            font=list_row_font(),
        )
        score_label.grid(row=0, column=8, padx=5, pady=5)
        score_label.bind("<Button-1>", lambda _event, item_id=item.id: self.edit_priority_inline(item_id))

        # Estimated time (planned_minutes) - ALWAYS shown (not collapsed)
        time_text = f"{item.planned_minutes}m" if item.planned_minutes else "-"
        time_label = ctk.CTkLabel(
            frame,
            text=time_text,
            width=50,
            anchor="w",
            text_color=row_text,
            font=list_row_font()
        )
        time_label.grid(row=0, column=9, padx=5, pady=5)

        # Factor chips (I, U, E, V) - only shown when expanded
        factors_frame = ctk.CTkFrame(frame, fg_color="transparent")
        if self.columns_expanded:
            factors_frame.grid(row=0, column=10, padx=5, pady=5)
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
                    "text_color": row_text,
                }
                if label in ("I", "U") and str(value).strip() == "20":
                    label_kwargs["fg_color"] = palette["danger"]
                    label_kwargs["text_color"] = pick_text_color(palette["danger"])
                    label_kwargs["corner_radius"] = 6
                ctk.CTkLabel(factors_frame, **label_kwargs).grid(
                    row=0, column=col, padx=2)

        # Action buttons (only for open items)
        # Column positions shift based on whether factors are shown
        btn_col_start = 11 if self.columns_expanded else 10
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
        if self.db_manager.complete_action_item(item_id):
            self._session_completed_count += 1
            self.refresh()
            self._maybe_show_completion_confetti()

    def _get_completion_badge_image(self):
        if self._completion_badge_image is not None:
            return self._completion_badge_image
        badge_path = getattr(self.settings, "completion_badge_path", None)
        if not badge_path:
            return None
        self._completion_badge_image = IconLoader.load_image_path(badge_path, size=34)
        return self._completion_badge_image

    def _maybe_show_completion_confetti(self):
        threshold = int(getattr(self.settings, "completion_confetti_threshold", 0) or 0)
        if threshold <= 0:
            return
        if self._session_completed_count % threshold != 0:
            return
        self._show_confetti_overlay()

    def _show_confetti_overlay(self):
        if self._confetti_overlay is not None:
            try:
                self._confetti_overlay.destroy()
            except Exception:
                pass
        self.update_idletasks()
        overlay = tk.Canvas(self, highlightthickness=0, bg=self.winfo_toplevel().cget("bg"), bd=0)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        overlay.lift()
        self._confetti_overlay = overlay

        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        colors = celebration_colors()
        pieces = []
        for _ in range(36):
            x = random.randint(0, width)
            y = random.randint(-height // 3, 0)
            size = random.randint(6, 12)
            color = random.choice(colors)
            shape = overlay.create_rectangle(x, y, x + size, y + size, fill=color, outline="")
            pieces.append({
                "id": shape,
                "dx": random.uniform(-2.2, 2.2),
                "dy": random.uniform(3.0, 6.0),
            })

        self._animate_confetti(overlay, pieces, 0, height)

    def _animate_confetti(self, overlay, pieces, step: int, max_height: int):
        if self._confetti_overlay is not overlay:
            return
        if step > 45:
            overlay.destroy()
            if self._confetti_overlay is overlay:
                self._confetti_overlay = None
            return

        for piece in pieces:
            overlay.move(piece["id"], piece["dx"], piece["dy"])
        self.after(35, lambda: self._animate_confetti(overlay, pieces, step + 1, max_height))

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
