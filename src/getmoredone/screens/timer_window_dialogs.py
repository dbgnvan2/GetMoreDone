"""Supporting dialogs extracted from timer_window.py."""

from __future__ import annotations

import customtkinter as ctk
from contextlib import contextmanager
from datetime import date, timedelta
from typing import Optional, TYPE_CHECKING

from ..app_settings import AppSettings
from ..date_utils import increment_date
from ..models import ActionItem
from .week_collision_notice import notify_weekly_tactic_changes
from ..theme import button_style, status_text_color
from ..utils.after_tracker import TrackedAfterMixin

if TYPE_CHECKING:
    from ..db_manager import DatabaseManager

def raise_above_parent(dialog) -> None:
    """Put a modal above the always-on-top timer, once the window really exists.

    Purpose: setting ``-topmost`` inside ``__init__`` does not stick. Measured:
             the dialog reads 0 immediately after construction and never
             recovers, while the timer window it opened from reads 1.
    Tests:   tests/test_reward_protocol_timer.py::test_every_timer_modal_raises_itself_above_the_timer

    The consequence was the whole window appearing dead. The modal opened
    *behind* the timer while holding ``grab_set()``, so it was invisible and
    swallowed every click: Stop then any of the session buttons left the timer
    sitting there, unresponsive, with nothing on screen to explain why.

    Re-asserting on the next idle cycle, when the window exists, holds.
    Swallows errors: a dialog dismissed before the callback runs must not raise
    into the event loop.
    """
    def raise_it():
        try:
            # Never touch a window that is not on screen. Raising a withdrawn
            # window is meaningless, and doing it anyway is what made a test run
            # hammer the window server: the suite withdraws every window, so
            # this fired hundreds of times against windows nobody could see.
            # state() only. "not mapped yet" is transient — a toplevel that has
            # not finished mapping by +10ms on a loaded machine — and treating
            # it as "never raise" turns a delay into the reported symptom
            # coming back intermittently, with nothing logged (P1). The test
            # suite withdraws every window, which state() covers completely.
            if dialog.state() == "withdrawn":
                return
            dialog.attributes("-topmost", True)
            dialog.lift()
        except Exception:
            pass

    try:
        dialog.after(10, raise_it)
    except Exception:
        pass


# ``wm attributes`` reached through the Tcl interpreter rather than through
# ``window.attributes``. The test suite's conftest patches the Python spelling
# (both of its names) so a run cannot throw always-on-top windows over the
# user's desktop; going through tk.call means the code below does the same
# thing in a test as it does in the app, so the fix can be measured rather than
# assumed. It is safe past that patch because it never raises a window: it only
# clears -topmost, or puts back the value it read a moment earlier.
def _read_topmost(window) -> bool:
    """Is this window always-on-top right now? False if it cannot be asked."""
    try:
        return bool(int(window.tk.call("wm", "attributes", window._w, "-topmost")))
    except Exception:
        return False


def _write_topmost(window, value: bool) -> None:
    """Best effort. A window destroyed under us is not an error worth raising."""
    try:
        if window.winfo_exists():
            window.tk.call("wm", "attributes", window._w, "-topmost", 1 if value else 0)
    except Exception:
        pass


def _suspend_topmost(parent) -> bool:
    """Lower the parent's always-on-top, counting nesting. True if it took.

    The depth counter is not decoration. Without it, a second modal opening
    over an already-suspended parent reads -topmost as False, decides there is
    nothing to do, and registers no restore — and then the FIRST modal's
    restore raises the parent back over the second one, which is still holding
    grab_set(). That is the reported bug, rebuilt out of the fix for it.
    """
    if parent is None:
        return False
    depth = getattr(parent, "_gmd_topmost_depth", 0)
    if depth == 0:
        if not _read_topmost(parent):
            return False
        parent._gmd_topmost_saved = True
        _write_topmost(parent, False)
    parent._gmd_topmost_depth = depth + 1
    return True


def _resume_topmost(parent) -> None:
    """Give the flag back, but only when the last modal over it has gone."""
    depth = getattr(parent, "_gmd_topmost_depth", 0)
    if depth <= 0:
        return
    depth -= 1
    parent._gmd_topmost_depth = depth
    if depth == 0 and getattr(parent, "_gmd_topmost_saved", False):
        parent._gmd_topmost_saved = False
        _write_topmost(parent, True)


