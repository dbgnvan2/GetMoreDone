"""Annual Vision Segments screen with drag/drop from Vision Elements."""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from ..theme import apply_segment_accent, button_style, semantic_colors

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class AnnualVisionSegmentsScreen(ctk.CTkFrame):
    """Drag vision elements into annual list to create AVE + APE records."""

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
        self.left_selected_idx: Optional[int] = None

        self.create_ui()
        self.refresh_lists()

    def create_ui(self):
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=12)
        header.grid_columnconfigure(6, weight=1)

        ctk.CTkLabel(header, text="Annual Vision Segments", font=ctk.CTkFont(size=22, weight="bold")).grid(
            row=0, column=0, padx=8, pady=8, sticky="w"
        )
        ctk.CTkLabel(header, text="Year:").grid(row=0, column=1, padx=(18, 4), pady=8)
        self.year_entry = ctk.CTkEntry(header, width=90, textvariable=self.year_var)
        self.year_entry.grid(row=0, column=2, padx=4, pady=8)
        ctk.CTkButton(header, text="Load Year", width=100, command=self.refresh_lists, **button_style("secondary")).grid(
            row=0, column=3, padx=6, pady=8
        )
        ctk.CTkButton(header, text="Add Selected >>", width=120, command=self.add_selected, **button_style("primary")).grid(
            row=0, column=4, padx=6, pady=8
        )
        ctk.CTkButton(header, text="Refresh", width=90, command=self.refresh_lists, **button_style("secondary")).grid(
            row=0, column=5, padx=6, pady=8
        )

        body = ctk.CTkFrame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(body, text="Vision Elements (drag from here)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, sticky="w", padx=8, pady=(8, 4)
        )
        ctk.CTkLabel(body, text="Annual Vision Elements (drop here)", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=1, sticky="w", padx=8, pady=(8, 4)
        )

        left_frame = ctk.CTkFrame(body)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        right_frame = ctk.CTkFrame(body)
        right_frame.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        self.left_list = ctk.CTkScrollableFrame(left_frame)
        self.left_list.grid(row=0, column=0, sticky="nsew")
        self.left_list.grid_columnconfigure(0, weight=1)
        self.right_list = ctk.CTkScrollableFrame(right_frame)
        self.right_list.grid(row=0, column=0, sticky="nsew")
        self.right_list.grid_columnconfigure(0, weight=1)

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

        self.segment_colors = self.vps_manager.get_segment_color_map()
        self.left_items = self.vps_manager.get_vision_elements()
        self.right_items = self.vps_manager.get_annual_vision_elements(year)
        self.left_selected_idx = None
        self._render_rows(self.left_list, self.left_items, selectable=True)
        self._render_rows(self.right_list, self.right_items, selectable=False)

    def _resolve_segment_color(self, segment_name: str) -> str:
        color = self.vps_manager.resolve_segment_color(segment_name, self.segment_colors)
        return color

    def _render_rows(self, container: ctk.CTkScrollableFrame, rows: list[dict], selectable: bool):
        for w in container.winfo_children():
            w.destroy()
        palette = semantic_colors()
        for idx, row in enumerate(rows):
            segment_name = row.get("segment_name", "")
            segment_color = self._resolve_segment_color(segment_name)
            bg = palette["selected_tint"] if selectable and idx == self.left_selected_idx else None
            item = ctk.CTkFrame(container, fg_color=bg)
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=2)
            item.grid_columnconfigure(1, weight=1)
            apply_segment_accent(item, segment_color)

            ctk.CTkLabel(item, text=str(idx + 1), width=28).grid(row=0, column=0, padx=5, pady=5)
            text = row.get("key_field") or "-"
            lbl = ctk.CTkLabel(item, text=text, anchor="w")
            lbl.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            chip = ctk.CTkLabel(item, text=f" {segment_name} ", fg_color=segment_color, text_color="white", corner_radius=6)
            chip.grid(row=0, column=2, padx=5, pady=5)

            if selectable:
                for widget in (item, lbl):
                    widget.bind("<Button-1>", lambda _e, i=idx: self.on_left_select(i))
            else:
                ctk.CTkButton(
                    item,
                    text="Edit",
                    width=64,
                    command=lambda r=row: self.edit_annual_item(r),
                    **button_style("secondary"),
                ).grid(row=0, column=3, padx=5, pady=5, sticky="e")

    def on_left_select(self, idx: int):
        self.left_selected_idx = idx
        self._render_rows(self.left_list, self.left_items, selectable=True)

    def _create_from_index(self, idx: int):
        year = self._parse_year()
        if year is None:
            return
        if idx < 0 or idx >= len(self.left_items):
            return
        item = self.left_items[idx]
        self.vps_manager.create_annual_records_from_vision_element(year, item["id"])
        self.refresh_lists()

    def add_selected(self):
        if self.left_selected_idx is None:
            return
        self._create_from_index(self.left_selected_idx)

    def on_left_press(self, event):
        self.drag_index = None

    def on_left_release(self, event):
        self.drag_index = None

    def on_right_release(self, _event):
        self.drag_index = None

    def edit_annual_item(self, row: dict):
        """Edit a right-side annual item by updating its source Vision Element."""
        vision_element_id = row.get("vision_element_id")
        if not vision_element_id:
            messagebox.showerror("Missing Source", "This annual record is missing its source Vision Element.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Annual Vision Element")
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
            self.refresh_lists()
