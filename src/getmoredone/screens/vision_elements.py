"""Vision Elements screen: maintain Segment/SubSegment/Category linked records."""

import customtkinter as ctk
from tkinter import messagebox
from typing import TYPE_CHECKING

from ..theme import apply_segment_accent, button_style, semantic_colors, status_text_color
from ..color_contrast import pick_text_color
from .segment_color_utils import load_latest_lineage_color_maps, resolve_lineage_colors

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
            selector_row, variable=self.segment_var, values=[], command=self.on_segment_change, state="readonly"
        )
        self.segment_combo.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=4)

        ctk.CTkLabel(selector_row, text="SubSegment:").grid(row=0, column=2, sticky="w", padx=(0, 6), pady=4)
        self.subsegment_combo = ctk.CTkComboBox(
            selector_row, variable=self.subsegment_var, values=[], command=self.on_subsegment_change, state="readonly"
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

    def _position_dialog_above_title(self, dialog: ctk.CTkToplevel, width: int, height: int):
        """Place modal centered above the Vision Elements title area."""
        self.update_idletasks()
        x = self.winfo_rootx() + max(0, (self.winfo_width() - width) // 2)
        y = self.winfo_rooty() + 24
        dialog.geometry(f"{width}x{height}+{x}+{y}")

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
        segment_colors, subsegment_colors = load_latest_lineage_color_maps(self.vps_manager)
        if not rows:
            ctk.CTkLabel(self.list_frame, text="No Vision Elements yet.").grid(
                row=0, column=0, padx=10, pady=20, sticky="w"
            )
            return

        col_widths = {
            "index": 34,
            "segment": 220,
            "subsegment": 220,
            "category": 220,
            "actions": 170,
        }

        header = ctk.CTkFrame(self.list_frame, fg_color=semantic_colors()["surface_subtle"])
        header.grid(row=0, column=0, sticky="ew", padx=5, pady=(0, 4))
        header.grid_columnconfigure(0, minsize=col_widths["index"])
        header.grid_columnconfigure(1, minsize=col_widths["segment"])
        header.grid_columnconfigure(2, minsize=col_widths["subsegment"])
        header.grid_columnconfigure(3, minsize=col_widths["category"])
        header.grid_columnconfigure(4, weight=1)
        header.grid_columnconfigure(5, minsize=col_widths["actions"])
        ctk.CTkLabel(header, text="#", width=col_widths["index"], font=ctk.CTkFont(weight="bold"), anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
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

        for i, row in enumerate(rows, start=1):
            segment_name = row.get("segment_name") or ""
            subsegment_name = row.get("subsegment_name") or ""
            segment_color, subsegment_color = resolve_lineage_colors(
                segment_name,
                subsegment_name,
                self.vps_manager,
                segment_colors,
                subsegment_colors,
            )

            item_row = ctk.CTkFrame(self.list_frame)
            item_row.grid(row=i, column=0, sticky="ew", padx=5, pady=2)
            item_row.grid_columnconfigure(0, minsize=col_widths["index"])
            item_row.grid_columnconfigure(1, minsize=col_widths["segment"])
            item_row.grid_columnconfigure(2, minsize=col_widths["subsegment"])
            item_row.grid_columnconfigure(3, minsize=col_widths["category"])
            item_row.grid_columnconfigure(4, weight=1)
            item_row.grid_columnconfigure(5, minsize=col_widths["actions"])
            apply_segment_accent(item_row, segment_color)

            ctk.CTkLabel(item_row, text=str(i), width=col_widths["index"], anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")

            chip = ctk.CTkLabel(
                item_row,
                text=f" {segment_name} ",
                fg_color=segment_color,
                text_color=pick_text_color(segment_color),
                corner_radius=6,
                width=col_widths["segment"] - 12,
                anchor="w",
            )
            chip.grid(row=0, column=1, padx=5, pady=5, sticky="w")
            sub_label = ctk.CTkLabel(
                item_row,
                text=f" {self._clip_label(subsegment_name or '-', 20)} ",
                anchor="w",
                width=col_widths["subsegment"] - 12,
                fg_color=subsegment_color,
                corner_radius=6,
                text_color=pick_text_color(subsegment_color),
            )
            sub_label.grid(row=0, column=2, padx=5, pady=5, sticky="w")
            cat_label = ctk.CTkLabel(
                item_row,
                text=self._clip_label(row.get("category_name") or "-", 20),
                anchor="w",
                width=col_widths["category"] - 12,
            )
            cat_label.grid(row=0, column=3, padx=5, pady=5, sticky="w")

            for widget in (chip,):
                widget.bind("<Button-1>", lambda _e, r=row: self.edit_level_vision(r, "segment"))
            sub_label.bind("<Button-1>", lambda _e, r=row: self.edit_level_vision(r, "subsegment"))
            cat_label.bind("<Button-1>", lambda _e, r=row: self.edit_level_vision(r, "category"))

            actions = ctk.CTkFrame(item_row, fg_color="transparent")
            actions.grid(row=0, column=5, padx=5, pady=5, sticky="e")
            ctk.CTkButton(
                actions,
                text="Edit",
                width=78,
                command=lambda r=row: self.edit_level_vision(r, "category"),
                **button_style("secondary"),
            ).pack(side="left", padx=(0, 4))
            ctk.CTkButton(
                actions,
                text="Delete",
                width=78,
                command=lambda r=row: self.delete_vision_element(r),
                **button_style("danger"),
            ).pack(side="left", padx=0)

    def edit_vision_element(self, row: dict):
        """Edit an existing Vision Element record."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Vision Element")
        self._position_dialog_above_title(dialog, 760, 420)
        dialog.transient(self)
        dialog.grab_set()

        segment_var = ctk.StringVar(value=row.get("segment_name") or "")
        subsegment_var = ctk.StringVar(value=row.get("subsegment_name") or "")
        category_var = ctk.StringVar(value=row.get("category_name") or "")
        vision_text_var = ctk.StringVar(value=row.get("vision_text") or "")

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Segment:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        segment_combo = ctk.CTkComboBox(frame, variable=segment_var, values=[])
        segment_combo.configure(state="readonly")
        segment_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="SubSegment:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        subsegment_combo = ctk.CTkComboBox(frame, variable=subsegment_var, values=[])
        subsegment_combo.configure(state="readonly")
        subsegment_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Category:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        category_combo = ctk.CTkComboBox(frame, variable=category_var, values=[])
        category_combo.grid(row=2, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Vision:").grid(row=3, column=0, sticky="nw", padx=8, pady=6)
        vision_text = ctk.CTkTextbox(frame, height=140)
        vision_text.grid(row=3, column=1, sticky="nsew", padx=8, pady=6)
        if vision_text_var.get():
            vision_text.insert("1.0", vision_text_var.get())
        frame.grid_rowconfigure(3, weight=1)

        status_label = ctk.CTkLabel(frame, text="", text_color=status_text_color("error"))
        status_label.grid(row=4, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 6))

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
        actions.grid(row=5, column=0, columnspan=2, sticky="e", padx=8, pady=(8, 4))
        ctk.CTkButton(actions, text="Cancel", width=90, command=dialog.destroy, **button_style("secondary")).pack(
            side="right", padx=4
        )

        def on_save():
            seg = segment_var.get().strip()
            sub = subsegment_var.get().strip()
            cat = category_var.get().strip()
            vision_value = vision_text.get("1.0", "end-1c").strip()
            if not seg or not sub or not cat:
                status_label.configure(text="Segment, SubSegment, and Category are required.")
                return
            try:
                self.vps_manager.update_vision_element(row["id"], seg, sub, cat, vision_value)
            except Exception as exc:
                status_label.configure(text=f"Unable to save: {exc}")
                return
            dialog.destroy()
            self.refresh_all()

        ctk.CTkButton(actions, text="Save", width=90, command=on_save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def delete_vision_element(self, row: dict):
        name = row.get("key_field") or "this vision element"
        if not messagebox.askyesno(
            "Delete Vision Element",
            f"Delete {name}?\n\nThis removes related annual records as well.",
            icon="warning",
        ):
            return

        if self.vps_manager.delete_vision_element(row["id"]):
            self.refresh_all()
        else:
            messagebox.showerror("Delete Failed", "Vision element could not be deleted.")

    def edit_level_vision(self, row: dict, level: str):
        labels = {
            "segment": ("Segment", row.get("segment_name") or "", row.get("segment_id"), row.get("segment_vision_text") or ""),
            "subsegment": ("SubSegment", row.get("subsegment_name") or "", row.get("subsegment_id"), row.get("subsegment_vision_text") or ""),
            "category": ("Category", row.get("category_name") or "", row.get("category_id"), row.get("category_vision_text") or ""),
        }
        if level not in labels:
            return
        level_title, level_name, level_id, current_text = labels[level]
        if not level_id:
            messagebox.showerror("Missing Record", f"Unable to edit {level_title} vision text.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Edit {level_title} Vision")
        self._position_dialog_above_title(dialog, 760, 360)
        dialog.transient(self)
        dialog.grab_set()

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            frame,
            text=f"{level_title}: {level_name}",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))

        name_var = ctk.StringVar(value=level_name)
        name_row = ctk.CTkFrame(frame, fg_color="transparent")
        name_row.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 4))
        name_row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(name_row, text=f"{level_title} Name:", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 8))
        name_entry = ctk.CTkEntry(name_row, textvariable=name_var)
        name_entry.grid(row=0, column=1, sticky="ew")

        text_box = ctk.CTkTextbox(frame, height=180)
        text_box.grid(row=2, column=0, sticky="nsew", padx=8, pady=6)
        if current_text:
            text_box.insert("1.0", current_text)

        context_lines = []
        if level in ("subsegment", "category"):
            context_lines.append(f"Segment Vision: {row.get('segment_vision_text') or '(empty)'}")
        if level == "category":
            context_lines.append(f"SubSegment Vision: {row.get('subsegment_vision_text') or '(empty)'}")
        if context_lines:
            ctk.CTkLabel(
                frame,
                text="\n".join(context_lines),
                anchor="w",
                justify="left",
                text_color=semantic_colors()["muted_text"],
            ).grid(row=3, column=0, sticky="w", padx=8, pady=(0, 4))
            status_row = 4
            action_row = 5
        else:
            status_row = 3
            action_row = 4

        status_label = ctk.CTkLabel(frame, text="", text_color=status_text_color("error"))
        status_label.grid(row=status_row, column=0, sticky="w", padx=8, pady=(2, 4))

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=action_row, column=0, sticky="e", padx=8, pady=(6, 6))

        ctk.CTkButton(actions, text="Cancel", width=90, command=dialog.destroy, **button_style("secondary")).pack(
            side="right", padx=4
        )

        def on_save():
            new_name = name_var.get().strip()
            if not new_name:
                status_label.configure(text=f"{level_title} name is required.")
                return
            value = text_box.get("1.0", "end-1c").strip()
            try:
                if level == "segment":
                    if new_name != level_name:
                        self.vps_manager.rename_vision_segment(level_id, new_name)
                    ok = self.vps_manager.update_segment_vision_text(level_id, value)
                elif level == "subsegment":
                    if new_name != level_name:
                        self.vps_manager.rename_vision_subsegment(level_id, new_name)
                    ok = self.vps_manager.update_subsegment_vision_text(level_id, value)
                else:
                    if new_name != level_name:
                        self.vps_manager.rename_vision_category(level_id, new_name)
                    ok = self.vps_manager.update_category_vision_text(level_id, value)
            except Exception as exc:
                status_label.configure(text=f"Unable to save: {exc}")
                return
            if not ok:
                status_label.configure(text="Unable to save vision text.")
                return
            dialog.destroy()
            self.refresh_list()

        ctk.CTkButton(actions, text="Save", width=90, command=on_save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def refresh_all(self):
        self.reload_dropdowns()
        self.refresh_list()

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"
