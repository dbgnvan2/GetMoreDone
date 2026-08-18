"""Reusable date picker widget for the GetMoreDone application.

Purpose: pick a date from a month grid without a GPL-licensed dependency.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m2b
Tests:   tests/test_date_picker.py

Previously backed by ``tkcalendar``, which is GPLv3 and therefore cannot ship
inside a binary distributed under the proprietary license of decision D1
(finding F2). The month grid is now built on the stdlib ``calendar`` module,
following the pattern already used in ``screens/drag_schedule.py``.

The public interface — the constructor signature, ``get_date``, ``set_date``
and ``open_calendar`` — is unchanged, so no calling screen needed edits.
Colors come from theme tokens rather than the literals the tkcalendar version
passed, so the popup now follows the active theme.
"""

import calendar
from datetime import date, datetime
from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from ..theme import button_style, semantic_colors

DATE_FORMAT = "%Y-%m-%d"
DEFAULT_FIRST_DAY_OF_WEEK = 0  # Monday, matching AppSettings.first_day_of_week


def normalize_first_day_of_week(value) -> int:
    """Coerce a persisted first-day-of-week setting to a valid weekday index.

    settings.json is user-writable and the value also arrives from arbitrary
    ``getattr`` lookups, so anything non-integer or out of range falls back to
    Monday rather than raising inside a widget build.
    """
    try:
        day = int(value)
    except (TypeError, ValueError):
        return DEFAULT_FIRST_DAY_OF_WEEK
    if 0 <= day <= 6:
        return day
    return DEFAULT_FIRST_DAY_OF_WEEK


def weekday_headers(first_day_of_week=DEFAULT_FIRST_DAY_OF_WEEK) -> List[str]:
    """Abbreviated weekday names, rotated to start at ``first_day_of_week``."""
    start = normalize_first_day_of_week(first_day_of_week)
    names = list(calendar.day_abbr)
    return names[start:] + names[:start]


def month_grid(year: int, month: int,
               first_day_of_week=DEFAULT_FIRST_DAY_OF_WEEK) -> List[List[int]]:
    """Weeks of day numbers for a month; 0 pads days outside the month.

    Purpose: the calendar layout, as data, so it can be verified without a display.
    Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m2b2
    Tests:   tests/test_date_picker.py::test_rm2b2_month_grid_matches_stdlib_calendar
    """
    start = normalize_first_day_of_week(first_day_of_week)
    return calendar.Calendar(firstweekday=start).monthdayscalendar(year, month)


def _parse_date(value: str) -> Optional[date]:
    """Parse a YYYY-MM-DD string, or None if it is not one."""
    try:
        return datetime.strptime((value or "").strip(), DATE_FORMAT).date()
    except (TypeError, ValueError):
        return None


