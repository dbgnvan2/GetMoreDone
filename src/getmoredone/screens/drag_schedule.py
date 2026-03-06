"""
Drag Schedule screen - drag items onto date boxes to reschedule.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING

from ..models import ActionItem
from ..app_settings import AppSettings
from ..color_contrast import pick_text_color
from ..date_utils import future_date_targets
from ..theme import semantic_colors
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
from .title_format import split_action_item_title, format_column_text

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class DragScheduleScreen(ctk.CTkFrame):
    """Screen with drag-and-drop scheduling onto date boxes."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app
        self.settings = AppSettings.load()

        self.drag_label = None
        self.drag_item: Optional[ActionItem] = None
        self.drag_hover_frame = None
        self.drag_hover_base_color = None
        self.date_box_colors = {}
        self.date_box_font_size = int(round(14 * 1.3))  # 30% larger
        self.date_box_height = 86
        self.item_row_height = 86
        self._sync_ui_sizing_from_settings()
        self.palette = semantic_colors()

        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}
        self._ape_lineage_cache = {}
        self._week_segment_cache = {}
        self._item_lineage_cache = {}

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
        header.grid_columnconfigure(6, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Drag Schedule",
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
            command=lambda _: self.refresh()
        )
        self.days_combo.grid(row=0, column=2, padx=5, pady=10)

        ctk.CTkLabel(header, text="days").grid(
            row=0, column=3, sticky="w", padx=5, pady=10)

        ctk.CTkLabel(header, text="Who:").grid(
            row=0, column=4, padx=(20, 5), pady=10)

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

        help_text = ctk.CTkLabel(
            header,
            text="Drag a Next Item onto a date box to reschedule",
            text_color="gray70"
        )
        help_text.grid(row=0, column=6, sticky="e", padx=10, pady=10)

    def create_body(self):
        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        # Left: Next Items list
        left_frame = ctk.CTkFrame(body)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="Next Items",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.items_frame = ctk.CTkScrollableFrame(left_frame, label_text="")
        self.items_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.items_frame.grid_columnconfigure(0, weight=1)

        # Right: Date boxes
        right_frame = ctk.CTkFrame(body)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        right_frame.grid_rowconfigure(1, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="Date Boxes",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        self.dates_frame = ctk.CTkScrollableFrame(right_frame, label_text="")
        self.dates_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.dates_frame.grid_columnconfigure(0, weight=1)

    def refresh(self):
        # Re-load settings so size/color changes from Settings screen apply immediately.
        self.settings = AppSettings.load()
        self._sync_ui_sizing_from_settings()
        self.palette = semantic_colors()
        self._reload_lineage_maps()

        for widget in self.items_frame.winfo_children():
            widget.destroy()
        for widget in self.dates_frame.winfo_children():
            widget.destroy()

        self.date_boxes = []
        self.date_box_colors = {}

        items = self.load_items()
        if not items:
            ctk.CTkLabel(
                self.items_frame,
                text="No next items",
                font=ctk.CTkFont(size=14)
            ).grid(row=0, column=0, pady=20)
        else:
            header = ctk.CTkFrame(self.items_frame, fg_color=self.palette["surface_subtle"])
            header.grid(row=0, column=0, sticky="ew", padx=2, pady=(0, 4))
            header.grid_columnconfigure(0, minsize=280)
            header.grid_columnconfigure(1, minsize=120)
            header.grid_columnconfigure(2, minsize=120)
            header.grid_columnconfigure(3, minsize=120)
            header.grid_columnconfigure(4, weight=1)
            ctk.CTkLabel(header, text="Title", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, sticky="w", padx=(10, 4), pady=5
            )
            ctk.CTkLabel(header, text="Segment", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=1, sticky="w", padx=4, pady=5
            )
            ctk.CTkLabel(header, text="SubSegment", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=2, sticky="w", padx=4, pady=5
            )
            ctk.CTkLabel(header, text="Category", anchor="w", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=3, sticky="w", padx=4, pady=5
            )
            ctk.CTkLabel(header, text="Date", anchor="e", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=4, sticky="e", padx=(4, 10), pady=5
            )

            row = 1
            for item in items:
                item_row = self.create_item_row(item)
                item_row.grid(row=row, column=0, sticky="ew", pady=2, padx=2)
                row += 1

        self.build_date_boxes()

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
        return items

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

    def create_item_row(self, item: ActionItem):
        frame = ctk.CTkFrame(self.items_frame, height=self.item_row_height)
        frame.grid_propagate(False)
        frame.grid_columnconfigure(0, minsize=280)
        frame.grid_columnconfigure(1, minsize=120)
        frame.grid_columnconfigure(2, minsize=112)
        frame.grid_columnconfigure(3, minsize=112)
        frame.grid_columnconfigure(4, weight=1)

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
        frame.configure(fg_color=category_color)

        title_text = parsed.title or (item.title or "")
        title_bg = category_color

        title_label = ctk.CTkLabel(
            frame,
            text=f" {format_column_text(title_text, 44)} ",
            anchor="w",
            fg_color=title_bg,
            text_color=pick_text_color(title_bg),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
        )
        title_label.grid(row=0, column=0, sticky="w", padx=(8, 4), pady=2)

        segment_label = ctk.CTkLabel(
            frame,
            text=f" {format_column_text(segment_name, 16)} ",
            anchor="w",
            fg_color=segment_color,
            text_color=pick_text_color(segment_color),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
        )
        segment_label.grid(row=0, column=1, sticky="w", padx=4, pady=2)

        subsegment_label = ctk.CTkLabel(
            frame,
            text=f" {format_column_text(subsegment_name, 15)} ",
            anchor="w",
            fg_color=category_color,
            text_color=pick_text_color(category_color),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
        )
        subsegment_label.grid(row=0, column=2, sticky="w", padx=4, pady=2)

        category_label = ctk.CTkLabel(
            frame,
            text=f" {format_column_text(category_name, 15)} ",
            anchor="w",
            fg_color=category_color,
            text_color=pick_text_color(category_color),
            corner_radius=6,
            font=ctk.CTkFont(size=14),
        )
        category_label.grid(row=0, column=3, sticky="w", padx=4, pady=2)

        date_text = item.start_date or item.due_date or ""
        date_bg = "transparent"
        if date_text:
            try:
                target_date = datetime.strptime(date_text, "%Y-%m-%d").date()
                today = datetime.now().date()
                if target_date < today:
                    date_bg = "#FBCFE8"  # pink
                elif target_date == today:
                    date_bg = "#FEF08A"  # yellow
                else:
                    date_bg = "#BBF7D0"  # light green
            except ValueError:
                date_bg = "transparent"
        date_label = ctk.CTkLabel(
            frame,
            text=date_text,
            text_color="black" if date_bg != "transparent" else "gray40",
            anchor="e",
            fg_color=date_bg,
            corner_radius=6,
            font=ctk.CTkFont(size=14),
        )
        date_label.grid(row=0, column=4, sticky="e", padx=(8, 10), pady=2)

        self.bind_drag_handlers(frame, item)
        self.bind_drag_handlers(title_label, item)
        self.bind_drag_handlers(segment_label, item)
        self.bind_drag_handlers(subsegment_label, item)
        self.bind_drag_handlers(category_label, item)
        self.bind_drag_handlers(date_label, item)
        return frame

    def build_date_boxes(self):
        n_days = int(self.days_var.get())
        today = datetime.now().date()
        who_filter = None if self.who_var.get() == "All" else self.who_var.get()

        # Future date options (bottom)
        options_start_row = n_days + 1

        mid_days = max(1, int(self.settings.mid_term_offset_days))
        long_days = max(1, int(self.settings.long_term_offset_days))
        next_month_offset = int(self.settings.next_month_offset_days)
        next_quarter_offset = int(self.settings.next_quarter_offset_days)

        near_date, long_date_obj, next_month_obj, next_quarter_obj = future_date_targets(
            today, mid_days, long_days, next_month_offset, next_quarter_offset
        )
        mid_date = near_date.strftime("%Y-%m-%d")
        long_date = long_date_obj.strftime("%Y-%m-%d")
        next_month_date = next_month_obj.strftime("%Y-%m-%d")
        next_quarter_date = next_quarter_obj.strftime("%Y-%m-%d")

        day_dates = [
            (today + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(n_days)
        ]

        future_options = [
            ("Near Term", f"+{mid_days} days\n{mid_date}", mid_date, "#FFD54F"),
            ("Long Term", f"+{long_days} days\n{long_date}", long_date, "#FFCDD2"),
            ("1st Next Month", next_month_date, next_month_date, "#FFF9C4"),
            ("1st Next Quarter", next_quarter_date, next_quarter_date, "#FFE0B2"),
        ]
        future_options.sort(key=lambda option: option[2])

        date_stats = self.build_date_stats(day_dates, who_filter)

        for i, date_str in enumerate(day_dates):
            day = datetime.strptime(date_str, "%Y-%m-%d").date()
            count, total_minutes = date_stats.get(date_str, (0, 0))
            label_text = (
                f"{day.strftime('%a')} - "
                f"{day.strftime('%m/%d')} - "
                f"{self.format_day_stats_text(count, total_minutes)}"
            )
            color = self.color_for_day_stats(count, total_minutes)

            frame = ctk.CTkFrame(self.dates_frame, height=self.date_box_height, fg_color=color)
            frame.grid_propagate(False)
            frame.grid(row=i, column=0, sticky="ew", padx=2, pady=2)
            frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(
                frame,
                text=label_text,
                justify="center",
                font=ctk.CTkFont(size=self.date_box_font_size, weight="bold"),
                text_color=self._get_date_text_color()
            )
            label.grid(row=0, column=0, sticky="ew", padx=6, pady=2)

            self.date_boxes.append({"frame": frame, "date": date_str})
            self.date_box_colors[frame] = color

        for idx, (title, subtitle, date_str, color) in enumerate(future_options):
            short_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%m/%d")
            future_text = f"{title} - {short_date}"
            frame = ctk.CTkFrame(self.dates_frame, height=self.date_box_height, fg_color=color)
            frame.grid_propagate(False)
            frame.grid(row=options_start_row + idx, column=0, sticky="ew", padx=2, pady=2)
            frame.grid_columnconfigure(0, weight=1)

            label = ctk.CTkLabel(
                frame,
                text=future_text,
                justify="center",
                font=ctk.CTkFont(size=self.date_box_font_size, weight="bold"),
                text_color=self._get_date_text_color()
            )
            label.grid(row=0, column=0, sticky="ew", padx=6, pady=2)

            self.date_boxes.append({"frame": frame, "date": date_str})
            self.date_box_colors[frame] = color

    def build_date_stats(self, target_dates, who_filter: Optional[str]):
        """Build per-day count and planned-minute totals for visible date boxes."""
        target_set = set(target_dates)
        date_stats = {}

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

            if scheduled_date not in target_set:
                continue

            day_key = scheduled_date
            count, total_minutes = date_stats.get(day_key, (0, 0))
            date_stats[day_key] = (
                count + 1,
                total_minutes + (item.planned_minutes or 0)
            )

        return date_stats

    def format_day_stats_text(self, count: int, total_minutes: int) -> str:
        item_label = "item" if count == 1 else "items"
        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{count} {item_label} - {hours}h {minutes}m"

    def _get_date_text_color(self) -> str:
        color = str(getattr(self.settings, "drag_schedule_date_text_color", "#FFFFFF") or "#FFFFFF").strip()
        if not color.startswith("#"):
            color = f"#{color}"
        if len(color) != 7:
            return "#FFFFFF"
        return color

    def color_for_day_stats(self, count: int, total_minutes: int) -> str:
        """
        Color ramp sequence:
        green (<2h / equivalent load) -> light orange -> darker orange ->
        light pink -> darker pink -> reddish
        based on 12 items or 6 hours (360 min), whichever is higher.
        """
        count_ratio = min(max(count / 12.0, 0.0), 1.0)
        time_ratio = min(max(total_minutes / 360.0, 0.0), 1.0)
        intensity = max(count_ratio, time_ratio)

        # Keep all low-load days green until one-third of max load
        # (equivalent to <2h out of 6h, or <4 items out of 12).
        if intensity < (1.0 / 3.0):
            return "#6BCB77"

        # After green zone, transition from orange -> pink -> red.
        post_green_t = (intensity - (1.0 / 3.0)) / (2.0 / 3.0)
        palette = [
            "#FFD8A8",  # light orange
            "#FFB347",  # darker orange
            "#FF9BC2",  # light pink
            "#FF5A8A",  # darker pink
            "#E5243B",  # reddish
        ]
        return self.interpolate_palette(palette, post_green_t)

    def interpolate_palette(self, colors, t: float) -> str:
        """Interpolate across a palette of 2+ colors."""
        t = min(max(t, 0.0), 1.0)
        if len(colors) < 2:
            return colors[0] if colors else "#DFF8D8"
        if t == 1.0:
            return colors[-1]

        segments = len(colors) - 1
        pos = t * segments
        left_idx = int(pos)
        right_idx = min(left_idx + 1, len(colors) - 1)
        local_t = pos - left_idx
        return self.interpolate_hex_color(colors[left_idx], colors[right_idx], local_t)

    def interpolate_hex_color(self, start_hex: str, end_hex: str, t: float) -> str:
        """Linearly interpolate between two hex colors."""
        t = min(max(t, 0.0), 1.0)

        s = start_hex.lstrip("#")
        e = end_hex.lstrip("#")

        sr, sg, sb = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        er, eg, eb = int(e[0:2], 16), int(e[2:4], 16), int(e[4:6], 16)

        r = round(sr + (er - sr) * t)
        g = round(sg + (eg - sg) * t)
        b = round(sb + (eb - sb) * t)

        return f"#{r:02X}{g:02X}{b:02X}"

    def bind_drag_handlers(self, widget, item: ActionItem):
        widget.bind("<ButtonPress-1>", lambda e: self.start_drag(e, item))
        widget.bind("<B1-Motion>", self.on_drag_motion)
        widget.bind("<ButtonRelease-1>", self.on_drag_release)

    def start_drag(self, event, item: ActionItem):
        self.drag_item = item
        if self.drag_label is None:
            self.drag_label = ctk.CTkLabel(
                self,
                text=item.title,
                fg_color="gray30",
                text_color="white",
                corner_radius=6,
                padx=8,
                pady=4
            )
        else:
            self.drag_label.configure(text=item.title)

        self.drag_label.lift()
        self.update_drag_position()

    def on_drag_motion(self, _event):
        if not self.drag_item or not self.drag_label:
            return
        self.update_drag_position()
        self.update_hover_target()

    def on_drag_release(self, _event):
        if not self.drag_item:
            return

        target_date = self.get_drop_target_date()
        self.clear_hover_target()

        if target_date:
            self.db_manager.reschedule_item(
                self.drag_item.id,
                target_date,
                target_date,
                "Drag-and-drop schedule"
            )
            self.refresh()

        if self.drag_label:
            self.drag_label.place_forget()
        self.drag_item = None

    def update_drag_position(self):
        if not self.drag_label:
            return
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()
        x = x_root - self.winfo_rootx() + 10
        y = y_root - self.winfo_rooty() + 10
        self.drag_label.place(x=x, y=y)

    def get_drop_target_date(self) -> Optional[str]:
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()

        for box in self.date_boxes:
            frame = box["frame"]
            if not frame.winfo_ismapped():
                continue
            x1 = frame.winfo_rootx()
            y1 = frame.winfo_rooty()
            x2 = x1 + frame.winfo_width()
            y2 = y1 + frame.winfo_height()
            if x1 <= x_root <= x2 and y1 <= y_root <= y2:
                return box["date"]
        return None

    def update_hover_target(self):
        x_root = self.winfo_pointerx()
        y_root = self.winfo_pointery()
        hovered = None

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

        if hovered is self.drag_hover_frame:
            return

        self.clear_hover_target()
        if hovered:
            hovered.configure(fg_color="gray35")
            self.drag_hover_frame = hovered
            self.drag_hover_base_color = self.date_box_colors.get(hovered, "gray20")

    def clear_hover_target(self):
        if self.drag_hover_frame:
            self.drag_hover_frame.configure(fg_color=self.drag_hover_base_color or "gray20")
            self.drag_hover_frame = None
            self.drag_hover_base_color = None
