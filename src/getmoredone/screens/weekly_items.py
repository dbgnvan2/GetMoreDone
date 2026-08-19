"""APE Weekly assignment screen with month-to-week workflow."""

from __future__ import annotations

from datetime import date, timedelta
from tkinter import messagebox
from typing import TYPE_CHECKING, Dict, List, Optional

import customtkinter as ctk
import tkinter as tk

from ..app_settings import AppSettings
from .. import week_calendar
from ..weekly_tactic_logging import get_weekly_tactic_logger
from ..color_contrast import pick_text_color
from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors

if TYPE_CHECKING:
    from ..app import GetMoreDoneApp
    from ..vps_manager import VPSManager

logger = get_weekly_tactic_logger()


class WeeklyItemsScreen(ctk.CTkFrame):
    """Assign month-selected Annual Plan Elements into weekly tactics."""

    SPLITTER_WIDTH = 8
    MIN_PANEL_WIDTH = 420
    INDEX_COL_WIDTH = 34
    SEGMENT_COL_WIDTH = 180
    SUBSEGMENT_COL_WIDTH = 180
    CATEGORY_COL_WIDTH = 180

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.week_options: List[str] = []
        self.week_var = ctk.StringVar(value="")
        self.segment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.category_filter_var = ctk.StringVar(value="All")

        self.left_items: List[Dict[str, object]] = []
        self.right_items: List[Dict[str, object]] = []
        self.left_checks: dict[str, ctk.BooleanVar] = {}
        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}

        self.selected_weekly_idx: Optional[int] = None
        self.selected_weekly_item: Optional[Dict[str, object]] = None
        self._split_ratio = 0.5
        self._drag_start_x: Optional[int] = None
        self._drag_start_left: Optional[int] = None
        self.dragged_row: Optional[Dict[str, object]] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_ui()
        self.refresh()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(12, weight=1)

        ctk.CTkLabel(
            header,
            text="APE Weekly Assignment",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, columnspan=13, padx=(10, 20), pady=(8, 6), sticky="w")

        ctk.CTkLabel(header, text="Week Start:").grid(row=1, column=0, padx=(8, 5), pady=(0, 8), sticky="e")
        self.week_combo = ctk.CTkComboBox(header, width=136, values=[""], variable=self.week_var, **combo_box_style())
        self.week_combo.grid(row=1, column=1, padx=5, pady=(0, 8), sticky="w")

        ctk.CTkButton(header, text="Load", width=76, command=self.load_selected_week, **button_style("secondary")).grid(
            row=1, column=2, padx=5, pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(header, text="This Week", width=86, command=self.jump_to_current_week, **button_style("secondary")).grid(
            row=1, column=3, padx=5, pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(header, text="Save", width=76, command=self.add_selected, **button_style("primary")).grid(
            row=1, column=4, padx=(8, 5), pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(header, text="Refresh", width=86, command=self.refresh, **button_style("secondary")).grid(
            row=1, column=5, padx=5, pady=(0, 8), sticky="w"
        )

        ctk.CTkLabel(header, text="Segment:").grid(row=1, column=6, padx=(10, 4), pady=(0, 8), sticky="e")
        self.segment_filter_combo = ctk.CTkComboBox(
            header,
            width=150,
            values=["All"],
            variable=self.segment_filter_var,
            command=lambda _v: self.on_filters_changed(),
            **combo_box_style(),
        )
        self.segment_filter_combo.grid(row=1, column=7, padx=4, pady=(0, 8), sticky="w")

        ctk.CTkLabel(header, text="Sub:").grid(row=1, column=8, padx=(8, 4), pady=(0, 8), sticky="e")
        self.subsegment_filter_combo = ctk.CTkComboBox(
            header,
            width=150,
            values=["All"],
            variable=self.subsegment_filter_var,
            command=lambda _v: self.on_filters_changed(),
            **combo_box_style(),
        )
        self.subsegment_filter_combo.grid(row=1, column=9, padx=4, pady=(0, 8), sticky="w")

        ctk.CTkLabel(header, text="Cat:").grid(row=1, column=10, padx=(8, 4), pady=(0, 8), sticky="e")
        self.category_filter_combo = ctk.CTkComboBox(
            header,
            width=150,
            values=["All"],
            variable=self.category_filter_var,
            command=lambda _v: self.on_filters_changed(),
            **combo_box_style(),
        )
        self.category_filter_combo.grid(row=1, column=11, padx=4, pady=(0, 8), sticky="w")

        self.status_label = ctk.CTkLabel(header, text="", text_color=status_text_color("muted"))
        self.status_label.grid(row=1, column=12, sticky="w", padx=10, pady=(0, 8))

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=0, minsize=520)
        body.grid_columnconfigure(1, weight=0, minsize=self.SPLITTER_WIDTH)
        body.grid_columnconfigure(2, weight=0, minsize=520)
        body.grid_rowconfigure(1, weight=1)
        self.body = body

        self.left_title_label = ctk.CTkLabel(body, text="Month-assigned Annual Plan Elements", font=ctk.CTkFont(weight="bold"))
        self.left_title_label.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self.right_title_label = ctk.CTkLabel(body, text="Weekly Tactics", font=ctk.CTkFont(weight="bold"))
        self.right_title_label.grid(row=0, column=2, sticky="w", padx=8, pady=(8, 4))

        self.left_frame = ctk.CTkScrollableFrame(body, label_text="")
        self.left_frame.grid(row=1, column=0, sticky="nsew")
        self.left_frame.grid_columnconfigure(0, weight=1)

        divider = ctk.CTkFrame(body, width=self.SPLITTER_WIDTH, corner_radius=999, fg_color=semantic_colors()["border"])
        divider.grid(row=1, column=1, sticky="ns", padx=4, pady=4)
        divider.bind("<ButtonPress-1>", self._on_divider_press)
        divider.bind("<B1-Motion>", self._on_divider_drag)
        divider.bind("<ButtonRelease-1>", self._on_divider_release)

        self.right_frame = ctk.CTkFrame(body)
        self.right_frame.grid(row=1, column=2, sticky="nsew")
        self.right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(0, weight=1)

        self.right_list = ctk.CTkScrollableFrame(self.right_frame, label_text="")
        self.right_list.grid(row=0, column=0, sticky="nsew")
        self.right_list.grid_columnconfigure(0, weight=1)

        right_actions = ctk.CTkFrame(self.right_frame)
        right_actions.grid(row=1, column=0, sticky="w", padx=4, pady=(6, 4))
        ctk.CTkButton(right_actions, text="Edit Weekly Tactic", command=self.open_selected_weekly_item, width=150, **button_style("secondary")).pack(
            side="left", padx=6, pady=6
        )
        ctk.CTkButton(right_actions, text="Delete Weekly", command=self.delete_selected_weekly_item, width=130, **button_style("danger")).pack(
            side="left", padx=6, pady=6
        )
        ctk.CTkButton(right_actions, text="Add Action Item", command=self.create_action_item_for_selected_weekly, width=130, **button_style("primary")).pack(
            side="left", padx=6, pady=6
        )

        self.body.bind("<Configure>", self._on_body_resize)
        self.after(100, self._apply_split_ratio)

    def refresh(self):
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            ((r.get("segment_name", "") or "").strip().lower(), (r.get("subsegment_name", "") or "").strip().lower(), (r.get("name", "") or "").strip().lower()): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_categories()
        }
        weekly_items = self.vps_manager.get_weekly_action_items(ape_only=True)
        existing_starts = sorted({wi["start_date"] for wi in weekly_items if wi.get("start_date")}, reverse=True)
        self.week_options = self._build_selectable_week_options(existing_starts)
        self.week_combo.configure(values=self.week_options or [""])
        if self.week_var.get() not in self.week_options:
            self.week_var.set(self.week_options[0] if self.week_options else "")
        self.load_selected_week()

    def load_selected_week(self):
        parsed = self._selected_week_context()
        if not parsed:
            self.left_items = []
            self.right_items = []
            self._render_lists()
            self.status_label.configure(text="Choose a Week Start.")
            return

        week_start, year, quarter, month = parsed
        self.left_items = self.vps_manager.get_annual_plan_elements_for_period(year, quarter, month)
        all_weekly_items = self.vps_manager.get_weekly_action_items(week_start_date=week_start, ape_only=True)

        self._refresh_filter_options(self.left_items, all_weekly_items)
        self.left_items = [row for row in self.left_items if self._ape_matches_filters(row)]
        self.right_items = [row for row in all_weekly_items if self._weekly_matches_filters(row)]

        self.selected_weekly_idx = None
        self.selected_weekly_item = None
        self._render_lists()
        self.left_title_label.configure(text=f"Month-assigned APEs for {year}-{month:02d}")
        self.right_title_label.configure(text=f"Weekly Tactics for {week_start}")
        self.status_label.configure(text=f"{len(self.left_items)} month item(s) on left, {len(self.right_items)} weekly tactic(s) on right")

    def jump_to_current_week(self):
        current_week_start = self._week_start_for(date.today()).isoformat()
        if current_week_start in self.week_options:
            self.week_var.set(current_week_start)
            self.load_selected_week()

    def _selected_week_context(self) -> Optional[tuple[str, int, int, int]]:
        week_start = self.week_var.get().strip()
        if not week_start:
            return None
        week_date = date.fromisoformat(week_start)
        year = week_date.year
        month = week_date.month
        quarter = ((month - 1) // 3) + 1
        return week_start, year, quarter, month

    def _first_day_of_week(self) -> int:
        try:
            settings = getattr(self.app, "settings", None) or AppSettings.load()
            value = int(getattr(settings, "first_day_of_week", 0))
        except Exception:
            value = 0
        return value if 0 <= value <= 6 else 0

    def _week_start_for(self, target_date: date) -> date:
        """WT-M2.B — week identity comes from the one helper, not local arithmetic."""
        return week_calendar.week_start(target_date, self._first_day_of_week())

    def _build_selectable_week_options(self, existing_starts: List[str]) -> List[str]:
        current_start = self._week_start_for(date.today())
        options = [(current_start + timedelta(days=7 * index)).isoformat() for index in range(4)]
        for week_start in existing_starts:
            if week_start not in options:
                options.append(week_start)
        return options

    def _refresh_filter_options(self, left_rows: List[Dict[str, object]], right_rows: List[Dict[str, object]]):
        combined_parts = [self._ape_parts(row) for row in left_rows] + [self._weekly_parts(row) for row in right_rows]
        seg_values = sorted({part[0] for part in combined_parts if part[0] and part[0] != "-"}, key=str.lower)
        sub_values = sorted({part[1] for part in combined_parts if part[1] and part[1] != "-"}, key=str.lower)
        cat_values = sorted({part[2] for part in combined_parts if part[2] and part[2] != "-"}, key=str.lower)
        self._configure_filter_combo(self.segment_filter_combo, self.segment_filter_var, ["All"] + seg_values)
        self._configure_filter_combo(self.subsegment_filter_combo, self.subsegment_filter_var, ["All"] + sub_values)
        self._configure_filter_combo(self.category_filter_combo, self.category_filter_var, ["All"] + cat_values)

    @staticmethod
    def _configure_filter_combo(combo: ctk.CTkComboBox, variable: ctk.StringVar, values: List[str]):
        current = variable.get().strip() or "All"
        if current not in values:
            current = "All"
            variable.set(current)
        combo.configure(values=values)

    def on_filters_changed(self):
        self.load_selected_week()

    def add_selected(self):
        parsed = self._selected_week_context()
        if not parsed:
            messagebox.showwarning("No Week Selected", "Choose a Week Start first.")
            return
        week_start, year, _quarter, month = parsed
        selected_ids = [ape_id for ape_id, var in self.left_checks.items() if var.get()]
        if not selected_ids:
            messagebox.showwarning("No APE Selected", "Check one or more month-assigned APEs on the left first.")
            return

        created = 0
        skipped = 0
        collided = 0
        for ape_id in selected_ids:
            result = self.vps_manager.create_week_action_items_for_ape(ape_id, year, month, [week_start])
            created += int(result.get("created_count", 0))
            skipped += int(result.get("skipped_count", 0))
            collided += int(result.get("collided_count", 0))

        self.refresh()
        self.status_label.configure(
            text=self._describe_week_creation(created, skipped, collided)
        )

    @staticmethod
    def _describe_week_creation(created: int, skipped: int, collided: int) -> str:
        """WT-M1.C.3 — one wording for every path that creates weekly tactics.

        Spec:  docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m1c3
        Tests: tests/test_weekly_tactic_schema.py::test_wt_m1c3_both_creation_paths_report_collisions

        Both callers of ``create_week_action_items_for_ape`` report through here.
        Hardening only the button and leaving the drag silent is the sibling
        problem P5 describes — and the drag was the one that showed nothing at
        all when a week was refused.
        """
        status = f"Created {created} weekly tactic(s); skipped {skipped} existing item(s)."
        if collided:
            status += f" {collided} already existed for that week and were not duplicated."
        return status

    def _render_lists(self):
        self._clear_scroll(self.left_frame)
        self._clear_scroll(self.right_list)
        self.left_checks = {}
        self._render_left_rows()
        self._render_right_rows()

    def _render_left_rows(self):
        if not self.left_items:
            ctk.CTkLabel(self.left_frame, text="No month-assigned Annual Plan Elements match the current week/filter.", text_color=status_text_color("muted")).grid(
                row=0, column=0, pady=20, padx=10, sticky="w"
            )
            return

        palette = semantic_colors()
        header = ctk.CTkFrame(self.left_frame, fg_color=palette["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))
        header.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(header, text="Pick", width=52, font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkLabel(header, text="#", width=self.INDEX_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Segment", width=self.SEGMENT_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="SubSegment", width=self.SUBSEGMENT_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=3, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Category", width=self.CATEGORY_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=4, padx=5, pady=5, sticky="w")

        for idx, row in enumerate(self.left_items, start=1):
            segment_name, subsegment_name, category_name = self._ape_parts(row)
            segment_color, subsegment_color = resolve_lineage_colors(segment_name, subsegment_name, self.vps_manager, self.segment_colors, self.subsegment_colors)
            category_color = self.category_colors.get((segment_name.strip().lower(), subsegment_name.strip().lower(), category_name.strip().lower()), "") or subsegment_color

            item = ctk.CTkFrame(self.left_frame)
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            item.grid_columnconfigure(4, weight=1)

            checked = ctk.BooleanVar(value=False)
            self.left_checks[row["id"]] = checked
            ctk.CTkCheckBox(item, text="", variable=checked, width=30).grid(row=0, column=0, padx=5, pady=5)
            index_label = ctk.CTkLabel(item, text=str(idx), width=self.INDEX_COL_WIDTH, anchor="w")
            index_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            seg_chip = ctk.CTkLabel(item, text=f" {self._clip_label(segment_name, 18)} ", width=self.SEGMENT_COL_WIDTH, fg_color=segment_color, text_color=pick_text_color(segment_color), corner_radius=6, anchor="w")
            seg_chip.grid(row=0, column=2, padx=5, pady=5, sticky="w")
            sub_chip = ctk.CTkLabel(item, text=f" {self._clip_label(subsegment_name, 18)} ", width=self.SUBSEGMENT_COL_WIDTH, fg_color=subsegment_color, text_color=pick_text_color(subsegment_color), corner_radius=6, anchor="w")
            sub_chip.grid(row=0, column=3, padx=5, pady=5, sticky="w")
            cat_chip = ctk.CTkLabel(item, text=f" {self._clip_label(category_name, 18)} ", width=self.CATEGORY_COL_WIDTH, fg_color=category_color, text_color=pick_text_color(category_color), corner_radius=6, anchor="w")
            cat_chip.grid(row=0, column=4, padx=5, pady=5, sticky="w")
            self._bind_drag_widgets((item, index_label, seg_chip, sub_chip, cat_chip), row)

    def _render_right_rows(self):
        if not self.right_items:
            ctk.CTkLabel(self.right_list, text="No weekly tactics exist for the selected week yet.", text_color=status_text_color("muted")).grid(
                row=0, column=0, pady=20, padx=10, sticky="w"
            )
            return

        palette = semantic_colors()
        row_text = palette["row_text"]
        header = ctk.CTkFrame(self.right_list, fg_color=palette["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))
        header.grid_columnconfigure(3, weight=1)
        ctk.CTkLabel(header, text="#", width=self.INDEX_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Segment", width=self.SEGMENT_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="SubSegment", width=self.SUBSEGMENT_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Category", width=self.CATEGORY_COL_WIDTH, font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=3, padx=5, pady=5, sticky="w")

        for idx, row in enumerate(self.right_items, start=1):
            segment_name, subsegment_name, category_name = self._weekly_parts(row)
            segment_color, subsegment_color = resolve_lineage_colors(segment_name, subsegment_name, self.vps_manager, self.segment_colors, self.subsegment_colors)
            category_color = self.category_colors.get((segment_name.strip().lower(), subsegment_name.strip().lower(), category_name.strip().lower()), "") or subsegment_color
            bg = palette["selected_tint"] if idx - 1 == self.selected_weekly_idx else None

            item = ctk.CTkFrame(self.right_list, fg_color=bg, border_width=2, border_color=segment_color)
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            item.grid_columnconfigure(3, weight=1)
            index_label = ctk.CTkLabel(item, text=str(idx), width=self.INDEX_COL_WIDTH, anchor="w", text_color=row_text)
            index_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
            seg_chip = ctk.CTkLabel(item, text=f" {self._clip_label(segment_name, 18)} ", width=self.SEGMENT_COL_WIDTH, fg_color=segment_color, text_color=pick_text_color(segment_color), corner_radius=6, anchor="w")
            seg_chip.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            sub_chip = ctk.CTkLabel(item, text=f" {self._clip_label(subsegment_name, 18)} ", width=self.SUBSEGMENT_COL_WIDTH, fg_color=subsegment_color, text_color=pick_text_color(subsegment_color), corner_radius=6, anchor="w")
            sub_chip.grid(row=0, column=2, padx=5, pady=5, sticky="w")
            cat_chip = ctk.CTkLabel(item, text=f" {self._clip_label(category_name, 18)} ", width=self.CATEGORY_COL_WIDTH, fg_color=category_color, text_color=pick_text_color(category_color), corner_radius=6, anchor="w")
            cat_chip.grid(row=0, column=3, padx=5, pady=5, sticky="w")
            for widget in (item, index_label, seg_chip, sub_chip, cat_chip):
                widget.bind("<Button-1>", lambda _e, i=idx - 1: self.on_select_weekly_item(i))
                widget.bind("<Double-Button-1>", lambda _e, i=idx - 1: self._open_weekly_from_index(i))

    def on_select_weekly_item(self, idx: int):
        if idx < 0 or idx >= len(self.right_items):
            return
        self.selected_weekly_idx = idx
        self.selected_weekly_item = self.right_items[idx]
        self._render_right_rows()

    def _open_weekly_from_index(self, idx: int):
        self.on_select_weekly_item(idx)
        self.open_selected_weekly_item()

    def create_action_item_for_selected_weekly(self):
        if not self.selected_weekly_item:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly tactic on the right first.")
            return

        from ..models import ActionItem
        from .title_format import build_action_item_title, split_action_item_title

        dialog = ctk.CTkInputDialog(text="Immediate Step:", title="New Related Action")
        title = (dialog.get_input() or "").strip()
        if not title:
            return

        weekly = self.selected_weekly_item
        weekly_title = self.vps_manager.normalize_week_token((weekly.get("title") or "").strip())
        weekly_title_short = self.vps_manager.shorten_pipe_prefix(weekly_title)
        parsed = split_action_item_title(weekly_title_short)
        full_title = build_action_item_title(parsed.context, title)
        item = ActionItem(
            who=weekly.get("who") or "",
            title=full_title,
            description=f"Related to weekly item: {weekly.get('title') or ''}",
            parent_id=weekly["id"],
            start_date=weekly.get("start_date"),
            due_date=weekly.get("start_date"),
            category=weekly.get("category"),
            annual_plan_element_id=weekly.get("annual_plan_element_id"),
            item_type="daily",
        )
        self.app.db_manager.create_action_item(item, apply_defaults=False)
        self.status_label.configure(text="Added a related Action Item for the selected weekly tactic.")

    def open_selected_weekly_item(self):
        if not self.selected_weekly_item:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly tactic on the right first.")
            return
        from .item_editor import ItemEditorDialog
        ItemEditorDialog(self, self.app.db_manager, item_id=self.selected_weekly_item["id"], vps_manager=self.vps_manager, on_close_callback=self.on_weekly_editor_closed)

    def delete_selected_weekly_item(self):
        if not self.selected_weekly_item:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly tactic on the right first.")
            return
        title = (self.selected_weekly_item.get("title") or "this weekly tactic").strip()
        if not messagebox.askyesno("Delete Weekly Tactic", f"Delete {title} and related action items?", icon="warning"):
            return
        if self.vps_manager.delete_weekly_action_item(self.selected_weekly_item["id"]):
            self.refresh()
        else:
            messagebox.showerror("Delete Failed", "Weekly tactic could not be deleted.")

    def on_weekly_editor_closed(self):
        self.refresh()

    def _start_row_drag(self, row: Dict[str, object]):
        self.dragged_row = row
        self.winfo_toplevel().bind("<ButtonRelease-1>", self._finish_row_drag)

    def _finish_row_drag(self, _event):
        self.winfo_toplevel().unbind("<ButtonRelease-1>")
        if not self.dragged_row:
            return
        pointer_x, pointer_y = self.winfo_pointerxy()
        target = self.winfo_containing(pointer_x, pointer_y)
        row = self.dragged_row
        self.dragged_row = None
        if self._is_descendant(target, self.right_list):
            parsed = self._selected_week_context()
            if not parsed:
                # The button path warns when no week is chosen; the drag path
                # used to do nothing at all for the same input.
                self.status_label.configure(
                    text="Select a Week Start before dragging an Annual Plan Element."
                )
                return
            week_start, year, _quarter, month = parsed
            try:
                result = self.vps_manager.create_week_action_items_for_ape(
                    row["id"], year, month, [week_start])
            except ValueError as exc:
                # create_week_action_items_for_ape raises on a stale APE or a
                # bad month. Unhandled inside a Tk binding that is a traceback
                # on stderr and nothing on screen.
                logger.exception("[weekly_items] drag create failed: %s", exc)
                self.status_label.configure(text=f"Could not create the weekly tactic: {exc}")
                return
            # Always refresh and always say what happened: a drag that collided
            # used to produce no refresh, no status and no sign of rejection.
            self.refresh()
            self.status_label.configure(
                text=self._describe_week_creation(
                    int(result.get("created_count", 0)),
                    int(result.get("skipped_count", 0)),
                    int(result.get("collided_count", 0)),
                )
            )

    def _bind_drag_widgets(self, widgets: tuple, row: Dict[str, object]):
        for widget in widgets:
            widget.bind("<ButtonPress-1>", lambda _event, r=row: self._start_row_drag(r))

    def _on_body_resize(self, _event):
        if self._drag_start_x is None:
            self._apply_split_ratio()

    def _on_divider_press(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_left = self.left_frame.winfo_width()

    def _on_divider_drag(self, event):
        if self._drag_start_x is None or self._drag_start_left is None:
            return
        total = self.body.winfo_width() - self.SPLITTER_WIDTH
        if total <= 0:
            return
        left = self._drag_start_left + (event.x_root - self._drag_start_x)
        max_left = max(self.MIN_PANEL_WIDTH, total - self.MIN_PANEL_WIDTH)
        left = max(self.MIN_PANEL_WIDTH, min(max_left, left))
        self._split_ratio = left / total
        self._apply_split_ratio()

    def _on_divider_release(self, _event):
        self._drag_start_x = None
        self._drag_start_left = None

    def _apply_split_ratio(self):
        total = self.body.winfo_width() - self.SPLITTER_WIDTH
        if total <= 0:
            return
        max_left = max(self.MIN_PANEL_WIDTH, total - self.MIN_PANEL_WIDTH)
        left = int(total * self._split_ratio)
        left = max(self.MIN_PANEL_WIDTH, min(max_left, left))
        right = total - left
        self.body.grid_columnconfigure(0, minsize=left)
        self.body.grid_columnconfigure(2, minsize=right)

    @staticmethod
    def _is_descendant(widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    @staticmethod
    def _clear_scroll(frame: ctk.CTkScrollableFrame):
        for child in frame.winfo_children():
            child.destroy()

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"

    def _ape_matches_filters(self, row: Dict[str, object]) -> bool:
        seg, sub, cat = self._ape_parts(row)
        return self._parts_match_filters(seg, sub, cat)

    def _weekly_matches_filters(self, row: Dict[str, object]) -> bool:
        seg, sub, cat = self._weekly_parts(row)
        return self._parts_match_filters(seg, sub, cat)

    def _parts_match_filters(self, seg_name: str, sub_name: str, cat_name: str) -> bool:
        seg = self.segment_filter_var.get().strip()
        sub = self.subsegment_filter_var.get().strip()
        cat = self.category_filter_var.get().strip()
        if seg and seg != "All" and seg_name != seg:
            return False
        if sub and sub != "All" and sub_name != sub:
            return False
        if cat and cat != "All" and cat_name != cat:
            return False
        return True

    @staticmethod
    def _ape_parts(row: Dict[str, object]) -> tuple[str, str, str]:
        return (
            (row.get("segment_name") or "-").strip(),
            (row.get("subsegment_name") or "-").strip(),
            (row.get("category_name") or "-").strip(),
        )

    def _weekly_parts(self, row: Dict[str, object]) -> tuple[str, str, str]:
        seg = (row.get("ape_segment_name") or row.get("who") or "").strip()
        sub = (row.get("ape_subsegment_name") or "").strip()
        cat = (row.get("ape_category_name") or "").strip()
        return seg or "-", sub or "-", cat or "-"
