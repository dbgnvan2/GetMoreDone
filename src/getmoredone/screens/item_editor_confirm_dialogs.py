"""Confirmation dialogs extracted from item_editor_dialogs.py."""

from __future__ import annotations

import customtkinter as ctk

from ..theme import button_style

class DeleteConfirmDialog(ctk.CTkToplevel):
    """Confirmation dialog for deleting an item."""

    def __init__(self, parent, item_title: str):
        super().__init__(parent)

        self.confirmed = False

        self.title("Confirm Delete")
        self.geometry("400x150")

        # Center on parent
        self.transient(parent)
        self.grab_set()

        # Message
        message = f"Are you sure you want to delete:\n\n{item_title}\n\nThis action cannot be undone."
        ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=12),
            wraplength=350
        ).pack(pady=20, padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            command=self.cancel
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Delete",
            width=100,
            **button_style("danger"),
            command=self.confirm
        ).pack(side="left", padx=5)

    def confirm(self):
        """Confirm deletion."""
        self.confirmed = True
        self.destroy()

    def cancel(self):
        """Cancel deletion."""
        self.confirmed = False
        self.destroy()


class DeleteChildrenWarningDialog(ctk.CTkToplevel):
    """Warning dialog when deleting item with children."""

    def __init__(self, parent, num_children: int):
        super().__init__(parent)

        self.confirmed = False

        self.title("Warning: Item Has Children")
        self.geometry("450x180")

        # Center on parent
        self.transient(parent)
        self.grab_set()

        # Message
        message = (
            f"This item has {num_children} child item(s).\n\n"
            "Deleting this item will NOT delete the children.\n"
            "Child items will become root items (no parent).\n\n"
            "Do you want to continue?"
        )
        ctk.CTkLabel(
            self,
            text=message,
            font=ctk.CTkFont(size=12),
            wraplength=400
        ).pack(pady=20, padx=20)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            command=self.cancel
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            btn_frame,
            text="Delete Anyway",
            width=120,
            **button_style("danger"),
            command=self.confirm
        ).pack(side="left", padx=5)

    def confirm(self):
        """Confirm deletion."""
        self.confirmed = True
        self.destroy()

    def cancel(self):
        """Cancel deletion."""
        self.confirmed = False
        self.destroy()
