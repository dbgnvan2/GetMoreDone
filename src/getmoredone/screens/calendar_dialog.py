"""
Dialog for creating Google Calendar events linked to action items.
"""

import customtkinter as ctk
from datetime import datetime, timedelta, date
from typing import Optional, TYPE_CHECKING

from ..app_settings import AppSettings
from ..date_utils import increment_date

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager


class CalendarEventDialog(ctk.CTkToplevel):
    """Dialog for creating a Google Calendar event."""

    def __init__(self, parent, db_manager: 'DatabaseManager', item_id: str):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item_id = item_id
        self.item = db_manager.get_action_item(item_id)
        self.result = None  # Will store the calendar link if successful

        if not self.item:
            self.destroy()
            return

        self.title("Create Calendar Event")
        self.geometry("600x650")

        self.create_form()

        # Make dialog modal
        self.transient(parent)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 600) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 650) // 2
        self.geometry(f"+{x}+{y}")

    def create_form(self):
        """Create the form layout."""
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(
            main_frame,
            text="Create Google Calendar Meeting",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(0, 20))

        # Event Title
        ctk.CTkLabel(main_frame, text="Event Title:").pack(anchor="w", pady=(0, 5))
        self.title_entry = ctk.CTkEntry(main_frame, width=550)
        self.title_entry.insert(0, self.item.title)
        self.title_entry.pack(pady=(0, 15))

        # Date Frame
        date_frame = ctk.CTkFrame(main_frame)
        date_frame.pack(fill="x", pady=(0, 15))

        # Start Date
        ctk.CTkLabel(date_frame, text="Date (YYYY-MM-DD):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.date_entry = ctk.CTkEntry(date_frame, width=150)
        # Default to item start date or today
        default_date = self.item.start_date or datetime.now().date().isoformat()
        self.date_entry.insert(0, default_date)
        self.date_entry.grid(row=0, column=1, sticky="w", padx=5, pady=5)

        # Quick date buttons
        btn_today = ctk.CTkButton(date_frame, text="Today", width=60,
                                  command=lambda: self.set_date(datetime.now().date()))
        btn_today.grid(row=0, column=2, padx=2, pady=5)

        btn_tomorrow = ctk.CTkButton(date_frame, text="+1", width=50,
                                     command=self.increment_date_by_one)
        btn_tomorrow.grid(row=0, column=3, padx=2, pady=5)

        # Time Frame
        time_frame = ctk.CTkFrame(main_frame)
        time_frame.pack(fill="x", pady=(0, 15))

        # Start Time
        ctk.CTkLabel(time_frame, text="Start Time:").grid(row=0, column=0, sticky="w", padx=5, pady=5)

        self.hour_entry = ctk.CTkEntry(time_frame, width=60, placeholder_text="HH")
        self.hour_entry.insert(0, "09")
        self.hour_entry.grid(row=0, column=1, padx=2, pady=5)

        ctk.CTkLabel(time_frame, text=":").grid(row=0, column=2, padx=2, pady=5)

        self.minute_entry = ctk.CTkEntry(time_frame, width=60, placeholder_text="MM")
        self.minute_entry.insert(0, "00")
        self.minute_entry.grid(row=0, column=3, padx=2, pady=5)

        # AM/PM
        self.ampm_var = ctk.StringVar(value="AM")
        self.ampm_combo = ctk.CTkComboBox(time_frame, values=["AM", "PM"], variable=self.ampm_var, width=70)
        self.ampm_combo.grid(row=0, column=4, padx=5, pady=5)

        # Duration
        ctk.CTkLabel(time_frame, text="Duration:").grid(row=0, column=5, sticky="w", padx=(20, 5), pady=5)
        self.duration_entry = ctk.CTkEntry(time_frame, width=60, placeholder_text="60")
        self.duration_entry.insert(0, "60")
        self.duration_entry.grid(row=0, column=6, padx=2, pady=5)
        ctk.CTkLabel(time_frame, text="minutes").grid(row=0, column=7, sticky="w", padx=2, pady=5)

        # Description
        ctk.CTkLabel(main_frame, text="Description (optional):").pack(anchor="w", pady=(0, 5))
        self.description_text = ctk.CTkTextbox(main_frame, height=100, width=550)
        if self.item.description:
            self.description_text.insert("1.0", self.item.description)
        self.description_text.pack(pady=(0, 15))

        # Location
        ctk.CTkLabel(main_frame, text="Location (optional):").pack(anchor="w", pady=(0, 5))
        self.location_entry = ctk.CTkEntry(main_frame, width=550)
        self.location_entry.pack(pady=(0, 15))

        # Attendees
        ctk.CTkLabel(main_frame, text="Attendees (comma-separated emails, optional):").pack(anchor="w", pady=(0, 5))
        self.attendees_entry = ctk.CTkEntry(main_frame, width=550)
        self.attendees_entry.pack(pady=(0, 15))

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red", wraplength=550)
        self.error_label.pack(pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(main_frame)
        btn_frame.pack(pady=(15, 0))

        btn_create = ctk.CTkButton(
            btn_frame,
            text="Create Calendar Event",
            command=self.create_event,
            fg_color="green",
            hover_color="darkgreen",
            width=180
        )
        btn_create.pack(side="left", padx=5)

        btn_cancel = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, width=100)
        btn_cancel.pack(side="left", padx=5)

    def set_date(self, date):
        """Set date in the entry field."""
        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date.isoformat())

    def increment_date_by_one(self):
        """Increment date by 1 day using weekend-aware logic."""
        settings = AppSettings.load()
        current_date = datetime.now().date()

        # Get current date from entry if it has a value
        date_str = self.date_entry.get().strip()
        if date_str:
            try:
                current_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        # Increment by 1 day using weekend-aware logic
        new_date = increment_date(current_date, 1, settings.include_saturday, settings.include_sunday)
        self.set_date(new_date)

    def create_event(self):
        """Create the calendar event and link it to the action item."""
        try:
            # Validate inputs
            event_title = self.title_entry.get().strip()
            if not event_title:
                self.error_label.configure(text="Event title is required")
                return

            date_str = self.date_entry.get().strip()
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                self.error_label.configure(text="Invalid date format. Use YYYY-MM-DD")
                return

            # Parse time
            try:
                hour = int(self.hour_entry.get())
                minute = int(self.minute_entry.get())

                # Convert to 24-hour format
                if self.ampm_var.get() == "PM" and hour != 12:
                    hour += 12
                elif self.ampm_var.get() == "AM" and hour == 12:
                    hour = 0

                if not (0 <= hour <= 23) or not (0 <= minute <= 59):
                    raise ValueError()

            except (ValueError, AttributeError):
                self.error_label.configure(text="Invalid time. Hour: 1-12, Minute: 0-59")
                return

            # Parse duration
            try:
                duration = int(self.duration_entry.get())
                if duration <= 0:
                    raise ValueError()
            except ValueError:
                self.error_label.configure(text="Invalid duration. Must be a positive number")
                return

            # Combine date and time
            start_datetime = datetime.combine(event_date, datetime.min.time())
            start_datetime = start_datetime.replace(hour=hour, minute=minute)

            description = self.description_text.get("1.0", "end").strip() or None
            location = self.location_entry.get().strip() or None

            # Parse attendees
            attendees = []
            attendees_str = self.attendees_entry.get().strip()
            if attendees_str:
                attendees = [email.strip() for email in attendees_str.split(",") if email.strip()]

            # Create calendar event
            from ..google_calendar import GoogleCalendarManager

            # Check if Google Calendar is available
            if not GoogleCalendarManager.is_available():
                self.error_label.configure(
                    text="Google Calendar libraries not installed.\n"
                         "Run: pip install -r requirements.txt"
                )
                return

            # Check for credentials
            if not GoogleCalendarManager.has_credentials():
                self.error_label.configure(
                    text="Google Calendar credentials not found.\n"
                         "Please set up credentials.json in ~/.getmoredone/\n"
                         "See README for instructions."
                )
                return

            self.error_label.configure(text="Creating calendar event...")
            self.update()

            # Create the event
            calendar_mgr = GoogleCalendarManager()
            event_result = calendar_mgr.create_event(
                summary=event_title,
                start_datetime=start_datetime,
                duration_minutes=duration,
                description=description,
                location=location,
                attendees=attendees if attendees else None
            )

            # Store the calendar link as an ItemLink
            calendar_url = event_result.get('htmlLink')
            event_id = event_result.get('id')

            if calendar_url:
                from ..models import ItemLink
                link = ItemLink(
                    item_id=self.item_id,
                    url=calendar_url,
                    label=f"Calendar: {event_title}",
                    link_type="google_calendar"
                )
                self.db_manager.add_item_link(link)

                # Update the action item to mark it as a meeting and store the meeting time
                self.item.is_meeting = True
                self.item.meeting_start_time = start_datetime.isoformat()
                self.db_manager.update_action_item(self.item)

                # Open the calendar event in browser (htmlLink already points to the event)
                import webbrowser
                webbrowser.open(calendar_url)

                self.result = calendar_url
                self.destroy()
            else:
                self.error_label.configure(text="Event created but no link returned")

        except FileNotFoundError as e:
            self.error_label.configure(text=str(e))
        except RuntimeError as e:
            self.error_label.configure(text=f"Calendar error: {str(e)}")
        except Exception as e:
            self.error_label.configure(text=f"Unexpected error: {str(e)}")
