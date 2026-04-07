"""Vision Segments admin inside VSP Plan: manage segments, subsegments, categories."""

from tkinter import colorchooser, messagebox
import customtkinter as ctk
from typing import TYPE_CHECKING, Optional

from ..theme import button_style, status_text_color
from ..color_contrast import pick_text_color

if TYPE_CHECKING:
    from ..vps_manager import VPSManager
    from ..app import GetMoreDoneApp


class VisionSegmentsScreen(ctk.CTkFrame):
    TAB_BUTTON_HEIGHT = 32
    ACTION_BUTTON_WIDTH = 120
    VIEW_BUTTON_WIDTH = 160
    SEGMENT_COL_WIDTH = 135
    SUBSEGMENT_COL_WIDTH = 155
    CATEGORY_COL_WIDTH = 125

    def __init__(self, parent, vps_manager: "VPSManager", app: "GetMoreDoneApp"):
        super().__init__(parent)
        self.vps_manager = vps_manager
        self.app = app
        self.active_view = "categories"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(2, weight=1)

        self._create_action_row()
        self._create_view_switcher()
        self._create_lists()
        self.refresh_all()
        self._set_active_view(self.active_view)

    def _create_action_row(self):
        top = ctk.CTkFrame(self.container)
        top.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 6))
        top.grid_columnconfigure(2, weight=1)
        self.primary_action_btn = ctk.CTkButton(
            top,
            text="",
            width=self.ACTION_BUTTON_WIDTH + 40,
            height=self.TAB_BUTTON_HEIGHT,
            command=self._run_primary_action,
            **button_style("primary"),
        )
        self.primary_action_btn.grid(row=0, column=0, padx=(4, 8), pady=6, sticky="w")
        self.refresh_btn = ctk.CTkButton(
            top,
            text="Refresh",
            width=self.ACTION_BUTTON_WIDTH,
            height=self.TAB_BUTTON_HEIGHT,
            command=self._refresh_active_view,
            **button_style("secondary"),
        )
        self.refresh_btn.grid(row=0, column=1, padx=4, pady=6, sticky="w")

    def _create_view_switcher(self):
        switcher = ctk.CTkFrame(self.container, fg_color="transparent")
        switcher.grid(row=1, column=0, sticky="w", padx=8, pady=(0, 8))
        self.view_buttons = {}
        for idx, (key, label) in enumerate((
            ("segments", "Segments"),
            ("subsegments", "SubSegments"),
            ("categories", "Categories"),
        )):
            btn = ctk.CTkButton(
                switcher,
                text=label,
                width=self.VIEW_BUTTON_WIDTH,
                height=self.TAB_BUTTON_HEIGHT,
                command=lambda k=key: self._set_active_view(k),
                **button_style("secondary"),
            )
            btn.grid(row=0, column=idx, padx=(4 if idx == 0 else 0, 4), pady=4, sticky="w")
            self.view_buttons[key] = btn

    def _create_lists(self):
        self.content = ctk.CTkFrame(self.container)
        self.content.grid(row=2, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.seg_list = ctk.CTkScrollableFrame(self.content, label_text="")
        self.sub_list = ctk.CTkScrollableFrame(self.content, label_text="")
        self.cat_list = ctk.CTkScrollableFrame(self.content, label_text="")
        for frame in (self.seg_list, self.sub_list, self.cat_list):
            frame.grid_columnconfigure(0, weight=1)

    def _set_active_view(self, view: str):
        self.active_view = view
        mapping = {
            "segments": self.seg_list,
            "subsegments": self.sub_list,
            "categories": self.cat_list,
        }
        for key, frame in mapping.items():
            if key == view:
                frame.grid(row=0, column=0, sticky="nsew")
            else:
                frame.grid_forget()
        self._update_view_buttons()
        self._update_primary_action_button()

    def _update_view_buttons(self):
        for key, button in self.view_buttons.items():
            button.configure(**button_style("primary" if key == self.active_view else "secondary"))

    def _update_primary_action_button(self):
        labels = {
            "segments": "+ New Segment",
            "subsegments": "+ New SubSegment",
            "categories": "+ New Category",
        }
        self.primary_action_btn.configure(text=labels[self.active_view])

    def _run_primary_action(self):
        if self.active_view == "segments":
            self.new_segment()
        elif self.active_view == "subsegments":
            self.new_subsegment()
        else:
            self.new_category()

    def _refresh_active_view(self):
        if self.active_view == "segments":
            self.refresh_segments()
        elif self.active_view == "subsegments":
            self.refresh_subsegments()
        else:
            self.refresh_categories()

    def refresh_all(self):
        self.refresh_segments()
        self.refresh_subsegments()
        self.refresh_categories()

    def refresh_segments(self):
        for w in self.seg_list.winfo_children():
            w.destroy()
        rows = self.vps_manager.get_vision_segments_admin()
        for i, row in enumerate(rows):
            frame = ctk.CTkFrame(self.seg_list)
            frame.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            frame.grid_columnconfigure(1, minsize=self.SEGMENT_COL_WIDTH)
            frame.grid_columnconfigure(2, weight=1)
            seg_chip = ctk.CTkLabel(
                frame,
                text=f" {self._clip_label(row.get('name') or '', 15)} ",
                fg_color=row.get("color_hex") or "#334155",
                text_color=pick_text_color(row.get("color_hex") or "#334155"),
                corner_radius=6,
                width=self.SEGMENT_COL_WIDTH - 12,
                anchor="w",
            )
            seg_chip.grid(row=0, column=1, padx=6, pady=6, sticky="w")
            ctk.CTkLabel(
                frame,
                text=row.get("description") or "",
                anchor="w",
            ).grid(row=0, column=2, sticky="w", padx=6, pady=6)
            ctk.CTkButton(frame, text="Edit", width=64, command=lambda r=row: self.edit_segment(r), **button_style("secondary")).grid(row=0, column=3, padx=4)
            ctk.CTkButton(frame, text="Delete", width=64, command=lambda r=row: self.delete_segment(r), **button_style("danger")).grid(row=0, column=4, padx=4)

    def refresh_subsegments(self):
        for w in self.sub_list.winfo_children():
            w.destroy()
        rows = self.vps_manager.get_vision_subsegments()
        segment_colors = self.vps_manager.get_segment_color_map()
        for i, row in enumerate(rows):
            frame = ctk.CTkFrame(self.sub_list)
            frame.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            frame.grid_columnconfigure(1, minsize=self.SEGMENT_COL_WIDTH)
            frame.grid_columnconfigure(2, minsize=self.SUBSEGMENT_COL_WIDTH)
            frame.grid_columnconfigure(3, weight=1)
            segment_color = self.vps_manager.resolve_segment_color(
                row.get("segment_name") or "",
                segment_colors,
            )
            seg_chip = ctk.CTkLabel(
                frame,
                text=f" {self._clip_label(row.get('segment_name') or '', 15)} ",
                fg_color=segment_color,
                text_color=pick_text_color(segment_color),
                corner_radius=6,
                width=self.SEGMENT_COL_WIDTH - 12,
                anchor="w",
            )
            seg_chip.grid(row=0, column=1, padx=6, pady=6, sticky="w")
            sub_chip = ctk.CTkLabel(
                frame,
                text=f" {self._clip_label(row.get('name') or '', 20)} ",
                fg_color=row.get("color_hex") or segment_color,
                text_color=pick_text_color(row.get("color_hex") or segment_color),
                corner_radius=6,
                width=self.SUBSEGMENT_COL_WIDTH - 12,
                anchor="w",
            )
            sub_chip.grid(row=0, column=2, padx=6, pady=6, sticky="w")
            ctk.CTkLabel(
                frame,
                text=row.get("description") or "",
                anchor="w",
            ).grid(row=0, column=3, sticky="w", padx=6, pady=6)
            ctk.CTkButton(frame, text="Edit", width=64, command=lambda r=row: self.edit_subsegment(r), **button_style("secondary")).grid(row=0, column=4, padx=4)
            ctk.CTkButton(frame, text="Delete", width=64, command=lambda r=row: self.delete_subsegment(r), **button_style("danger")).grid(row=0, column=5, padx=4)

    def refresh_categories(self):
        for w in self.cat_list.winfo_children():
            w.destroy()
        rows = self.vps_manager.get_vision_categories()
        segment_colors = self.vps_manager.get_segment_color_map()
        subsegment_colors = {
            (
                (r.get("segment_name", "") or "").strip().lower(),
                (r.get("name", "") or "").strip().lower(),
            ): (r.get("color_hex") or "")
            for r in self.vps_manager.get_vision_subsegments()
        }
        for i, row in enumerate(rows):
            frame = ctk.CTkFrame(self.cat_list)
            frame.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            frame.grid_columnconfigure(1, minsize=self.SEGMENT_COL_WIDTH)
            frame.grid_columnconfigure(2, minsize=self.SUBSEGMENT_COL_WIDTH)
            frame.grid_columnconfigure(3, minsize=self.CATEGORY_COL_WIDTH)
            frame.grid_columnconfigure(4, weight=1)
            segment_color = self.vps_manager.resolve_segment_color(
                row.get("segment_name") or "",
                segment_colors,
            )
            subsegment_name = row.get("subsegment_name") or ""
            subsegment_color = subsegment_colors.get(
                ((row.get("segment_name") or "").strip().lower(), subsegment_name.strip().lower()),
                "",
            ) or segment_color
            seg_chip = ctk.CTkLabel(
                frame,
                text=f" {self._clip_label(row.get('segment_name') or '', 15)} ",
                fg_color=segment_color,
                text_color=pick_text_color(segment_color),
                corner_radius=6,
                width=self.SEGMENT_COL_WIDTH - 12,
                anchor="w",
            )
            seg_chip.grid(row=0, column=1, padx=6, pady=6, sticky="w")
            sub_chip = ctk.CTkLabel(
                frame,
                text=f" {self._clip_label(subsegment_name, 20)} ",
                fg_color=subsegment_color,
                text_color=pick_text_color(subsegment_color),
                corner_radius=6,
                width=self.SUBSEGMENT_COL_WIDTH - 12,
                anchor="w",
            )
            sub_chip.grid(row=0, column=2, padx=6, pady=6, sticky="w")
            cat_chip = ctk.CTkLabel(
                frame,
                text=f" {self._clip_label(row.get('name') or '', 15)} ",
                fg_color=row.get("color_hex") or subsegment_color,
                text_color=pick_text_color(row.get("color_hex") or subsegment_color),
                corner_radius=6,
                width=self.CATEGORY_COL_WIDTH - 12,
                anchor="w",
            )
            cat_chip.grid(row=0, column=3, padx=6, pady=6, sticky="w")
            ctk.CTkLabel(
                frame,
                text=row.get("description") or "",
                anchor="w",
            ).grid(row=0, column=4, sticky="w", padx=6, pady=6)
            ctk.CTkButton(frame, text="Edit", width=64, command=lambda r=row: self.edit_category(r), **button_style("secondary")).grid(row=0, column=5, padx=4)
            ctk.CTkButton(frame, text="Delete", width=64, command=lambda r=row: self.delete_category(r), **button_style("danger")).grid(row=0, column=6, padx=4)

    @staticmethod
    def _clip_label(value: str, limit: int) -> str:
        text = (value or "").strip()
        if len(text) <= limit:
            return text
        return text[:limit - 1].rstrip() + "…"

    def _color_input(self, parent, initial: str):
        var = ctk.StringVar(value=initial)
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid_columnconfigure(1, weight=1)
        swatch = ctk.CTkFrame(row, width=20, height=20, fg_color=initial)
        swatch.grid(row=0, column=0, padx=(0, 6))
        entry = ctk.CTkEntry(row, textvariable=var)
        entry.grid(row=0, column=1, sticky="ew")

        def pick():
            picked = colorchooser.askcolor(initialcolor=var.get(), title="Pick Color")
            if picked[1]:
                var.set(picked[1])
                swatch.configure(fg_color=picked[1])

        ctk.CTkButton(row, text="Pick", width=64, command=pick, **button_style("secondary")).grid(row=0, column=2, padx=(6, 0))
        return row, var

    def new_segment(self):
        self.edit_segment(None)

    def edit_segment(self, row: Optional[dict]):
        d = ctk.CTkToplevel(self)
        d.title("Segment")
        d.geometry("700x440")
        d.transient(self)
        d.grab_set()
        f = ctk.CTkFrame(d)
        f.pack(fill="both", expand=True, padx=12, pady=12)
        f.grid_columnconfigure(1, weight=1)
        name = ctk.StringVar(value=(row or {}).get("name", ""))
        desc = ctk.StringVar(value=(row or {}).get("description", ""))
        vision = ctk.StringVar(value=(row or {}).get("vision_text", ""))
        active = ctk.BooleanVar(value=bool((row or {}).get("is_active", 1)))
        ctk.CTkLabel(f, text="Name:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(f, textvariable=name).grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="What it is:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(f, textvariable=desc).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="Color:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        color_row, color = self._color_input(f, (row or {}).get("color_hex", "#334155"))
        color_row.grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkCheckBox(f, text="Active", variable=active).grid(row=3, column=1, sticky="w", padx=8, pady=6)
        ctk.CTkLabel(f, text="Vision:").grid(row=4, column=0, sticky="nw", padx=8, pady=6)
        vision_box = ctk.CTkTextbox(f, height=170)
        vision_box.grid(row=4, column=1, sticky="nsew", padx=8, pady=6)
        if vision.get():
            vision_box.insert("1.0", vision.get())
        f.grid_rowconfigure(4, weight=1)
        msg = ctk.CTkLabel(f, text="", text_color=status_text_color("error"))
        msg.grid(row=5, column=0, columnspan=2, sticky="w", padx=8)
        act = ctk.CTkFrame(f, fg_color="transparent")
        act.grid(row=6, column=0, columnspan=2, sticky="e", padx=8, pady=8)
        ctk.CTkButton(act, text="Cancel", command=d.destroy, width=84, **button_style("secondary")).pack(side="right", padx=4)

        def save():
            try:
                if row:
                    self.vps_manager.update_vision_segment_admin(
                        row["id"], name.get(), desc.get(), color.get(), vision_box.get("1.0", "end-1c"), active.get()
                    )
                else:
                    self.vps_manager.create_vision_segment_admin(
                        name.get(), desc.get(), color.get(), vision_box.get("1.0", "end-1c"), active.get()
                    )
            except Exception as exc:
                msg.configure(text=str(exc))
                return
            d.destroy()
            self.refresh_all()

        ctk.CTkButton(act, text="Save", command=save, width=84, **button_style("primary")).pack(side="right", padx=4)

    def delete_segment(self, row: dict):
        if not messagebox.askyesno("Delete Segment", f"Delete {row.get('name')}?", icon="warning"):
            return
        ok = self.vps_manager.delete_vision_segment_admin(row["id"])
        if not ok:
            messagebox.showerror("Delete Failed", "Segment has dependent records. Remove children first.")
        self.refresh_all()

    def new_subsegment(self):
        self.edit_subsegment(None)

    def edit_subsegment(self, row: Optional[dict]):
        segments = self.vps_manager.get_vision_segments_admin()
        if not segments:
            messagebox.showwarning("No Segments", "Create a segment first.")
            return
        d = ctk.CTkToplevel(self)
        d.title("SubSegment")
        d.geometry("700x430")
        d.transient(self)
        d.grab_set()
        f = ctk.CTkFrame(d)
        f.pack(fill="both", expand=True, padx=12, pady=12)
        f.grid_columnconfigure(1, weight=1)
        seg_var = ctk.StringVar(value=(row or {}).get("segment_name", segments[0]["name"]))
        name = ctk.StringVar(value=(row or {}).get("name", ""))
        desc = ctk.StringVar(value=(row or {}).get("description", ""))
        ctk.CTkLabel(f, text="Segment:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        seg_combo = ctk.CTkComboBox(f, values=[s["name"] for s in segments], variable=seg_var, state="readonly")
        seg_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="Name:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(f, textvariable=name).grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="What it is:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(f, textvariable=desc).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        default_color = self.vps_manager.default_subsegment_color_for_segment(seg_var.get())
        ctk.CTkLabel(f, text="Color:").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        color_row, color = self._color_input(f, (row or {}).get("color_hex", default_color))
        color_row.grid(row=3, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="Vision:").grid(row=4, column=0, sticky="nw", padx=8, pady=6)
        vision_box = ctk.CTkTextbox(f, height=160)
        vision_box.grid(row=4, column=1, sticky="nsew", padx=8, pady=6)
        if (row or {}).get("vision_text"):
            vision_box.insert("1.0", row["vision_text"])
        f.grid_rowconfigure(4, weight=1)
        msg = ctk.CTkLabel(f, text="", text_color=status_text_color("error"))
        msg.grid(row=5, column=0, columnspan=2, sticky="w", padx=8)
        act = ctk.CTkFrame(f, fg_color="transparent")
        act.grid(row=6, column=0, columnspan=2, sticky="e", padx=8, pady=8)
        ctk.CTkButton(act, text="Cancel", command=d.destroy, width=84, **button_style("secondary")).pack(side="right", padx=4)

        def save():
            try:
                if row:
                    self.vps_manager.update_vision_subsegment(
                        row["id"], name.get(), color.get(), desc.get(), vision_box.get("1.0", "end-1c")
                    )
                else:
                    sub_id = self.vps_manager.create_vision_subsegment(seg_var.get(), name.get(), color.get())
                    self.vps_manager.update_vision_subsegment(
                        sub_id, name.get(), color.get(), desc.get(), vision_box.get("1.0", "end-1c")
                    )
            except Exception as exc:
                msg.configure(text=str(exc))
                return
            d.destroy()
            self.refresh_all()

        ctk.CTkButton(act, text="Save", command=save, width=84, **button_style("primary")).pack(side="right", padx=4)

    def delete_subsegment(self, row: dict):
        if not messagebox.askyesno("Delete SubSegment", f"Delete {row.get('name')}?", icon="warning"):
            return
        self.vps_manager.delete_vision_subsegment(row["id"])
        self.refresh_all()

    def new_category(self):
        self.edit_category(None)

    def edit_category(self, row: Optional[dict]):
        segments = self.vps_manager.get_vision_segments_admin()
        if not segments:
            messagebox.showwarning("No Segments", "Create a segment first.")
            return
        d = ctk.CTkToplevel(self)
        d.title("Category")
        d.geometry("720x470")
        d.transient(self)
        d.grab_set()
        f = ctk.CTkFrame(d)
        f.pack(fill="both", expand=True, padx=12, pady=12)
        f.grid_columnconfigure(1, weight=1)
        seg_var = ctk.StringVar(value=(row or {}).get("segment_name", segments[0]["name"]))
        sub_var = ctk.StringVar(value=(row or {}).get("subsegment_name", ""))
        name = ctk.StringVar(value=(row or {}).get("name", ""))
        desc = ctk.StringVar(value=(row or {}).get("description", ""))
        ctk.CTkLabel(f, text="Segment:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        seg_combo = ctk.CTkComboBox(f, values=[s["name"] for s in segments], variable=seg_var, state="readonly")
        seg_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="SubSegment:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        sub_combo = ctk.CTkComboBox(f, values=[""], variable=sub_var, state="readonly")
        sub_combo.grid(row=1, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="Name:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(f, textvariable=name).grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="What it is:").grid(row=3, column=0, sticky="w", padx=8, pady=6)
        ctk.CTkEntry(f, textvariable=desc).grid(row=3, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="Color:").grid(row=4, column=0, sticky="w", padx=8, pady=6)
        color_row, color = self._color_input(f, (row or {}).get("color_hex", "#94A3B8"))
        color_row.grid(row=4, column=1, sticky="ew", padx=8, pady=6)
        ctk.CTkLabel(f, text="Vision:").grid(row=5, column=0, sticky="nw", padx=8, pady=6)
        vision_box = ctk.CTkTextbox(f, height=160)
        vision_box.grid(row=5, column=1, sticky="nsew", padx=8, pady=6)
        if (row or {}).get("vision_text"):
            vision_box.insert("1.0", row["vision_text"])
        f.grid_rowconfigure(5, weight=1)
        msg = ctk.CTkLabel(f, text="", text_color=status_text_color("error"))
        msg.grid(row=6, column=0, columnspan=2, sticky="w", padx=8)
        act = ctk.CTkFrame(f, fg_color="transparent")
        act.grid(row=7, column=0, columnspan=2, sticky="e", padx=8, pady=8)
        ctk.CTkButton(act, text="Cancel", command=d.destroy, width=84, **button_style("secondary")).pack(side="right", padx=4)

        def load_subs(*_args):
            subs = self.vps_manager.get_vision_subsegments(seg_var.get())
            names = [s["name"] for s in subs] or [""]
            sub_combo.configure(values=names)
            if sub_var.get() not in names:
                sub_var.set(names[0])

        seg_combo.configure(command=lambda _v: load_subs())
        load_subs()

        def save():
            try:
                if row:
                    self.vps_manager.update_vision_category(
                        row["id"], name.get(), color.get(), desc.get(), vision_box.get("1.0", "end-1c")
                    )
                else:
                    cat_id = self.vps_manager.create_vision_category(
                        seg_var.get(), sub_var.get(), name.get(), color.get(), desc.get(), vision_box.get("1.0", "end-1c")
                    )
                    if not cat_id:
                        raise ValueError("Failed to create category.")
            except Exception as exc:
                msg.configure(text=str(exc))
                return
            d.destroy()
            self.refresh_all()

        ctk.CTkButton(act, text="Save", command=save, width=84, **button_style("primary")).pack(side="right", padx=4)

    def delete_category(self, row: dict):
        if not messagebox.askyesno("Delete Category", f"Delete {row.get('name')}?", icon="warning"):
            return
        self.vps_manager.delete_vision_category(row["id"])
        self.refresh_all()