@contextmanager
def parent_topmost_suspended(parent):
    """For a blocking modal with no window of its own to bind to.

    ``tkinter.messagebox`` builds and tears down its own Toplevel inside one
    call, so there is no <Destroy> to hang a restore on. These are the error
    dialogs on the failure path of every timer ending — precisely where an
    invisible modal behind an always-on-top window is worst, because something
    has already gone wrong and the user is being told nothing.
    """
    taken = _suspend_topmost(parent)
    try:
        yield
    finally:
        if taken:
            _resume_topmost(parent)


def suspend_parent_topmost(dialog, parent) -> None:
    """Drop the parent's always-on-top for as long as ``dialog`` is up.

    Purpose: a modal that opens *behind* its parent still holds ``grab_set()``,
             so it takes every click while showing the user nothing. The window
             underneath looks dead — which is exactly how it was reported:
             "the Next Step Note pops and then is hidden. No buttons work on
             the Timer window."
    Tests:   tests/test_timer_session_endings.py::test_t51_a_modal_drops_the_timers_always_on_top
             tests/test_timer_session_endings.py::test_t52_the_timer_is_topmost_again_afterwards

    ``raise_above_parent`` tried to win that fight by re-asserting -topmost on
    the dialog and lifting it. Two windows both claiming the top is a race, and
    it lost: the timer sets -topmost at construction and never drops it, so the
    dialog was arguing with a permanent flag. Dropping the parent's flag ends
    the argument instead of competing in it. Both are kept — this is the fix,
    the lift is belt.

    Restores on the dialog's own ``<Destroy>``, so an ending that raises
    part-way through still gives the timer its flag back.
    """
    if not _suspend_topmost(parent):
        return

    def restore(event=None):
        # <Destroy> fires for every descendant widget as the dialog comes
        # apart; only the dialog's own is the end of its life.
        if event is not None and event.widget is not dialog:
            return
        _resume_topmost(parent)

    try:
        dialog.bind("<Destroy>", restore, add="+")
    except Exception:
        # Could not arm the restore, so do not leave the parent demoted.
        _resume_topmost(parent)


def _center_on(dialog, parent, width: int, height: int) -> None:
    """Put ``dialog`` over ``parent``, or leave it where Tk put it.

    Swallows the failure on purpose: the parent may already be destroyed by the
    time a dialog opens over it, and a window that is merely mis-positioned must
    not become an error the user sees.
    """
    try:
        dialog.update_idletasks()
        if parent.winfo_exists():
            x = parent.winfo_x() + (parent.winfo_width() - width) // 2
            y = parent.winfo_y() + (parent.winfo_height() - height) // 2
            dialog.geometry(f"+{x}+{y}")
    except Exception as e:
        print(f"[DEBUG] Could not center dialog on parent: {e}")


class CompletionNoteDialog(ctk.CTkToplevel):
    """Simple dialog for entering completion notes."""

    def __init__(self, parent, title: str):
        super().__init__(parent)

        self.result = None

        self.title(title)
        self.geometry("400x250")
        self.transient(parent)
        # Appear above always-on-top timer window
        self.attributes('-topmost', True)
        suspend_parent_topmost(self, parent)
        self.grab_set()
        raise_above_parent(self)

        # Center on parent if it still exists
        try:
            self.update_idletasks()
            if parent.winfo_exists():
                x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
                y = parent.winfo_y() + (parent.winfo_height() - 250) // 2
                self.geometry(f"+{x}+{y}")
        except Exception as e:
            # If parent is destroyed, just use default position
            print(f"[DEBUG] Could not center dialog on parent: {e}")

        # Widgets
        label = ctk.CTkLabel(
            self, text=title, font=ctk.CTkFont(size=14, weight="bold"))
        label.pack(pady=10, padx=10)

        self.textbox = ctk.CTkTextbox(self, height=120)
        self.textbox.pack(pady=10, padx=10, fill="both", expand=True)
        self.textbox.focus()

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.save,
            **button_style("primary"),
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            button_frame,
            text="Skip",
            command=self.skip,
            **button_style("secondary"),
        ).pack(side="left", expand=True, padx=5)

    def save(self):
        """Save the note and close."""
        self.result = self.textbox.get("1.0", "end-1c").strip()
        if not self.result:
            self.result = None
        self.destroy()

    def skip(self):
        """Skip note and close."""
        self.result = None
        self.destroy()


