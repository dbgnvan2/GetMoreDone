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
        self.grid_rowconfigure(1, weight=1)

        self.segment_var = ctk.StringVar(value="")
        self.subsegment_var = ctk.StringVar(value="")
        self.category_var = ctk.StringVar(value="")
        self.key_var = ctk.StringVar(value="")

        self.create_ui()
        self.reload_dropdowns()
        self.refresh_list()

    def create_ui(self):
        top = ctk.CTkFrame(self)
        top.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)
        top.grid_columnconfigure(2, weight=1)
        top.grid_columnconfigure(4, weight=1)

        # Line 1: title
        ctk.CTkLabel(
            top,
            text="Vision Elements",
            font=ctk.CTkFont(size=22, weight="bold")
        ).grid(row=0, column=0, columnspan=5, sticky="w", padx=12, pady=(10, 6))

        # Line 2: selectors in one row
        selector_row = ctk.CTkFrame(top, fg_color="transparent")
        selector_row.grid(row=1, column=0, columnspan=5, sticky="ew", padx=8, pady=4)
        selector_row.grid_columnconfigure(1, weight=1)
        selector_row.grid_columnconfigure(3, weight=1)
        selector_row.grid_columnconfigure(5, weight=1)

        ctk.CTkLabel(selector_row, text="Segment:").grid(row=0, column=0, sticky="w", padx=(4, 6), pady=4)
        self.segment_combo = ctk.CTkComboBox(
            selector_row, variable=self.segment_var, values=[], command=self.on_segment_change
        )
        self.segment_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        ctk.CTkLabel(selector_row, text="SubSegment:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.subsegment_combo = ctk.CTkComboBox(
            selector_row, variable=self.subsegment_var, values=[], command=self.on_subsegment_change
        )
        self.subsegment_combo.grid(row=0, column=3, sticky="ew", padx=(0, 8), pady=4)

        ctk.CTkLabel(selector_row, text="Category:").grid(row=0, column=4, sticky="w", padx=(0, 6), pady=4)
        self.category_combo = ctk.CTkComboBox(
            selector_row, variable=self.category_var, values=[], command=lambda _: self.update_key_preview()
        )
        self.category_combo.grid(row=0, column=5, sticky="ew", padx=(0, 4), pady=4)

        # Line 3: key field + actions
        ctk.CTkLabel(top, text="Key Field:").grid(row=2, column=0, sticky="w", padx=(12, 6), pady=(4, 10))
        self.key_entry = ctk.CTkEntry(top, textvariable=self.key_var, state="readonly")
        self.key_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 8), pady=(4, 10))

        ctk.CTkButton(
            top,
            text="Create Linked Vision Element",
            command=self.create_vision_element,
            width=210,
            **button_style("primary"),
        ).grid(row=2, column=3, sticky="e", padx=(0, 6), pady=(4, 10))
        ctk.CTkButton(
            top,
            text="Refresh",
            command=self.refresh_all,
            width=110,
            **button_style("secondary"),
        ).grid(row=2, column=4, sticky="e", padx=(0, 8), pady=(4, 10))

        self.list_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))
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
        ctk.CTkLabel(header, text="Actions", width=80, font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=3, padx=5, pady=5, sticky="w"
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
            ctk.CTkButton(
                item_row,
                text="Edit",
                width=70,
                command=lambda r=row: self.edit_vision_element(r),
                **button_style("secondary"),
            ).grid(row=0, column=3, padx=5, pady=5, sticky="e")

    def edit_vision_element(self, row: dict):
        """Edit an existing Vision Element record."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Vision Element")
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
                self.vps_manager.update_vision_element(row["id"], seg, sub, cat)
            except Exception as exc:
                status_label.configure(text=f"Unable to save: {exc}")
                return
            dialog.destroy()
            self.refresh_all()

        ctk.CTkButton(actions, text="Save", width=90, command=on_save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def refresh_all(self):
        self.reload_dropdowns()
        self.refresh_list()