class DatePickerButton(ctk.CTkFrame):
    """A date entry with a calendar popup."""

    def __init__(self, parent, initial_date: Optional[str] = None,
                 on_date_changed: Optional[Callable[[str], None]] = None,
                 settings=None,
                 **kwargs):
        """
        Initialize the date picker button.

        Args:
            parent: The parent widget
            initial_date: Initial date in YYYY-MM-DD format (defaults to today)
            on_date_changed: Callback function called when date changes
            settings: Optional AppSettings-like object; supplies
                ``first_day_of_week``. Loaded lazily when the popup opens if not
                given, so constructing a picker stays cheap.
            **kwargs: Additional arguments passed to CTkFrame
        """
        super().__init__(parent, **kwargs)

        self.on_date_changed = on_date_changed
        self.calendar_popup = None
        self._settings = settings
        self._visible_year: Optional[int] = None
        self._visible_month: Optional[int] = None
        self._header_labels: List[str] = []
        self._grid_frame = None

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
            self.set_date(datetime.now().strftime(DATE_FORMAT))

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

    # ------------------------------------------------------------------
    # Value
    # ------------------------------------------------------------------

    def _on_entry_changed(self, event=None):
        """Handle changes to the date entry field."""
        if self.on_date_changed:
            date_str = self.get_date()
            if date_str:
                self.on_date_changed(date_str)

    def get_date(self) -> str:
        """Get the current date value as a string in YYYY-MM-DD format."""
        return self.date_entry.get().strip()

    def set_date(self, date_str):
        """
        Set the date value.

        Args:
            date_str: Date string in YYYY-MM-DD format, or a datetime/date object
        """
        if isinstance(date_str, datetime):
            date_str = date_str.strftime(DATE_FORMAT)
        elif isinstance(date_str, date):
            date_str = date_str.strftime(DATE_FORMAT)

        self.date_entry.delete(0, "end")
        self.date_entry.insert(0, date_str)

        if self.on_date_changed:
            self.on_date_changed(date_str)

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _first_day_of_week(self) -> int:
        """Resolve first-day-of-week from injected settings, else from disk."""
        if self._settings is None:
            try:
                from ..app_settings import AppSettings
                self._settings = AppSettings.load()
            except Exception:
                # Settings are a preference, not a precondition for picking a date.
                return DEFAULT_FIRST_DAY_OF_WEEK
        return normalize_first_day_of_week(
            getattr(self._settings, "first_day_of_week", DEFAULT_FIRST_DAY_OF_WEEK)
        )

    # ------------------------------------------------------------------
    # Popup
    # ------------------------------------------------------------------

    def open_calendar(self):
        """Open the calendar popup dialog."""
        if self.calendar_popup and self.calendar_popup.winfo_exists():
            self.calendar_popup.lift()
            return

        current = _parse_date(self.get_date()) or date.today()
        self._visible_year, self._visible_month = current.year, current.month

        self.calendar_popup = ctk.CTkToplevel(self)
        self.calendar_popup.title("Select Date")
        self.calendar_popup.geometry("320x340")
        self.calendar_popup.resizable(False, False)

        # Make it modal
        self.calendar_popup.transient(self.winfo_toplevel())
        self.calendar_popup.grab_set()

        # Position near the button
        self.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self.calendar_popup.geometry(f"+{x}+{y}")

        palette = semantic_colors()

        # Month navigation header
        header = ctk.CTkFrame(self.calendar_popup, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkButton(
            header, text="‹", width=32, command=self.show_previous_month,
            **button_style("ghost"),
        ).grid(row=0, column=0, sticky="w")

        self.month_label = ctk.CTkLabel(
            header, text="", font=ctk.CTkFont(size=14, weight="bold"),
            text_color=palette["body_text"],
        )
        self.month_label.grid(row=0, column=1, sticky="ew")

        ctk.CTkButton(
            header, text="›", width=32, command=self.show_next_month,
            **button_style("ghost"),
        ).grid(row=0, column=2, sticky="e")

        # Month grid
        self._grid_frame = ctk.CTkFrame(self.calendar_popup, fg_color="transparent")
        self._grid_frame.pack(fill="both", expand=True, padx=10, pady=4)
        for col in range(7):
            self._grid_frame.grid_columnconfigure(col, weight=1, uniform="picker-cal")

        # Action buttons
        btn_frame = ctk.CTkFrame(self.calendar_popup, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(
            btn_frame, text="Today", command=self.select_today, width=80,
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_frame, text="Cancel", command=self.close_calendar, width=80,
            **button_style("secondary"),
        ).pack(side="right", padx=5)

        self.calendar_popup.protocol("WM_DELETE_WINDOW", self.close_calendar)
        self._render_month()

    def close_calendar(self):
        """Close the popup if it is open."""
        if self.calendar_popup and self.calendar_popup.winfo_exists():
            self.calendar_popup.destroy()
        self.calendar_popup = None

    def _render_month(self):
        """Redraw the weekday headers and day buttons for the visible month."""
        if not self._grid_frame or not self._grid_frame.winfo_exists():
            return

        for child in self._grid_frame.winfo_children():
            child.destroy()

        palette = semantic_colors()
        first_day = self._first_day_of_week()
        self._header_labels = weekday_headers(first_day)

        self.month_label.configure(
            text=f"{calendar.month_name[self._visible_month]} {self._visible_year}"
        )

        for col, name in enumerate(self._header_labels):
            ctk.CTkLabel(
                self._grid_frame, text=name, anchor="center",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=palette["muted_text"],
            ).grid(row=0, column=col, sticky="ew", padx=1, pady=(0, 2))

        selected = _parse_date(self.get_date())
        today = date.today()
        weeks = month_grid(self._visible_year, self._visible_month, first_day)

        for row, week in enumerate(weeks, start=1):
            for col, day in enumerate(week):
                if day == 0:
                    continue
                this_day = date(self._visible_year, self._visible_month, day)
                if selected is not None and this_day == selected:
                    style = {}                      # theme's primary button
                elif this_day == today:
                    style = button_style("secondary")
                else:
                    style = button_style("ghost")
                ctk.CTkButton(
                    self._grid_frame,
                    text=str(day),
                    width=36,
                    height=28,
                    command=lambda d=day: self.select_day(d),
                    **style,
                ).grid(row=row, column=col, sticky="nsew", padx=1, pady=1)

    # ------------------------------------------------------------------
    # Navigation and selection
    # ------------------------------------------------------------------

    def visible_month(self) -> Tuple[Optional[int], Optional[int]]:
        """The (year, month) currently drawn in the popup."""
        return (self._visible_year, self._visible_month)

    def header_labels(self) -> List[str]:
        """The weekday header names as rendered, left to right."""
        return list(self._header_labels)

    def show_previous_month(self):
        """Step the view back one month. Does not change the stored date."""
        if self._visible_year is None:
            return
        year, month = self._visible_year, self._visible_month
        self._visible_year, self._visible_month = (year - 1, 12) if month == 1 else (year, month - 1)
        self._render_month()

    def show_next_month(self):
        """Step the view forward one month. Does not change the stored date."""
        if self._visible_year is None:
            return
        year, month = self._visible_year, self._visible_month
        self._visible_year, self._visible_month = (year + 1, 1) if month == 12 else (year, month + 1)
        self._render_month()

    def select_day(self, day: int):
        """Choose a day in the visible month, then close the popup."""
        if self._visible_year is None:
            return
        self.set_date(date(self._visible_year, self._visible_month, day).strftime(DATE_FORMAT))
        self.close_calendar()

    def select_today(self):
        """Choose today, then close the popup."""
        self.set_date(date.today().strftime(DATE_FORMAT))
        self.close_calendar()
