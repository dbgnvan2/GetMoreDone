"""Vision Elements screen: maintain Segment/SubSegment/Category linked records."""

import customtkinter as ctk
from tkinter import messagebox
from typing import TYPE_CHECKING

from ..theme import apply_segment_accent, button_style, semantic_colors

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
        palette = semantic_colors()
        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 4))
        header_frame.grid_columnconfigure(0, weight=1)

        header = ctk.CTkLabel(
            header_frame,
            text="Vision Elements",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        header.grid(row=0, column=0, sticky="w", padx=12, pady=(10, 2))

        subtitle = ctk.CTkLabel(
            header_frame,
            text="Build linked Segment → SubSegment → Category records",
            text_color=palette["muted_text"],
        )
        subtitle.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

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

        self.list_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=(4, 12))
        self.list_frame.grid_columnconfigure(0, weight=1)

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
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        rows = self.vps_manager.get_vision_elements()
        segment_colors = self.vps_manager.get_segment_color_map()
        if not rows:
            ctk.CTkLabel(self.list_frame, text="No Vision Elements yet.").grid(
                row=0, column=0, padx=10, pady=20, sticky="w"
            )
            return

        header = ctk.CTkFrame(self.list_frame, fg_color=semantic_colors()["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 4))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="#", width=34, font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5, pady=5)
        ctk.CTkLabel(header, text="Vision Element", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=1, padx=5, pady=5, sticky="w"
        )
        ctk.CTkLabel(header, text="Key", width=280, font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )

        for i, row in enumerate(rows, start=1):
            segment_name = row.get("segment_name") or ""
            segment_color = segment_colors.get(segment_name.strip().lower())
            if not segment_color:
                segment_color = self.vps_manager.resolve_segment_color(segment_name, segment_colors)

            item_row = ctk.CTkFrame(self.list_frame)
            item_row.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            item_row.grid_columnconfigure(1, weight=1)
            apply_segment_accent(item_row, segment_color)

            ctk.CTkLabel(item_row, text=str(i), width=34).grid(row=0, column=0, padx=5, pady=5)

            text_col = ctk.CTkFrame(item_row, fg_color="transparent")
            text_col.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            chip = ctk.CTkLabel(
                text_col,
                text=f" {segment_name} ",
                fg_color=segment_color,
                text_color="white",
                corner_radius=6,
            )
            chip.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(
                text_col,
                text=f"{row.get('subsegment_name') or '-'} | {row.get('category_name') or '-'}",
                anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(item_row, text=row.get("key_field") or "-", width=280, anchor="w").grid(
                row=0, column=2, padx=5, pady=5, sticky="w"
            )

    def refresh_all(self):
        self.reload_dropdowns()
        self.refresh_list()
