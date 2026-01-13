"""
Manage Contacts screen - list and manage all contacts.
"""

import customtkinter as ctk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager
    from ..app import GetMoreDoneApp


class ManageContactsScreen(ctk.CTkFrame):
    """Screen for managing contacts."""

    def __init__(self, parent, db_manager: 'DatabaseManager', app: 'GetMoreDoneApp'):
        super().__init__(parent)
        self.db_manager = db_manager
        self.app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Create header
        self.create_header()

        # Create scrollable frame for contacts
        self.scroll_frame = ctk.CTkScrollableFrame(self, label_text="")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

        # Load contacts
        self.refresh()

    def create_header(self):
        """Create header with search and controls."""
        header = ctk.CTkFrame(self)
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))
        header.grid_columnconfigure(3, weight=1)

        # Title
        title = ctk.CTkLabel(
            header,
            text="Contacts",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title.grid(row=0, column=0, padx=10, pady=10)

        # Search box
        ctk.CTkLabel(header, text="Search:").grid(row=0, column=1, padx=(20, 5), pady=10)
        self.search_var = ctk.StringVar()
        self.search_var.trace('w', lambda *args: self.refresh())
        self.search_entry = ctk.CTkEntry(
            header,
            textvariable=self.search_var,
            placeholder_text="Search by name, email...",
            width=250
        )
        self.search_entry.grid(row=0, column=2, padx=5, pady=10)

        # New Contact button
        btn_new = ctk.CTkButton(
            header,
            text="+ New Contact",
            command=self.create_new_contact
        )
        btn_new.grid(row=0, column=4, padx=10, pady=10)

    def refresh(self):
        """Refresh the list of contacts."""
        # Clear current contacts
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        # Get search term
        search_term = self.search_var.get().strip()

        # Get contacts
        if search_term:
            contacts = self.db_manager.search_contacts(search_term, active_only=True)
        else:
            contacts = self.db_manager.get_all_contacts(active_only=True)

        # Display contacts
        if not contacts:
            no_data = ctk.CTkLabel(
                self.scroll_frame,
                text="No contacts found" if search_term else "No contacts yet. Click '+ New Contact' to add one.",
                font=ctk.CTkFont(size=14),
                text_color="gray"
            )
            no_data.grid(row=0, column=0, pady=50)
        else:
            # Create header row
            header_frame = ctk.CTkFrame(self.scroll_frame)
            header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
            header_frame.grid_columnconfigure(0, weight=2)
            header_frame.grid_columnconfigure(1, weight=1)
            header_frame.grid_columnconfigure(2, weight=2)
            header_frame.grid_columnconfigure(3, weight=2)

            ctk.CTkLabel(header_frame, text="Name", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=0, padx=10, pady=5, sticky="w"
            )
            ctk.CTkLabel(header_frame, text="Type", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=1, padx=10, pady=5, sticky="w"
            )
            ctk.CTkLabel(header_frame, text="Email", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=2, padx=10, pady=5, sticky="w"
            )
            ctk.CTkLabel(header_frame, text="Phone", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=3, padx=10, pady=5, sticky="w"
            )

            # Display each contact
            for idx, contact in enumerate(contacts, start=1):
                self.create_contact_row(contact, idx)

    def create_contact_row(self, contact, row_idx):
        """Create a row for a contact."""
        row = ctk.CTkFrame(self.scroll_frame)
        row.grid(row=row_idx, column=0, sticky="ew", pady=2)
        row.grid_columnconfigure(0, weight=2)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=2)
        row.grid_columnconfigure(3, weight=2)

        # Make row clickable
        def on_click(event=None):
            self.edit_contact(contact.id)

        # Name (clickable)
        name_label = ctk.CTkLabel(
            row,
            text=contact.name,
            cursor="hand2",
            anchor="w"
        )
        name_label.grid(row=0, column=0, padx=10, pady=8, sticky="w")
        name_label.bind("<Button-1>", on_click)

        # Type
        type_label = ctk.CTkLabel(row, text=contact.contact_type or "", anchor="w")
        type_label.grid(row=0, column=1, padx=10, pady=8, sticky="w")

        # Email
        email_label = ctk.CTkLabel(row, text=contact.email or "", anchor="w")
        email_label.grid(row=0, column=2, padx=10, pady=8, sticky="w")

        # Phone
        phone_label = ctk.CTkLabel(row, text=contact.phone or "", anchor="w")
        phone_label.grid(row=0, column=3, padx=10, pady=8, sticky="w")

        # Bind click event to entire row
        row.bind("<Button-1>", on_click)
        for child in row.winfo_children():
            child.bind("<Button-1>", on_click)

    def create_new_contact(self):
        """Open dialog to create new contact."""
        from .edit_contact import EditContactDialog
        dialog = EditContactDialog(self, self.db_manager, contact_id=None)
        dialog.wait_window()
        self.refresh()

    def edit_contact(self, contact_id: int):
        """Open dialog to edit contact."""
        from .edit_contact import EditContactDialog
        dialog = EditContactDialog(self, self.db_manager, contact_id=contact_id)
        dialog.wait_window()
        self.refresh()
