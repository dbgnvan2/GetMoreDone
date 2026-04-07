"""APE quarter assignment screen with two-panel APE workflow."""

from datetime import datetime
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

import customtkinter as ctk

from ..color_contrast import pick_text_color
from ..theme import button_style, semantic_colors
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors

if TYPE_CHECKING:
    from ..app import GetMoreDoneApp
    from ..vps_manager import VPSManager


class APEAssignmentScreen(ctk.CTkFrame):
    """Assign Annual Plan Elements to a selected quarter."""
    SPLITTER_WIDTH = 8
    MIN_PANEL_WIDTH = 420

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.year_var = ctk.StringVar(value=str(datetime.now().year))
        self.quarter_var = ctk.StringVar(value="1")
        self.segment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.category_filter_var = ctk.StringVar(value="All")

        self.left_items: list[dict] = []
        self.right_items: list[dict] = []
        self.segment_colors = {}
        self.subsegment_colors = {}
        self.category_colors = {}
        self.left_checks: dict[str, ctk.BooleanVar] = {}
        self._split_ratio = 0.5
        self._drag_start_x: Optional[int] = None
        self._drag_start_left: Optional[int] = None
        self.dragged_row: Optional[dict] = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.create_ui()
        self.refresh_lists()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(12, weight=1)

        ctk.CTkLabel(
            header,
            text="APE Quarter Assignment",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).grid(row=0, column=0, columnspan=13, sticky="w", padx=8, pady=(8, 6))

        ctk.CTkLabel(header, text="Year:").grid(row=1, column=0, padx=(8, 4), pady=(0, 8), sticky="e")
        ctk.CTkEntry(header, width=86, textvariable=self.year_var).grid(row=1, column=1, padx=4, pady=(0, 8), sticky="w")
        ctk.CTkLabel(header, text="Quarter:").grid(row=1, column=2, padx=(8, 4), pady=(0, 8), sticky="e")
        ctk.CTkComboBox(header, width=74, values=["1", "2", "3", "4"], variable=self.quarter_var).grid(
            row=1, column=3, padx=4, pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(header, text="Load", width=88, command=self.refresh_lists, **button_style("secondary")).grid(
            row=1, column=4, padx=(8, 4), pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(header, text="Save", width=88, command=self.add_selected, **button_style("primary")).grid(
            row=1, column=5, padx=4, pady=(0, 8), sticky="w"
        )
        ctk.CTkButton(header, text="Refresh", width=88, command=self.refresh_lists, **button_style("secondary")).grid(
            row=1, column=6, padx=(4, 12), pady=(0, 8), sticky="w"
        )

        ctk.CTkLabel(header, text="Segment:").grid(row=1, column=7, padx=(0, 4), pady=(0, 8), sticky="e")
        self.segment_filter_combo = ctk.CTkComboBox(
            header, width=160, values=["All"], variable=self.segment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.segment_filter_combo.grid(row=1, column=8, padx=4, pady=(0, 8), sticky="w")

        ctk.CTkLabel(header, text="SubSegment:").grid(row=1, column=9, padx=(10, 4), pady=(0, 8), sticky="e")
        self.subsegment_filter_combo = ctk.CTkComboBox(
            header, width=160, values=["All"], variable=self.subsegment_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.subsegment_filter_combo.grid(row=1, column=10, padx=4, pady=(0, 8), sticky="w")

        ctk.CTkLabel(header, text="Category:").grid(row=1, column=11, padx=(10, 4), pady=(0, 8), sticky="e")
        self.category_filter_combo = ctk.CTkComboBox(
            header, width=160, values=["All"], variable=self.category_filter_var, command=lambda _v: self.on_filters_changed()
        )
        self.category_filter_combo.grid(row=1, column=12, padx=4, pady=(0, 8), sticky="w")

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=0, minsize=520)
        body.grid_columnconfigure(1, weight=0, minsize=self.SPLITTER_WIDTH)
        body.grid_columnconfigure(2, weight=0, minsize=520)
        body.grid_rowconfigure(1, weight=1)
        self.body = body

        self.left_title_label = ctk.CTkLabel(body, text="", font=ctk.CTkFont(weight="bold"))
        self.left_title_label.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self.right_title_label = ctk.CTkLabel(body, text="", font=ctk.CTkFont(weight="bold"))
        self.right_title_label.grid(row=0, column=2, sticky="w", padx=8, pady=(8, 4))

        left_frame = ctk.CTkFrame(body)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 2), pady=(0, 8))
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame = left_frame

        divider = ctk.CTkFrame(
            body,
            width=self.SPLITTER_WIDTH,
            fg_color=semantic_colors()["border"],
            corner_radius=2,
            cursor="sb_h_double_arrow",
        )
        divider.grid(row=1, column=1, sticky="ns", padx=0, pady=(0, 8))
        divider.bind("<ButtonPress-1>", self._on_divider_press)
        divider.bind("<B1-Motion>", self._on_divider_drag)
        divider.bind("<ButtonRelease-1>", self._on_divider_release)
        self.divider = divider

        right_frame = ctk.CTkFrame(body)
        right_frame.grid(row=1, column=2, sticky="nsew", padx=(2, 8), pady=(0, 8))
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)
        self.right_frame = right_frame

        self.left_list = ctk.CTkScrollableFrame(left_frame)
        self.left_list.grid(row=0, column=0, sticky="nsew")
        self.left_list.grid_columnconfigure(0, weight=1)

        self.right_list = ctk.CTkScrollableFrame(right_frame)
        self.right_list.grid(row=0, column=0, sticky="nsew")
        self.right_list.grid_columnconfigure(0, weight=1)
        body.bind("<Configure>", self._on_body_resize)

    def _parse_period(self) -> Optional[tuple[int, int]]:
        try:
            year = int(self.year_var.get().strip())
            quarter = int(self.quarter_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Period", "Enter a valid year and quarter.")
            return None
        if quarter not in (1, 2, 3, 4):
            messagebox.showerror("Invalid Quarter", "Quarter must be 1, 2, 3, or 4.")
            return None
        return year, quarter

    def refresh_lists(self):
        parsed = self._parse_period()
        if not parsed:
            return
        year, quarter = parsed

        self.segment_colors, self.subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        self.category_colors = {
            (
                (r.get("segment_name", "") or "").strip().lower(),
                (r.get("subsegment_name", "") or "").strip().lower(),
                (r.get("name", "") or "").strip().lower(),
            ): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_categories()
        }
        self.left_items = self.vps_manager.get_annual_plan_elements(year)
        self.right_items = self.vps_manager.get_annual_plan_elements_for_quarter(year, quarter)
        self._refresh_filter_options()
        self.left_title_label.configure(text=f"Annual Plan Elements (check APEs to add to Quarter Q{quarter} and hit save)")
        self.right_title_label.configure(text=f"APE For Quarter Q{quarter}")
        self._render_rows(self.left_list, self._filtered_rows(self.left_items), selectable=True)
        self._render_rows(self.right_list, self._filtered_rows(self.right_items), selectable=False)

    def _filtered_rows(self, rows: list[dict]) -> list[dict]:
        seg = self.segment_filter_var.get().strip()
        sub = self.subsegment_filter_var.get().strip()
        cat = self.category_filter_var.get().strip()
        filtered = rows
        if seg and seg != "All":
            filtered = [r for r in filtered if (r.get("segment_name") or "").strip() == seg]
        if sub and sub != "All":
            filtered = [r for r in filtered if (r.get("subsegment_name") or "").strip() == sub]
        if cat and cat != "All":
            filtered = [r for r in filtered if (r.get("category_name") or "").strip() == cat]
        return filtered

    def _refresh_filter_options(self):
        rows = self.left_items
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
        self._render_rows(self.left_list, self._filtered_rows(self.left_items), selectable=True)
        self._render_rows(self.right_list, self._filtered_rows(self.right_items), selectable=False)

    def add_selected(self):
        parsed = self._parse_period()
        if not parsed:
            return
        _year, quarter = parsed
        selected_ids = [row_id for row_id, var in self.left_checks.items() if var.get()]
        if not selected_ids:
            return
        for ape_id in selected_ids:
            self.vps_manager.assign_ape_to_quarter(ape_id, quarter)
        self.refresh_lists()

    def _render_rows(self, container: ctk.CTkScrollableFrame, rows: list[dict], selectable: bool):
        for w in container.winfo_children():
            w.destroy()

        col_widths = {
            "index": 34,
            "segment": 135,
            "subsegment": 155,
            "category": 125,
            "actions": 84,
            "checkbox": 34,
        }

        header = ctk.CTkFrame(container, fg_color=semantic_colors()["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=4, pady=(0, 4))
        if selectable:
            header.grid_columnconfigure(0, minsize=col_widths["checkbox"])
            offset = 1
            ctk.CTkLabel(header, text="", width=col_widths["checkbox"]).grid(row=0, column=0, padx=2, pady=5, sticky="w")
        else:
            offset = 0
        header.grid_columnconfigure(offset + 0, minsize=col_widths["index"])
        header.grid_columnconfigure(offset + 1, minsize=col_widths["segment"])
        header.grid_columnconfigure(offset + 2, minsize=col_widths["subsegment"])
        header.grid_columnconfigure(offset + 3, minsize=col_widths["category"])
        header.grid_columnconfigure(offset + 4, weight=1 if selectable else 0, minsize=0 if selectable else col_widths["actions"])

        for idx, label in enumerate(("#", "Segment", "SubSegment", "Category")):
            width = col_widths[("index", "segment", "subsegment", "category")[idx]]
            ctk.CTkLabel(header, text=label, width=width, font=ctk.CTkFont(weight="bold"), anchor="w").grid(
                row=0, column=offset + idx, padx=5, pady=5, sticky="w"
            )
        if not selectable:
            ctk.CTkLabel(header, text="Actions", width=col_widths["actions"], font=ctk.CTkFont(weight="bold"), anchor="e").grid(
                row=0, column=offset + 4, padx=5, pady=5, sticky="e"
            )

        for idx, row in enumerate(rows):
            segment_name = row.get("segment_name") or ""
            subsegment_raw = row.get("subsegment_name") or "-"
            category_raw = row.get("category_name") or "-"
            segment_color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_raw,
                self.vps_manager,
                self.segment_colors,
                self.subsegment_colors,
            )
            category_color = self.category_colors.get(
                (segment_name.strip().lower(), subsegment_raw.strip().lower(), category_raw.strip().lower()),
                "",
            ) or subsegment_color

            item = ctk.CTkFrame(container)
            item.grid(row=idx + 1, column=0, sticky="ew", padx=4, pady=2)
            if selectable:
                item.grid_columnconfigure(0, minsize=col_widths["checkbox"])
                offset = 1
            else:
                offset = 0
            item.grid_columnconfigure(offset + 0, minsize=col_widths["index"])
            item.grid_columnconfigure(offset + 1, minsize=col_widths["segment"])
            item.grid_columnconfigure(offset + 2, minsize=col_widths["subsegment"])
            item.grid_columnconfigure(offset + 3, minsize=col_widths["category"])
            item.grid_columnconfigure(offset + 4, weight=1 if selectable else 0, minsize=0 if selectable else col_widths["actions"])

            if selectable:
                item_id = row.get("id", f"row-{idx}")
                var = self.left_checks.get(item_id)
                if var is None:
                    var = ctk.BooleanVar(value=False)
                    self.left_checks[item_id] = var
                ctk.CTkCheckBox(item, text="", variable=var, width=20).grid(row=0, column=0, padx=2, pady=5, sticky="w")

            index_label = ctk.CTkLabel(item, text=str(idx + 1), width=col_widths["index"], anchor="w")
            index_label.grid(
                row=0, column=offset + 0, padx=5, pady=5, sticky="w"
            )
            seg_chip = ctk.CTkLabel(
                item,
                text=f" {self._clip_label(segment_name, 15)} ",
                fg_color=segment_color,
                text_color=pick_text_color(segment_color),
                corner_radius=6,
                width=col_widths["segment"] - 12,
                anchor="w",
            )
            seg_chip.grid(row=0, column=offset + 1, padx=5, pady=5, sticky="w")
            sub_chip = ctk.CTkLabel(
                item,
                text=f" {self._clip_label(subsegment_raw, 15)} ",
                fg_color=subsegment_color,
                text_color=pick_text_color(subsegment_color),
                corner_radius=6,
                width=col_widths["subsegment"] - 12,
                anchor="w",
            )
            sub_chip.grid(row=0, column=offset + 2, padx=5, pady=5, sticky="w")
            cat_chip = ctk.CTkLabel(
                item,
                text=f" {self._clip_label(category_raw, 15)} ",
                fg_color=category_color,
                text_color=pick_text_color(category_color),
                corner_radius=6,
                width=col_widths["category"] - 12,
                anchor="w",
            )
            cat_chip.grid(row=0, column=offset + 3, padx=5, pady=5, sticky="w")

            if not selectable:
                ctk.CTkButton(
                    item,
                    text="Delete",
                    width=72,
                    command=lambda r=row: self.delete_quarter_item(r),
                    **button_style("danger"),
                ).grid(row=0, column=offset + 4, padx=5, pady=5, sticky="e")
            else:
                self._bind_drag_widgets((item, index_label, seg_chip, sub_chip, cat_chip), row)

    def delete_quarter_item(self, row: dict):
        parsed = self._parse_period()
        if not parsed:
            return
        _year, quarter = parsed
        label = row.get("key_field") or "this APE"
        if not messagebox.askyesno("Remove APE", f"Remove {label} from Quarter Q{quarter}?", icon="warning"):
            return
        self.vps_manager.unassign_ape_from_quarter(row["id"], quarter)
        self.refresh_lists()

    def _bind_drag_widgets(self, widgets: tuple, row: dict):
        for widget in widgets:
            widget.bind("<ButtonPress-1>", lambda _event, r=row: self._start_row_drag(r))

    def _start_row_drag(self, row: dict):
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
            parsed = self._parse_period()
            if parsed:
                _year, quarter = parsed
                self.vps_manager.assign_ape_to_quarter(row["id"], quarter)
                self.refresh_lists()

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

    def _is_descendant(self, widget, ancestor) -> bool:
        current = widget
        while current is not None:
            if current == ancestor:
                return True
            current = getattr(current, "master", None)
        return False

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"
