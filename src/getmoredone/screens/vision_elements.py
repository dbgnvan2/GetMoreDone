"""Vision Elements screen: maintain Segment/SubSegment/Category linked records."""

import customtkinter as ctk
from tkinter import messagebox
from typing import TYPE_CHECKING

from ..theme import button_style

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class VisionElementsScreen(ctk.CTkFrame):
    """Create and browse Vision Elements."""

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self.segment_var = ctk.StringVar(value="")
        self.subsegment_var = ctk.StringVar(value="")
        self.category_var = ctk.StringVar(value="")
        self.key_var = ctk.StringVar(value="")

        self.create_ui()
        self.reload_dropdowns()
        self.refresh_list()

    def create_ui(self):
        header_frame = ctk.CTkFrame(self, fg_color="#0F172A")
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header_frame.grid_columnconfigure(1, weight=1)

        header = ctk.CTkLabel(
            header_frame,
            text="Vision Elements",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Build linked Segment → SubSegment → Category records",
            text_color="#93C5FD"
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        chip_row = ctk.CTkFrame(header_frame, fg_color="transparent")
        chip_row.grid(row=0, column=1, rowspan=2, sticky="e", padx=8)
        ctk.CTkLabel(chip_row, text="Segment", fg_color="#334155", corner_radius=6, padx=8, pady=3).pack(side="left", padx=4)
        ctk.CTkLabel(chip_row, text="SubSegment", fg_color="#1D4ED8", corner_radius=6, padx=8, pady=3).pack(side="left", padx=4)
        ctk.CTkLabel(chip_row, text="Category", fg_color="#0D9488", corner_radius=6, padx=8, pady=3).pack(side="left", padx=4)

        form = ctk.CTkFrame(self)
        form.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        form.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(form, text="Segment:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.segment_combo = ctk.CTkComboBox(form, variable=self.segment_var, values=[], command=self.on_segment_change)
        self.segment_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(form, text="SubSegment:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        self.subsegment_combo = ctk.CTkComboBox(form, variable=self.subsegment_var, values=[], command=self.on_subsegment_change)
        self.subsegment_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(form, text="Category:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        self.category_combo = ctk.CTkComboBox(form, variable=self.category_var, values=[], command=lambda _: self.update_key_preview())
        self.category_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(form, text="Key Field:").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        self.key_entry = ctk.CTkEntry(form, textvariable=self.key_var, state="readonly")
        self.key_entry.grid(row=3, column=1, sticky="ew", padx=8, pady=6)

        btn_row = ctk.CTkFrame(form, fg_color="transparent")
        btn_row.grid(row=4, column=0, columnspan=2, sticky="ew", padx=8, pady=8)
        btn_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            btn_row,
            text="Create Linked Vision Element",
            command=self.create_vision_element,
            **button_style("primary"),
        ).grid(
            row=0, column=0, padx=4, pady=4, sticky="ew"
        )
        ctk.CTkButton(
            btn_row,
            text="Refresh",
            command=self.refresh_all,
            **button_style("secondary"),
        ).grid(
            row=0, column=1, padx=4, pady=4, sticky="ew"
        )

        self.list_box = ctk.CTkTextbox(self)
        self.list_box.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))

    def on_segment_change(self, _value: str):
        self.load_subsegments()
        self.update_key_preview()

    def on_subsegment_change(self, _value: str):
        self.load_categories()
        self.update_key_preview()

    def update_key_preview(self):
        s = self.segment_var.get().strip()
        ss = self.subsegment_var.get().strip()
        c = self.category_var.get().strip()
        if s and ss and c:
            self.key_var.set(f"{s}|{ss}|{c}")
        else:
            self.key_var.set("")

    def reload_dropdowns(self):
        segments = [r["name"] for r in self.vps_manager.get_vision_segments()]
        self.segment_combo.configure(values=segments if segments else [""])
        self.load_subsegments()
        self.load_categories()

    def load_subsegments(self):
        segment = self.segment_var.get().strip() or None
        subsegments = [r["name"] for r in self.vps_manager.get_vision_subsegments(segment_name=segment)]
        self.subsegment_combo.configure(values=subsegments if subsegments else [""])

    def load_categories(self):
        segment = self.segment_var.get().strip() or None
        subsegment = self.subsegment_var.get().strip() or None
        categories = [r["name"] for r in self.vps_manager.get_vision_categories(
            segment_name=segment, subsegment_name=subsegment
        )]
        self.category_combo.configure(values=categories if categories else [""])

    def create_vision_element(self):
        segment = self.segment_var.get().strip()
        subsegment = self.subsegment_var.get().strip()
        category = self.category_var.get().strip()

        if not segment or not subsegment or not category:
            messagebox.showerror("Missing Values", "Segment, SubSegment, and Category are required.")
            return

        try:
            self.vps_manager.create_or_get_vision_element(segment, subsegment, category)
            self.update_key_preview()
            self.refresh_all()
            messagebox.showinfo("Created", "Vision Element created/updated successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to create Vision Element:\n{e}")

    def refresh_list(self):
        rows = self.vps_manager.get_vision_elements()
        segment_colors = self.vps_manager.get_segment_color_map()
        self.list_box.configure(state="normal")
        self.list_box.delete("1.0", "end")
        if not rows:
            self.list_box.insert("end", "No Vision Elements yet.\n")
        else:
            for i, row in enumerate(rows, start=1):
                line = (
                    f"{i:>3}. {row['segment_name']} | {row['subsegment_name']} | {row['category_name']}\n"
                )
                start_idx = self.list_box.index("end-1c")
                self.list_box.insert(
                    "end",
                    line
                )
                end_idx = self.list_box.index("end-1c")
                tag_name = f"seg_color_{i}"
                color = segment_colors.get((row.get("segment_name") or "").strip().lower())
                if not color:
                    color = self.vps_manager.resolve_segment_color(row.get("segment_name", ""), segment_colors)
                self.list_box.tag_add(tag_name, start_idx, end_idx)
                self.list_box.tag_config(tag_name, background=color, foreground="white")
        self.list_box.configure(state="disabled")

    def refresh_all(self):
        self.reload_dropdowns()
        self.refresh_list()
