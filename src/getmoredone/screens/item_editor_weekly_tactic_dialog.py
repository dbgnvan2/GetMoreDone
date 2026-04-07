"""Weekly tactic selection dialog extracted from item_editor_dialogs.py."""

from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

import customtkinter as ctk

from ..paths import app_data_dir_path
from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from ..color_contrast import pick_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
from .title_format import split_action_item_title

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..vps_manager import VPSManager


def _get_weekly_debug_logger() -> logging.Logger:
    logger = logging.getLogger("getmoredone.weekly_tactic")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    log_path = app_data_dir_path() / "weekly_tactic_debug.log"
    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger

class SetWeeklyTacticDialog(ctk.CTkToplevel):
    """Dialog for selecting a weekly tactic within a limited window."""

    def __init__(self, parent, db_manager: 'DatabaseManager', vps_manager: 'VPSManager',
                 item_id: Optional[str], item_title: str, first_day_of_week: int,
                 anchor_date: date,
                 segment_name_map: Dict[str, str], on_select):
        super().__init__(parent)
        self.db_manager = db_manager
        self.vps_manager = vps_manager
        self.logger = _get_weekly_debug_logger()
        self.item_id = item_id
        self.item_title = item_title
        self.first_day_of_week = first_day_of_week
        self.anchor_date = anchor_date
        self.segment_name_map = segment_name_map
        self.on_select = on_select
        self.current_selection: Optional[str] = None
        self.rolling_mode = True

        self.month_default_label = "Rolling Window (Prev/Current/Next)"
        self.month_past_week_label = "Past Week"
        self.month_current_week_label = "Current Week"
        self.month_next_week_label = "Next Week"
        self.month_all_label = "All Weeks"
        self.month_filter_var = ctk.StringVar(value=self.month_default_label)
        self.month_lookup: Dict[str, Tuple[int, int]] = {}
        self.month_options = self._build_month_options()

        self.title(f"Set Weekly Tactic for: {item_title}")
        self.geometry("900x520")

        self.prev_start = date.today()
        self.current_start = date.today()
        self.next_start = date.today()
        self._set_rolling_window_range()

        self.segment_filter_var = ctk.StringVar(value="All Segments")
        self.subsegment_filter_var = ctk.StringVar(value="All SubSegments")
        self.category_filter_var = ctk.StringVar(value="All Categories")
        self.segments = self.vps_manager.get_all_segments()
        self.segment_options = ["All Segments"] + [seg["name"] for seg in self.segments]
        self.subsegment_options = ["All SubSegments"]
        self.category_options = ["All Categories"]
        self.segment_colors_by_id = self.vps_manager.get_segment_colors_by_id()
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (row.get("segment_name", "") or "").strip().lower(),
                (row.get("subsegment_name", "") or "").strip().lower(),
                (row.get("name", "") or "").strip().lower(),
            ): (row.get("color_hex") or "").strip()
            for row in self.vps_manager.get_vision_categories()
        }

        self.create_ui()
        self.logger.info(
            "[set_weekly_dialog:init] item_id=%s title=%s anchor=%s month_options=%d segments=%d",
            self.item_id,
            self.item_title,
            self.anchor_date.isoformat() if self.anchor_date else None,
            len(self.month_options),
            len(self.segment_options),
        )
        self.refresh_actions()

        self.transient(parent)
        self.grab_set()
        self.center_on_parent()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=10, pady=10)
        header.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(
            header,
            text="Select a Weekly Tactic",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=(5, 12))

        ctk.CTkLabel(header, text="Month Filter:").grid(row=0, column=1, sticky="e", padx=5, pady=3)
        self.month_combo = ctk.CTkComboBox(
            header,
            values=self.month_options,
            variable=self.month_filter_var,
            width=220,
            **combo_box_style(),
            command=lambda _: self._on_month_filter_change()
        )
        self.month_combo.grid(row=0, column=2, sticky="w", padx=5, pady=3)

        ctk.CTkLabel(header, text="Segment Filter:").grid(row=0, column=3, sticky="e", padx=5, pady=3)
        self.segment_combo = ctk.CTkComboBox(
            header,
            values=self.segment_options,
            variable=self.segment_filter_var,
            width=200,
            **combo_box_style(),
            command=lambda _: self._on_segment_filter_change()
        )
        self.segment_combo.grid(row=0, column=4, sticky="w", padx=5, pady=3)

        ctk.CTkLabel(header, text="SubSegment Filter:").grid(row=1, column=1, sticky="e", padx=5, pady=3)
        self.subsegment_combo = ctk.CTkComboBox(
            header,
            values=self.subsegment_options,
            variable=self.subsegment_filter_var,
            width=200,
            **combo_box_style(),
            command=lambda _: self._on_subsegment_filter_change()
        )
        self.subsegment_combo.grid(row=1, column=2, sticky="w", padx=5, pady=3)

        ctk.CTkLabel(header, text="Category Filter:").grid(row=1, column=3, sticky="e", padx=5, pady=3)
        self.category_combo = ctk.CTkComboBox(
            header,
            values=self.category_options,
            variable=self.category_filter_var,
            width=200,
            **combo_box_style(),
            command=lambda _: self.refresh_actions()
        )
        self.category_combo.grid(row=1, column=4, sticky="w", padx=5, pady=3)

        self.list_frame = ctk.CTkScrollableFrame(self, height=360)
        self.list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        btn_frame = ctk.CTkFrame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(btn_frame, text="Close", command=self.destroy, width=100, **button_style("secondary")).pack(side="right")

    def refresh_actions(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        selected_segment_name = self.segment_filter_var.get()
        segment_ids = None
        if selected_segment_name != "All Segments":
            seg = next((s for s in self.segments if s["name"] == selected_segment_name), None)
            if seg:
                segment_ids = [seg["id"]]

        self.logger.info(
            "[set_weekly_dialog:refresh] month=%s segment=%s range=%s..%s rolling_mode=%s",
            self.month_filter_var.get(),
            selected_segment_name,
            self.range_start.isoformat(),
            self.range_end.isoformat(),
            self.rolling_mode,
        )
        week_items = self._get_week_items_for_current_window(segment_ids)
        self.logger.info("[set_weekly_dialog:refresh] initial_count=%d", len(week_items))
        allow_auto_fallback = self.month_filter_var.get() == self.month_default_label

        if not week_items:
            # Auto-switch to the latest defined month if the rolling window is empty.
            if allow_auto_fallback:
                month_labels = [option for option in self.month_options if option in self.month_lookup]
                latest_label = month_labels[0] if month_labels else None
            else:
                latest_label = None
            if latest_label:
                self.month_filter_var.set(latest_label)
                self._set_month_range(*self.month_lookup[latest_label])
                week_items = self._get_week_items_for_current_window(segment_ids)
                self.logger.info(
                    "[set_weekly_dialog:refresh] fallback_latest_month=%s count=%d",
                    latest_label,
                    len(week_items),
                )

        if not week_items and allow_auto_fallback and self.month_filter_var.get() != self.month_all_label:
            # Fall back to showing the entire archive.
            self.month_filter_var.set(self.month_all_label)
            if self._set_all_weeks_range():
                week_items = self._get_week_items_for_current_window(segment_ids)
                self.logger.info(
                    "[set_weekly_dialog:refresh] fallback_all_weeks count=%d",
                    len(week_items),
                )

        if not week_items:
            self.logger.warning("[set_weekly_dialog:refresh] no_results_after_fallbacks")
            ctk.CTkLabel(
                self.list_frame,
                text="No weekly tactics found for the selected window.",
                text_color=status_text_color("muted")
            ).grid(row=0, column=0, pady=20, padx=5)
            return

        self._refresh_subsegment_options(week_items)
        selected_subsegment = self.subsegment_filter_var.get()
        if selected_subsegment != "All SubSegments":
            week_items = [
                action for action in week_items
                if (action.get("ape_subsegment_name") or "").strip() == selected_subsegment
            ]
        self._refresh_category_options(week_items)
        selected_category = self.category_filter_var.get()
        if selected_category != "All Categories":
            week_items = [
                action for action in week_items
                if (action.get("ape_category_name") or "").strip() == selected_category
            ]

        if not week_items:
            ctk.CTkLabel(
                self.list_frame,
                text="No weekly tactics found for the selected filters.",
                text_color=status_text_color("muted")
            ).grid(row=0, column=0, pady=20, padx=5)
            return

        header = ctk.CTkFrame(self.list_frame, fg_color=self.palette["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 5))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Week", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=10, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Segment", width=150, font=ctk.CTkFont(weight="bold")).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkLabel(header, text="Immediate Step", font=ctk.CTkFont(weight="bold")).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        ctk.CTkLabel(header, text="Action", font=ctk.CTkFont(weight="bold")).grid(row=0, column=3, padx=5, pady=5)

        row = 1
        for week_item in week_items:
            segment_id = week_item.get("segment_description_id")
            segment_name = (week_item.get("ape_segment_name") or self.segment_name_map.get(segment_id) or "").strip()
            subsegment_name = (week_item.get("ape_subsegment_name") or "").strip()
            category_name = (week_item.get("ape_category_name") or "").strip()

            segment_color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_name,
                self.vps_manager,
                self.segment_colors,
                self.subsegment_colors,
            )
            row_color = self.category_colors.get(
                (
                    segment_name.lower(),
                    subsegment_name.lower(),
                    category_name.lower(),
                ),
                "",
            ) or subsegment_color or self.segment_colors_by_id.get(segment_id, "gray20")
            text_color = pick_text_color(row_color)

            frame = ctk.CTkFrame(self.list_frame, fg_color=row_color)
            frame.grid(row=row, column=0, sticky="ew", padx=5, pady=2)
            frame.grid_columnconfigure(2, weight=1)

            week_label = self._week_label(week_item.get("start_date"))
            ctk.CTkLabel(frame, text=week_label, width=120, anchor="w", text_color=text_color).grid(row=0, column=0, padx=10, pady=5, sticky="w")

            seg_name = self.segment_name_map.get(week_item.get("segment_description_id"), "-")
            ctk.CTkLabel(frame, text=seg_name or "-", width=150, anchor="w", text_color=text_color).grid(row=0, column=1, padx=5, pady=5, sticky="w")

            ctk.CTkLabel(frame, text=week_item.get("title") or "-", anchor="w", text_color=text_color).grid(row=0, column=2, padx=5, pady=5, sticky="w")

            display = self._format_week_action_display(week_item)
            btn = ctk.CTkButton(
                frame,
                text="Select",
                width=80,
                command=lambda wi=week_item, disp=display: self._select_week_action(wi, disp),
                **button_style("primary"),
            )
            btn.grid(row=0, column=3, padx=5, pady=5)
            row += 1

    def _on_segment_filter_change(self):
        self.subsegment_filter_var.set("All SubSegments")
        self.category_filter_var.set("All Categories")
        self.refresh_actions()

    def _on_subsegment_filter_change(self):
        self.category_filter_var.set("All Categories")
        self.refresh_actions()

    def _refresh_subsegment_options(self, week_items: List[Dict[str, Any]]):
        subsegments = sorted(
            {
                (item.get("ape_subsegment_name") or "").strip()
                for item in week_items
                if (item.get("ape_subsegment_name") or "").strip()
            },
            key=str.casefold,
        )
        options = ["All SubSegments"] + subsegments
        current = self.subsegment_filter_var.get()
        if current not in options:
            self.subsegment_filter_var.set("All SubSegments")
        self.subsegment_options = options
        self.subsegment_combo.configure(values=self.subsegment_options)

    def _refresh_category_options(self, week_items: List[Dict[str, Any]]):
        categories = sorted(
            {
                (item.get("ape_category_name") or "").strip()
                for item in week_items
                if (item.get("ape_category_name") or "").strip()
            },
            key=str.casefold,
        )
        options = ["All Categories"] + categories
        current = self.category_filter_var.get()
        if current not in options:
            self.category_filter_var.set("All Categories")
        self.category_options = options
        self.category_combo.configure(values=self.category_options)

    def _select_week_action(self, week_item: Dict[str, Any], display: str):
        self.on_select(
            week_item.get("week_action_id"),
            week_item.get("segment_description_id"),
            display,
            week_item.get("id")
        )
        self.logger.info(
            "[set_weekly_dialog:select] week_item_id=%s week_action_id=%s segment_id=%s title=%s",
            week_item.get("id"),
            week_item.get("week_action_id"),
            week_item.get("segment_description_id"),
            week_item.get("title"),
        )
        self.destroy()

    def _format_week_action_display(self, week_action: Dict[str, Any]) -> str:
        start = week_action.get("week_start_date") or week_action.get("start_date") or "-"
        end = week_action.get("week_end_date") or week_action.get("due_date") or "-"
        seg_name = self.segment_name_map.get(week_action.get("segment_description_id"), "").strip()
        seg_suffix = f" [{seg_name}]" if seg_name else ""
        title = week_action.get("title") or "(untitled)"
        return f"{title} [{start} - {end}]{seg_suffix}"

    def _week_label(self, start_date_str: Optional[str]) -> str:
        if not start_date_str:
            return "-"
        label = start_date_str
        if self.rolling_mode:
            if start_date_str == self.current_start.isoformat():
                label += " (Current)"
            elif start_date_str == self.prev_start.isoformat():
                label += " (Previous)"
            elif start_date_str == self.next_start.isoformat():
                label += " (Next)"
        return label

    def _text_color_for_background(self, color_hex: str) -> str:
        value = (color_hex or "").strip()
        if value.startswith("#") and len(value) == 7:
            try:
                r = int(value[1:3], 16)
                g = int(value[3:5], 16)
                b = int(value[5:7], 16)
                luminance = (0.299 * r) + (0.587 * g) + (0.114 * b)
                return "black" if luminance > 160 else "white"
            except ValueError:
                pass
        return "white"

    def _build_month_options(self) -> list:
        self.month_lookup = {}
        options = [
            self.month_default_label,
            self.month_past_week_label,
            self.month_current_week_label,
            self.month_next_week_label,
            self.month_all_label,
        ]
        try:
            months = self.vps_manager.get_weekly_action_item_months()
        except Exception:
            months = []

        seen = set()
        for entry in months:
            year = entry.get("year")
            month = entry.get("month")
            if not year or not month:
                continue
            label = f"{calendar.month_name[month]} {year}"
            if label in seen:
                continue
            seen.add(label)
            self.month_lookup[label] = (year, month)
            options.append(label)
        return options

    def _align_to_week_start(self, value: date) -> date:
        offset = (value.weekday() - self.first_day_of_week) % 7
        return value - timedelta(days=offset)

    def _align_to_week_end(self, value: date) -> date:
        last_day_index = (self.first_day_of_week + 6) % 7
        offset = (last_day_index - value.weekday()) % 7
        return value + timedelta(days=offset)

    def _set_rolling_window_range(self):
        self.prev_start, self.current_start, self.next_start = self._compute_week_starts()
        anchor = self.anchor_date or date.today()
        start = self._align_to_week_start(anchor - timedelta(days=21))
        end = self._align_to_week_end(anchor + timedelta(days=7))
        self.range_start = start
        self.range_end = end
        self.rolling_mode = True

    def _set_month_range(self, year: int, month: int):
        self.rolling_mode = False
        month_start = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        month_end = date(year, month, last_day)
        self.range_start = self._align_to_week_start(month_start)
        self.range_end = self._align_to_week_end(month_end)

    def _set_specific_week_range(self, week_start: date):
        self.rolling_mode = True
        aligned_start = self._align_to_week_start(week_start)
        self.range_start = aligned_start
        self.range_end = aligned_start + timedelta(days=6)

    def _set_all_weeks_range(self) -> bool:
        self.rolling_mode = False
        bounds = self.vps_manager.get_weekly_action_item_bounds()
        if not bounds:
            return False
        min_start = date.fromisoformat(bounds[0])
        max_start = date.fromisoformat(bounds[1])
        self.range_start = self._align_to_week_start(min_start)
        self.range_end = self._align_to_week_end(max_start)
        return True

    def _on_month_filter_change(self):
        selection = self.month_filter_var.get()
        if selection == self.month_default_label:
            self._set_rolling_window_range()
        elif selection == self.month_past_week_label:
            self._set_specific_week_range(self.prev_start)
        elif selection == self.month_current_week_label:
            self._set_specific_week_range(self.current_start)
        elif selection == self.month_next_week_label:
            self._set_specific_week_range(self.next_start)
        elif selection == self.month_all_label:
            if not self._set_all_weeks_range():
                self.month_filter_var.set(self.month_default_label)
                self._set_rolling_window_range()
        else:
            target = self.month_lookup.get(selection)
            if target:
                self._set_month_range(*target)
        self.refresh_actions()

    def _compute_week_starts(self):
        anchor = self.anchor_date or date.today()
        offset = (anchor.weekday() - self.first_day_of_week) % 7
        current = anchor - timedelta(days=offset)
        prev = current - timedelta(days=7)
        nxt = current + timedelta(days=7)
        return prev, current, nxt

    def _get_week_items_for_current_window(self, segment_ids: Optional[List[str]]):
        if self.month_filter_var.get() == self.month_all_label:
            actions = self.vps_manager.get_weekly_action_items(ape_only=True)
            if segment_ids:
                segment_set = set(segment_ids)
                actions = [
                    action for action in actions
                    if action.get("segment_description_id") in segment_set
                ]
            self.logger.info(
                "[set_weekly_dialog:get_items] mode=all_weeks segment_filter=%s count=%d",
                segment_ids,
                len(actions),
            )
            return actions

        actions = self.vps_manager.get_weekly_action_items_in_range(
            self.range_start.isoformat(),
            self.range_end.isoformat(),
            segment_ids=segment_ids,
            ape_only=True,
        )
        self.logger.info(
            "[set_weekly_dialog:get_items] mode=range segment_filter=%s count=%d",
            segment_ids,
            len(actions),
        )
        return actions

    def center_on_parent(self):
        self.update_idletasks()
        dialog_width = 900
        dialog_height = 520
        parent_x = self.master.winfo_rootx()
        parent_y = self.master.winfo_rooty()
        parent_width = self.master.winfo_width()
        parent_height = self.master.winfo_height()
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.geometry(f"{dialog_width}x{dialog_height}+{max(0, x)}+{max(0, y)}")

