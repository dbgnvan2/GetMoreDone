"""
Edit Contact dialog - create or edit a contact.
"""

import customtkinter as ctk
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

from ..models import Contact

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager


class EditContactDialog(ctk.CTkToplevel):
    """Dialog for creating or editing a contact."""

    def __init__(self, parent, db_manager: 'DatabaseManager', contact_id: Optional[int] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.contact_id = contact_id
        self.contact = None

        # Configure window
        if contact_id:
            self.title("Edit Contact")
            self.contact = self.db_manager.get_contact(contact_id)
            if not self.contact:
                messagebox.showerror("Error", "Contact not found")
                self.destroy()
                return
        else:
            self.title("New Contact")

        self.geometry("500x450")
        self.resizable(False, False)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Configure grid
        self.grid_columnconfigure(0, weight=1)

        # Create form
        self.create_form()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - self.winfo_width()) // 2
        y = parent.winfo_y() + (parent.winfo_height() - self.winfo_height()) // 2
        self.geometry(f"+{x}+{y}")

    def create_form(self):
        """Create the contact form."""
        # Form frame
        form = ctk.CTkFrame(self)
        form.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        form.grid_columnconfigure(1, weight=1)

        row = 0

        # Name
        ctk.CTkLabel(form, text="Name*:", anchor="w").grid(
            row=row, column=0, padx=10, pady=10, sticky="w"
        )
        self.name_var = ctk.StringVar(value=self.contact.name if self.contact else "")
        self.name_entry = ctk.CTkEntry(form, textvariable=self.name_var, width=300)
        self.name_entry.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        row += 1

        # Contact Type
        ctk.CTkLabel(form, text="Type:", anchor="w").grid(
            row=row, column=0, padx=10, pady=10, sticky="w"
        )
        self.type_var = ctk.StringVar(value=self.contact.contact_type if self.contact else "Contact")
        self.type_combo = ctk.CTkComboBox(
            form,
            values=["Client", "Contact", "Personal"],
            variable=self.type_var,
            width=300
        )
        self.type_combo.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        row += 1

        # Email
        ctk.CTkLabel(form, text="Email:", anchor="w").grid(
            row=row, column=0, padx=10, pady=10, sticky="w"
        )
        self.email_var = ctk.StringVar(value=self.contact.email if self.contact and self.contact.email else "")
        self.email_entry = ctk.CTkEntry(form, textvariable=self.email_var, width=300)
        self.email_entry.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        row += 1

        # Phone
        ctk.CTkLabel(form, text="Phone:", anchor="w").grid(
            row=row, column=0, padx=10, pady=10, sticky="w"
        )
        self.phone_var = ctk.StringVar(value=self.contact.phone if self.contact and self.contact.phone else "")
        self.phone_entry = ctk.CTkEntry(form, textvariable=self.phone_var, width=300)
        self.phone_entry.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        row += 1

        # Notes
        ctk.CTkLabel(form, text="Notes:", anchor="nw").grid(
            row=row, column=0, padx=10, pady=10, sticky="nw"
        )
        self.notes_text = ctk.CTkTextbox(form, width=300, height=100)
        if self.contact and self.contact.notes:
            self.notes_text.insert("1.0", self.contact.notes)
        self.notes_text.grid(row=row, column=1, padx=10, pady=10, sticky="ew")
        row += 1

        # Buttons frame
        btn_frame = ctk.CTkFrame(self)
        btn_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))
        btn_frame.grid_columnconfigure(1, weight=1)

        # Delete button (only for existing contacts)
        if self.contact_id:
            btn_delete = ctk.CTkButton(
                btn_frame,
                text="Delete",
                command=self.delete_contact,
                fg_color="red",
                hover_color="darkred"
            )
            btn_delete.grid(row=0, column=0, padx=5, pady=10)

        # Save button
        btn_save = ctk.CTkButton(
            btn_frame,
            text="Save",
            command=self.save_contact,
            fg_color="green",
            hover_color="darkgreen"
        )
        btn_save.grid(row=0, column=2, padx=5, pady=10)

        # Cancel button
        btn_cancel = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.cancel
        )
        btn_cancel.grid(row=0, column=3, padx=5, pady=10)

        # Focus on name field
        self.name_entry.focus()

    def save_contact(self):
        """Save the contact."""
        # Validate
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Name is required")
            return

        # Check for duplicate name (if creating new or changing name)
        if not self.contact_id or (self.contact and name != self.contact.name):
            existing = self.db_manager.get_contact_by_name(name)
            if existing:
                messagebox.showerror("Validation Error", f"A contact with the name '{name}' already exists")
                return

        # Get values
        contact_type = self.type_var.get()
        email = self.email_var.get().strip() or None
        phone = self.phone_var.get().strip() or None
        notes = self.notes_text.get("1.0", "end-1c").strip() or None

        try:
            if self.contact_id:
                # Update existing contact
                self.contact.name = name
                self.contact.contact_type = contact_type
                self.contact.email = email
                self.contact.phone = phone
                self.contact.notes = notes
                self.db_manager.update_contact(self.contact)
                messagebox.showinfo("Success", "Contact updated successfully")
            else:
                # Create new contact
                new_contact = Contact(
                    name=name,
                    contact_type=contact_type,
                    email=email,
                    phone=phone,
                    notes=notes
                )
                self.db_manager.create_contact(new_contact)
                messagebox.showinfo("Success", "Contact created successfully")

            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save contact: {str(e)}")

    def delete_contact(self):
        """Delete the contact."""
        if not self.contact_id:
            return

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete '{self.contact.name}'?\n\n"
            "Note: This will fail if there are action items referencing this contact."
        )

        if not confirm:
            return

        try:
            self.db_manager.delete_contact(self.contact_id)
            messagebox.showinfo("Success", "Contact deleted successfully")
            self.destroy()
        except Exception as e:
            # If deletion fails (likely due to foreign key constraint), offer to deactivate instead
            deactivate = messagebox.askyesno(
                "Cannot Delete",
                f"Cannot delete contact because it's referenced by action items.\n\n"
                f"Would you like to deactivate it instead?\n"
                f"(Deactivated contacts won't show up in the list but data is preserved)"
            )
            if deactivate:
                try:
                    self.db_manager.deactivate_contact(self.contact_id)
                    messagebox.showinfo("Success", "Contact deactivated successfully")
                    self.destroy()
                except Exception as e2:
                    messagebox.showerror("Error", f"Failed to deactivate contact: {str(e2)}")

    def cancel(self):
        """Cancel and close dialog."""
        self.destroy()
