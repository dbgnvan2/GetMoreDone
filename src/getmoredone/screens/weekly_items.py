"""APE Weekly screen: weekly action items on the left and related actions on the right."""

import customtkinter as ctk
from datetime import date, timedelta
from tkinter import messagebox
import tkinter as tk
from typing import TYPE_CHECKING, List, Dict, Any, Optional
import re

from ..theme import button_style, semantic_colors
from ..color_contrast import pick_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors
from .title_format import split_action_item_title, build_action_item_title

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class WeeklyItemsScreen(ctk.CTkFrame):
    """Show APE weekly action items for a selected week and related actions."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.week_options: List[str] = []
        self.week_var = ctk.StringVar(value="")

        self.weekly_items: List[Dict[str, Any]] = []
        self.all_weekly_items: List[Dict[str, Any]] = []
        self.selected_weekly_item: Optional[Dict[str, Any]] = None

        self.related_actions: List[Dict[str, Any]] = []
        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}
        self.segment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.category_filter_var = ctk.StringVar(value="All")
        self.selected_weekly_idx: Optional[int] = None
        self.selected_action_idx: Optional[int] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_ui()
        self.refresh()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(12, weight=1)

        ctk.CTkLabel(
            header,
            text="APE Weekly",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, columnspan=13, padx=(10, 20), pady=(8, 6), sticky="w")

        ctk.CTkLabel(header, text="Week Start:").grid(row=1, column=0, padx=(8, 5), pady=(0, 10), sticky="e")

        self.week_combo = ctk.CTkComboBox(header, width=136, values=[""], variable=self.week_var)
        self.week_combo.grid(row=1, column=1, padx=5, pady=(0, 10), sticky="w")

        ctk.CTkButton(header, text="Load", width=76, command=self.load_selected_week, **button_style("secondary")).grid(
            row=1, column=2, padx=5, pady=(0, 10), sticky="w"
        )

        ctk.CTkButton(header, text="This Week", width=76, command=self.jump_to_current_week, **button_style("secondary")).grid(
            row=1, column=3, padx=5, pady=(0, 10), sticky="w"
        )
        ctk.CTkLabel(header, text="Segment:").grid(row=1, column=4, padx=(10, 4), pady=(0, 10), sticky="e")
        self.segment_filter_combo = ctk.CTkComboBox(
            header, width=150, values=["All"], variable=self.segment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.segment_filter_combo.grid(row=1, column=5, padx=4, pady=(0, 10), sticky="w")
        ctk.CTkLabel(header, text="Sub:").grid(row=1, column=6, padx=(8, 4), pady=(0, 10), sticky="e")
        self.subsegment_filter_combo = ctk.CTkComboBox(
            header, width=150, values=["All"], variable=self.subsegment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.subsegment_filter_combo.grid(row=1, column=7, padx=4, pady=(0, 10), sticky="w")
        ctk.CTkLabel(header, text="Cat:").grid(row=1, column=8, padx=(8, 4), pady=(0, 10), sticky="e")
        self.category_filter_combo = ctk.CTkComboBox(
            header, width=150, values=["All"], variable=self.category_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.category_filter_combo.grid(row=1, column=9, padx=4, pady=(0, 10), sticky="w")

        self.status_label = ctk.CTkLabel(header, text="", text_color="gray")
        self.status_label.grid(row=1, column=10, columnspan=3, sticky="w", padx=10, pady=(0, 10))

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        palette = semantic_colors()

        labels = ctk.CTkFrame(body, fg_color="transparent")
        labels.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        labels.grid_columnconfigure(0, weight=1)
        labels.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(labels, text="Weekly Tactics", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(labels, text="Related Action Items", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=(8, 0)
        )

        self.splitter = tk.PanedWindow(
            body,
            orient=tk.HORIZONTAL,
            sashwidth=8,
            sashrelief=tk.RAISED,
            bd=0,
            bg=palette["surface_subtle"],
        )
        self.splitter.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))

        left = ctk.CTkFrame(self.splitter)
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        right = ctk.CTkFrame(self.splitter)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.splitter.add(left, minsize=320)
        self.splitter.add(right, minsize=320)

        self.weekly_list = ctk.CTkScrollableFrame(left, label_text="")
        self.weekly_list.grid(row=0, column=0, sticky="nsew")
        self.weekly_list.grid_columnconfigure(0, weight=1)

        self.actions_list = ctk.CTkScrollableFrame(right, label_text="")
        self.actions_list.grid(row=0, column=0, sticky="nsew")
        self.actions_list.grid_columnconfigure(0, weight=1)

        left_actions = ctk.CTkFrame(left)
        left_actions.grid(row=1, column=0, sticky="w", padx=4, pady=(4, 4))

        ctk.CTkButton(
            left_actions,
            text="Edit Week Tactic",
            command=self.open_selected_weekly_item,
            width=140,
            **button_style("secondary"),
        ).pack(side="left", padx=6, pady=6)

        ctk.CTkButton(
            left_actions,
            text="Delete Weekly",
            command=self.delete_selected_weekly_item,
            width=130,
            **button_style("danger"),
        ).pack(side="left", padx=6, pady=6)

        right_actions = ctk.CTkFrame(right)
        right_actions.grid(row=1, column=0, sticky="w", padx=4, pady=(4, 4))

        ctk.CTkButton(
            right_actions,
            text="Add Action Item",
            command=self.create_action_item_for_selected_weekly,
            width=130,
            **button_style("primary"),
        ).pack(side="left", padx=6, pady=6)

        ctk.CTkButton(
            right_actions,
            text="Open Action",
            command=self.open_selected_action_item,
            width=120,
            **button_style("secondary"),
        ).pack(side="left", padx=6, pady=6)

        self.after(100, self._init_splitter_position)

    def _init_splitter_position(self):
        if not hasattr(self, "splitter"):
            return
        width = self.splitter.winfo_width()
        if width <= 0:
            self.after(100, self._init_splitter_position)
            return
        self.splitter.sash_place(0, int(width * 0.58), 0)

    def refresh(self):
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (r.get("segment_name", "") or "").strip().lower(),
                (r.get("subsegment_name", "") or "").strip().lower(),
                (r.get("name", "") or "").strip().lower(),
            ): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_categories()
        }
        weekly_items = self.vps_manager.get_weekly_action_items(ape_only=True)
        unique_starts = sorted({wi["start_date"] for wi in weekly_items if wi.get("start_date")})
        unique_starts.reverse()
        self.week_options = unique_starts

        if not self.week_options:
            self.week_combo.configure(values=[""])
            self.week_var.set("")
            self._clear_scroll(self.weekly_list)
            self._clear_scroll(self.actions_list)
            self.status_label.configure(text="No weekly action items found.")
            return

        self.week_combo.configure(values=self.week_options)
        if self.week_var.get() not in self.week_options:
            self.week_var.set(self.week_options[0])

        self.load_selected_week()

    def jump_to_current_week(self):
        today = date.today()
        current_week_start = (today - timedelta(days=today.weekday())).isoformat()

        if current_week_start in self.week_options:
            self.week_var.set(current_week_start)
            self.load_selected_week()
        else:
            messagebox.showinfo("Week Not Found", "No weekly items exist for the current week.")

    def load_selected_week(self):
        week_start = self.week_var.get().strip()
        if not week_start:
            return

        self.all_weekly_items = self.vps_manager.get_weekly_action_items(
            week_start_date=week_start,
            ape_only=True,
        )
        self._refresh_filter_options()
        self.weekly_items = self._filtered_weekly_items()

        self._clear_scroll(self.weekly_list)
        self._clear_scroll(self.actions_list)
        self.related_actions = []
        self.selected_weekly_item = None
        self.selected_weekly_idx = None
        self.selected_action_idx = None

        self._render_weekly_rows(week_start)

        self.status_label.configure(
            text=f"{len(self.weekly_items)} weekly item(s) for {week_start}"
        )

    def _filtered_weekly_items(self) -> List[Dict[str, Any]]:
        seg = self.segment_filter_var.get().strip()
        sub = self.subsegment_filter_var.get().strip()
        cat = self.category_filter_var.get().strip()
        rows = self.all_weekly_items
        if seg and seg != "All":
            rows = [r for r in rows if self._weekly_parts(r)[0] == seg]
        if sub and sub != "All":
            rows = [r for r in rows if self._weekly_parts(r)[1] == sub]
        if cat and cat != "All":
            rows = [r for r in rows if self._weekly_parts(r)[2] == cat]
        return rows

    def _refresh_filter_options(self):
        rows = self.all_weekly_items
        parts = [self._weekly_parts(r) for r in rows]
        seg_values = sorted({p[0] for p in parts if p[0] and p[0] != "-"}, key=str.lower)
        seg_combo_values = ["All"] + seg_values
        current_seg = self.segment_filter_var.get().strip() or "All"
        if current_seg not in seg_combo_values:
            current_seg = "All"
            self.segment_filter_var.set(current_seg)
        self.segment_filter_combo.configure(values=seg_combo_values)

        sub_source = [p for p in parts if current_seg == "All" or p[0] == current_seg]
        sub_values = sorted({p[1] for p in sub_source if p[1] and p[1] != "-"}, key=str.lower)
        sub_combo_values = ["All"] + sub_values
        current_sub = self.subsegment_filter_var.get().strip() or "All"
        if current_sub not in sub_combo_values:
            current_sub = "All"
            self.subsegment_filter_var.set(current_sub)
        self.subsegment_filter_combo.configure(values=sub_combo_values)

        cat_source = [p for p in sub_source if current_sub == "All" or p[1] == current_sub]
        cat_values = sorted({p[2] for p in cat_source if p[2] and p[2] != "-"}, key=str.lower)
        cat_combo_values = ["All"] + cat_values
        current_cat = self.category_filter_var.get().strip() or "All"
        if current_cat not in cat_combo_values:
            current_cat = "All"
            self.category_filter_var.set(current_cat)
        self.category_filter_combo.configure(values=cat_combo_values)

    def on_filters_changed(self):
        self._refresh_filter_options()
        self.weekly_items = self._filtered_weekly_items()
        self.selected_weekly_item = None
        self.selected_weekly_idx = None
        self.selected_action_idx = None
        self.related_actions = []
        self._render_weekly_rows(self.week_var.get().strip())
        self._clear_scroll(self.actions_list)
        week_start = self.week_var.get().strip()
        if week_start:
            self.status_label.configure(text=f"{len(self.weekly_items)} weekly item(s) for {week_start}")

    def on_select_weekly_item(self, idx: int):
        if idx < 0 or idx >= len(self.weekly_items):
            return

        self.selected_weekly_idx = idx
        self.selected_weekly_item = self.weekly_items[idx]
        self._render_weekly_rows(self.week_var.get().strip())
        self.related_actions = self.vps_manager.get_related_actions_for_weekly_item(self.selected_weekly_item["id"])
        self.selected_action_idx = None

        self._render_action_rows()

        self.status_label.configure(
            text=f"{len(self.related_actions)} related action item(s) for selected weekly item"
        )

    def create_action_item_for_selected_weekly(self):
        if not self.selected_weekly_item:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly item on the left first.")
            return
        from ..models import ActionItem

        dialog = ctk.CTkInputDialog(text="Immediate Step:", title="New Related Action")
        title = (dialog.get_input() or "").strip()
        if not title:
            return

        weekly = self.selected_weekly_item
        weekly_title = self.vps_manager.normalize_week_token((weekly.get("title") or "").strip())
        weekly_title_short = self._shorten_pipe_prefix(weekly_title)
        parsed = split_action_item_title(weekly_title_short)
        context = parsed.context
        if not context:
            match = re.match(r"^\s*(.+?\bW\s*\d+\b)", weekly_title_short, flags=re.IGNORECASE)
            if match:
                context = (match.group(1) or "").strip()
        context = re.sub(r"\s*[-–—]?\s*\(\d{4}-\d{2}-\d{2}\)\s*$", "", context or "").strip()
        full_title = build_action_item_title(context, title)
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
        self.on_action_editor_closed()

    def _shorten_pipe_prefix(self, text: str) -> str:
        return self.vps_manager.shorten_pipe_prefix(text)

    def open_selected_weekly_item(self):
        """Open the selected weekly action item in the editor."""
        if not self.selected_weekly_item:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly item on the left first.")
            return

        from .item_editor import ItemEditorDialog

        ItemEditorDialog(
            self,
            self.app.db_manager,
            item_id=self.selected_weekly_item["id"],
            vps_manager=self.vps_manager,
            on_close_callback=self.on_action_editor_closed,
        )

    def delete_selected_weekly_item(self):
        if not self.selected_weekly_item:
            messagebox.showwarning("No Weekly Item Selected", "Select a weekly item on the left first.")
            return
        title = (self.selected_weekly_item.get("title") or "this weekly item").strip()
        if not messagebox.askyesno(
            "Delete Weekly Item",
            f"Delete {title} and related action items?",
            icon="warning",
        ):
            return
        weekly_id = self.selected_weekly_item["id"]
        if self.vps_manager.delete_weekly_action_item(weekly_id):
            self.refresh()
        else:
            messagebox.showerror("Delete Failed", "Weekly item could not be deleted.")

    def on_action_editor_closed(self):
        if self.selected_weekly_item:
            self.related_actions = self.vps_manager.get_related_actions_for_weekly_item(self.selected_weekly_item["id"])
            self.selected_action_idx = None
            self._render_action_rows()

    def open_selected_action_item(self, _event=None):
        if not self.related_actions:
            return
        if self.selected_action_idx is None:
            return
        idx = self.selected_action_idx
        if idx < 0 or idx >= len(self.related_actions):
            return

        action_id = self.related_actions[idx]["id"]

        from .item_editor import ItemEditorDialog

        ItemEditorDialog(
            self,
            self.app.db_manager,
            item_id=action_id,
            vps_manager=self.vps_manager,
            on_close_callback=self.on_action_editor_closed,
        )

    def _render_weekly_rows(self, week_start: str):
        self._clear_scroll(self.weekly_list)
        palette = semantic_colors()
        col_widths = {
            "index": 34,
            "segment": 135,
            "subsegment": 155,
            "category": 125,
        }

        header = ctk.CTkFrame(self.weekly_list, fg_color=palette["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))
        header.grid_columnconfigure(0, minsize=col_widths["index"])
        header.grid_columnconfigure(1, minsize=col_widths["segment"])
        header.grid_columnconfigure(2, minsize=col_widths["subsegment"])
        header.grid_columnconfigure(3, minsize=col_widths["category"])
        header.grid_columnconfigure(4, weight=1)
        ctk.CTkLabel(header, text="#", width=col_widths["index"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=0, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="Segment", width=col_widths["segment"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=1, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="SubSegment", width=col_widths["subsegment"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="Category", width=col_widths["category"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=3, padx=5, pady=5, sticky="w"
        )

        for idx, wi in enumerate(self.weekly_items):
            segment_name, subsegment_name, category_name = self._weekly_parts(wi)
            color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_name,
                self.vps_manager,
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
            bg = palette["selected_tint"] if idx == self.selected_weekly_idx else palette["surface_subtle"]

            row = ctk.CTkFrame(
                self.weekly_list,
                fg_color=bg,
                border_width=2,
                border_color=color,
            )
            row.grid(row=idx + 1, column=0, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(0, minsize=col_widths["index"])
            row.grid_columnconfigure(1, minsize=col_widths["segment"])
            row.grid_columnconfigure(2, minsize=col_widths["subsegment"])
            row.grid_columnconfigure(3, minsize=col_widths["category"])
            row.grid_columnconfigure(4, weight=1)

            idx_label = ctk.CTkLabel(
                row,
                text=str(idx + 1),
                width=col_widths["index"],
                anchor="w",
                text_color="black",
            )
            idx_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")
            seg_chip = ctk.CTkLabel(
                row,
                text=f" {self._clip_label(segment_name, 15)} ",
                fg_color=color,
                text_color=pick_text_color(color),
                corner_radius=6,
                width=col_widths["segment"] - 12,
                anchor="w",
            )
            seg_chip.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            sub_chip = ctk.CTkLabel(
                row,
                text=f" {self._clip_label(subsegment_name, 15)} ",
                fg_color=subsegment_color,
                text_color=pick_text_color(subsegment_color),
                corner_radius=6,
                width=col_widths["subsegment"] - 12,
                anchor="w",
            )
            sub_chip.grid(row=0, column=2, padx=5, pady=5, sticky="w")
            cat_chip = ctk.CTkLabel(
                row,
                text=f" {self._clip_label(category_name, 15)} ",
                fg_color=category_color,
                text_color=pick_text_color(category_color),
                corner_radius=6,
                anchor="w",
                width=col_widths["category"] - 12,
            )
            cat_chip.grid(row=0, column=3, padx=5, pady=5, sticky="w")
            for widget in (row, idx_label, seg_chip, sub_chip, cat_chip):
                widget.bind("<Button-1>", lambda _e, i=idx: self.on_select_weekly_item(i))

    def _render_action_rows(self):
        self._clear_scroll(self.actions_list)
        palette = semantic_colors()
        segment_name = ""
        if self.selected_weekly_item:
            segment_name = self.selected_weekly_item.get("ape_segment_name") or self.selected_weekly_item.get("who") or ""
        color = self.vps_manager.resolve_segment_color(segment_name, self.segment_colors)
        for idx, action in enumerate(self.related_actions):
            title = (action.get("title") or "(untitled)").strip()
            start = action.get("start_date") or ""
            status = action.get("status") or "open"
            bg = palette["selected_tint"] if idx == self.selected_action_idx else None

            row = ctk.CTkFrame(
                self.actions_list,
                fg_color=bg,
                border_width=2,
                border_color=color,
            )
            row.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=str(idx + 1), width=30, text_color="black").grid(
                row=0, column=0, padx=5, pady=5
            )
            lbl = ctk.CTkLabel(row, text=f"{title}  [{start}] ({status})", anchor="w", text_color="black")
            lbl.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            for widget in (row, lbl):
                widget.bind("<Button-1>", lambda _e, i=idx: self._select_action(i))
                widget.bind("<Double-Button-1>", lambda _e, i=idx: self._open_action_from_index(i))

    def _select_action(self, idx: int):
        self.selected_action_idx = idx
        self._render_action_rows()

    def _open_action_from_index(self, idx: int):
        self.selected_action_idx = idx
        self.open_selected_action_item()

    def _clear_scroll(self, frame: ctk.CTkScrollableFrame):
        for child in frame.winfo_children():
            child.destroy()

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"

    def _weekly_parts(self, row: Dict[str, Any]) -> tuple[str, str, str]:
        seg = (row.get("ape_segment_name") or row.get("who") or "").strip()
        sub = (row.get("ape_subsegment_name") or "").strip()
        cat = (row.get("ape_category_name") or "").strip()
        if seg and sub and cat:
            return seg, sub, cat

        title = (row.get("title") or "").strip()
        parts = [p.strip() for p in title.split("|") if p.strip()]
        if len(parts) >= 3:
            seg = seg or parts[0]
            sub = sub or parts[1]
            cat = cat or parts[2].split(" - ")[0].strip()
        return seg or "-", sub or "-", cat or "-"
