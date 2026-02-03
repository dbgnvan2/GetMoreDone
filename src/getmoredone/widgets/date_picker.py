"""
Reusable date picker widget for the GetMoreDone application.
"""

import customtkinter as ctk
from datetime import datetime
from tkcalendar import Calendar
from typing import Optional, Callable


class DatePickerButton(ctk.CTkFrame):
    """A date picker widget with a calendar popup."""

    def __init__(self, parent, initial_date: Optional[str] = None,
                 on_date_changed: Optional[Callable[[str], None]] = None,
                 **kwargs):
        """
        Initialize the date picker button.

        Args:
            parent: The parent widget
            initial_date: Initial date in YYYY-MM-DD format (defaults to today)
            on_date_changed: Callback function called when date changes
            **kwargs: Additional arguments passed to CTkFrame
        """
        super().__init__(parent, **kwargs)

        self.on_date_changed = on_date_changed
        self.calendar_popup = None

        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)

        # Date entry field
        self.date_entry = ctk.CTkEntry(
            self,
            placeholder_text="YYYY-MM-DD",
            width=150
        )
        self.date_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))

        # Set initial date
        if initial_date:
            self.set_date(initial_date)
        else:
            self.set_date(datetime.now().strftime("%Y-%m-%d"))

        # Calendar button
        self.calendar_btn = ctk.CTkButton(
            self,
            text="📅",
            width=40,
            command=self.open_calendar
        )
        self.calendar_btn.grid(row=0, column=1, sticky="e")

        # Bind entry field changes to callback
        self.date_entry.bind('<FocusOut>', self._on_entry_changed)
        self.date_entry.bind('<Return>', self._on_entry_changed)

    def _on_entry_changed(self, event=None):
        """Handle changes to the date entry field."""
        if self.on_date_changed:
            date_str = self.get_date()
            if date_str:
                self.on_date_changed(date_str)

    def get_date(self) -> str:
        """Get the current date value as a string in YYYY-MM-DD format."""
        return self.date_entry.get().strip()

    def set_date(self, date_str: str):
        """
        Set the date value.

        Args:
            date_str: Date string in YYYY-MM-DD format or datetime object
        """
        if isinstance(date_str, datetime):
            date_str = date_str.strftime("%Y-%m-%d")

        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date_str)

        if self.on_date_changed:
            self.on_date_changed(date_str)

    def open_calendar(self):
        """Open the calendar popup dialog."""
        if self.calendar_popup and self.calendar_popup.winfo_exists():
            self.calendar_popup.lift()
            return

        # Create popup window
        self.calendar_popup = ctk.CTkToplevel(self)
        self.calendar_popup.title("Select Date")
        self.calendar_popup.geometry("300x320")
        self.calendar_popup.resizable(False, False)

        # Make it modal
        self.calendar_popup.transient(self.winfo_toplevel())
        self.calendar_popup.grab_set()

        # Position near the button
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.calendar_popup.geometry(f"+{x}+{y}")

        # Parse current date or use today
        current_date = datetime.now()
        date_str = self.get_date()
        if date_str:
            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                pass

        # Create calendar widget
        cal = Calendar(
            self.calendar_popup,
            selectmode='day',
            year=current_date.year,
            month=current_date.month,
            day=current_date.day,
            background='darkblue',
            foreground='white',
            selectbackground='lightblue',
            selectforeground='black',
            headersbackground='darkblue',
            headersforeground='white',
            normalbackground='white',
            normalforeground='black',
            weekendbackground='lightgray',
            weekendforeground='black',
            bordercolor='darkblue',
            date_pattern='yyyy-mm-dd'
        )
        cal.pack(padx=10, pady=10, fill="both", expand=True)

        # Button frame
        btn_frame = ctk.CTkFrame(self.calendar_popup)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        def select_date():
            selected = cal.get_date()
            self.set_date(selected)
            self.calendar_popup.destroy()

        def today_date():
            today = datetime.now().strftime("%Y-%m-%d")
            self.set_date(today)
            self.calendar_popup.destroy()

        # Today button
        today_btn = ctk.CTkButton(
            btn_frame,
            text="Today",
            command=today_date,
            width=80
        )
        today_btn.pack(side="left", padx=5)

        # Select button
        select_btn = ctk.CTkButton(
            btn_frame,
            text="Select",
            command=select_date,
            width=80
        )
        select_btn.pack(side="left", padx=5)

        # Cancel button
        cancel_btn = ctk.CTkButton(
            btn_frame,
            text="Cancel",
            command=self.calendar_popup.destroy,
            width=80
        )
        cancel_btn.pack(side="left", padx=5)

        # Bind double-click to select
        cal.bind("<<CalendarSelected>>", lambda e: select_date())
