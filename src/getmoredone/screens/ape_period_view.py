"""View APEs assigned to a selected quarter and month, then create weekly Action Items."""

import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
import tkinter as tk
from typing import TYPE_CHECKING, Optional

from ..app_settings import AppSettings
from ..theme import button_style, semantic_colors
from ..color_contrast import pick_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class APEPeriodViewScreen(ctk.CTkFrame):
    """Filter Annual Plan Elements by Year + Quarter + Month and create weekly Action Items."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.year_var = ctk.StringVar(value=str(datetime.now().year))
        self.q_var = ctk.StringVar(value="1")
        self.m_var = ctk.StringVar(value=str(datetime.now().month))

        self.ape_rows = []
        self.all_ape_rows = []
        self.selected_ape_id: Optional[str] = None
        self.week_vars = {}
        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}
        self.segment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.category_filter_var = ctk.StringVar(value="All")
        self.selected_idx: Optional[int] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_ui()
        self.refresh()

    def create_ui(self):
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        top.grid_columnconfigure(10, weight=1)

        ctk.CTkLabel(top, text="APE by Quarter/Month", font=ctk.CTkFont(size=20, weight="bold")).grid(
            row=0, column=0, columnspan=11, padx=8, pady=(8, 6), sticky="w"
        )
        ctk.CTkLabel(top, text="Year").grid(row=1, column=0, padx=(8, 4), pady=(0, 8), sticky="e")
        ctk.CTkEntry(top, width=86, textvariable=self.year_var).grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkLabel(top, text="Quarter").grid(row=1, column=2, padx=(8, 4), pady=(0, 8), sticky="e")
        ctk.CTkComboBox(top, width=74, values=["1", "2", "3", "4"], variable=self.q_var).grid(
            row=1, column=3, padx=4, pady=(0, 8), sticky="w"
        )
        ctk.CTkLabel(top, text="Month").grid(row=1, column=4, padx=(8, 4), pady=(0, 8), sticky="e")
        ctk.CTkComboBox(top, width=74, values=[str(i) for i in range(1, 13)], variable=self.m_var).grid(
            row=1, column=5, padx=4, pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(top, text="Load", width=88, command=self.refresh, **button_style("secondary")).grid(
            row=1, column=6, padx=(8, 12), pady=(0, 8), sticky="w"
        )
        ctk.CTkLabel(top, text="Segment").grid(row=1, column=7, padx=(0, 4), pady=(0, 8), sticky="e")
        self.segment_filter_combo = ctk.CTkComboBox(
            top, width=156, values=["All"], variable=self.segment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.segment_filter_combo.grid(row=1, column=8, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkLabel(top, text="SubSegment").grid(row=1, column=9, padx=(10, 4), pady=(0, 8), sticky="e")
        self.subsegment_filter_combo = ctk.CTkComboBox(
            top, width=156, values=["All"], variable=self.subsegment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.subsegment_filter_combo.grid(row=1, column=10, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkLabel(top, text="Category").grid(row=1, column=11, padx=(10, 4), pady=(0, 8), sticky="e")
        self.category_filter_combo = ctk.CTkComboBox(
            top, width=156, values=["All"], variable=self.category_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.category_filter_combo.grid(row=1, column=12, padx=4, pady=(0, 8), sticky="w")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        palette = semantic_colors()

        labels = ctk.CTkFrame(body, fg_color="transparent")
        labels.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        labels.grid_columnconfigure(0, weight=1)
        labels.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(labels, text="APEs In Period", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(labels, text="Select Weeks", font=ctk.CTkFont(weight="bold")).grid(
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
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.splitter.add(left, minsize=320)
        self.splitter.add(right, minsize=300)

        self.ape_list = ctk.CTkScrollableFrame(left)
        self.ape_list.grid(row=0, column=0, sticky="nsew")
        self.ape_list.grid_columnconfigure(0, weight=1)

        self.week_info_label = ctk.CTkLabel(right, text="")
        self.week_info_label.grid(row=0, column=0, sticky="w", padx=8, pady=4)

        self.week_scroll = ctk.CTkScrollableFrame(right)
        self.week_scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=8)
        self.week_scroll.grid_columnconfigure(0, weight=1)

        actions = ctk.CTkFrame(right)
        actions.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        actions.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            actions,
            text="Create Week Action Items",
            command=self.create_week_items_for_selected_ape,
            **button_style("primary"),
            width=220,
        ).grid(row=0, column=0, sticky="w")

        self.status_label = ctk.CTkLabel(actions, text="", text_color="gray")
        self.status_label.grid(row=0, column=1, sticky="w", padx=10)

        self.after(100, self._init_splitter_position)

    def _init_splitter_position(self):
        if not hasattr(self, "splitter"):
            return
        width = self.splitter.winfo_width()
        if width <= 0:
            self.after(100, self._init_splitter_position)
            return
        self.splitter.sash_place(0, int(width * 0.62), 0)

    def _parse_period(self):
        try:
            year = int(self.year_var.get().strip())
            quarter = int(self.q_var.get().strip())
            month = int(self.m_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Period", "Enter valid numeric Year, Quarter, and Month values.")
            return None

        if quarter not in (1, 2, 3, 4) or month < 1 or month > 12:
            messagebox.showerror("Invalid Period", "Quarter must be 1-4 and Month must be 1-12.")
            return None

        return year, quarter, month

    def refresh(self):
        parsed = self._parse_period()
        if not parsed:
            return
        year, quarter, month = parsed

        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (r.get("segment_name", "") or "").strip().lower(),
                (r.get("subsegment_name", "") or "").strip().lower(),
                (r.get("name", "") or "").strip().lower(),
            ): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_categories()
        }
        self.all_ape_rows = self.vps_manager.get_annual_plan_elements_for_period(year, quarter, month)
        self._refresh_filter_options()
        self.ape_rows = self._filtered_rows()
        self.selected_idx = None
        self._render_ape_rows()

        self.selected_ape_id = None
        self.render_week_options()
        self.status_label.configure(text=f"Loaded {len(self.ape_rows)} APE record(s).", text_color="gray")

    def _filtered_rows(self):
        seg = self.segment_filter_var.get().strip()
        sub = self.subsegment_filter_var.get().strip()
        cat = self.category_filter_var.get().strip()
        rows = self.all_ape_rows
        if seg and seg != "All":
            rows = [r for r in rows if (r.get("segment_name") or "").strip() == seg]
        if sub and sub != "All":
            rows = [r for r in rows if (r.get("subsegment_name") or "").strip() == sub]
        if cat and cat != "All":
            rows = [r for r in rows if (r.get("category_name") or "").strip() == cat]
        return rows

    def _refresh_filter_options(self):
        rows = self.all_ape_rows
        seg_values = sorted({(r.get("segment_name") or "").strip() for r in rows if (r.get("segment_name") or "").strip()}, key=str.lower)
        seg_combo_values = ["All"] + seg_values
        current_seg = self.segment_filter_var.get().strip() or "All"
        if current_seg not in seg_combo_values:
            current_seg = "All"
            self.segment_filter_var.set(current_seg)
        self.segment_filter_combo.configure(values=seg_combo_values)

        sub_rows = rows if current_seg == "All" else [r for r in rows if (r.get("segment_name") or "").strip() == current_seg]
        sub_values = sorted({(r.get("subsegment_name") or "").strip() for r in sub_rows if (r.get("subsegment_name") or "").strip()}, key=str.lower)
        sub_combo_values = ["All"] + sub_values
        current_sub = self.subsegment_filter_var.get().strip() or "All"
        if current_sub not in sub_combo_values:
            current_sub = "All"
            self.subsegment_filter_var.set(current_sub)
        self.subsegment_filter_combo.configure(values=sub_combo_values)

        cat_rows = sub_rows if current_sub == "All" else [r for r in sub_rows if (r.get("subsegment_name") or "").strip() == current_sub]
        cat_values = sorted({(r.get("category_name") or "").strip() for r in cat_rows if (r.get("category_name") or "").strip()}, key=str.lower)
        cat_combo_values = ["All"] + cat_values
        current_cat = self.category_filter_var.get().strip() or "All"
        if current_cat not in cat_combo_values:
            current_cat = "All"
            self.category_filter_var.set(current_cat)
        self.category_filter_combo.configure(values=cat_combo_values)

    def on_filters_changed(self):
        self._refresh_filter_options()
        self.ape_rows = self._filtered_rows()
        self.selected_ape_id = None
        self.selected_idx = None
        self._render_ape_rows()
        self.status_label.configure(text=f"Loaded {len(self.ape_rows)} APE record(s).", text_color="gray")

    def render_week_options(self):
        for child in self.week_scroll.winfo_children():
            child.destroy()

        self.week_vars = {}

        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, month = parsed

        settings = AppSettings.load()
        first_day = int(getattr(settings, "first_day_of_week", 0))
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        if first_day < 0 or first_day > 6:
            first_day = 0

        self.week_info_label.configure(text=f"Week starts use: {day_names[first_day]}")
        week_options = self.vps_manager.get_month_week_starts(year, month, first_day)

        if not week_options:
            ctk.CTkLabel(self.week_scroll, text="No week options available for this month.").grid(
                row=0, column=0, sticky="w", padx=6, pady=4
            )
            return

        for idx, wk in enumerate(week_options):
            var = ctk.BooleanVar(value=False)
            self.week_vars[wk["week_start_date"]] = var
            text = f"[{wk['week_start_date']}] {wk['label']}"
            ctk.CTkCheckBox(self.week_scroll, text=text, variable=var).grid(
                row=idx, column=0, sticky="w", padx=6, pady=4
            )

    def _find_selected_ape(self) -> Optional[dict]:
        if not self.selected_ape_id:
            return None
        for row in self.ape_rows:
            if row["id"] == self.selected_ape_id:
                return row
        return None

    def _render_ape_rows(self):
        for w in self.ape_list.winfo_children():
            w.destroy()
        palette = semantic_colors()
        col_widths = {
            "index": 34,
            "segment": 135,
            "subsegment": 155,
            "category": 125,
            "actions": 150,
        }

        header = ctk.CTkFrame(self.ape_list, fg_color=palette["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))
        header.grid_columnconfigure(0, minsize=col_widths["index"])
        header.grid_columnconfigure(1, minsize=col_widths["segment"])
        header.grid_columnconfigure(2, minsize=col_widths["subsegment"])
        header.grid_columnconfigure(3, minsize=col_widths["category"])
        header.grid_columnconfigure(4, weight=1)
        header.grid_columnconfigure(5, minsize=col_widths["actions"])
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
        ctk.CTkLabel(header, text="Actions", width=col_widths["actions"], font=ctk.CTkFont(weight="bold"), anchor="e").grid(
            row=0, column=5, padx=5, pady=5, sticky="e"
        )

        for idx, row in enumerate(self.ape_rows):
            segment_name = row.get("segment_name", "")
            subsegment_raw = row.get("subsegment_name") or "-"
            category_raw = row.get("category_name") or "-"
            color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_raw,
                self.vps_manager,
                self.segment_colors,
                self.subsegment_colors,
            )
            category_color = self.category_colors.get(
                (
                    segment_name.strip().lower(),
                    subsegment_raw.strip().lower(),
                    category_raw.strip().lower(),
                ),
                "",
            ) or subsegment_color
            bg = palette["selected_tint"] if idx == self.selected_idx else None
            item = ctk.CTkFrame(
                self.ape_list,
                fg_color=bg,
                border_width=2,
                border_color=color,
            )
            item.grid(row=idx + 1, column=0, sticky="ew", padx=4, pady=2)
            item.grid_columnconfigure(0, minsize=col_widths["index"])
            item.grid_columnconfigure(1, minsize=col_widths["segment"])
            item.grid_columnconfigure(2, minsize=col_widths["subsegment"])
            item.grid_columnconfigure(3, minsize=col_widths["category"])
            item.grid_columnconfigure(4, weight=1)
            item.grid_columnconfigure(5, minsize=col_widths["actions"])

            idx_label = ctk.CTkLabel(item, text=str(idx + 1), width=col_widths["index"], anchor="w")
            idx_label.grid(row=0, column=0, padx=5, pady=5, sticky="w")

            seg_chip = ctk.CTkLabel(
                item,
                text=f" {self._clip_label(segment_name, 15)} ",
                fg_color=color,
                text_color=pick_text_color(color),
                corner_radius=6,
                width=col_widths["segment"] - 12,
                anchor="w",
            )
            seg_chip.grid(row=0, column=1, padx=5, pady=5, sticky="w")

            sub_chip = ctk.CTkLabel(
                item,
                text=f" {self._clip_label(subsegment_raw, 15)} ",
                fg_color=subsegment_color,
                text_color=pick_text_color(subsegment_color),
                corner_radius=6,
                width=col_widths["subsegment"] - 12,
                anchor="w",
            )
            sub_chip.grid(row=0, column=2, padx=5, pady=5, sticky="w")

            cat_chip = ctk.CTkLabel(
                item,
                text=f" {self._clip_label(category_raw, 15)} ",
                fg_color=category_color,
                text_color=pick_text_color(category_color),
                corner_radius=6,
                anchor="w",
                width=col_widths["category"] - 12,
            )
            cat_chip.grid(row=0, column=3, padx=5, pady=5, sticky="w")

            actions = ctk.CTkFrame(item, fg_color="transparent")
            actions.grid(row=0, column=5, padx=5, pady=5, sticky="e")
            ctk.CTkButton(
                actions,
                text="Edit",
                width=64,
                command=lambda r=row: self.edit_ape_row(r),
                **button_style("secondary"),
            ).pack(side="left", padx=(0, 2))
            ctk.CTkButton(
                actions,
                text="Delete",
                width=64,
                command=lambda r=row: self.delete_ape_row(r),
                **button_style("danger"),
            ).pack(side="left", padx=(2, 0))
            for widget in (item, idx_label, seg_chip, sub_chip, cat_chip):
                widget.bind("<Button-1>", lambda _e, i=idx: self.on_select_ape(i))

    def on_select_ape(self, index: int):
        if index < 0 or index >= len(self.ape_rows):
            return
        row = self.ape_rows[index]
        self.selected_ape_id = row["id"]
        self.selected_idx = index
        self._render_ape_rows()

        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, month = parsed

        existing = set(self.vps_manager.get_existing_week_item_starts_for_ape(row["id"], year, month))
        for week_start, var in self.week_vars.items():
            var.set(week_start in existing)

        self.status_label.configure(
            text=f"Selected: {row.get('segment_name', '')} | {row.get('subsegment_name', '')} | {row.get('category_name', '')}",
            text_color="gray",
        )

    def create_week_items_for_selected_ape(self):
        row = self._find_selected_ape()
        if not row:
            messagebox.showwarning("No APE Selected", "Select an Annual Plan Element first.")
            return

        selected_weeks = [ws for ws, var in self.week_vars.items() if bool(var.get())]
        if not selected_weeks:
            messagebox.showwarning("No Weeks Selected", "Check at least one week.")
            return

        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, month = parsed

        result = self.vps_manager.create_week_action_items_for_ape(
            row["id"], year, month, selected_weeks
        )

        self.status_label.configure(
            text=f"Created {result['created_count']} week item(s); skipped {result['skipped_count']} existing.",
            text_color="green",
        )
        messagebox.showinfo(
            "Week Action Items Created",
            f"Created {result['created_count']} week item(s).\nSkipped {result['skipped_count']} existing week(s).",
        )

    def _apply_row_color(self, index: int, segment_name: str):
        return

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"

    def edit_ape_row(self, row: dict):
        vision_element_id = row.get("vision_element_id")
        if not vision_element_id:
            messagebox.showerror("Missing Source", "This APE record is missing its source Vision Element.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit APE Record")
        dialog.geometry("620x220")
        dialog.transient(self)
        dialog.grab_set()

        segment_var = ctk.StringVar(value=row.get("segment_name") or "")
        subsegment_var = ctk.StringVar(value=row.get("subsegment_name") or "")
        category_var = ctk.StringVar(value=row.get("category_name") or "")

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Segment:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        segment_combo = ctk.CTkComboBox(frame, variable=segment_var, values=[])
        segment_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="SubSegment:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        subsegment_combo = ctk.CTkComboBox(frame, variable=subsegment_var, values=[])
        subsegment_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Category:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        category_combo = ctk.CTkComboBox(frame, variable=category_var, values=[])
        category_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=6)

        status_label = ctk.CTkLabel(frame, text="", text_color="red")
        status_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 6))

        def load_segments():
            values = [r["name"] for r in self.vps_manager.get_vision_segments()]
            segment_combo.configure(values=values or [""])

        def load_subsegments():
            seg = segment_var.get().strip() or None
            values = [r["name"] for r in self.vps_manager.get_vision_subsegments(segment_name=seg)]
            subsegment_combo.configure(values=values or [""])

        def load_categories():
            seg = segment_var.get().strip() or None
            sub = subsegment_var.get().strip() or None
            values = [r["name"] for r in self.vps_manager.get_vision_categories(segment_name=seg, subsegment_name=sub)]
            category_combo.configure(values=values or [""])

        segment_combo.configure(command=lambda _v: (load_subsegments(), load_categories()))
        subsegment_combo.configure(command=lambda _v: load_categories())
        load_segments()
        load_subsegments()
        load_categories()

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=2, sticky="e", padx=8, pady=(8, 4))
        ctk.CTkButton(actions, text="Cancel", width=90, command=dialog.destroy, **button_style("secondary")).pack(
            side="right", padx=4
        )

        def on_save():
            seg = segment_var.get().strip()
            sub = subsegment_var.get().strip()
            cat = category_var.get().strip()
            if not seg or not sub or not cat:
                status_label.configure(text="Segment, SubSegment, and Category are required.")
                return
            try:
                self.vps_manager.update_vision_element(vision_element_id, seg, sub, cat)
            except Exception as exc:
                status_label.configure(text=f"Unable to save: {exc}")
                return
            dialog.destroy()
            self.refresh()

        ctk.CTkButton(actions, text="Save", width=90, command=on_save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def delete_ape_row(self, row: dict):
        parsed = self._parse_period()
        if not parsed:
            return
        year, _quarter, _month = parsed
        vision_element_id = row.get("vision_element_id")
        if not vision_element_id:
            messagebox.showerror("Missing Source", "This APE record is missing its source Vision Element.")
            return
        key = row.get("key_field") or "this APE record"
        if not messagebox.askyesno(
            "Delete APE Record",
            f"Delete {key} from {year}?",
            icon="warning",
        ):
            return

        deleted = self.vps_manager.delete_annual_records_for_vision_element(year, vision_element_id)
        if deleted:
            self.refresh()
        else:
            messagebox.showerror("Delete Failed", "APE record could not be deleted.")
