"""Annual Plan Elements screen with drag/drop from Vision Elements."""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ..theme import button_style, combo_box_style, semantic_colors, status_text_color
from ..color_contrast import pick_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class AnnualVisionSegmentsScreen(ctk.CTkFrame):
    """Drag vision elements into annual list to create annual plan records."""
    SPLITTER_WIDTH = 8
    MIN_PANEL_WIDTH = 420

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app
        self.drag_index: Optional[int] = None
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.year_var = ctk.StringVar(value=str(datetime.now().year))
        self.left_items = []  # list of dict vision elements
        self.right_items = []
        self.segment_colors = {}
        self.subsegment_colors: dict[tuple[str, str], str] = {}
        self.category_colors: dict[tuple[str, str, str], str] = {}
        self.left_checks: dict[str, ctk.BooleanVar] = {}
        self._split_ratio = 0.5
        self._drag_start_x: Optional[int] = None
        self._drag_start_left: Optional[int] = None
        self.dragged_row: Optional[dict] = None

        self.create_ui()
        self.refresh_lists()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(header, text="Annual Plan Elements", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=8, pady=8, sticky="w"
        )
        ctk.CTkLabel(header, text="Year:").grid(row=0, column=1, padx=(18, 4), pady=8)
        self.year_entry = ctk.CTkEntry(header, width=90, textvariable=self.year_var)
        self.year_entry.grid(row=0, column=2, padx=4, pady=8)
        ctk.CTkButton(header, text="Load Year", width=100, command=self.refresh_lists, **button_style("secondary")).grid(
            row=0, column=3, padx=6, pady=8
        )
        ctk.CTkButton(header, text="Save", width=100, command=self.add_selected, **button_style("primary")).grid(
            row=0, column=4, padx=6, pady=8
        )
        ctk.CTkButton(header, text="Refresh", width=90, command=self.refresh_lists, **button_style("secondary")).grid(
            row=0, column=5, padx=6, pady=8
        )

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=0, minsize=520)
        body.grid_columnconfigure(1, weight=0, minsize=self.SPLITTER_WIDTH)
        body.grid_columnconfigure(2, weight=0, minsize=520)
        body.grid_rowconfigure(1, weight=1)
        self.body = body

        self.left_title_label = ctk.CTkLabel(
            body,
            text="Vision Elements (check elements to add to the year and hit save)",
            font=ctk.CTkFont(weight="bold"),
        )
        self.left_title_label.grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        self.right_title_label = ctk.CTkLabel(
            body,
            text="Annual Plan Elements for the year 0",
            font=ctk.CTkFont(weight="bold"),
        )
        self.right_title_label.grid(
            row=0, column=2, sticky="w", padx=8, pady=(8, 4)
        )

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

    def _parse_year(self) -> Optional[int]:
        try:
            return int(self.year_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid Year", "Enter a valid year, e.g. 2026.")
            return None

    def refresh_lists(self):
        year = self._parse_year()
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
        self.left_items = self.vps_manager.get_vision_elements()
        self.right_items = self.vps_manager.get_annual_vision_elements(year)
        self.left_title_label.configure(
            text="Vision Elements (check elements to add to the year and hit save)"
        )
        self.right_title_label.configure(
            text=f"Annual Plan Elements for the year {year}"
        )
        self._render_rows(self.left_list, self.left_items, selectable=True)
        self._render_rows(self.right_list, self.right_items, selectable=False)

    def _render_rows(self, container: ctk.CTkScrollableFrame, rows: list[dict], selectable: bool):
        for w in container.winfo_children():
            w.destroy()

        col_widths = {
            "index": 34,
            "segment": 135,
            "subsegment": 155,
            "category": 125,
            "actions": 140,
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
        if selectable:
            header.grid_columnconfigure(offset + 4, weight=1)
        else:
            header.grid_columnconfigure(offset + 4, minsize=col_widths["actions"])

        ctk.CTkLabel(header, text="#", width=col_widths["index"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=offset + 0, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="Segment", width=col_widths["segment"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=offset + 1, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="SubSegment", width=col_widths["subsegment"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=offset + 2, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="Category", width=col_widths["category"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=offset + 3, padx=5, pady=5, sticky="w"
        )
        if not selectable:
            ctk.CTkLabel(header, text="Actions", width=col_widths["actions"], font=ctk.CTkFont(weight="bold"), anchor="e").grid(
                row=0, column=offset + 4, padx=5, pady=5, sticky="e"
            )

        for idx, row in enumerate(rows):
            segment_name = row.get("segment_name", "")
            subsegment_raw = row.get("subsegment_name") or "-"
            segment_color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_raw,
                self.vps_manager,
                self.segment_colors,
                self.subsegment_colors,
            )
            subsegment_name = self._clip_label(subsegment_raw, 15)
            category_raw = row.get("category_name") or "-"
            category_name = self._clip_label(category_raw, 15)
            category_color = row.get("category_color_hex") or self.category_colors.get(
                (
                    segment_name.strip().lower(),
                    subsegment_raw.strip().lower(),
                    category_raw.strip().lower(),
                ),
                "",
            )
            if not category_color:
                category_color = subsegment_color
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
            if selectable:
                item.grid_columnconfigure(offset + 4, weight=1)
            else:
                item.grid_columnconfigure(offset + 4, minsize=col_widths["actions"])

            if selectable:
                item_id = row.get("id", f"row-{idx}")
                var = self.left_checks.get(item_id)
                if var is None:
                    var = ctk.BooleanVar(value=False)
                    self.left_checks[item_id] = var
                ctk.CTkCheckBox(item, text="", variable=var, width=20).grid(
                    row=0, column=0, padx=2, pady=5, sticky="w"
                )

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
                text=f" {subsegment_name} ",
                fg_color=subsegment_color,
                text_color=pick_text_color(subsegment_color),
                corner_radius=6,
                width=col_widths["subsegment"] - 12,
                anchor="w",
            )
            sub_chip.grid(row=0, column=offset + 2, padx=5, pady=5, sticky="w")

            cat_chip = ctk.CTkLabel(
                item,
                text=f" {category_name} ",
                fg_color=category_color,
                text_color=pick_text_color(category_color),
                corner_radius=6,
                anchor="w",
                width=col_widths["category"] - 12,
            )
            cat_chip.grid(row=0, column=offset + 3, padx=5, pady=5, sticky="w")

            if not selectable:
                actions = ctk.CTkFrame(item, fg_color="transparent")
                actions.grid(row=0, column=offset + 4, padx=(4, 2), pady=5, sticky="w")
                ctk.CTkButton(
                    actions,
                    text="Edit",
                    width=64,
                    command=lambda r=row: self.edit_annual_item(r),
                    **button_style("secondary"),
                ).pack(side="left", padx=(0, 2))
                ctk.CTkButton(
                    actions,
                    text="Delete",
                    width=64,
                    command=lambda r=row: self.delete_annual_item(r),
                    **button_style("danger"),
                ).pack(side="left", padx=(2, 0))
            else:
                self._bind_drag_widgets((item, index_label, seg_chip, sub_chip, cat_chip), row)

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

    def _create_from_index(self, idx: int):
        year = self._parse_year()
        if year is None:
            return
        if idx < 0 or idx >= len(self.left_items):
            return
        item = self.left_items[idx]
        self._create_from_row(item)

    def _create_from_row(self, row: dict):
        year = self._parse_year()
        if year is None:
            return
        self.vps_manager.create_annual_records_from_vision_element(year, row["id"])
        self.refresh_lists()

    def add_selected(self):
        year = self._parse_year()
        if year is None:
            return
        selected_ids = [k for k, v in self.left_checks.items() if v.get()]
        if not selected_ids:
            return
        selected_set = set(selected_ids)
        for row in self.left_items:
            if row.get("id") in selected_set:
                self.vps_manager.create_annual_records_from_vision_element(year, row["id"])
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
        if self._is_descendant(target, self.right_frame):
            self._create_from_row(row)

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

    def edit_annual_item(self, row: dict):
        """Edit a right-side annual item by updating its source Vision Element."""
        vision_element_id = row.get("vision_element_id")
        if not vision_element_id:
            messagebox.showerror("Missing Source", "This annual record is missing its source Vision Element.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Annual Plan Element")
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
        subsegment_combo = ctk.CTkComboBox(frame, variable=subsegment_var, values=[], **combo_box_style())
        subsegment_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Category:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        category_combo = ctk.CTkComboBox(frame, variable=category_var, values=[], **combo_box_style())
        category_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=6)

        status_label = ctk.CTkLabel(frame, text="", text_color=status_text_color("error"))
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
            self.refresh_lists()

        ctk.CTkButton(actions, text="Save", width=90, command=on_save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def delete_annual_item(self, row: dict):
        year = self._parse_year()
        if year is None:
            return

        vision_element_id = row.get("vision_element_id")
        if not vision_element_id:
            messagebox.showerror("Missing Source", "This annual record is missing its source Vision Element.")
            return

        key = row.get("key_field") or "this annual record"
        if not messagebox.askyesno(
            "Delete Annual Vision Record",
            f"Delete {key} from {year}?",
            icon="warning",
        ):
            return

        if self.vps_manager.delete_annual_records_for_vision_element(year, vision_element_id):
            self.refresh_lists()
        else:
            messagebox.showerror("Delete Failed", "Annual record could not be deleted.")
