"""Annual Plan Element assignment screen (Quarter/Month flags)."""

import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
import tkinter as tk
from typing import TYPE_CHECKING, Optional

from ..theme import button_style, semantic_colors
from ..color_contrast import pick_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class APEAssignmentScreen(ctk.CTkFrame):
    """Assign APEs to quarters/months by drag/drop and toggles."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app
        self.drag_idx: Optional[int] = None
        self.ape_rows = []
        self.all_ape_rows = []
        self.selected_ape_id: Optional[str] = None
        self.selected_idx: Optional[int] = None
        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}
        self.segment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.category_filter_var = ctk.StringVar(value="All")
        self.q_vars = {}
        self.m_vars = {}
        self._syncing_targets = False

        self.year_var = ctk.StringVar(value=str(datetime.now().year))

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.create_ui()
        self.refresh_all()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(10, weight=1)

        ctk.CTkLabel(
            header,
            text="APE Quarter/Month Assignment",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, columnspan=11, sticky="w", padx=8, pady=(8, 6))
        ctk.CTkLabel(header, text="Year:").grid(row=1, column=0, padx=(8, 4), pady=(0, 8), sticky="e")
        ctk.CTkEntry(header, width=86, textvariable=self.year_var).grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkButton(header, text="Load", width=88, command=self.refresh_all, **button_style("secondary")).grid(
            row=1, column=2, padx=(8, 12), pady=(0, 8), sticky="w"
        )
        ctk.CTkLabel(header, text="Segment:").grid(row=1, column=3, padx=(0, 4), pady=(0, 8), sticky="e")
        self.segment_filter_combo = ctk.CTkComboBox(
            header, width=168, values=["All"], variable=self.segment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.segment_filter_combo.grid(row=1, column=4, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkLabel(header, text="SubSegment:").grid(row=1, column=5, padx=(10, 4), pady=(0, 8), sticky="e")
        self.subsegment_filter_combo = ctk.CTkComboBox(
            header, width=168, values=["All"], variable=self.subsegment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.subsegment_filter_combo.grid(row=1, column=6, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkLabel(header, text="Category:").grid(row=1, column=7, padx=(10, 4), pady=(0, 8), sticky="e")
        self.category_filter_combo = ctk.CTkComboBox(
            header, width=168, values=["All"], variable=self.category_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.category_filter_combo.grid(row=1, column=8, padx=4, pady=(0, 8), sticky="w")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        palette = semantic_colors()

        labels = ctk.CTkFrame(body, fg_color="transparent")
        labels.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        labels.grid_columnconfigure(0, weight=1)
        labels.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(labels, text="Annual Plan Elements (Left)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(labels, text="Quarter / Month Targets (Right)", font=ctk.CTkFont(weight="bold")).grid(
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
        right.grid_columnconfigure(0, weight=1, minsize=106)
        right.grid_columnconfigure(1, weight=1, minsize=106)
        self.splitter.add(left, minsize=320)
        self.splitter.add(right, minsize=230)

        self.ape_list = ctk.CTkScrollableFrame(left)
        self.ape_list.grid(row=0, column=0, sticky="nsew")
        self.ape_list.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Quarters").grid(row=0, column=0, sticky="w", padx=(6, 2), pady=4)
        ctk.CTkLabel(right, text="Months").grid(row=0, column=1, sticky="w", padx=(2, 6), pady=4)

        self.q_list = ctk.CTkScrollableFrame(right, label_text="", width=112)
        self.q_list.grid(row=1, column=0, sticky="nsew", padx=(6, 2), pady=(0, 6))
        self.q_list.grid_columnconfigure(0, weight=1)

        self.m_list = ctk.CTkScrollableFrame(right, label_text="", width=112)
        self.m_list.grid(row=1, column=1, sticky="nsew", padx=(2, 6), pady=(0, 6))
        self.m_list.grid_columnconfigure(0, weight=1)

        self.after(100, self._init_splitter_position)

    def _init_splitter_position(self):
        if not hasattr(self, "splitter"):
            return
        width = self.splitter.winfo_width()
        if width <= 0:
            self.after(100, self._init_splitter_position)
            return
        self.splitter.sash_place(0, int(width * 0.67), 0)

    def parse_year(self) -> Optional[int]:
        try:
            return int(self.year_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Year", "Enter a valid year.")
            return None

    def refresh_all(self):
        year = self.parse_year()
        if year is None:
            return
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (r.get("segment_name", "") or "").strip().lower(),
                (r.get("subsegment_name", "") or "").strip().lower(),
                (r.get("name", "") or "").strip().lower(),
            ): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_categories()
        }
        self.all_ape_rows = self.vps_manager.get_annual_plan_elements(year)
        self._refresh_filter_options()
        self.ape_rows = self._filtered_rows()
        self._render_ape_rows()
        self.selected_ape_id = None
        self.selected_idx = None
        self.render_targets(None)

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
        self.render_targets(None)

    def _render_ape_rows(self):
        for w in self.ape_list.winfo_children():
            w.destroy()
        palette = semantic_colors()
        col_widths = {
            "index": 34,
            "segment": 135,
            "subsegment": 155,
            "category": 125,
        }

        header = ctk.CTkFrame(self.ape_list, fg_color=palette["surface_subtle"])
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

            for widget in (item, idx_label, seg_chip, sub_chip, cat_chip):
                widget.bind("<Button-1>", lambda _e, i=idx: self.on_select_ape(i))

    def on_select_ape(self, index: int):
        if index < 0 or index >= len(self.ape_rows):
            return
        row = self.ape_rows[index]
        self.selected_ape_id = row["id"]
        self.selected_idx = index
        self._render_ape_rows()
        self.render_targets(row)

    def render_targets(self, row: Optional[dict]):
        self._syncing_targets = True
        for w in self.q_list.winfo_children():
            w.destroy()
        for w in self.m_list.winfo_children():
            w.destroy()
        self.q_vars = {}
        self.m_vars = {}

        for q in range(1, 5):
            checked = bool(row and row.get(f"q{q}", 0) == 1)
            var = ctk.BooleanVar(value=checked)
            self.q_vars[q] = var
            ctk.CTkCheckBox(
                self.q_list,
                text=f"Q{q}",
                variable=var,
                command=lambda qq=q: self.set_quarter(qq),
            ).grid(row=q - 1, column=0, sticky="w", padx=4, pady=3)

        for m in range(1, 13):
            checked = bool(row and row.get(f"m{m}", 0) == 1)
            var = ctk.BooleanVar(value=checked)
            self.m_vars[m] = var
            ctk.CTkCheckBox(
                self.m_list,
                text=f"M{m}",
                variable=var,
                command=lambda mm=m: self.set_month(mm),
            ).grid(row=m - 1, column=0, sticky="w", padx=4, pady=2)
        self._syncing_targets = False

    def _selected_row(self) -> Optional[dict]:
        if not self.selected_ape_id:
            return None
        for r in self.ape_rows:
            if r["id"] == self.selected_ape_id:
                return r
        return None

    def set_quarter(self, q: int):
        if self._syncing_targets:
            return
        row = self._selected_row()
        if not row:
            return
        enabled = bool(self.q_vars[q].get())
        self.vps_manager.set_annual_plan_element_quarter(row["id"], q, enabled)
        self.refresh_row(row["id"])

    def set_month(self, m: int):
        if self._syncing_targets:
            return
        row = self._selected_row()
        if not row:
            return
        enabled = bool(self.m_vars[m].get())
        self.vps_manager.set_annual_plan_element_month(row["id"], m, enabled)
        self.refresh_row(row["id"])

    def refresh_row(self, ape_id: str):
        year = self.parse_year()
        if year is None:
            return
        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (r.get("segment_name", "") or "").strip().lower(),
                (r.get("subsegment_name", "") or "").strip().lower(),
                (r.get("name", "") or "").strip().lower(),
            ): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_categories()
        }
        self.all_ape_rows = self.vps_manager.get_annual_plan_elements(year)
        self._refresh_filter_options()
        self.ape_rows = self._filtered_rows()
        self.selected_ape_id = ape_id
        self.selected_idx = next((i for i, r in enumerate(self.ape_rows) if r["id"] == ape_id), None)
        self._render_ape_rows()
        row = self._selected_row()
        self.render_targets(row)

    def on_drag_start(self, _event):
        self.drag_idx = None

    def on_drag_release(self, _event):
        # no-op here; handled in target release
        pass

    def on_target_release(self, event):
        self.drag_idx = None

    def _apply_row_color(self, index: int, segment_name: str):
        return

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"
