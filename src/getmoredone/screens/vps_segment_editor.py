"""
VPS Segment Editor Dialog for creating and editing life segments.
"""

import customtkinter as ctk
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from tkinter import messagebox, colorchooser

if TYPE_CHECKING:
    from ..vps_manager import VPSManager


class VPSSegmentEditorDialog(ctk.CTkToplevel):
    """Dialog for creating/editing VPS life segments with color picker."""

    def __init__(self, parent, vps_manager: 'VPSManager', segment: Optional[dict] = None):
        super().__init__(parent)

        self.vps_manager = vps_manager
        self.segment = segment
        self.selected_color = segment['color_hex'] if segment else "#4A90E2"

        # Set title
        if segment:
            self.title(f"Edit Life Segment: {segment['name']}")
        else:
            self.title("New Life Segment")

        self.geometry("500x400")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Load data if editing
        if self.segment:
            self.load_segment_data()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        main_frame.grid_columnconfigure(1, weight=1)

        row = 0

        # Name
        ctk.CTkLabel(main_frame, text="Name *", anchor="w").grid(
            row=row, column=0, sticky="w", padx=5, pady=5
        )
        self.name_entry = ctk.CTkEntry(main_frame, width=300)
        self.name_entry.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        row += 1

        # Description
        ctk.CTkLabel(main_frame, text="Description", anchor="w").grid(
            row=row, column=0, sticky="nw", padx=5, pady=5
        )
        self.description_text = ctk.CTkTextbox(
            main_frame, height=80, width=300)
        self.description_text.grid(
            row=row, column=1, sticky="ew", padx=5, pady=5)
        row += 1

        # Color picker
        ctk.CTkLabel(main_frame, text="Color *", anchor="w").grid(
            row=row, column=0, sticky="w", padx=5, pady=5
        )

        color_frame = ctk.CTkFrame(main_frame)
        color_frame.grid(row=row, column=1, sticky="ew", padx=5, pady=5)
        color_frame.grid_columnconfigure(1, weight=1)

        # Color preview
        self.color_preview = ctk.CTkFrame(
            color_frame,
            width=50,
            height=30,
            fg_color=self.selected_color
        )
        self.color_preview.grid(row=0, column=0, padx=(0, 10))
        self.color_preview.grid_propagate(False)

        # Color code entry
        self.color_entry = ctk.CTkEntry(color_frame, width=100)
        self.color_entry.insert(0, self.selected_color)
        self.color_entry.grid(row=0, column=1, sticky="w")

        # Color picker button
        ctk.CTkButton(
            color_frame,
            text="🎨 Pick Color",
            command=self.pick_color,
            width=120
        ).grid(row=0, column=2, padx=(10, 0))
        row += 1

        # Order index
        ctk.CTkLabel(main_frame, text="Display Order", anchor="w").grid(
            row=row, column=0, sticky="w", padx=5, pady=5
        )
        self.order_entry = ctk.CTkEntry(main_frame, width=100)
        if self.segment:
            self.order_entry.insert(0, str(self.segment['order_index']))
        else:
            # Default to next available order
            segments = self.vps_manager.get_all_segments(active_only=False)
            next_order = len(segments) + 1
            self.order_entry.insert(0, str(next_order))
        self.order_entry.grid(row=row, column=1, sticky="w", padx=5, pady=5)
        row += 1

        # Active checkbox
        self.active_var = ctk.BooleanVar(
            value=True if not self.segment else self.segment['is_active'])
        self.active_checkbox = ctk.CTkCheckBox(
            main_frame,
            text="Active (visible in VPS Planning)",
            variable=self.active_var
        )
        self.active_checkbox.grid(
            row=row, column=1, sticky="w", padx=5, pady=10)
        row += 1

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.grid(row=row, column=0, columnspan=2, pady=20)

        ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.save_segment,
            fg_color="green",
            width=120
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="Cancel",
            command=self.destroy,
            fg_color="gray",
            width=120
        ).pack(side="left", padx=5)

    def load_segment_data(self):
        """Load existing segment data into form."""
        self.name_entry.insert(0, self.segment['name'])
        if self.segment['description']:
            self.description_text.insert("1.0", self.segment['description'])
        self.color_entry.delete(0, 'end')
        self.color_entry.insert(0, self.segment['color_hex'])
        self.selected_color = self.segment['color_hex']
        self.color_preview.configure(fg_color=self.selected_color)

    def pick_color(self):
        """Open color picker dialog."""
        # Open color chooser with current color
        color_code = colorchooser.askcolor(
            initialcolor=self.selected_color,
            title="Choose Segment Color"
        )

        if color_code[1]:  # color_code is ((r,g,b), "#hexcode")
            self.selected_color = color_code[1]
            self.color_entry.delete(0, 'end')
            self.color_entry.insert(0, self.selected_color)
            self.color_preview.configure(fg_color=self.selected_color)

    def validate_color(self, color_hex: str) -> bool:
        """Validate that color_hex is a valid hex color."""
        if not color_hex.startswith('#'):
            return False
        if len(color_hex) != 7:
            return False
        try:
            int(color_hex[1:], 16)
            return True
        except ValueError:
            return False

    def save_segment(self):
        """Validate and save the segment."""
        # Get values
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Name is required")
            return

        description = self.description_text.get("1.0", "end-1c").strip()

        # Get color from entry field (user might have typed it)
        color_hex = self.color_entry.get().strip()
        if not self.validate_color(color_hex):
            messagebox.showerror(
                "Validation Error",
                "Invalid color code. Must be in format #RRGGBB (e.g., #4A90E2)"
            )
            return

        try:
            order_index = int(self.order_entry.get().strip())
        except ValueError:
            messagebox.showerror("Validation Error",
                                 "Display Order must be a number")
            return

        is_active = self.active_var.get()

        # Save or update
        try:
            if self.segment:
                # Update existing
                self.vps_manager.update_segment(
                    self.segment['id'],
                    name=name,
                    description=description,
                    color_hex=color_hex,
                    order_index=order_index,
                    is_active=is_active
                )
            else:
                # Create new
                self.vps_manager.create_segment(
                    name=name,
                    description=description,
                    color_hex=color_hex,
                    order_index=order_index
                )

            # Close dialog
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save segment: {str(e)}")
