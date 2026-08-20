"""
Scheduler screen - drag items onto date boxes to reschedule.
"""

import calendar
import logging
import customtkinter as ctk
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import messagebox
from typing import Optional, TYPE_CHECKING

from ..db_manager import DatabaseManager
from ..models import ActionItem
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from .project_link_notice import confirm_exclusive_relink
from .week_collision_notice import notify_weekly_tactic_changes
from ..theme import button_style, combo_box_style, semantic_colors
from .drag_schedule_support import (
    color_for_day_stats,
    date_background_for,
    date_text_color_for,
    format_day_stats_text,
    future_options_for,
)
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
from .title_format import split_action_item_title, format_column_text
from .column_resize import ColumnResizer, ColumnSpec

if TYPE_CHECKING:
    from ..app import GetMoreDoneApp


class DragScheduleScreen(ctk.CTkFrame):
    """Screen with drag-and-drop scheduling onto date boxes."""

    # BP5/S2-4 — a lineage-filtered "No Project" view cannot filter in SQL, so
    # it fetches wider than it shows. Wider, not unbounded.
    UNLINKED_FILTERED_LIMIT = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT * 10

    DATE_BOX_DAY_MIN_WIDTH = 104
    DATE_BOX_DATE_MIN_WIDTH = 84
    DATE_BOX_ITEMS_MIN_WIDTH = 84
    DATE_BOX_TIME_MIN_WIDTH = 84

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.settings = AppSettings.load()

        self.drag_label = None
        self.drag_item: Optional[ActionItem] = None
        self.drag_items: list[ActionItem] = []  # Items to drag (single or multiple)
        self.drag_hover_frame = None
        self.drag_hover_base_color = None
        self.date_box_colors = {}
        self.date_box_font_size = int(round(14 * 1.3))  # 30% larger
        self.date_box_height = 86
        self.item_row_height = 86
        self._sync_ui_sizing_from_settings()
        self.palette = semantic_colors()
        self.checked_items: set[str] = set()  # Set of checked item IDs

        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}
        self._ape_lineage_cache = {}
        self._week_segment_cache = {}
        self._item_lineage_cache = {}
        self.selected_date_filter: Optional[str] = None
        self.selected_date_frames: dict[str, list[ctk.CTkFrame]] = {}
        self.date_frame_dates: dict[ctk.CTkFrame, str] = {}
        self.project_boxes: list[dict] = []
        self.project_box_ids: dict[ctk.CTkFrame, str] = {}
        self.selected_project_id: Optional[str] = None
        self.segment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.project_sort_var = ctk.StringVar(value="Title")
        # Header "Project:" filter — shares selected_project_id with clicking a
        # project box; project_filter_map maps a display name back to its id.
        self.project_filter_var = ctk.StringVar(value="All")
        self.project_filter_map: dict[str, str] = {}
        # Per-refresh registry of row checkboxes so the header "select all" box
        # can drive them, keyed by item id.
        self.item_checkboxes: dict[str, ctk.CTkCheckBox] = {}
        self.select_all_var = ctk.BooleanVar(value=False)
        self.select_all_checkbox: Optional[ctk.CTkCheckBox] = None
        # All Action Items data columns are resizable, spreadsheet-style.
        self.resizer = ColumnResizer(
            owner=self,
            settings=self.settings,
            prefix="drag_schedule",
            text_pad=" ",
            specs=[
                ColumnSpec("title", grid_col=1, default_width=220, min_width=120),
                ColumnSpec("segment", grid_col=2, default_width=170, min_width=90),
                ColumnSpec("subsegment", grid_col=3, default_width=170, min_width=90),
                ColumnSpec("category", grid_col=4, default_width=170, min_width=90),
                ColumnSpec("start_date", grid_col=5, default_width=120, min_width=80),
            ],
        )

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_header()
        self.create_body()
        self.refresh()

    def _sync_ui_sizing_from_settings(self):
        """Sync Drag Schedule sizing options from persisted settings."""
        box_height = max(20, int(getattr(self.settings, "drag_schedule_box_height_px", 86)))
        self.date_box_height = box_height
        self.item_row_height = box_height

    def create_header(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(13, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Scheduler",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        ctk.CTkLabel(header, text="Next").grid(
            row=0, column=1, padx=(20, 5), pady=10)

        self.days_var = ctk.StringVar(value="7")
        self.days_combo = ctk.CTkComboBox(
            header,
            values=["1", "3", "7", "14", "30"],
            variable=self.days_var,
            width=80,
            **combo_box_style(),
        )
        self.days_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkLabel(header, text="days").grid(
            row=0, column=3, sticky="w", padx=5, pady=10)

        self.refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=88,
            command=self.refresh_all_dates,
            **button_style("secondary"),
        )
        self.refresh_btn.grid(row=0, column=4, padx=(10, 5), pady=10)

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

        ctk.CTkLabel(header, text="Segment:").grid(
            row=0, column=7, padx=(14, 5), pady=10
        )
        self.segment_filter_combo = ctk.CTkComboBox(
            header,
            values=["All"],
            variable=self.segment_filter_var,
            width=160,
            **combo_box_style(),
            command=lambda _v: self.on_segment_filter_changed(),
        )
        self.segment_filter_combo.grid(row=0, column=8, padx=5, pady=10)

        ctk.CTkLabel(header, text="SubSegment:").grid(
            row=0, column=9, padx=(14, 5), pady=10
        )
        self.subsegment_filter_combo = ctk.CTkComboBox(
            header,
            values=["All"],
            variable=self.subsegment_filter_var,
            width=160,
            **combo_box_style(),
            command=lambda _v: self.on_subsegment_filter_changed(),
        )
        self.subsegment_filter_combo.grid(row=0, column=10, padx=5, pady=10)

        ctk.CTkLabel(header, text="Project:").grid(
            row=0, column=11, padx=(14, 5), pady=10
        )
        self.project_filter_combo = ctk.CTkComboBox(
            header,
            values=["All"],
            variable=self.project_filter_var,
            width=180,
            **combo_box_style(),
            command=lambda _v: self.on_project_filter_changed(),
        )
        self.project_filter_combo.grid(row=0, column=12, padx=5, pady=10)

    def create_body(self):
        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)
        palette = semantic_colors()

        self.splitter = tk.PanedWindow(
            body,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            bd=0,
            bg=palette["surface_subtle"],
        )
        self.splitter.grid(row=0, column=0, sticky="nsew")

        # Left: Next Items list
        left_frame = ctk.CTkFrame(self.splitter)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        left_title = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_title.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        left_title.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            left_title,
            text="Action Items",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(
            left_title,
            text="(Click and drag an Item to the Date Box to set the Start Date)",
            text_color=palette["muted_text"],
        ).grid(row=0, column=1, sticky="w", padx=(10, 0))

        self.items_frame = ctk.CTkScrollableFrame(left_frame, label_text="")
        self.items_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.items_frame.grid_columnconfigure(0, weight=1)

        # Right: Date views
        right_frame = ctk.CTkFrame(self.splitter)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.date_view_tabs = ctk.CTkTabview(right_frame)
        self.date_view_tabs.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.date_boxes_tab = self.date_view_tabs.add("Date Boxes")
        self.date_boxes_tab.grid_rowconfigure(0, weight=1)
        self.date_boxes_tab.grid_columnconfigure(0, weight=1)

        self.calendar_tab = self.date_view_tabs.add("Calendar")
        self.calendar_tab.grid_rowconfigure(0, weight=1)
        self.calendar_tab.grid_columnconfigure(0, weight=1)

        self.projects_tab = self.date_view_tabs.add("Projects")
        self.projects_tab.grid_rowconfigure(1, weight=1)
        self.projects_tab.grid_columnconfigure(0, weight=1)

        self.project_controls = ctk.CTkFrame(self.projects_tab, fg_color="transparent")
        self.project_controls.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))
        
        ctk.CTkLabel(self.project_controls, text="Sort Projects by:").pack(side="left", padx=(0, 5))
        self.project_sort_combo = ctk.CTkComboBox(
            self.project_controls,
            values=["Title", "Subsegment", "Category"],
            variable=self.project_sort_var,
            width=140,
            **combo_box_style(),
            command=lambda _: self.refresh()
        )
        self.project_sort_combo.pack(side="left")

        self.dates_frame = ctk.CTkScrollableFrame(self.date_boxes_tab, label_text="")
        self.dates_frame.grid(row=0, column=0, sticky="nsew")
        self.dates_frame.grid_columnconfigure(0, weight=1)

        self.calendar_frame = ctk.CTkFrame(self.calendar_tab)
        self.calendar_frame.grid(row=0, column=0, sticky="nsew")
        self.calendar_frame.grid_columnconfigure(0, weight=1)
        self.calendar_frame.grid_rowconfigure(1, weight=1)

        self.projects_frame = ctk.CTkScrollableFrame(self.projects_tab, label_text="")
        self.projects_frame.grid(row=1, column=0, sticky="nsew")
        self.projects_frame.grid_columnconfigure(0, weight=1)

        self.splitter.add(left_frame, minsize=320)
        self.splitter.add(right_frame, minsize=320)
        self.after(100, self._init_splitter_position)

    def _init_splitter_position(self):
        if not hasattr(self, "splitter"):
            return
        width = self.splitter.winfo_width()
        if width < 10:
            self.after(100, self._init_splitter_position)
            return
        self.splitter.sash_place(0, int(width * 0.5), 0)

    def refresh(self):
        # Re-load settings so size/color changes from Settings screen apply immediately.
        self.settings = AppSettings.load()
        self._sync_ui_sizing_from_settings()
        self.palette = semantic_colors()
        self._reload_lineage_maps()
        self._refresh_filter_options()
        self._refresh_project_filter_options()
        self._sync_project_filter_var()

        for widget in self.items_frame.winfo_children():
            widget.destroy()
        for widget in self.dates_frame.winfo_children():
            widget.destroy()
        for widget in self.calendar_frame.winfo_children():
            widget.destroy()
        for widget in self.projects_frame.winfo_children():
            widget.destroy()

        self.checked_items.clear()
        self.item_checkboxes = {}
        self.select_all_var.set(False)
        self.date_boxes = []
        self.date_box_colors = {}
        self.selected_date_frames = {}
        self.date_frame_dates = {}
        self.project_boxes = []
        self.project_box_ids = {}

        items = self.load_items()
        self.resizer.clear_rows()
        if not items:
            ctk.CTkLabel(
                self.items_frame,
                text="No action items",
                font=ctk.CTkFont(size=14)
            ).grid(row=0, column=0, pady=20)
        else:
            self.items_header = ctk.CTkFrame(self.items_frame, fg_color=self.palette["surface_subtle"])
            self.items_header.grid(row=0, column=0, sticky="ew", padx=2, pady=(0, 4))
            self.items_header.grid_columnconfigure(0, minsize=40)
            self.resizer.apply_grid(self.items_header)
            self.items_header.grid_columnconfigure(6, weight=1)  # trailing slack

            header_font = ctk.CTkFont(weight="bold")
            # "Select all" toggle: checking it checks every row; unchecking
            # clears them all.
            self.select_all_checkbox = ctk.CTkCheckBox(
                self.items_header,
                text="",
                width=30,
                variable=self.select_all_var,
                command=self._on_select_all_toggled,
            )
            self.select_all_checkbox.grid(row=0, column=0, sticky="w", padx=(10, 4), pady=5)
            header_labels = {}
            for key, text in (
                ("title", "Title"),
                ("segment", "Segment"),
                ("subsegment", "SubSegment"),
                ("category", "Category"),
                ("start_date", "Start Date"),
            ):
                lbl = ctk.CTkLabel(
                    self.items_header, text=text, anchor="w",
                    width=self.resizer.width(key), font=header_font,
                )
                lbl.grid(row=0, column=self.resizer.specs[key].grid_col,
                         sticky="w", padx=(10, 4), pady=5)
                header_labels[key] = lbl
            # Draggable dividers at each column's right edge ("end of column" lines).
            self.resizer.build_dividers(
                self.items_header, header_labels, fg_color=self.palette["border"]
            )

            row = 1
            for item in items:
                item_row = self.create_item_row(item)
                item_row.grid(row=row, column=0, sticky="ew", pady=2, padx=2)
                row += 1

        self.build_date_boxes()
        self.build_calendar_view()
        self.build_project_boxes()

    def refresh_all_dates(self):
        self.selected_date_filter = None
        self.selected_project_id = None
        self.refresh()

    def _reload_lineage_maps(self):
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.app.vps_manager)
        self.category_colors = {
            (
                (row.get("segment_name", "") or "").strip().lower(),
                (row.get("subsegment_name", "") or "").strip().lower(),
                (row.get("name", "") or "").strip().lower(),
            ): (row.get("color_hex") or "").strip()
            for row in self.app.vps_manager.get_vision_categories()
        }
        self._ape_lineage_cache.clear()
        self._week_segment_cache.clear()
        self._item_lineage_cache.clear()

    def load_items(self):
        n_days = int(self.days_var.get())
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()
        # Only the "No Project" branch writes these; a stale pair left the box
        # reading "showing 4 of 525" after the user clicked a project box and
        # nothing was capped at all (P8 — a value that persists between loads).
        self.unlinked_shown = self.unlinked_total = None

        if self.selected_date_filter:
            all_open = self.db_manager.get_all_items(
                status_filter="open",
                who_filter=who_filter,
                sort_by="priority_score",
                sort_desc=True
            )
            return [
                item for item in all_open
                if (item.start_date or item.due_date) == self.selected_date_filter
                and self._item_matches_filters(item)
            ]

        if self.selected_project_id:
            if self.selected_project_id == "__none__":
                return self._load_unlinked_items(who_filter)
            else:
                return [
                    item for item in self.db_manager.get_project_board_items(self.selected_project_id)
                    if item.status == "open"
                    and (who_filter is None or (item.who and item.who.strip().lower() == who_filter.strip().lower()))
                    and self._item_matches_filters(item)
                ]

        upcoming = self.db_manager.get_upcoming_items(n_days, who_filter)
        all_open = self.db_manager.get_all_items(
            status_filter="open",
            who_filter=who_filter,
            sort_by="priority_score",
            sort_desc=True
        )
        no_date = [item for item in all_open if not item.start_date and not item.due_date]
        no_date_ids = {item.id for item in no_date}

        items = no_date[:]
        for item in upcoming:
            if item.id not in no_date_ids:
                items.append(item)
        return [item for item in items if self._item_matches_filters(item)]

    def _lineage_filter_active(self) -> bool:
        """Is a segment or subsegment filter narrowing what the screen shows?

        These are derived from an item's lineage rather than stored on the row,
        so they cannot go into SQL — which is why the unlinked query fetches
        wider than it shows and why a count query cannot answer for them.
        """
        return (
            (self.segment_filter_var.get() or "All").strip() != "All"
            or (self.subsegment_filter_var.get() or "All").strip() != "All"
        )

    def _unlinked_box_text(self, total: int) -> str:
        """The "No Project" box's second line.

        Purpose: BP5 — the unlinked query is capped, so a partial list must not
                 be presented as the whole one (P9).
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp5
        Tests:   tests/test_db_project_drag.py::test_bp5_the_box_says_showing_n_of_m_when_capped
        """
        shown = getattr(self, "unlinked_shown", None)
        if shown is None:
            # This box is not the selected one, so no filtered pass has run for
            # it. The count is Who-filtered (SQL) but not segment-filtered —
            # every other box in the row is — so say which number this is
            # rather than letting it read as the filtered one (sweep pass 3).
            if self._lineage_filter_active():
                return f"{total} unlinked items (unfiltered)"
            return f"{total} unlinked items"
        if getattr(self, "unlinked_total", None) is None:
            # A lineage filter searched a capped slice, so the population
            # behind these rows is genuinely unknown. Saying "N of M" with the
            # unfiltered M would be a number about a different set (S2-3).
            return f"showing {shown} (filtered, not all items searched)"
        if shown < self.unlinked_total:
            return f"showing {shown} of {self.unlinked_total} unlinked items"
        return f"{self.unlinked_total} unlinked items"

    def _load_unlinked_items(self, who_filter):
        """The "No Project" list, capped, with the cap described honestly.

        Purpose: BP5 capped the query so the Scheduler stopped loading every
                 unlinked row to render a handful. Sweep F3: the cap ran
                 *before* the Who and segment filters, so a filtered view
                 silently dropped matching items while the box announced
                 "showing 500 of 525" — a number describing a different set
                 than the one on screen (P9/P3).
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp5
        Tests:   tests/test_db_project_drag.py::test_f3_a_segment_filtered_view_searches_past_the_default_cap

        ``who_filter`` is applied in the query so the cap and the count describe
        the same population. The segment/subsegment filters are derived from an
        item's lineage and cannot be, so when one of them is active the query
        fetches up to ``UNLINKED_FILTERED_LIMIT`` — wider than the default cap,
        so the filter has more than the top 500 to look at, but still bounded.
        """
        segment_filtered = self._lineage_filter_active()
        # A lineage filter cannot go into SQL, so the query has to fetch more
        # than it will show — but not *everything*, which is the unbounded load
        # BP5 exists to remove (S2-4). A ten-times ceiling instead of no
        # ceiling, and it still announces what it dropped.
        limit = (self.UNLINKED_FILTERED_LIMIT if segment_filtered
                 else DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT)
        fetched = self.db_manager.get_unlinked_action_items(
            status_filter="open", who_filter=who_filter, limit=limit)
        fetched_total = self.db_manager.count_unlinked_action_items(
            status_filter="open", who_filter=who_filter)

        items = [item for item in fetched if self._item_matches_filters(item)]

        # The label describes what is on screen. Counting before the lineage
        # filter ran left it announcing 30 beside three rows (S2-3): the Who
        # dimension agreed and the segment dimension — the one deliberately not
        # pushed into SQL — did not.
        if segment_filtered:
            shown, total = len(items), len(items)
            if fetched_total > len(fetched):
                # The ceiling bit, so the filter searched a slice: the true
                # total is unknown and must not be presented as if it were.
                total = None
        else:
            shown, total = len(items), fetched_total

        self.unlinked_shown, self.unlinked_total = shown, total
        if fetched_total > len(fetched):
            logging.getLogger(__name__).warning(
                "[scheduler] unlinked list capped: searched %s of %s items%s",
                len(fetched), fetched_total,
                " before the segment filter" if segment_filtered else "",
            )
        return items

    def build_project_boxes(self):
        projects = self.db_manager.get_project_boards(show_pending=True)
        # Filter projects by current segment/subsegment filters if applicable
        selected_segment = (self.segment_filter_var.get() or "All").strip()
        selected_subsegment = (self.subsegment_filter_var.get() or "All").strip()
        
        filtered_projects = []
        for p in projects:
            if selected_segment != "All" and p.get("segment_name") != selected_segment:
                continue
            if selected_subsegment != "All" and p.get("subsegment_name") != selected_subsegment:
                continue
            filtered_projects.append(p)

        # Apply sorting
        sort_by = self.project_sort_var.get()
        if sort_by == "Subsegment":
            filtered_projects.sort(key=lambda x: ((x.get("subsegment_name") or "").lower(), (x.get("title") or "").lower()))
        elif sort_by == "Category":
            filtered_projects.sort(key=lambda x: ((x.get("category_name") or "").lower(), (x.get("title") or "").lower()))
        else: # Title
            filtered_projects.sort(key=lambda x: (x.get("title") or "").lower())

        # "No Project" special filter box. BP5 — a count query, not the length
        # of every unlinked row in the database. Sweep F3: counted with the
        # same Who filter the list uses, so the number and the rows agree.
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()
        unlinked_count = self.db_manager.count_unlinked_action_items(
            status_filter="open", who_filter=who_filter)
        no_project_color = self.palette["surface_subtle"]
        no_project_text = pick_text_color(no_project_color)
        project_box_height = int(self.date_box_height * 1.5)

        no_project_frame = ctk.CTkFrame(self.projects_frame, height=project_box_height, fg_color=no_project_color)
        no_project_frame.grid_propagate(False)
        no_project_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        no_project_frame.grid_columnconfigure(0, weight=1)
        no_project_frame.grid_rowconfigure(0, weight=1)
        no_project_frame.grid_rowconfigure(1, weight=1)

        label_np_title = ctk.CTkLabel(
            no_project_frame,
            text="Unlinked (No Project)",
            font=ctk.CTkFont(size=self.date_box_font_size, weight="bold"),
            text_color=no_project_text,
            anchor="w"
        )
        label_np_title.grid(row=0, column=0, sticky="sw", padx=10, pady=(2, 0))

        label_np_stats = ctk.CTkLabel(
            no_project_frame,
            text=self._unlinked_box_text(unlinked_count),
            font=ctk.CTkFont(size=12),
            text_color=no_project_text,
            anchor="w"
        )
        label_np_stats.grid(row=1, column=0, sticky="nw", padx=10, pady=(0, 2))

        for w in [no_project_frame, label_np_title, label_np_stats]:
            w.bind("<ButtonPress-1>", lambda _e: self.on_project_target_click("__none__"))

        self.project_boxes.append({"frame": no_project_frame, "id": "__none__"})
        self.project_box_ids[no_project_frame] = "__none__"
        self.date_box_colors[no_project_frame] = no_project_color
        
        is_np_selected = self.selected_project_id == "__none__"
        no_project_frame.configure(
            border_width=2 if is_np_selected else 0,
            border_color=self.palette["primary"] if is_np_selected else self.palette["border"],
        )

        for i, row in enumerate(filtered_projects):
            color = (row.get("category_color_hex") or "").strip() or self.palette["surface_subtle"]
            text_color = pick_text_color(color)
            
            frame = ctk.CTkFrame(self.projects_frame, height=project_box_height, fg_color=color)
            frame.grid_propagate(False)
            frame.grid(row=i + 1, column=0, sticky="ew", padx=2, pady=2)
            frame.grid_columnconfigure(0, weight=1)
            frame.grid_rowconfigure(0, weight=1)
            frame.grid_rowconfigure(1, weight=1)
            
            title = row.get("title") or "Untitled Project"
            meta = f"{row.get('segment_name')} | {row.get('subsegment_name')} | {row.get('category_name')}"
            stats = f"{row.get('open_item_count', 0)} open items"
            
            label_title = ctk.CTkLabel(
                frame,
                text=title,
                font=ctk.CTkFont(size=self.date_box_font_size, weight="bold"),
                text_color=text_color,
                anchor="w"
            )
            label_title.grid(row=0, column=0, sticky="sw", padx=10, pady=(2, 0))
            
            label_meta = ctk.CTkLabel(
                frame,
                text=f"{meta}  ({stats})",
                font=ctk.CTkFont(size=12),
                text_color=text_color,
                anchor="w"
            )
            label_meta.grid(row=1, column=0, sticky="nw", padx=10, pady=(0, 2))
            
            # Bind clicks for filtering
            for w in [frame, label_title, label_meta]:
                w.bind("<ButtonPress-1>", lambda _e, pid=row["id"]: self.on_project_target_click(pid))

            self.project_boxes.append({"frame": frame, "id": row["id"]})
            self.project_box_ids[frame] = row["id"]
            self.date_box_colors[frame] = color # For hover effect
            
            # Highlight if selected
            is_selected = self.selected_project_id == row["id"]
            frame.configure(
                border_width=2 if is_selected else 0,
                border_color=self.palette["primary"] if is_selected else self.palette["border"],
            )

    def on_project_target_click(self, project_id: str):
        if self.selected_project_id == project_id:
            self.selected_project_id = None
        else:
            self.selected_project_id = project_id
            self.selected_date_filter = None # Clear date filter when project is selected
        self.refresh()

    @staticmethod
    def _lineage_from_structured_title(item: ActionItem) -> tuple[str, str, str]:
        parsed = split_action_item_title(item.title)
        context_parts = [part.strip() for part in parsed.context.split("|") if part.strip()]
        if len(context_parts) >= 3:
            category = context_parts[2].split(" - ", 1)[0].strip()
            return context_parts[0], context_parts[1], category
        return "", "", ""

    def _lineage_from_ape_id(self, ape_id: str | None) -> tuple[str, str, str]:
        if not ape_id:
            return "", "", ""
        if ape_id in self._ape_lineage_cache:
            return self._ape_lineage_cache[ape_id]

        lineage = ("", "", "")
        conn = getattr(getattr(self.db_manager, "db", None), "conn", None)
        if conn:
            row = conn.execute(
                """
                SELECT segment_name, subsegment_name, category_name
                FROM annual_plan_elements
                WHERE id = ?
                """,
                (ape_id,),
            ).fetchone()
            if row:
                lineage = (
                    (row["segment_name"] or "").strip(),
                    (row["subsegment_name"] or "").strip(),
                    (row["category_name"] or "").strip(),
                )
        self._ape_lineage_cache[ape_id] = lineage
        return lineage

    def _segment_from_week_action(self, week_action_id: str | None) -> str:
        if not week_action_id:
            return ""
        if week_action_id in self._week_segment_cache:
            return self._week_segment_cache[week_action_id]

        segment_name = ""
        conn = getattr(getattr(self.db_manager, "db", None), "conn", None)
        if conn:
            row = conn.execute(
                """
                SELECT sd.name AS segment_name
                FROM week_actions wa
                LEFT JOIN segment_descriptions sd ON sd.id = wa.segment_description_id
                WHERE wa.id = ?
                """,
                (week_action_id,),
            ).fetchone()
            if row:
                segment_name = (row["segment_name"] or "").strip()
        self._week_segment_cache[week_action_id] = segment_name
        return segment_name

    def _lineage_for_item(self, item: ActionItem, depth: int = 0) -> tuple[str, str, str]:
        item_id = getattr(item, "id", "") or ""
        if item_id and item_id in self._item_lineage_cache:
            return self._item_lineage_cache[item_id]

        lineage = self._lineage_from_ape_id(getattr(item, "annual_plan_element_id", None))
        if any(lineage):
            if item_id:
                self._item_lineage_cache[item_id] = lineage
            return lineage

        if depth < 2:
            parent_id = getattr(item, "parent_id", None)
            if parent_id:
                parent_item = self.db_manager.get_action_item(parent_id)
                if parent_item:
                    parent_lineage = self._lineage_for_item(parent_item, depth + 1)
                    if any(parent_lineage):
                        if item_id:
                            self._item_lineage_cache[item_id] = parent_lineage
                        return parent_lineage

        structured_lineage = self._lineage_from_structured_title(item)
        if any(structured_lineage):
            if item_id:
                self._item_lineage_cache[item_id] = structured_lineage
            return structured_lineage

        week_segment = self._segment_from_week_action(getattr(item, "week_action_id", None))
        lineage = (week_segment, "", "")
        if item_id:
            self._item_lineage_cache[item_id] = lineage
        return lineage

    def _refresh_filter_options(self):
        segment_values = ["All"] + [row["name"] for row in self.app.vps_manager.get_vision_segments()]
        current_segment = self.segment_filter_var.get().strip() or "All"
        if current_segment not in segment_values:
            current_segment = "All"
            self.segment_filter_var.set(current_segment)
        self.segment_filter_combo.configure(values=segment_values)

        segment_name = None if current_segment == "All" else current_segment
        subsegment_values = ["All"] + [
            row["name"] for row in self.app.vps_manager.get_vision_subsegments(segment_name=segment_name)
        ]
        current_subsegment = self.subsegment_filter_var.get().strip() or "All"
        if current_subsegment not in subsegment_values:
            current_subsegment = "All"
            self.subsegment_filter_var.set(current_subsegment)
        self.subsegment_filter_combo.configure(values=subsegment_values)

    def _refresh_project_filter_options(self):
        """Rebuild the header Project filter's values + display→id map.

        Only the value list and map are rebuilt here; ``selected_project_id`` is
        the single source of truth and is reflected into the combo by
        ``_sync_project_filter_var`` after the list is ready.
        """
        boards = self.db_manager.get_project_boards(show_pending=True)
        self.project_filter_map = {}
        display_values = ["All", "(Unlinked)"]
        for board in boards:
            title = (board.get("title") or "Untitled Project").strip()
            display = title
            n = 2
            while display in self.project_filter_map:
                display = f"{title} ({n})"
                n += 1
            self.project_filter_map[display] = board["id"]
            display_values.append(display)
        self.project_filter_combo.configure(values=display_values)

    def _sync_project_filter_var(self):
        """Point the Project combo at whatever ``selected_project_id`` holds."""
        if self.selected_project_id is None:
            self.project_filter_var.set("All")
        elif self.selected_project_id == "__none__":
            self.project_filter_var.set("(Unlinked)")
        else:
            for display, pid in self.project_filter_map.items():
                if pid == self.selected_project_id:
                    self.project_filter_var.set(display)
                    return
            # The selected project is no longer listed (completed/deleted) — clear
            # the stale filter so the item list and the combo agree (P6).
            self.selected_project_id = None
            self.project_filter_var.set("All")

    def on_project_filter_changed(self):
        selection = self.project_filter_var.get()
        if selection == "All":
            self.selected_project_id = None
        elif selection == "(Unlinked)":
            self.selected_project_id = "__none__"
        else:
            self.selected_project_id = self.project_filter_map.get(selection)
        # A project filter and a single-date filter are mutually exclusive.
        self.selected_date_filter = None
        self.refresh()

    def on_segment_filter_changed(self):
        self._refresh_filter_options()
        self.refresh()

    def on_subsegment_filter_changed(self):
        self.refresh()

    def _item_matches_filters(self, item: ActionItem) -> bool:
        segment_name, subsegment_name, _category_name = self._lineage_for_item(item)
        selected_segment = (self.segment_filter_var.get() or "All").strip()
        selected_subsegment = (self.subsegment_filter_var.get() or "All").strip()

        if selected_segment != "All" and segment_name != selected_segment:
            return False
        if selected_subsegment != "All" and subsegment_name != selected_subsegment:
            return False
        return True

    def create_item_row(self, item: ActionItem):
        frame = ctk.CTkFrame(self.items_frame, height=self.item_row_height)
        frame.item = item  # Store item for dynamic text clamping during resize
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, minsize=40)
        self.resizer.apply_grid(frame)
        frame.grid_columnconfigure(6, weight=1)  # trailing slack

        parsed = split_action_item_title(item.title)
        segment_name, subsegment_name, category_name = self._lineage_for_item(item)
        segment_name = segment_name or "-"
        subsegment_name = subsegment_name or "-"
        category_name = category_name or "-"

        segment_color, subsegment_color = resolve_lineage_colors(
            segment_name if segment_name != "-" else "",
            subsegment_name if subsegment_name != "-" else "",
            self.app.vps_manager,
            self.segment_colors,
            self.subsegment_colors,
        )
        category_color = self.category_colors.get(
            (
                segment_name.strip().lower(),
                subsegment_name.strip().lower(),
                category_name.strip().lower(),
            ),
            "",
        ) or subsegment_color

        title_text = parsed.title or (item.title or "")
        title_bg = category_color
        start_date_text = item.start_date or "-"

        checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            width=30,
            command=lambda: self._on_item_checkbox_toggled(item.id)
        )
        checkbox.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=2)
        self.item_checkboxes[item.id] = checkbox

        title_label = ctk.CTkLabel(
            frame,
            text=self.resizer.cell_text("title", title_text),
            anchor="w",
            fg_color=title_bg,
            text_color=pick_text_color(title_bg),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
            width=self.resizer.width("title"),
        )
        title_label.grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=2)

        segment_label = ctk.CTkLabel(
            frame,
            text=self.resizer.cell_text("segment", segment_name),
            anchor="w",
            fg_color=segment_color,
            text_color=pick_text_color(segment_color),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
            width=self.resizer.width("segment"),
        )
        segment_label.grid(row=0, column=2, sticky="ew", padx=4, pady=2)

        subsegment_label = ctk.CTkLabel(
            frame,
            text=self.resizer.cell_text("subsegment", subsegment_name),
            anchor="w",
            fg_color=subsegment_color,
            text_color=pick_text_color(subsegment_color),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
            width=self.resizer.width("subsegment"),
        )
        subsegment_label.grid(row=0, column=3, sticky="ew", padx=4, pady=2)

        category_label = ctk.CTkLabel(
            frame,
            text=self.resizer.cell_text("category", category_name),
            anchor="w",
            fg_color=category_color,
            text_color=pick_text_color(category_color),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
            width=self.resizer.width("category"),
        )
        category_label.grid(row=0, column=4, sticky="ew", padx=4, pady=2)

        start_label = ctk.CTkLabel(
            frame,
            text=self.resizer.cell_text("start_date", start_date_text),
            anchor="w",
            fg_color=self.palette["surface_subtle"],
            text_color=self.palette["body_text"],
            corner_radius=6,
            font=ctk.CTkFont(size=14),
            width=self.resizer.width("start_date"),
        )
        start_label.grid(row=0, column=5, sticky="ew", padx=4, pady=2)

        self.bind_drag_handlers(title_label, item)
        self.bind_drag_handlers(segment_label, item)
        self.bind_drag_handlers(subsegment_label, item)
        self.bind_drag_handlers(category_label, item)
        self.bind_drag_handlers(start_label, item)

        self.resizer.register_row(frame, [
            ("title", title_label, title_text),
            ("segment", segment_label, segment_name),
            ("subsegment", subsegment_label, subsegment_name),
            ("category", category_label, category_name),
            ("start_date", start_label, start_date_text),
        ])
        return frame

    def build_date_boxes(self):
        n_days = int(self.days_var.get())
        today = datetime.now().date()
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()

        # Future date options (bottom)
        options_start_row = n_days + 1

        day_dates = [
            (today + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(n_days)
        ]

        future_options = future_options_for(today, self.settings)

        date_stats, _items_by_date = self.build_date_stats(day_dates, who_filter)

        for i, date_str in enumerate(day_dates):
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
            count, total_minutes = date_stats.get(date_str, (0, 0))
            color = color_for_day_stats(count, total_minutes)

            frame = ctk.CTkFrame(self.dates_frame, height=self.date_box_height, fg_color=color)
            frame.grid_propagate(False)
            frame.grid(row=i, column=0, sticky="ew", padx=2, pady=2)
            self._configure_date_box_columns(frame)
            day_text, date_short, items_text, time_text = self._date_box_values(day.strftime("%A"), day.strftime('%m/%d'), count, total_minutes)
            self._render_date_box_columns(
                frame,
                day_text,
                date_short,
                items_text,
                time_text,
                date_text_color_for(color, getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF")),
                date_str,
            )

            self.date_boxes.append({"frame": frame, "date": date_str})
            self.date_box_colors[frame] = color
            self._register_date_frame(date_str, frame)

        for idx, (title, date_str, color) in enumerate(future_options):
            short_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d")
            frame = ctk.CTkFrame(self.dates_frame, height=self.date_box_height, fg_color=color)
            frame.grid_propagate(False)
            frame.grid(row=options_start_row + idx, column=0, sticky="ew", padx=2, pady=2)
            self._configure_date_box_columns(frame)
            self._render_date_box_columns(
                frame,
                title,
                short_date,
                "",
                "",
                date_text_color_for(color, getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF")),
                date_str,
            )

            self.date_boxes.append({"frame": frame, "date": date_str})
            self.date_box_colors[frame] = color
            self._register_date_frame(date_str, frame)

    def _configure_date_box_columns(self, frame: ctk.CTkFrame):
        frame.grid_columnconfigure(0, minsize=self.DATE_BOX_DAY_MIN_WIDTH)
        frame.grid_columnconfigure(1, minsize=self.DATE_BOX_DATE_MIN_WIDTH)
        frame.grid_columnconfigure(2, minsize=self.DATE_BOX_ITEMS_MIN_WIDTH)
        frame.grid_columnconfigure(3, minsize=self.DATE_BOX_TIME_MIN_WIDTH, weight=1)
        frame.grid_rowconfigure(0, weight=1)

    def _render_date_box_columns(
        self,
        frame: ctk.CTkFrame,
        day_text: str,
        date_text: str,
        items_text: str,
        time_text: str,
        text_color: str,
        filter_date: str,
    ):
        values = (day_text, date_text, items_text, time_text)
        for idx, value in enumerate(values):
            label = ctk.CTkLabel(
                frame,
                text=value,
                anchor="w",
                justify="left",
                font=ctk.CTkFont(size=self.date_box_font_size, weight="bold"),
                text_color=text_color,
            )
            label.grid(row=0, column=idx, sticky="w", padx=(10 if idx == 0 else 6, 0), pady=2)
            self._bind_date_filter_target(label, filter_date)
        self._bind_date_filter_target(frame, filter_date)

    def _date_box_values(self, day_text: str, date_text: str, count: int, total_minutes: int) -> tuple[str, str, str, str]:
        item_label = "item" if count == 1 else "items"
        items_text = f"{count} {item_label}"
        hours = total_minutes // 60
        minutes = total_minutes % 60
        time_text = f"{hours}h {minutes}m"
        return day_text, date_text, items_text, time_text

    def build_date_stats(self, target_dates, who_filter: Optional[str]):
        """Build per-day count and planned-minute totals for visible date boxes."""
        target_set = set(target_dates)
        date_stats = {}
        items_by_date: dict[str, list[ActionItem]] = {}

        items = self.db_manager.get_all_items(
            status_filter="open",
            who_filter=who_filter,
            sort_by="start_date",
            sort_desc=False
        )

        for item in items:
            scheduled_date = item.start_date or item.due_date
            if not scheduled_date:
                continue
            if not self._item_matches_filters(item):
                continue

            if scheduled_date not in target_set:
                continue

            day_key = scheduled_date
            count, total_minutes = date_stats.get(day_key, (0, 0))
            date_stats[day_key] = (
                count + 1,
                total_minutes + (item.planned_minutes or 0)
            )
            items_by_date.setdefault(day_key, []).append(item)

        return date_stats, items_by_date

    def build_calendar_view(self):
        today = datetime.now().date()
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()
        cal = calendar.Calendar(firstweekday=int(getattr(self.settings, "first_day_of_week", 0)))
        month_label = ctk.CTkLabel(
            self.calendar_frame,
            text=today.strftime("%B %Y"),
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        month_label.grid(row=0, column=0, sticky="w", padx=8, pady=(4, 8))

        grid = ctk.CTkFrame(self.calendar_frame, fg_color="transparent")
        grid.grid(row=1, column=0, sticky="nsew")
        for col in range(7):
            grid.grid_columnconfigure(col, weight=1, uniform="sched-cal")
        week_rows = cal.monthdatescalendar(today.year, today.month)
        for row_idx in range(len(week_rows) + 1):
            grid.grid_rowconfigure(row_idx, weight=1)

        weekday_names = list(calendar.day_name)
        ordered_weekday_names = weekday_names[int(getattr(self.settings, "first_day_of_week", 0)):] + weekday_names[:int(getattr(self.settings, "first_day_of_week", 0))]
        for col_idx, name in enumerate(ordered_weekday_names):
            ctk.CTkLabel(
                grid,
                text=name,
                anchor="center",
                font=ctk.CTkFont(weight="bold"),
            ).grid(row=0, column=col_idx, sticky="ew", padx=2, pady=(0, 4))

        month_dates = [day.isoformat() for week in week_rows for day in week]
        date_stats, items_by_date = self.build_date_stats(month_dates, who_filter)
        for row_idx, week in enumerate(week_rows, start=1):
            for col_idx, day in enumerate(week):
                self._render_calendar_day(grid, row_idx, col_idx, day, today, date_stats, items_by_date)

        future_frame = ctk.CTkFrame(self.calendar_frame, fg_color="transparent")
        future_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=(10, 0))
        for col in range(4):
            future_frame.grid_columnconfigure(col, weight=1, uniform="sched-future")
        for idx, (title, date_str, color) in enumerate(future_options_for(today, self.settings)):
            short_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d")
            box = ctk.CTkFrame(future_frame, fg_color=color, corner_radius=8)
            box.grid(row=0, column=idx, sticky="ew", padx=4, pady=4)
            box.grid_columnconfigure(0, weight=1)
            label = ctk.CTkLabel(
                box,
                text=f"{title}\n{short_date}",
                justify="center",
                anchor="center",
                font=ctk.CTkFont(weight="bold"),
                text_color=date_text_color_for(color, getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF")),
            )
            label.grid(row=0, column=0, sticky="ew", padx=8, pady=8)
            self._bind_date_filter_target(label, date_str)
            self._bind_date_filter_target(box, date_str)
            self.date_boxes.append({"frame": box, "date": date_str})
            self.date_box_colors[box] = color
            self._register_date_frame(date_str, box)

    def _render_calendar_day(self, parent, row_idx: int, col_idx: int, day, today, date_stats, items_by_date):
        date_str = day.isoformat()
        count, total_minutes = date_stats.get(date_str, (0, 0))
        cell_color = color_for_day_stats(count, total_minutes) if count or total_minutes else self.palette["surface_subtle"]
        if day.month != today.month:
            cell_color = self.palette["surface_subtle"]

        cell = ctk.CTkFrame(parent, fg_color=cell_color, corner_radius=8)
        cell.grid(row=row_idx, column=col_idx, sticky="nsew", padx=2, pady=2)
        cell.grid_columnconfigure(0, weight=1)

        day_kwargs = {
            "text": str(day.day),
            "anchor": "center",
            "font": ctk.CTkFont(size=18, weight="bold"),
            "text_color": self._calendar_day_text_color(day, today, cell_color),
        }
        if day == today:
            day_kwargs["fg_color"] = self.palette["primary"]
            day_kwargs["text_color"] = self.palette["on_primary"]
            day_kwargs["corner_radius"] = 999
            day_kwargs["width"] = 42
            day_kwargs["height"] = 42
        day_label = ctk.CTkLabel(cell, **day_kwargs)
        day_label.grid(row=0, column=0, sticky="n", padx=6, pady=(8, 4))
        self._bind_date_filter_target(day_label, date_str)

        preview_items = items_by_date.get(date_str, [])[:2]
        text_color = pick_text_color(cell_color)
        for idx, item in enumerate(preview_items, start=1):
            preview = format_column_text(split_action_item_title(item.title).title or item.title or "", 18)
            label = ctk.CTkLabel(
                cell,
                text=preview,
                anchor="w",
                justify="left",
                text_color=text_color,
            )
            label.grid(row=idx, column=0, sticky="ew", padx=8, pady=1)
            self._bind_date_filter_target(label, date_str)

        remaining = max(0, len(items_by_date.get(date_str, [])) - len(preview_items))
        if remaining:
            more_label = ctk.CTkLabel(
                cell,
                text=f"{remaining} more",
                anchor="w",
                justify="left",
                text_color=text_color,
            )
            more_label.grid(row=len(preview_items) + 1, column=0, sticky="ew", padx=8, pady=(2, 6))
            self._bind_date_filter_target(more_label, date_str)
        self._bind_date_filter_target(cell, date_str)
        self.date_boxes.append({"frame": cell, "date": date_str})
        self.date_box_colors[cell] = cell_color
        self._register_date_frame(date_str, cell)

    def _calendar_day_text_color(self, day, today, bg_color: str) -> str:
        if day.month != today.month:
            return self.palette["muted_text"]
        return pick_text_color(bg_color)

    def _future_options_for(self, today) -> list[tuple[str, str, str]]:
        return future_options_for(today, self.settings)

    def _bind_date_filter_target(self, widget, date_str: str):
        widget.bind("<ButtonPress-1>", lambda _event, d=date_str: self.on_date_target_click(d), add="+")

    def on_date_target_click(self, date_str: str):
        if self.selected_date_filter == date_str:
            self.selected_date_filter = None
        else:
            self.selected_date_filter = date_str
        self.refresh()

    def _register_date_frame(self, date_str: str, frame):
        self.selected_date_frames.setdefault(date_str, []).append(frame)
        self.date_frame_dates[frame] = date_str
        self._apply_selected_date_style(frame, date_str)

    def _apply_selected_date_style(self, frame, date_str: str):
        is_selected = self.selected_date_filter == date_str
        frame.configure(
            border_width=2 if is_selected else 0,
            border_color=self.palette["primary"] if is_selected else self.palette["border"],
        )

    def format_day_stats_text(self, count: int, total_minutes: int) -> str:
        return format_day_stats_text(count, total_minutes)

    def _get_date_text_color(self) -> str:
        from .drag_schedule_support import normalized_date_text_color

        return normalized_date_text_color(getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF"))

    def _date_text_color_for(self, bg_color: str) -> str:
        return date_text_color_for(bg_color, getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF"))

    def _date_background_for(self, date_text: str) -> str:
        return date_background_for(date_text)

    def _on_item_checkbox_toggled(self, item_id: str):
        if item_id in self.checked_items:
            self.checked_items.remove(item_id)
        else:
            self.checked_items.add(item_id)
        self._sync_select_all_state()

    def _on_select_all_toggled(self):
        """Header check/uncheck drives every row checkbox."""
        check = bool(self.select_all_var.get())
        self.checked_items = set()
        for item_id, cb in self.item_checkboxes.items():
            try:
                if check:
                    cb.select()
                    self.checked_items.add(item_id)
                else:
                    cb.deselect()
            except Exception:
                pass

    def _sync_select_all_state(self):
        """Reflect 'all rows checked' into the header box without firing its command."""
        if not self.select_all_checkbox:
            return
        all_checked = bool(self.item_checkboxes) and (
            len(self.checked_items) == len(self.item_checkboxes)
        )
        # .select()/.deselect() update the shared variable but do NOT invoke the
        # checkbox command, so this cannot recurse into _on_select_all_toggled.
        if all_checked:
            self.select_all_checkbox.select()
        else:
            self.select_all_checkbox.deselect()

    def bind_drag_handlers(self, widget, item: ActionItem):
        widget.bind("<ButtonPress-1>", lambda e: self.start_drag(e, item))
        widget.bind("<B1-Motion>", self.on_drag_motion)
        widget.bind("<ButtonRelease-1>", self.on_drag_release)

    def start_drag(self, event, item: ActionItem):
        self.drag_item = item
        palette = self.palette

        # Collect items to drag: if item is checked, drag all checked items; else drag just this one
        if item.id in self.checked_items:
            items = self.load_items()
            self.drag_items = [i for i in items if i.id in self.checked_items]
            drag_text = f"{len(self.drag_items)} item{'s' if len(self.drag_items) != 1 else ''}"
        else:
            self.drag_items = [item]
            drag_text = item.title

        if self.drag_label is None:
            self.drag_label = ctk.CTkLabel(
                self,
                text=drag_text,
                fg_color=palette["chip_bg"],
                text_color=palette["chip_text"],
                corner_radius=6,
                padx=8,
                pady=4
            )
        else:
            self.drag_label.configure(text=drag_text)

        self.drag_label.lift()
        self.update_drag_position()

    def on_drag_motion(self, _event):
        if not self.drag_item or not self.drag_label:
            return
        self.update_drag_position()
        self.update_hover_target()

    def on_drag_release(self, _event):
        if not self.drag_item or not self.drag_items:
            return

        target_date, target_project_id = self.get_drop_target()
        self.clear_hover_target()

        if target_date:
            # Batched: reporting after the loop kept only the last item's
            # report, and the cascade is idempotent — so the first item builds
            # everything and the last has nothing to say.
            with self.db_manager.batch_cascade():
                for item in self.drag_items:
                    self.db_manager.reschedule_item(
                        item.id,
                        target_date,
                        target_date,
                        "Drag-and-drop schedule"
                    )
            notify_weekly_tactic_changes(self.db_manager, self)
            self.refresh()
        elif target_project_id:
            self._drop_onto_project(target_project_id)

        if self.drag_label:
            self.drag_label.place_forget()
        self.drag_item = None
        self.drag_items = []

    def _drop_onto_project(self, target_project_id: str):
        """File the dragged items under one project, or clear their project.

        Purpose: sweep F1 — this was the surface that deleted project links
                 with no confirmation while the Projects screen asked, so the
                 same destructive write was guarded in one place and silent in
                 the other (P5). Dropping onto "No Project" is the worse of the
                 two: ``clear_item_project_links`` also nulls the item's
                 Annual Plan Element.
        Spec:    docs/implementation_plan_2026-08-19_backlog_clearance.md#bp1
        Tests:   tests/test_project_multi_link.py::test_f1_dragging_onto_a_project_asks_before_unfiling

        One question per drag, not one per item, and nothing is written unless
        the whole batch can be — a half-applied drag leaves some items moved
        and the rest where they were, with no way to tell which.
        """
        board_id = None if target_project_id == "__none__" else target_project_id
        item_ids = [item.id for item in self.drag_items]
        if not confirm_exclusive_relink(self, self.db_manager, item_ids, board_id):
            return

        try:
            with self.db_manager.transaction():
                for item_id in item_ids:
                    if board_id is None:
                        self.db_manager.clear_item_project_links(item_id)
                    else:
                        self.db_manager.link_item_to_project_exclusive(board_id, item_id)
        except Exception as exc:
            messagebox.showerror(
                "Move Failed",
                f"None of the {len(item_ids)} dragged items were moved: {exc}",
                parent=self,
            )
        self.refresh()

    def update_drag_position(self):
        if not self.drag_label:
            return
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()
        x = x_root - self.winfo_rootx() + 10
        y = y_root - self.winfo_rooty() + 10
        self.drag_label.place(x=x, y=y)

    def get_drop_target(self) -> tuple[Optional[str], Optional[str]]:
        """Find the drop target under the mouse. Returns (date_str, project_id)."""
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()

        # Check date boxes
        for box in self.date_boxes:
            frame = box["frame"]
            if not frame.winfo_ismapped():
                continue
            x1 = frame.winfo_rootx()
            y1 = frame.winfo_rooty()
            x2 = x1 + frame.winfo_width()
            y2 = y1 + frame.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return box["date"], None
                
        # Check project boxes
        for box in self.project_boxes:
            frame = box["frame"]
            if not frame.winfo_ismapped():
                continue
            x1 = frame.winfo_rootx()
            y1 = frame.winfo_rooty()
            x2 = x1 + frame.winfo_width()
            y2 = y1 + frame.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return None, box["id"]
                
        return None, None

    def update_hover_target(self):
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()
        hovered = None

        # Try date boxes
        for box in self.date_boxes:
            frame = box["frame"]
            if not frame.winfo_ismapped():
                continue
            x1 = frame.winfo_rootx()
            y1 = frame.winfo_rooty()
            x2 = x1 + frame.winfo_width()
            y2 = y1 + frame.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                hovered = frame
                break
        
        # Try project boxes if no date box hovered
        if not hovered:
            for box in self.project_boxes:
                frame = box["frame"]
                if not frame.winfo_ismapped():
                    continue
                x1 = frame.winfo_rootx()
                y1 = frame.winfo_rooty()
                x2 = x1 + frame.winfo_width()
                y2 = y1 + frame.winfo_height()
                if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                    hovered = frame
                    break

        if hovered is self.drag_hover_frame:
            return

        self.clear_hover_target()
        if hovered:
            hovered.configure(border_width=2, border_color=self.palette["primary_hover"])
            self.drag_hover_frame = hovered
            self.drag_hover_base_color = self.date_box_colors.get(hovered, self.palette["surface_subtle"])

    def clear_hover_target(self):
        if self.drag_hover_frame:
            date_str = self.date_frame_dates.get(self.drag_hover_frame)
            project_id = self.project_box_ids.get(self.drag_hover_frame)
            
            if date_str:
                self._apply_selected_date_style(self.drag_hover_frame, date_str)
            elif project_id:
                is_selected = self.selected_project_id == project_id
                self.drag_hover_frame.configure(
                    border_width=2 if is_selected else 0,
                    border_color=self.palette["primary"] if is_selected else self.palette["border"],
                )
            else:
                self.drag_hover_frame.configure(border_width=0, border_color=self.palette["border"])
            self.drag_hover_frame = None
            self.drag_hover_base_color = None