class NextActionWindow(TrackedAfterMixin, ctk.CTkToplevel):
    """Floating window for viewing/editing action item notes independently."""

    def __init__(self, parent, db_manager: DatabaseManager, item: ActionItem, parent_window=None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item = item
        self.parent_window = parent_window  # Reference to TimerWindow for sync
        self.settings = AppSettings.load()

        self.setup_window()
        self.create_widgets()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def setup_window(self):
        """Configure window properties."""
        self.title(f"Notes: {self.item.title}")

        # Set size from settings (or defaults)
        width = getattr(self.settings, 'next_action_window_width', 500)
        height = getattr(self.settings, 'next_action_window_height', 400)

        # Set position if saved, otherwise offset from center
        next_action_x = getattr(self.settings, 'next_action_window_x', None)
        next_action_y = getattr(self.settings, 'next_action_window_y', None)

        if next_action_x and next_action_y:
            self.geometry(f"{width}x{height}+{next_action_x}+{next_action_y}")
        else:
            # Offset from center
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = (screen_width - width) // 2 + 50
            y = (screen_height - height) // 2 + 50
            self.geometry(f"{width}x{height}+{x}+{y}")

        # Make window stay on top
        self.attributes('-topmost', True)
        raise_above_parent(self)

        # Make window resizable
        self.minsize(300, 200)
        self.resizable(True, True)

        # Grid configuration
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create all UI widgets."""
        # Main container
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(2, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Action title
        title_label = ctk.CTkLabel(
            main_frame,
            text=self.item.title,
            font=ctk.CTkFont(size=16, weight="bold"),
            wraplength=450
        )
        title_label.grid(row=0, column=0, pady=(10, 5), padx=10, sticky="ew")

        # Header with Save button
        header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        header_frame.grid(row=1, column=0, pady=(10, 5), padx=10, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        notes_label = ctk.CTkLabel(
            header_frame,
            text="Notes:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        notes_label.grid(row=0, column=0, sticky="w")

        # Save button
        self.save_button = ctk.CTkButton(
            header_frame,
            text="Save Notes",
            width=100,
            command=self.save_notes,
            **button_style("primary"),
        )
        self.save_button.grid(row=0, column=1, padx=5)

        # Notes textbox
        self.notes_text = ctk.CTkTextbox(
            main_frame,
            wrap="word"
        )
        self.notes_text.grid(row=2, column=0, pady=5, padx=10, sticky="nsew")

        # Populate notes
        description = self.item.description or ""
        self.notes_text.insert("1.0", description)
        self.notes_text.focus()

    def save_notes(self):
        """Save the edited notes back to the action item."""
        try:
            # Get the text from the textbox
            notes = self.notes_text.get("1.0", "end-1c").strip()

            # Update the item's description
            self.item.description = notes if notes else None

            # Save to database
            self.db_manager.update_action_item(self.item)
            notify_weekly_tactic_changes(self.db_manager, self)

            print(f"[DEBUG] Notes saved for item: {self.item.id}")

            # Refresh the parent window (TimerWindow) if it exists
            if self.parent_window and self.parent_window.winfo_exists():
                self.parent_window.refresh_notes()

            # Visual feedback - briefly change button color
            self.save_button.configure(text="✓ Saved")
            self.tracked_after(2000, lambda: self.save_button.configure(
                text="Save Notes"))
        except Exception as e:
            print(f"[ERROR] Failed to save notes: {e}")
            import traceback
            traceback.print_exc()
            import tkinter.messagebox as messagebox
            with parent_topmost_suspended(self.parent_window):
                messagebox.showerror("Error", f"Failed to save notes: {e}",
                                     parent=self)

    def refresh_notes(self):
        """Refresh notes textbox from the current item data."""
        try:
            # Clear and update the textbox with current item description
            self.notes_text.delete("1.0", "end")
            description = self.item.description or ""
            self.notes_text.insert("1.0", description)
            print(
                f"[DEBUG] Notes refreshed in NextActionWindow for item: {self.item.id}")
        except Exception as e:
            print(f"[ERROR] Failed to refresh notes in NextActionWindow: {e}")

    def on_window_close(self):
        """Handle window close event."""
        # Clear the parent's reference to this window
        if self.parent_window and self.parent_window.winfo_exists():
            self.parent_window.next_action_window = None

        self.save_window_settings()
        self.destroy()

    def save_window_settings(self):
        """Save window position and size to settings."""
        # Store in settings
        self.settings.next_action_window_width = self.winfo_width()
        self.settings.next_action_window_height = self.winfo_height()
        self.settings.next_action_window_x = self.winfo_x()
        self.settings.next_action_window_y = self.winfo_y()
        self.settings.save()


class NextStepsDialog(ctk.CTkToplevel):
    """Dialog for entering next steps note with date selection."""

    def __init__(self, parent):
        super().__init__(parent)

        self.result = None  # Will be dict with 'note', 'start_date', 'due_date'

        self.title("Next Steps Note")
        self.geometry("450x400")
        self.transient(parent)
        # Appear above always-on-top timer window
        self.attributes('-topmost', True)
        suspend_parent_topmost(self, parent)
        self.grab_set()
        raise_above_parent(self)

        # Center on parent if it still exists
        try:
            self.update_idletasks()
            if parent.winfo_exists():
                x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
                y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
                self.geometry(f"+{x}+{y}")
        except Exception as e:
            # If parent is destroyed, just use default position
            print(f"[DEBUG] Could not center dialog on parent: {e}")

        # Main container
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Title label
        label = ctk.CTkLabel(main_frame, text="Next Steps Note",
                             font=ctk.CTkFont(size=14, weight="bold"))
        label.pack(pady=(5, 10), padx=10)

        # Note textbox
        self.textbox = ctk.CTkTextbox(main_frame, height=120)
        self.textbox.pack(pady=5, padx=10, fill="both", expand=True)
        self.textbox.focus()

        # Date selection frame
        date_frame = ctk.CTkFrame(main_frame)
        date_frame.pack(pady=10, padx=10, fill="x")
        date_frame.grid_columnconfigure(1, weight=1)

        # Default to tomorrow
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        # Start Date
        ctk.CTkLabel(date_frame, text="Start Date:", width=80).grid(
            row=0, column=0, padx=5, pady=5, sticky="w")
        self.start_date_entry = ctk.CTkEntry(date_frame, width=120)
        self.start_date_entry.insert(0, tomorrow)
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Start date quick buttons
        btn_frame_start = ctk.CTkFrame(date_frame)
        btn_frame_start.grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(btn_frame_start, text="Today", width=60, command=lambda: self.set_date(
            self.start_date_entry, 0), **button_style("secondary")).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame_start, text="+1", width=50, command=lambda: self.adjust_date(
            self.start_date_entry, 1), **button_style("secondary")).pack(side="left", padx=2)

        # Due Date
        ctk.CTkLabel(date_frame, text="Due Date:", width=80).grid(
            row=1, column=0, padx=5, pady=5, sticky="w")
        self.due_date_entry = ctk.CTkEntry(date_frame, width=120)
        self.due_date_entry.insert(0, tomorrow)
        self.due_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Due date quick buttons
        btn_frame_due = ctk.CTkFrame(date_frame)
        btn_frame_due.grid(row=1, column=2, padx=5, pady=5)
        ctk.CTkButton(btn_frame_due, text="Today", width=60, command=lambda: self.set_date(
            self.due_date_entry, 0), **button_style("secondary")).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame_due, text="+1", width=50, command=lambda: self.adjust_date(
            self.due_date_entry, 1), **button_style("secondary")).pack(side="left", padx=2)

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color=status_text_color("error"))
        self.error_label.pack(pady=5)

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.save,
            **button_style("primary"),
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            button_frame,
            text="Skip",
            command=self.skip,
            **button_style("secondary"),
        ).pack(side="left", expand=True, padx=5)

    def set_date(self, entry: ctk.CTkEntry, days_offset: int):
        """Set date to today + offset using weekend-aware logic."""
        settings = AppSettings.load()
        new_date = increment_date(
            date.today(), days_offset, settings.include_saturday, settings.include_sunday)
        entry.delete(0, "end")
        entry.insert(0, new_date.isoformat())

    def adjust_date(self, entry: ctk.CTkEntry, days: int):
        """Adjust current date by days using weekend-aware logic."""
        from datetime import datetime
        settings = AppSettings.load()

        current = entry.get().strip()
        if not current:
            self.set_date(entry, days)
            return

        try:
            current_date = datetime.strptime(current, "%Y-%m-%d").date()
            new_date = increment_date(
                current_date, days, settings.include_saturday, settings.include_sunday)
            entry.delete(0, "end")
            entry.insert(0, new_date.isoformat())
        except ValueError:
            # Invalid date, reset to today + days
            self.set_date(entry, days)

    def save(self):
        """Save the note and dates, with validation."""
        note = self.textbox.get("1.0", "end-1c").strip()
        start_date = self.start_date_entry.get().strip()
        due_date = self.due_date_entry.get().strip()

        # Validate dates
        if not start_date or not due_date:
            self.error_label.configure(text="Both dates are required")
            return

        from datetime import datetime
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            due = datetime.strptime(due_date, "%Y-%m-%d").date()

            if due < start:
                self.error_label.configure(
                    text="Due date must be >= Start date")
                return

        except ValueError:
            self.error_label.configure(
                text="Invalid date format (use YYYY-MM-DD)")
            return

        self.result = {
            'note': note if note else None,
            'start_date': start_date,
            'due_date': due_date
        }
        self.destroy()

    def skip(self):
        """Skip and use defaults."""
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        self.result = {
            'note': None,
            'start_date': tomorrow,
            'due_date': tomorrow
        }
        self.destroy()


# --- Reward protocol dialogs -------------------------------------------------
#
# Spec: docs/spec_2026-08-23_dopamine_reward_protocol.md#4-ux-flow-hook-points-into-screenstimer_windowpy
#
# The copy below is the feature, not decoration around it, so it lives in named
# constants and the tests pin the literal strings. In particular the savor copy
# contains no "well done" and no "good job": it points at the artifact and at
# the felt sense of having closed something, because a verbal pat is exactly the
# cheap reward this protocol is trying to stop training.

DELIVERABLE_HINT = "What does 'done' look like? A checkable artifact, not time spent."
DELIVERABLE_BLANK_ERROR = "Name the artifact before you start — that is what the session is for."

SAVOR_TITLE = "Deliverable complete"
SAVOR_WHAT = "You set out to: {deliverable}. It's done."
SAVOR_HOW = (
    "Pause 5 seconds. Look at what you just made. Notice the physical sense of "
    "'closed.' You did something hard and leaned in — feel the effort, not just "
    "the finish."
)
SAVOR_BUTTON = "Finished"


class DeliverableDialog(ctk.CTkToplevel):
    """Confirm what "done" means for this session, before the clock starts.

    Purpose: RP-4.2 — capture the deliverable up front so the reward can be
             contingent on completing it rather than on the timer ringing.
    Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#42-timer-start--confirm-deliverable-in-start_timer-line-407
    Tests:   tests/test_reward_celebration.py::test_rp42a_deliverable_dialog_refuses_blank_and_shows_the_hint

    ``result`` is the confirmed text, or None when the user cancelled. Cancel
    means "do not start", not "start without one" — a reward-tracked session
    with no deliverable has nothing to be contingent on.
    """

    HINT = DELIVERABLE_HINT
    BLANK_ERROR = DELIVERABLE_BLANK_ERROR

    def __init__(self, parent, item_title: str, deliverable: Optional[str] = None,
                 board_title: Optional[str] = None, phase: Optional[str] = None,
                 savor_count: Optional[int] = None, confirm_text: str = "Start"):
        super().__init__(parent)

        self.result: Optional[str] = None

        self.title("Deliverable")
        self.geometry("480x280")
        self.transient(parent)
        self.attributes('-topmost', True)
        suspend_parent_topmost(self, parent)
        self.grab_set()
        raise_above_parent(self)
        _center_on(self, parent, 480, 280)

        ctk.CTkLabel(
            self, text=item_title, font=ctk.CTkFont(size=14, weight="bold"),
            wraplength=440, justify="left",
        ).pack(pady=(14, 4), padx=16, anchor="w")

        if board_title:
            # Factual, not encouraging: which project this counts towards and
            # where it currently sits. No progress bar — the count is a fact
            # about the past, not a target to chase.
            context = f"{board_title} · {savor_count} completed · phase: {phase}"
            ctk.CTkLabel(
                self, text=context, font=ctk.CTkFont(size=11),
                text_color=status_text_color("muted"), wraplength=440, justify="left",
            ).pack(padx=16, anchor="w")

        ctk.CTkLabel(
            self, text=self.HINT, font=ctk.CTkFont(size=12),
            text_color=status_text_color("muted"), wraplength=440, justify="left",
        ).pack(pady=(10, 4), padx=16, anchor="w")

        self.entry = ctk.CTkEntry(self, placeholder_text="Draft section 2's opening paragraph")
        self.entry.pack(pady=4, padx=16, fill="x")
        if deliverable:
            self.entry.insert(0, deliverable)
        self.entry.focus()
        self.entry.bind("<Return>", lambda _event: self.confirm())

        self.error_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(size=11),
            text_color=status_text_color("danger"), wraplength=440, justify="left",
        )
        self.error_label.pack(padx=16, anchor="w")

        button_frame = ctk.CTkFrame(self)
        button_frame.pack(pady=12, padx=16, fill="x")

        self.confirm_button = ctk.CTkButton(
            button_frame, text=confirm_text, command=self.confirm, **button_style("primary"),
        )
        self.confirm_button.pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            button_frame, text="Cancel", command=self.cancel, **button_style("secondary"),
        ).pack(side="left", expand=True, padx=5)

        self.protocol("WM_DELETE_WINDOW", self.cancel)

    def confirm(self):
        """Accept the deliverable, or refuse to close while it is blank."""
        text = self.entry.get().strip()
        if not text:
            self.error_label.configure(text=self.BLANK_ERROR)
            return
        self.result = text
        self.destroy()

    def cancel(self):
        """Close without a deliverable; the caller must not start the timer."""
        self.result = None
        self.destroy()


class SavorDialog(ctk.CTkToplevel):
    """The savor step: attention on the artifact and the effort, briefly.

    Purpose: RP-4.5 — aim the felt "good" signal at what was made and at the
             effort of making it, so wanting attaches to the work itself.
    Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#45-reward-sequence-on-done
    Tests:   tests/test_reward_celebration.py::test_rp45e_savor_dialog_copy_is_verbatim

    ``acknowledged`` records whether the user pressed the button rather than
    closing the window. It does not gate anything — a session that showed the
    savor step showed it either way — but it keeps the two events distinct.
    """

    WHAT = SAVOR_WHAT
    HOW = SAVOR_HOW
    BUTTON = SAVOR_BUTTON

    def __init__(self, parent, snapshot: str):
        super().__init__(parent)

        self.acknowledged = False

        self.title(SAVOR_TITLE)
        self.geometry("460x300")
        self.transient(parent)
        self.attributes('-topmost', True)
        suspend_parent_topmost(self, parent)
        self.grab_set()
        raise_above_parent(self)
        _center_on(self, parent, 460, 300)

        ctk.CTkLabel(
            self, text=SAVOR_TITLE, font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(18, 10), padx=18)

        self.what_label = ctk.CTkLabel(
            self, text=self.WHAT.format(deliverable=snapshot),
            font=ctk.CTkFont(size=14), wraplength=420, justify="left",
        )
        self.what_label.pack(pady=(0, 12), padx=18, anchor="w")

        self.how_label = ctk.CTkLabel(
            self, text=self.HOW, font=ctk.CTkFont(size=12),
            text_color=status_text_color("muted"), wraplength=420, justify="left",
        )
        self.how_label.pack(pady=(0, 14), padx=18, anchor="w")

        ctk.CTkButton(
            self, text=self.BUTTON, command=self.acknowledge, **button_style("primary"),
        ).pack(pady=(0, 16), padx=18)

        self.protocol("WM_DELETE_WINDOW", self.close_unacknowledged)

    def acknowledge(self):
        self.acknowledged = True
        self.destroy()

    def close_unacknowledged(self):
        self.acknowledged = False
        self.destroy()
