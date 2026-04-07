"""VSP segment-management support for the Settings screen."""

from __future__ import annotations

import customtkinter as ctk
from tkinter import colorchooser, messagebox

from ..theme import button_style, combo_box_style, semantic_colors, status_text_color


class SettingsVSPSegmentsMixin:
    def create_vps_segments_section(self, parent=None):
        """Create VSP Life Segments management section."""
        if parent is None:
            parent = self

        section = ctk.CTkFrame(parent)
        section.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        section.grid_columnconfigure(0, weight=1)
        section.grid_columnconfigure(1, weight=1)
        section.grid_rowconfigure(2, weight=1)

        # Section title
        title_frame = ctk.CTkFrame(section)
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        title_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_frame,
            text="VSP Life Segments",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=10)

        ctk.CTkLabel(
            title_frame,
            text="Manage your life segments for Vision Strategy Plan",
            font=ctk.CTkFont(size=11),
            text_color=status_text_color("muted")
        ).pack(side="left", padx=10)

        # Buttons frame
        buttons_frame = ctk.CTkFrame(section)
        buttons_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

        ctk.CTkButton(
            buttons_frame,
            text="+ New Segment",
            command=self.create_new_segment,
            width=150,
            **button_style("primary"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="+ New SubSegment",
            command=self.create_new_subsegment,
            width=160,
            **button_style("secondary"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            buttons_frame,
            text="↻ Refresh",
            command=lambda: (self.refresh_segments_list(), self.refresh_subsegments_list()),
            width=100,
            **button_style("secondary"),
        ).pack(side="left", padx=5)

        # Left column: Segments
        segments_panel = ctk.CTkFrame(section)
        segments_panel.grid(row=2, column=0, sticky="nsew", padx=(10, 5), pady=10)
        segments_panel.grid_columnconfigure(0, weight=1)
        segments_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            segments_panel,
            text="Segments",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 6))

        self.segments_scroll_frame = ctk.CTkScrollableFrame(segments_panel, label_text="")
        self.segments_scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.segments_scroll_frame.grid_columnconfigure(0, weight=1)

        # Right column: Subsegments
        subsegments_panel = ctk.CTkFrame(section)
        subsegments_panel.grid(row=2, column=1, sticky="nsew", padx=(5, 10), pady=10)
        subsegments_panel.grid_columnconfigure(1, weight=1)
        subsegments_panel.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            subsegments_panel,
            text="Subsegments",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(10, 5), pady=(10, 6))
        ctk.CTkLabel(subsegments_panel, text="Segment Filter:").grid(
            row=0, column=1, sticky="w", padx=(0, 6), pady=(10, 6)
        )
        self.subsegment_filter_var = ctk.StringVar(value="All")
        self.subsegment_filter_combo = ctk.CTkComboBox(
            subsegments_panel,
            values=["All"],
            variable=self.subsegment_filter_var,
            command=lambda _v: self.refresh_subsegments_list(),
            width=220,
            **combo_box_style(),
        )
        self.subsegment_filter_combo.grid(row=0, column=2, sticky="w", padx=(0, 10), pady=(10, 6))

        self.subsegments_scroll_frame = ctk.CTkScrollableFrame(subsegments_panel, label_text="")
        self.subsegments_scroll_frame.grid(row=1, column=0, columnspan=3, sticky="nsew", padx=10, pady=(0, 10))
        self.subsegments_scroll_frame.grid_columnconfigure(0, weight=1)

        # Load lists
        self.refresh_segments_list()
        self.refresh_subsegments_list()

    def refresh_segments_list(self):
        """Refresh the segments list display."""
        if not hasattr(self, "segments_scroll_frame"):
            return
        # Clear current widgets
        for widget in self.segments_scroll_frame.winfo_children():
            widget.destroy()

        # Get all segments (including inactive)
        segments = self.app.vps_manager.get_all_segments(active_only=False)
        if hasattr(self, "subsegment_filter_combo"):
            names = ["All"] + [s["name"] for s in segments]
            self.subsegment_filter_combo.configure(values=names)
            if self.subsegment_filter_var.get() not in names:
                self.subsegment_filter_var.set("All")

        if not segments:
            label = ctk.CTkLabel(
                self.segments_scroll_frame,
                text="No life segments defined. Click '+ New Segment' to create one.",
                font=ctk.CTkFont(size=12),
                text_color=status_text_color("muted")
            )
            label.grid(row=0, column=0, pady=20)
            return

        # Display each segment
        for idx, segment in enumerate(segments):
            self.create_segment_row(segment, idx)

    def create_segment_row(self, segment: dict, row: int):
        """Create a row displaying a segment with edit/delete buttons."""
        frame = ctk.CTkFrame(self.segments_scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=5, padx=5)
        frame.grid_columnconfigure(2, weight=1)

        # Color indicator
        color_frame = ctk.CTkFrame(
            frame, width=40, height=40, fg_color=segment['color_hex'])
        color_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=5)
        color_frame.grid_propagate(False)

        # Segment name
        name_label = ctk.CTkLabel(
            frame,
            text=f"🎯 {segment['name']}",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w"
        )
        name_label.grid(row=0, column=1, columnspan=2,
                        sticky="w", padx=10, pady=(5, 0))

        # Segment description
        desc_label = ctk.CTkLabel(
            frame,
            text=segment['description'] or "No description",
            font=ctk.CTkFont(size=11),
            text_color=status_text_color("muted"),
            anchor="w"
        )
        desc_label.grid(row=1, column=1, columnspan=2,
                        sticky="w", padx=10, pady=(0, 5))

        # Status badge
        status_text = "✓ Active" if segment['is_active'] else "○ Inactive"
        status_color = status_text_color("success") if segment['is_active'] else status_text_color("muted")
        status_label = ctk.CTkLabel(
            frame,
            text=status_text,
            font=ctk.CTkFont(size=10),
            text_color=status_color
        )
        status_label.grid(row=0, column=3, padx=5, pady=5)

        # Edit button
        edit_btn = ctk.CTkButton(
            frame,
            text="✎ Edit",
            command=lambda s=segment: self.edit_segment(s),
            width=80,
            **button_style("secondary"),
        )
        edit_btn.grid(row=0, column=4, rowspan=2, padx=5, pady=5)

        # Delete button
        delete_btn = ctk.CTkButton(
            frame,
            text="🗑 Delete",
            command=lambda s=segment: self.delete_segment(s),
            **button_style("danger"),
            width=80
        )
        delete_btn.grid(row=0, column=5, rowspan=2, padx=5, pady=5)

    def refresh_subsegments_list(self):
        """Refresh subsegments list (right column)."""
        if not hasattr(self, "subsegments_scroll_frame"):
            return
        for widget in self.subsegments_scroll_frame.winfo_children():
            widget.destroy()

        selected_segment = (self.subsegment_filter_var.get() or "All").strip()
        segment_filter = None if selected_segment in ("", "All") else selected_segment
        rows = self.app.vps_manager.get_vision_subsegments(segment_name=segment_filter)

        if not rows:
            ctk.CTkLabel(
                self.subsegments_scroll_frame,
                text="No subsegments found. Create them via Vision Elements or edit existing records.",
                font=ctk.CTkFont(size=12),
                text_color=status_text_color("muted"),
            ).grid(row=0, column=0, pady=20, padx=10, sticky="w")
            return

        for idx, row in enumerate(rows):
            self.create_subsegment_row(row, idx)

    def create_subsegment_row(self, subsegment: dict, row: int):
        """Render a subsegment row with color controls."""
        frame = ctk.CTkFrame(self.subsegments_scroll_frame)
        frame.grid(row=row, column=0, sticky="ew", pady=4, padx=5)
        frame.grid_columnconfigure(1, weight=1)

        color_hex = subsegment.get("color_hex") or "#64748B"
        color_frame = ctk.CTkFrame(frame, width=26, height=26, fg_color=color_hex)
        color_frame.grid(row=0, column=0, rowspan=2, padx=10, pady=8)
        color_frame.grid_propagate(False)

        ctk.CTkLabel(
            frame,
            text=subsegment.get("name") or "(unnamed subsegment)",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 0))

        ctk.CTkLabel(
            frame,
            text=f"Segment: {subsegment.get('segment_name') or '-'}",
            font=ctk.CTkFont(size=11),
            text_color=status_text_color("muted"),
            anchor="w",
        ).grid(row=1, column=1, sticky="w", padx=8, pady=(0, 6))

        ctk.CTkButton(
            frame,
            text="Pick Color",
            width=96,
            command=lambda s=subsegment: self.pick_subsegment_color(s),
            **button_style("secondary"),
        ).grid(row=0, column=2, rowspan=2, padx=6, pady=6)

    def pick_subsegment_color(self, subsegment: dict):
        """Pick and save one subsegment color."""
        initial = subsegment.get("color_hex") or "#64748B"
        picked = colorchooser.askcolor(initialcolor=initial, title="Choose Subsegment Color")
        new_color = (picked[1] or "").strip()
        if not new_color:
            return
        try:
            self.app.vps_manager.update_vision_subsegment_color(subsegment["id"], new_color)
            self.refresh_subsegments_list()
        except Exception as exc:
            messagebox.showerror("Color Update Failed", str(exc))

    def create_new_segment(self):
        """Open dialog to create a new segment."""
        from .vps_segment_editor import VPSSegmentEditorDialog
        dialog = VPSSegmentEditorDialog(self, self.app.vps_manager)
        self.wait_window(dialog)
        self.refresh_segments_list()
        self.refresh_subsegments_list()

    def create_new_subsegment(self):
        """Create a subsegment under an existing Settings life segment."""
        segments = self.app.vps_manager.get_all_segments(active_only=False)
        if not segments:
            messagebox.showwarning("No Segments", "Create a life segment first.")
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("New SubSegment")
        dialog.geometry("520x250")
        dialog.transient(self)
        dialog.grab_set()

        segment_var = ctk.StringVar(value=segments[0]["name"])
        name_var = ctk.StringVar(value="")
        color_var = ctk.StringVar(value=self.app.vps_manager.default_subsegment_color_for_segment(segments[0]["name"]))

        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame, text="Segment:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        seg_combo = ctk.CTkComboBox(frame, variable=segment_var, values=[s["name"] for s in segments], **combo_box_style())
        seg_combo.grid(row=0, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="SubSegment:").grid(row=1, column=0, sticky="w", padx=8, pady=6)
        name_entry = ctk.CTkEntry(frame, textvariable=name_var)
        name_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=6)

        ctk.CTkLabel(frame, text="Color:").grid(row=2, column=0, sticky="w", padx=8, pady=6)
        color_row = ctk.CTkFrame(frame, fg_color="transparent")
        color_row.grid(row=2, column=1, sticky="ew", padx=8, pady=6)
        color_row.grid_columnconfigure(1, weight=1)

        swatch = ctk.CTkFrame(color_row, width=24, height=24, fg_color=color_var.get())
        swatch.grid(row=0, column=0, padx=(0, 8))
        swatch.grid_propagate(False)

        color_entry = ctk.CTkEntry(color_row, textvariable=color_var)
        color_entry.grid(row=0, column=1, sticky="ew")

        def recalc_default(*_args):
            default = self.app.vps_manager.default_subsegment_color_for_segment(segment_var.get().strip())
            color_var.set(default)
            swatch.configure(fg_color=default)

        def pick_color():
            picked = colorchooser.askcolor(initialcolor=color_var.get(), title="Choose SubSegment Color")
            if picked[1]:
                color_var.set(picked[1])
                swatch.configure(fg_color=picked[1])

        seg_combo.configure(command=lambda _v: recalc_default())
        ctk.CTkButton(color_row, text="Pick", width=70, command=pick_color, **button_style("secondary")).grid(
            row=0, column=2, padx=(8, 0)
        )

        status = self._status_label(frame, text="", level="error")
        status.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(4, 4))

        actions = ctk.CTkFrame(frame, fg_color="transparent")
        actions.grid(row=4, column=0, columnspan=2, sticky="e", padx=8, pady=(8, 4))
        ctk.CTkButton(actions, text="Cancel", width=90, command=dialog.destroy, **button_style("secondary")).pack(
            side="right", padx=4
        )

        def on_save():
            seg = segment_var.get().strip()
            sub = name_var.get().strip()
            col = color_var.get().strip()
            if not seg or not sub:
                self._set_status(status, "Segment and SubSegment are required.", "error")
                return
            try:
                self.app.vps_manager.create_vision_subsegment(seg, sub, col)
            except Exception as exc:
                self._set_status(status, f"Unable to save: {exc}", "error")
                return
            dialog.destroy()
            self.refresh_subsegments_list()

        ctk.CTkButton(actions, text="Save", width=90, command=on_save, **button_style("primary")).pack(
            side="right", padx=4
        )

    def edit_segment(self, segment: dict):
        """Open dialog to edit a segment."""
        from .vps_segment_editor import VPSSegmentEditorDialog
        dialog = VPSSegmentEditorDialog(self, self.app.vps_manager, segment)
        self.wait_window(dialog)
        self.refresh_segments_list()
        self.refresh_subsegments_list()

    def delete_segment(self, segment: dict):
        """Delete a segment after comprehensive check and typed confirmation."""
        from tkinter import messagebox
        import customtkinter as ctk

        # First check: Get comprehensive count of all related records
        success, counts = self.app.vps_manager.delete_segment(segment['id'])

        if not success:
            # Has child records - show detailed breakdown and require typed confirmation
            total = sum(counts.values())

            # Build detailed message
            breakdown = "\n".join(
                [f"  • {label}: {count}" for label, count in counts.items()])

            warning_msg = (
                f"⚠️  CASCADE DELETE WARNING  ⚠️\n\n"
                f"Segment '{segment['name']}' has {total} linked records:\n\n"
                f"{breakdown}\n\n"
                f"If you proceed, ALL {total} records will be PERMANENTLY DELETED.\n\n"
                f"This includes all child records in the hierarchy:\n"
                f"Visions → Plans → Initiatives → Tactics → Actions\n\n"
                f"⚠️  THIS CANNOT BE UNDONE  ⚠️\n\n"
                f"To proceed with deletion, type exactly:\n"
                f"yes proceed"
            )

            # Create custom dialog for typed confirmation
            dialog = ctk.CTkToplevel(self)
            dialog.title("Confirm Cascade Deletion")
            dialog.geometry("600x500")
            dialog.transient(self)
            dialog.grab_set()

            # Warning message
            warning_frame = ctk.CTkFrame(dialog, fg_color=semantic_colors()["danger"])
            warning_frame.pack(fill="x", padx=20, pady=(20, 10))

            ctk.CTkLabel(
                warning_frame,
                text=warning_msg,
                justify="left",
                text_color=semantic_colors()["on_danger"],
                font=("Arial", 12)
            ).pack(padx=20, pady=20)

            # Typed confirmation entry
            entry_frame = ctk.CTkFrame(dialog)
            entry_frame.pack(fill="x", padx=20, pady=10)

            ctk.CTkLabel(
                entry_frame,
                text="Type 'yes proceed' to confirm:",
                font=("Arial", 12, "bold")
            ).pack(anchor="w", padx=10, pady=(10, 5))

            confirmation_var = ctk.StringVar()
            entry = ctk.CTkEntry(
                entry_frame,
                textvariable=confirmation_var,
                width=400,
                height=35,
                font=("Arial", 12)
            )
            entry.pack(padx=10, pady=(0, 10))
            entry.focus()

            # Status label
            status_label = self._status_label(dialog, text="", level="error", font=("Arial", 11))
            status_label.pack(pady=5)

            # Button frame
            btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
            btn_frame.pack(pady=20)

            def proceed_deletion():
                typed_text = confirmation_var.get().strip()
                if typed_text == "yes proceed":
                    dialog.destroy()
                    # Actually delete by clearing all records first
                    try:
                        # Since we can't delete with children, we need to tell user
                        # to remove records manually
                        messagebox.showwarning(
                            "Manual Deletion Required",
                            f"To delete segment '{segment['name']}':\n\n"
                            f"1. Go to VSP Planning screen\n"
                            f"2. Delete all {total} records in this segment\n"
                            f"   (Start with Week Actions, work up to TL Visions)\n"
                            f"3. Return here to delete the empty segment\n\n"
                            f"This manual process prevents accidental data loss."
                        )
                    except Exception as e:
                        messagebox.showerror(
                            "Error", f"Deletion failed: {str(e)}")
                else:
                    status_label.configure(
                        text="❌ Incorrect confirmation text. Type exactly: yes proceed"
                    )

            def cancel_deletion():
                dialog.destroy()

            # Buttons
            ctk.CTkButton(
                btn_frame,
                text="Cancel",
                command=cancel_deletion,
                width=120,
                **button_style("secondary"),
            ).pack(side="left", padx=5)

            ctk.CTkButton(
                btn_frame,
                text="Proceed with Deletion",
                command=proceed_deletion,
                width=180,
                **button_style("danger"),
            ).pack(side="left", padx=5)

            # Bind Enter key
            entry.bind('<Return>', lambda e: proceed_deletion())
            entry.bind('<Escape>', lambda e: cancel_deletion())

        else:
            # No child records - safe to delete with simple confirmation
            response = messagebox.askyesno(
                "Confirm Deletion",
                f"Delete segment '{segment['name']}'?\n\n"
                f"This segment has no linked records.",
                icon='warning'
            )

            if response:
                messagebox.showinfo(
                    "Success",
                    f"Segment '{segment['name']}' has been deleted."
                )
                self.refresh_segments_list()
                self.refresh_subsegments_list()
