"""
Action Timer Window.
Provides a countdown timer with pause/resume and completion workflows.
"""

import customtkinter as ctk
import tkinter as tk
import random
from datetime import datetime, timedelta, date
from typing import Optional, Callable
from pathlib import Path
from ..models import ActionItem, WorkLog
from ..db_manager import DatabaseManager
from ..app_settings import AppSettings
from ..date_utils import increment_date
from .week_collision_notice import notify_weekly_tactic_changes
from ..theme import button_style, semantic_colors, status_text_color
from ..utils.audio_playback import play_audio_file_async, play_system_beep
from ..utils.music_library import select_track
from ..utils.icon_loader import load_music_note_icon
from .timer_window_dialogs import CompletionNoteDialog, NextActionWindow, NextStepsDialog
from .timer_window_reward import TimerRewardMixin


class TimerWindow(TimerRewardMixin, ctk.CTkToplevel):
    """Floating timer window for action items.

    The reward protocol (RP-4) lives in TimerRewardMixin; this class owns the
    widgets and the clock.

    Spec: docs/spec_2026-08-23_dopamine_reward_protocol.md#4-ux-flow-hook-points-into-screenstimer_windowpy
    """

    # RP-4.3 / spec decision D2. Break end no longer stops the timer, so there
    # is a fifth state: the break is over and the user has not yet said whether
    # they are resting or starting another focus block. It needs its own name
    # because both countdowns are zero at that moment, and the resume rule in
    # pause_timer reads exactly those two numbers.
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    IN_BREAK = "in_break"
    AWAITING_CHOICE = "awaiting_choice"

    # Every state, in one place. Membership tests spelled out as list literals
    # are how AWAITING_CHOICE got added to tick() and _sync_done_button() and
    # missed in on_window_close(): three enumerations of the same set, and only
    # two were updated. A test reconciles this tuple against every value the
    # module actually assigns to timer_state, so a sixth state cannot be added
    # without appearing here.
    # Tests: tests/test_reward_protocol_timer.py::test_rp44_states_tuple_matches_what_the_code_assigns
    STATES = (STOPPED, RUNNING, PAUSED, IN_BREAK, AWAITING_CHOICE)
    # Anything that is not "stopped" is a live session: the clock may be
    # counting, or waiting for the user, but there is work in progress.
    # Sliced rather than written out, so a state added to STATES joins this
    # automatically and there is only ever one list to update. STOPPED is first
    # in STATES and a test pins that, since the slice depends on it.
    ACTIVE_STATES = STATES[1:]

    def __init__(self, parent, db_manager: DatabaseManager, item: ActionItem,
                 on_close: Optional[Callable] = None,
                 rng: Optional[random.Random] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item = item
        self.on_close_callback = on_close
        self.settings = AppSettings.load()

        # Timer state
        self.timer_state = self.STOPPED
        self.time_block_minutes = item.planned_minutes or self.settings.default_time_block_minutes
        self.break_minutes = self.settings.default_break_minutes
        self.work_minutes = self.time_block_minutes - self.break_minutes

        # Time tracking
        self.work_seconds_remaining = self.work_minutes * 60
        self.break_seconds_remaining = self.break_minutes * 60
        self.work_seconds_elapsed = 0  # Actual work time (excluding pauses)
        self.total_seconds_elapsed = 0  # Wall clock time from start to now
        self.start_timestamp = None  # When timer first started
        self.pause_timestamp = None  # When last paused
        self.resume_timestamp = None  # When last resumed
        self.last_tick_time = None  # For calculating elapsed time

        # UI update timer
        self.update_timer_id = None

        # Track pop-out window for note synchronization
        self.next_action_window = None

        # RP-4: reward-protocol session state (deliverable snapshot, board,
        # phase, and the decision made at Done).
        self.init_reward_session(rng)

        # Music playback
        self.music_player = None
        self.current_music_file = None
        self.current_track_name = None
        self.music_is_playing = False

        # Window setup
        self.setup_window()
        self.create_widgets()
        self.update_display()

        # Handle window close as Stop
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def setup_window(self):
        """Configure window properties."""
        self.title(
            f"{self.item.title} - {self.format_time(self.work_seconds_remaining)}")

        # Set size from settings
        width = self.settings.timer_window_width
        height = self.settings.timer_window_height

        # Set position if saved, otherwise center
        if self.settings.timer_window_x and self.settings.timer_window_y:
            self.geometry(
                f"{width}x{height}+{self.settings.timer_window_x}+{self.settings.timer_window_y}")
        else:
            # Center on screen
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.geometry(f"{width}x{height}+{x}+{y}")

        # Make window stay on top
        self.attributes('-topmost', True)

        # Make window resizable
        self.minsize(300, 400)
        self.resizable(True, True)

        # Grid configuration
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def create_widgets(self):
        """Create all UI widgets."""
        palette = semantic_colors()
        # Main container
        main_frame = ctk.CTkFrame(self)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.grid_rowconfigure(7, weight=1)  # Next steps section expands
        main_frame.grid_columnconfigure(0, weight=1)

        # Action title
        self.title_label = ctk.CTkLabel(
            main_frame,
            text=self.item.title,
            font=ctk.CTkFont(size=18, weight="bold"),
            wraplength=400
        )
        self.title_label.grid(row=0, column=0, pady=(
            10, 20), padx=10, sticky="ew")

        # Time display frame
        time_frame = ctk.CTkFrame(main_frame)
        time_frame.grid(row=1, column=0, pady=10, padx=10, sticky="ew")
        time_frame.grid_columnconfigure(1, weight=1)

        # Time Block
        ctk.CTkLabel(time_frame, text="Time Block:", font=ctk.CTkFont(size=12)).grid(
            row=0, column=0, padx=5, pady=3, sticky="w"
        )
        self.time_block_value = ctk.CTkEntry(time_frame, width=60)
        self.time_block_value.insert(0, str(self.time_block_minutes))
        self.time_block_value.grid(row=0, column=1, padx=5, pady=3, sticky="w")
        ctk.CTkLabel(time_frame, text="min").grid(
            row=0, column=2, padx=5, pady=3, sticky="w")

        # Time To Finish (countdown)
        ctk.CTkLabel(time_frame, text="Time To Finish:", font=ctk.CTkFont(size=12)).grid(
            row=1, column=0, padx=5, pady=3, sticky="w"
        )
        self.time_remaining_label = ctk.CTkLabel(
            time_frame,
            text=self.format_time(self.work_seconds_remaining),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=status_text_color("success")
        )
        self.time_remaining_label.grid(
            row=1, column=1, columnspan=2, padx=5, pady=3, sticky="w")

        # Wrap/Break
        ctk.CTkLabel(time_frame, text="Wrap/Break:", font=ctk.CTkFont(size=12)).grid(
            row=2, column=0, padx=5, pady=3, sticky="w"
        )
        ctk.CTkLabel(time_frame, text=f"{self.break_minutes} min").grid(
            row=2, column=1, columnspan=2, padx=5, pady=3, sticky="w"
        )

        # Timer controls
        controls_frame = ctk.CTkFrame(main_frame)
        controls_frame.grid(row=2, column=0, pady=10, padx=10, sticky="ew")
        controls_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_button = ctk.CTkButton(
            controls_frame,
            text="Start",
            command=self.start_timer,
            **button_style("primary"),
        )
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.pause_button = ctk.CTkButton(
            controls_frame,
            text="Pause",
            command=self.pause_timer,
            **button_style("secondary"),
            state="disabled"
        )
        self.pause_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.stop_button = ctk.CTkButton(
            controls_frame,
            text="Stop",
            command=self.stop_timer,
            **button_style("danger"),
            state="disabled"
        )
        self.stop_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # RP-4.4 — "Done" means the deliverable is finished, and it is
        # available at any point in a session rather than only when the timer
        # rings. Completion is the contingency; elapsed time is not.
        # Spec:  docs/spec_2026-08-23_dopamine_reward_protocol.md#44-done-button-new--deliverable-complete
        # Tests: tests/test_reward_protocol_timer.py::test_rp44_done_button_visibility_across_every_timer_state
        self.done_button = ctk.CTkButton(
            controls_frame,
            text="Done — deliverable complete",
            command=self.done_action,
            **button_style("primary"),
        )
        self.done_button.grid(row=1, column=0, columnspan=3, padx=5, pady=(0, 5), sticky="ew")
        self.done_button.grid_remove()  # nothing to finish until a session starts

        # RP-4.3 — break end offers a neutral choice instead of dropping into
        # the completion flow. The reward must never fire on the ring.
        # Spec:  docs/spec_2026-08-23_dopamine_reward_protocol.md#43-break-end-is-neutral-in-tick-line-537551
        # Tests: tests/test_reward_protocol_timer.py::test_rp43_break_end_does_not_auto_stop
        self.break_choice_frame = ctk.CTkFrame(controls_frame, fg_color="transparent")
        self.break_choice_frame.grid(row=2, column=0, columnspan=3, padx=5, pady=(0, 5), sticky="ew")
        self.break_choice_frame.grid_columnconfigure((0, 1), weight=1)
        self.break_choice_frame.grid_remove()

        self.rest_button = ctk.CTkButton(
            self.break_choice_frame,
            text="Pause (rest)",
            command=self.rest_action,
            **button_style("secondary"),
        )
        self.rest_button.grid(row=0, column=0, padx=(0, 5), sticky="ew")

        self.continue_focus_button = ctk.CTkButton(
            self.break_choice_frame,
            text="Continue focus",
            command=self.continue_focus_action,
            **button_style("secondary"),
        )
        self.continue_focus_button.grid(row=0, column=1, padx=(5, 0), sticky="ew")

        # Music controls (separate row)
        music_frame = ctk.CTkFrame(main_frame)
        music_frame.grid(row=3, column=0, pady=10, padx=10, sticky="ew")
        music_frame.grid_columnconfigure((0, 1, 2), weight=1)

        # Music label
        ctk.CTkLabel(
            music_frame,
            text="🎵 Music:",
            font=ctk.CTkFont(size=12, weight="bold")
        ).grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # Music play button
        self.music_play_button = ctk.CTkButton(
            music_frame,
            text="▶ Play",
            command=self.play_music,
            **button_style("secondary"),
            width=80
        )
        self.music_play_button.grid(row=0, column=1, padx=5, pady=5)

        # Music pause button
        self.music_pause_button = ctk.CTkButton(
            music_frame,
            text="⏸ Pause",
            command=self.pause_music,
            **button_style("secondary"),
            width=80,
            state="disabled"
        )
        self.music_pause_button.grid(row=0, column=2, padx=5, pady=5)

        # Music status line — surfaces why music did/didn't start (no folder,
        # no playable files, now playing) instead of only printing to console.
        self.music_status_label = ctk.CTkLabel(
            music_frame,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=palette["muted_text"],
            wraplength=380,
            justify="left",
        )
        self.music_status_label.grid(
            row=1, column=0, columnspan=3, padx=5, pady=(0, 5), sticky="w")

        # Status label
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Ready to start",
            font=ctk.CTkFont(size=11),
            text_color=palette["muted_text"]
        )
        self.status_label.grid(row=4, column=0, pady=5, padx=10)

        # Completion controls (hidden until stopped)
        self.completion_frame = ctk.CTkFrame(main_frame)
        self.completion_frame.grid(
            row=5, column=0, pady=10, padx=10, sticky="ew")
        self.completion_frame.grid_columnconfigure((0, 1), weight=1)
        self.completion_frame.grid_remove()  # Hidden initially

        self.finished_button = ctk.CTkButton(
            self.completion_frame,
            text="Finished",
            command=self.finished_action,
            **button_style("secondary"),
        )
        self.finished_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.continue_button = ctk.CTkButton(
            self.completion_frame,
            text="Continue",
            command=self.continue_action,
            **button_style("primary"),
        )
        self.continue_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Next Steps section
        next_steps_header = ctk.CTkFrame(main_frame, fg_color="transparent")
        next_steps_header.grid(
            row=6, column=0, pady=(20, 5), padx=10, sticky="ew")
        next_steps_header.grid_columnconfigure(0, weight=1)

        next_steps_label = ctk.CTkLabel(
            next_steps_header,
            text="Notes:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        next_steps_label.grid(row=0, column=0, sticky="w")

        # Pop out notes button
        self.popout_notes_button = ctk.CTkButton(
            next_steps_header,
            text="Pop Out",
            width=90,
            command=self.open_next_action_window,
            **button_style("secondary"),
        )
        self.popout_notes_button.grid(row=0, column=1, padx=5)

        # Save notes button
        self.save_notes_button = ctk.CTkButton(
            next_steps_header,
            text="Save Notes",
            width=100,
            command=self.save_notes,
            **button_style("primary"),
        )
        self.save_notes_button.grid(row=0, column=2, padx=5)

        self.next_steps_text = ctk.CTkTextbox(
            main_frame,
            height=100,
            wrap="word"
        )
        self.next_steps_text.grid(
            row=7, column=0, pady=5, padx=10, sticky="nsew")

        # Populate next steps (keep editable, don't disable)
        description = self.item.description or ""
        self.next_steps_text.insert("1.0", description)

    def save_notes(self):
        """Save the edited notes back to the action item."""
        try:
            # Get the text from the textbox
            notes = self.next_steps_text.get("1.0", "end-1c").strip()

            # Update the item's description
            self.item.description = notes if notes else None

            # Save to database
            self.db_manager.update_action_item(self.item)
            notify_weekly_tactic_changes(self.db_manager, self)

            print(f"[DEBUG] Notes saved for item: {self.item.id}")

            # Refresh the pop-out window if it exists
            if self.next_action_window and self.next_action_window.winfo_exists():
                self.next_action_window.refresh_notes()

            # Visual feedback - briefly change button color
            self.save_notes_button.configure(text="✓ Saved")
            self.after(2000, lambda: self.save_notes_button.configure(
                text="Save Notes"))
        except Exception as e:
            print(f"[ERROR] Failed to save notes: {e}")
            import traceback
            traceback.print_exc()
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to save notes: {e}")

    def _show_error_dialog(self, message: str):
        """Best-effort error dialog for UI flows that may race window teardown."""
        try:
            import tkinter.messagebox as messagebox

            messagebox.showerror("Error", message)
        except tk.TclError as exc:
            print(f"[ERROR] Could not show error dialog: {exc}")

    def _cancel_pending_timer(self):
        """Cancel any queued timer callback if it still exists."""
        if not self.update_timer_id:
            return
        try:
            self.after_cancel(self.update_timer_id)
        except tk.TclError:
            pass
        self.update_timer_id = None

    def refresh_notes(self):
        """Refresh notes textbox from the current item data."""
        try:
            # Clear and update the textbox with current item description
            self.next_steps_text.delete("1.0", "end")
            description = self.item.description or ""
            self.next_steps_text.insert("1.0", description)
            print(
                f"[DEBUG] Notes refreshed in TimerWindow for item: {self.item.id}")
        except Exception as e:
            print(f"[ERROR] Failed to refresh notes in TimerWindow: {e}")

    def open_next_action_window(self):
        """Open the independent Next Action Window."""
        try:
            # If window already exists, just bring it to front
            if self.next_action_window and self.next_action_window.winfo_exists():
                self.next_action_window.lift()
                self.next_action_window.focus_force()
                print(f"[DEBUG] Next Action Window already open, bringing to front")
                return

            # Save current notes from the textbox first
            notes = self.next_steps_text.get("1.0", "end-1c").strip()
            self.item.description = notes if notes else None
            self.db_manager.update_action_item(self.item)
            notify_weekly_tactic_changes(self.db_manager, self)

            # Open the floating window and keep reference
            self.next_action_window = NextActionWindow(
                self, self.db_manager, self.item, self)
            print(
                f"[DEBUG] Next Action Window opened for item: {self.item.id}")
        except Exception as e:
            print(f"[ERROR] Failed to open Next Action Window: {e}")
            import traceback
            traceback.print_exc()
            import tkinter.messagebox as messagebox
            messagebox.showerror(
                "Error", f"Failed to open Next Action Window: {e}")

    def format_time(self, seconds: int) -> str:
        """Format seconds as MM:SS."""
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes:02d}:{secs:02d}"

    def start_timer(self):
        """Start the countdown timer.

        RP-4.2: a project-linked item confirms its deliverable first, and a
        cancelled confirmation starts nothing. That check comes before the
        time-block edit is saved, so cancelling leaves the item exactly as it
        was rather than half-updated.

        Spec:  docs/spec_2026-08-23_dopamine_reward_protocol.md#42-timer-start--confirm-deliverable-in-start_timer-line-407
        Tests: tests/test_reward_protocol_timer.py::test_rp42b_cancelling_the_deliverable_dialog_does_not_start_the_timer
        """
        if not self.prepare_reward_session():
            return

        # Update time block if edited
        try:
            new_time_block = int(self.time_block_value.get())
            if new_time_block != self.time_block_minutes:
                self.time_block_minutes = new_time_block
                self.work_minutes = self.time_block_minutes - self.break_minutes
                self.work_seconds_remaining = self.work_minutes * 60
                # Update action item's planned_minutes
                self.item.planned_minutes = self.time_block_minutes
                self.db_manager.update_action_item(self.item)
                notify_weekly_tactic_changes(self.db_manager, self)
        except ValueError:
            pass

        # Start always begins a *work* block, so an exhausted work countdown is
        # what makes a fresh cycle necessary — whatever the break is on.
        #
        # This deliberately differs from the resume guard in pause_timer, which
        # requires both to be zero. Resuming mid-break should re-enter the break;
        # Start should not. Copying that condition verbatim was the bug: it
        # caught Start-after-a-full-cycle and missed Stop-during-the-break, which
        # leaves work=0 and break=300 and gave a zero-length block whose first
        # tick fired the BREAK TIME alarm and dropped the user back into the
        # break they had just left.
        if self.work_seconds_remaining <= 0:
            self._reset_countdowns()

        self.timer_state = self.RUNNING
        self.start_timestamp = datetime.now()
        self.last_tick_time = datetime.now()

        # Update UI
        self.start_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self.time_block_value.configure(state="disabled")
        self.break_choice_frame.grid_remove()
        # Finished/Continue belong to a stopped session. Left showing, a
        # Start -> Stop -> Start put them on screen beside "Done", and two of
        # the three end the work without the reward protocol ever running —
        # a user reaching for the familiar button silently loses the feature.
        self.completion_frame.grid_remove()
        self._sync_done_button()
        self._update_status_label("Working...", "green")

        # Start music playback
        self._start_music()

        # Start timer loop
        self.tick()

    def pause_timer(self):
        """Pause the timer."""
        if self.timer_state in (self.RUNNING, self.IN_BREAK):
            self.timer_state = self.PAUSED
            self.pause_timestamp = datetime.now()
            self.pause_button.configure(text="Resume")
            self._update_status_label("Paused", "orange")

            # Music continues independently - user controls it separately

            # Cancel timer updates
            if self.update_timer_id:
                self.after_cancel(self.update_timer_id)
                self.update_timer_id = None

        elif self.timer_state == self.PAUSED:
            # Resume
            self.resume_timestamp = datetime.now()

            # Calculate pause duration and add to total elapsed (but not work time)
            if self.pause_timestamp:
                pause_duration = (self.resume_timestamp -
                                  self.pause_timestamp).total_seconds()
                # Note: pause duration is already excluded from work time in tick()

            # RP-4.3b — after a rest taken at break end both countdowns are
            # zero. The rule below would call that "in_break", and a
            # zero-second break re-fires the break-over branch on the very next
            # tick, forever. A fresh cycle is what "resume" means there.
            if self.work_seconds_remaining <= 0 and self.break_seconds_remaining <= 0:
                self.begin_new_focus_cycle()
                return

            self.timer_state = self.RUNNING if self.work_seconds_remaining > 0 else self.IN_BREAK
            self.pause_button.configure(text="Pause")
            status_text = "Working..." if self.timer_state == self.RUNNING else "Break time!"
            status_color = "green" if self.timer_state == self.RUNNING else "blue"
            self._update_status_label(status_text, status_color)

            # Music continues independently - user controls it separately

            self.last_tick_time = datetime.now()
            self.tick()

    def stop_timer(self):
        """Stop the timer."""
        self.timer_state = self.STOPPED

        # Stop music
        self._stop_music()

        # Cancel timer updates
        if self.update_timer_id:
            self.after_cancel(self.update_timer_id)
            self.update_timer_id = None

        # Update UI
        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Pause")
        self.stop_button.configure(state="disabled")
        self.time_block_value.configure(state="normal")
        self.break_choice_frame.grid_remove()
        self._sync_done_button()
        self._update_status_label("Stopped", "red")

        # Show completion buttons
        self.completion_frame.grid()

    def tick(self):
        """Timer tick - called every second."""
        if self.timer_state not in (self.RUNNING, self.IN_BREAK):
            return

        now = datetime.now()

        # Calculate time since last tick
        if self.last_tick_time:
            delta = (now - self.last_tick_time).total_seconds()
            delta = min(delta, 2)  # Cap at 2 seconds to handle system sleep

            # Update work time elapsed
            self.work_seconds_elapsed += int(delta)

            # Update total elapsed time
            if self.start_timestamp:
                self.total_seconds_elapsed = int(
                    (now - self.start_timestamp).total_seconds())

        self.last_tick_time = now

        # Countdown
        if self.timer_state == self.RUNNING:
            self.work_seconds_remaining -= 1

            if self.work_seconds_remaining <= 0:
                # Work time finished, start break
                self.work_seconds_remaining = 0
                self.timer_state = self.IN_BREAK
                self._update_status_label("⏰ BREAK TIME! ⏰", "yellow")
                self.status_label.configure(
                    font=ctk.CTkFont(size=14, weight="bold"))
                self.update_title_bar()
                # Play break start sound
                self.play_sound(is_break_start=True)
                # Flash the window to get attention
                self._flash_window()

        elif self.timer_state == self.IN_BREAK:
            self.break_seconds_remaining -= 1

            if self.break_seconds_remaining <= 0:
                # RP-4.3 — the break ending is not a completion. It used to call
                # stop_timer(), which showed Finished/Continue and so made the
                # timer ringing the thing that ended the work. Now it asks.
                self.break_seconds_remaining = 0
                self._update_status_label("⏰ BREAK OVER! ⏰", "red")
                self.status_label.configure(
                    font=ctk.CTkFont(size=14, weight="bold"))
                # Play break end sound
                self.play_sound(is_break_start=False)
                # Flash the window
                self._flash_window()
                self.enter_break_choice()
                return

        # Update display
        self.update_display()

        # Schedule next tick
        self.update_timer_id = self.after(1000, self.tick)

    def _sync_done_button(self):
        """Show "Done" for every state except stopped.

        Purpose: RP-4.4 — one rule, applied at every transition, rather than a
                 show call on start and a hide call on stop. Written the other
                 way, a state added later silently gets whichever visibility it
                 happened to inherit.
        Tests:   tests/test_reward_protocol_timer.py::test_rp44_done_button_visibility_across_every_timer_state
        """
        if self.timer_state == self.STOPPED:
            self.done_button.grid_remove()
        else:
            self.done_button.grid()

    def enter_break_choice(self):
        """Break over: rest, or another focus block? Neither completes anything.

        Purpose: RP-4.3 — the reward must never fire on the timer ringing.
        Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#43-break-end-is-neutral-in-tick-line-537551
        Tests:   tests/test_reward_protocol_timer.py::test_rp43_break_end_does_not_auto_stop
        """
        self.timer_state = self.AWAITING_CHOICE
        self._cancel_pending_timer()

        # The two buttons below own the choice while it is open; leaving the
        # main Pause button live as well would offer the same action twice
        # under two different names.
        self.pause_button.configure(state="disabled", text="Pause")
        self._sync_done_button()
        self.break_choice_frame.grid()

    def rest_action(self):
        """Stop the clock and wait. Resume starts a fresh focus block."""
        self.break_choice_frame.grid_remove()
        self.timer_state = self.PAUSED
        self.pause_timestamp = datetime.now()
        self.pause_button.configure(state="normal", text="Resume")
        self._sync_done_button()
        self._update_status_label("Resting — Resume starts another block", "orange")

    def continue_focus_action(self):
        """Straight into another focus block, no completion flow in between."""
        self.break_choice_frame.grid_remove()
        self.begin_new_focus_cycle()

    def halt_for_completion(self):
        """Stop the clock for the completion flow, and change nothing else.

        Purpose: the savor step needs the tick cancelled — the dialogs pump the
                 Tk event loop, so an alarm would fire over it. It does not need
                 anything else stop_timer does.
        Tests:   tests/test_reward_protocol_timer.py::test_rp45_the_window_behind_the_savor_prompt_is_not_dressed_as_finished

        Using stop_timer here was too big a hammer, and it landed on exactly the
        moment this feature exists to protect: while the prompt asked the user to
        look at what they had just made, the window behind it turned red and read
        "Stopped", the music cut, Done vanished, and Finished and Continue — the
        two endings the whole protocol routes around — appeared beside it.

        Paused, not stopped: the session is not over until the completion flow
        says so, and if that flow fails the user needs Done still on screen to
        try again.
        """
        self.timer_state = self.PAUSED
        self.pause_timestamp = datetime.now()
        self._cancel_pending_timer()
        self.break_choice_frame.grid_remove()
        # The other two routes into PAUSED both relabel this button, and the
        # state is a lie without it: pressing something marked "Pause" while
        # already paused takes the resume branch. Reached from the break-end
        # choice it was disabled as well, leaving no resume control at all.
        self.pause_button.configure(state="normal", text="Resume")
        self._update_status_label("Recording...", "green")

    def completion_failed(self):
        """Take back what the window is claiming when the completion did not land.

        Purpose: the status label is what survives after the user dismisses the
                 error modal, so it must not be the thing still asserting the
                 work was recorded.
        Tests:   tests/test_reward_protocol_timer.py::test_rp45_a_failed_completion_does_not_leave_the_window_claiming_success

        halt_for_completion runs before anything is persisted, so between it and
        a successful save the window is describing an intention. If the save
        raises, that intention has to be withdrawn — otherwise the item is still
        open, the work log does not exist, and the timer reads green.
        """
        self._update_status_label("Not saved — try Done again", "red")

    def _reset_countdowns(self):
        """Both countdowns back to a full block. The only place that does it."""
        self.work_seconds_remaining = self.work_minutes * 60
        self.break_seconds_remaining = self.break_minutes * 60

    def begin_new_focus_cycle(self):
        """Reset both countdowns and start working again.

        Purpose: RP-4.3a — shared by "Continue focus" and by resuming after a
                 rest, so the two cannot drift into meaning different things.
        Tests:   tests/test_reward_protocol_timer.py::test_rp43a_continue_focus_starts_a_fresh_cycle
                 tests/test_reward_protocol_timer.py::test_rp43b_resume_after_rest_does_not_re_enter_a_zero_second_break
        """
        self._reset_countdowns()
        self.timer_state = self.RUNNING
        self.pause_timestamp = None
        # The break banner left the status label bold and oversized.
        self.status_label.configure(font=ctk.CTkFont(size=11))
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self._sync_done_button()
        self._update_status_label("Working...", "green")
        self.last_tick_time = datetime.now()
        self.update_display()
        self.tick()

    def update_display(self):
        """Update time display and title bar."""
        if self.timer_state == self.IN_BREAK:
            self.time_remaining_label.configure(
                text=self.format_time(self.break_seconds_remaining),
                text_color=status_text_color("info")
            )
        else:
            # Color based on time remaining
            if self.work_seconds_remaining < self.settings.timer_warning_minutes * 60:
                color = status_text_color("success")
            else:
                color = status_text_color("body")

            self.time_remaining_label.configure(
                text=self.format_time(self.work_seconds_remaining),
                text_color=color
            )

        self.update_title_bar()

    def update_title_bar(self):
        """Update window title with time remaining."""
        if self.timer_state == self.IN_BREAK:
            title = f"{self.item.title} - BREAK {self.format_time(self.break_seconds_remaining)}"
        else:
            title = f"{self.item.title} - {self.format_time(self.work_seconds_remaining)}"

        self.title(title)

    def finished_action(self):
        """Handle Finished workflow: complete action and close."""
        try:
            print(f"[DEBUG] Finished button clicked for item: {self.item.id}")

            # Check if window still exists
            if not self.winfo_exists():
                print("[ERROR] Window already destroyed, cannot complete action")
                return

            # Close the Next Action window FIRST if it exists
            if self.next_action_window and self.next_action_window.winfo_exists():
                print(f"[DEBUG] Closing Next Action window before completing")
                self.next_action_window.destroy()
                self.next_action_window = None

            # Update action item's notes from the timer window BEFORE showing dialog
            timer_notes = self.next_steps_text.get("1.0", "end-1c").strip()
            if timer_notes:
                self.item.description = timer_notes
                self.db_manager.update_action_item(self.item)
                notify_weekly_tactic_changes(self.db_manager, self)
                print(f"[DEBUG] Updated action item notes from timer window")

            # Prompt for completion note
            dialog = CompletionNoteDialog(self, "Completion Note")
            self.wait_window(dialog)

            # Check if window still exists after dialog (user might have closed it)
            if not self.winfo_exists():
                print(
                    "[DEBUG] Window was closed while dialog was open, completing action anyway")
                # Still save the work log and complete the item even if window is gone
                completion_note = dialog.result
                self.save_work_log(completion_note)
                self.db_manager.complete_action_item(self.item.id)
                # No parent: this branch exists *because* the window is gone,
                # and Tk raises "bad window path name" on a destroyed parent —
                # which the outer handler would then report as "failed to
                # complete" for an item that was completed.
                notify_weekly_tactic_changes(self.db_manager)
                if self.on_close_callback:
                    self.on_close_callback()
                return

            completion_note = dialog.result
            print(f"[DEBUG] Completion note: {completion_note}")

            # Create work log
            self.save_work_log(completion_note)
            print(f"[DEBUG] Work log saved")

            # Complete the action item
            self.db_manager.complete_action_item(self.item.id)
            notify_weekly_tactic_changes(self.db_manager, self)
            print(f"[DEBUG] Action item completed")

            # Close window
            self.save_window_settings()
            if self.on_close_callback:
                self.on_close_callback()
            self._cleanup_and_destroy()
            print(f"[DEBUG] Timer window closed")
        except Exception as e:
            print(f"[ERROR] Finished action failed: {e}")
            import traceback
            traceback.print_exc()
            # Before the modal, because the label outlives it.
            self.completion_failed()
            self._show_error_dialog(f"Failed to complete action: {e}")

    def continue_action(self):
        """Handle Continue workflow: update current, duplicate, complete, show Next Action screen, present editor."""
        try:
            print(f"[DEBUG] Continue button clicked for item: {self.item.id}")

            # Check if window still exists
            if not self.winfo_exists():
                print("[ERROR] Window already destroyed, cannot continue action")
                return

            # Close the Next Action window FIRST if it exists
            if self.next_action_window and self.next_action_window.winfo_exists():
                print(f"[DEBUG] Closing Next Action window before continuing")
                self.next_action_window.destroy()
                self.next_action_window = None

            # Step 2: Update Current Action Item with notes from the timer window
            timer_notes = self.next_steps_text.get("1.0", "end-1c").strip()
            if timer_notes:
                self.item.description = timer_notes
                self.db_manager.update_action_item(self.item)
                notify_weekly_tactic_changes(self.db_manager, self)
                print(f"[DEBUG] Step 2: Current Action Item updated with notes")

            # Save references we'll need if window gets destroyed
            parent = self.master
            db_manager = self.db_manager
            item = self.item
            on_close_callback = self.on_close_callback
            # start_timestamp / work_seconds_elapsed used to be captured here
            # because the window can be destroyed by the dialog below. They no
            # longer are: save_work_log reads them off self, and destroying a Tk
            # window does not clear the Python attributes on it.

            # Prompt for completion note (for work log)
            completion_dialog = CompletionNoteDialog(self, "Completion Note")
            self.wait_window(completion_dialog)

            completion_note = completion_dialog.result
            print(f"[DEBUG] Completion note: {completion_note}")

            # Check if window still exists after dialog
            window_exists = self.winfo_exists()
            if not window_exists:
                print(
                    "[DEBUG] Window was closed during completion dialog, continuing workflow anyway")

            # Step 3: Duplicate Current Action Item Record
            print(f"[DEBUG] Step 3: Duplicating Current Action Item")

            # Determine parent_id for new item based on current item's parent status
            # If current item has no parent, new item becomes child of current
            # If current item has a parent, new item becomes sibling (shares same parent)
            new_parent_id = None
            if item.parent_id:
                # Current item is a child, so new item should use the same parent
                new_parent_id = item.parent_id
                print(
                    f"[DEBUG] Current item has parent {item.parent_id}, new item will share this parent")
            else:
                # Current item has no parent, so new item becomes child of current
                new_parent_id = item.id
                print(
                    f"[DEBUG] Current item has no parent, new item will be child of current item")

            new_item = ActionItem(
                who=item.who,
                title=item.title,
                description=item.description,  # Will be updated later from Next Action dialog
                # Carried deliberately: Continue means the same piece of work
                # goes on tomorrow, so what "done" looks like has not changed.
                # It was omitted here at first simply because this list is
                # written out field by field and the new one was not added.
                deliverable=item.deliverable,
                contact_id=item.contact_id,
                parent_id=new_parent_id,  # Set parent_id based on logic above
                start_date=item.start_date,  # Will be updated later from Next Action dialog
                due_date=item.due_date,  # Will be updated later from Next Action dialog
                importance=item.importance,
                urgency=item.urgency,
                size=item.size,
                value=item.value,
                group=item.group,
                category=item.category,
                planned_minutes=item.planned_minutes,
                status="open"
            )
            db_manager.create_action_item(new_item)
            print(
                f"[DEBUG] Step 3: New Action Item duplicated with ID: {new_item.id}, parent_id: {new_parent_id}")

            # Step 4: Save Current Action Item as completed (with work log).
            # Routed through save_work_log rather than building a second WorkLog
            # here. Two writers of the same row had already drifted: this one
            # dropped deliverable_snapshot, so the identical session ended with
            # Continue recorded nothing about what it was for while Stop ->
            # Finished recorded it.
            #
            # The reward columns are normally empty here, because Continue does
            # not set _pending_reward. One case fills them and should: Done was
            # pressed, the save failed, and the user ended the session with
            # Continue instead of retrying Done. The flags survive a failed save
            # precisely so that retry records the completion, and ending by
            # Continue is still that same completed deliverable.
            self.save_work_log(completion_note)
            print(f"[DEBUG] Step 4: Work log saved")

            db_manager.complete_action_item(item.id)
            notify_weekly_tactic_changes(db_manager)
            print(f"[DEBUG] Step 4: Current Action Item saved as completed")

            # Step 5: Present Next Action Screen
            dialog_parent = parent if not window_exists else self
            next_action_dialog = NextStepsDialog(dialog_parent)

            if window_exists:
                self.wait_window(next_action_dialog)
                window_exists = self.winfo_exists()
            else:
                dialog_parent.wait_window(next_action_dialog)

            # Step 6: Next Action Screen closed (save or cancel)
            next_action_result = next_action_dialog.result
            print(f"[DEBUG] Step 5-6: Next Action Screen presented and closed")

            if next_action_result:
                # Update the new item with the next action details
                new_item.description = next_action_result['note'] or new_item.description
                new_item.start_date = next_action_result['start_date']
                new_item.due_date = next_action_result['due_date']
                db_manager.update_action_item(new_item)
                notify_weekly_tactic_changes(db_manager)
                print(f"[DEBUG] New Action Item updated with Next Action details")
            else:
                # User cancelled - use default next day dates
                settings = AppSettings.load()
                current_start = date.fromisoformat(
                    item.start_date) if item.start_date else date.today()
                current_due = date.fromisoformat(
                    item.due_date) if item.due_date else date.today()

                new_start = increment_date(
                    current_start, 1, settings.include_saturday, settings.include_sunday)
                new_due = increment_date(
                    current_due, 1, settings.include_saturday, settings.include_sunday)

                new_item.start_date = new_start.isoformat()
                new_item.due_date = new_due.isoformat()
                db_manager.update_action_item(new_item)
                notify_weekly_tactic_changes(db_manager)
                print(
                    f"[DEBUG] Next Action cancelled - using default next day dates")

            new_item_id = new_item.id

            # Close timer if it still exists
            if window_exists:
                self.save_window_settings()
                if on_close_callback:
                    on_close_callback()
                self._cleanup_and_destroy()
                print(f"[DEBUG] Timer window closed")
            else:
                # Window already destroyed, just call the callback
                if on_close_callback:
                    on_close_callback()
                print(
                    f"[DEBUG] Timer window closed (was already destroyed during dialog)")

            # Step 7: Present New Action Item Record
            from .item_editor import ItemEditorDialog
            ItemEditorDialog(parent, db_manager, new_item_id,
                             on_close_callback=on_close_callback)
            print(f"[DEBUG] Step 7: New Action Item Record presented in editor")
            # Step 8: User updates and saves (happens in the editor)
        except Exception as e:
            print(f"[ERROR] Continue action failed: {e}")
            import traceback
            traceback.print_exc()
            self._show_error_dialog(f"Failed to continue action: {e}")

    def save_work_log(self, note: Optional[str] = None):
        """Save work log entry to database, with the reward-protocol audit trail.

        Purpose: RP-4.5b / RP-4.5d — record what the protocol did for this
                 session, and advance the board counter in the same breath.
        Spec:    docs/spec_2026-08-23_dopamine_reward_protocol.md#45-reward-sequence-on-done
        Tests:   tests/test_reward_protocol_timer.py::test_rp45b_done_writes_every_reward_column
                 tests/test_reward_protocol_timer.py::test_rp45d_counter_never_advances_without_a_work_log

        The counter is advanced here rather than as its own step in done_action.
        Spec §4.5 lists it before the save; done that way, a window closed
        between the two leaves a project claiming a completion that no work log
        records, and nothing can tell afterwards which of the two happened.
        """
        if not self.start_timestamp:
            # No session to log. The counter stays put too — a completion that
            # was not recorded must not be counted either.
            if self._done_pressed:
                print("[WARN] Done pressed with no session start; "
                      "nothing logged and savor_count not advanced")
            return

        decision = self._pending_reward

        work_log = WorkLog(
            item_id=self.item.id,
            started_at=self.start_timestamp.isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=self.work_seconds_elapsed // 60,  # Convert to minutes
            note=note,
            deliverable_snapshot=self.session_deliverable,
            deliverable_completed=self._done_pressed,
            savor_delivered=self._savor_shown,
            celebration_type=decision.celebration if decision else None,
            phase=decision.phase if decision else None,
        )

        # One transaction, because these two writes are one fact. Committed
        # separately, a failure between them leaves a row saying
        # deliverable_completed=1, phase='wiring' while the counter that phase is
        # derived from never moved — and nothing afterwards can tell, because the
        # counter is the only source of truth for the phase.
        with self.db_manager.transaction():
            self.db_manager.create_work_log(work_log)

            if decision is not None and self.session_board_id:
                counted = self.db_manager.increment_project_savor_count(
                    self.session_board_id)
                if counted is None:
                    # The board went away mid-session. The session still
                    # happened and is still worth keeping, so this is not
                    # raised — but it is said out loud rather than left to look
                    # like a completion that counted.
                    print("[WARN] project %s no longer exists; the session was "
                          "logged but not counted towards it"
                          % self.session_board_id)

        # Cleared together, and only once the writes have committed.
        #
        # start_timestamp is what makes a second call a no-op, so it is the
        # duplicate guard; the three flags are the session's facts. Clearing the
        # flags in a finally looked safer and was not: the writes are atomic, so
        # a failed attempt leaves nothing behind and a retry with the flags
        # intact produces exactly one correct row — while a retry *without* them
        # wrote the same work as an ordinary session, with no
        # deliverable_completed, no phase, and the board counter never
        # advancing. That path is reachable: save_work_log raises,
        # finished_action reports it, and the user presses Finished.
        self.start_timestamp = None
        self._pending_reward = None
        self._done_pressed = False
        self._savor_shown = False

    def on_window_close(self):
        """Handle window close event - treat as Stop.

        Reads ACTIVE_STATES rather than spelling the values out. The literal
        list this replaced predated AWAITING_CHOICE and was never updated, so
        closing the window at the break-end choice quietly skipped the "treat
        as Stop" this docstring promises.
        """
        if self.timer_state in self.ACTIVE_STATES:
            self.stop_timer()

        self.save_window_settings()

        if self.on_close_callback:
            self.on_close_callback()

        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        """Clean up resources and destroy window safely."""
        # A celebration may still be animating: the completion dialog opens on
        # top of it and this runs moments later. Its scheduled frames have to
        # be cancelled before the window they draw on goes away.
        self.cancel_celebration()

        # Stop music if playing
        self._stop_music()

        # Cancel any pending timer callbacks
        self._cancel_pending_timer()

        # Destroy the window
        try:
            self.destroy()
        except Exception as e:
            # Ignore errors during destruction (e.g., customtkinter scaling tracker race condition)
            print(
                f"[DEBUG] Window destruction completed with minor error (safe to ignore): {e}")

    def save_window_settings(self):
        """Save window position and size to settings."""
        try:
            # Check if window still exists before accessing properties
            if not self.winfo_exists():
                print("[DEBUG] Window already destroyed, skipping settings save")
                return

            self.settings.timer_window_width = self.winfo_width()
            self.settings.timer_window_height = self.winfo_height()
            self.settings.timer_window_x = self.winfo_x()
            self.settings.timer_window_y = self.winfo_y()
            self.settings.save()
        except Exception as e:
            # If window was destroyed during save, log but don't fail
            print(
                f"[DEBUG] Could not save window settings (window may be destroyed): {e}")

    def play_sound(self, is_break_start: bool):
        """Play sound for break start or break end."""
        if not self.settings.enable_break_sounds:
            return

        # Get sound file path from settings
        sound_file = self.settings.break_start_sound if is_break_start else self.settings.break_end_sound

        # Try to play custom sound file if specified
        if sound_file:
            try:
                import os
                if os.path.exists(sound_file):
                    self._play_wav_file(sound_file)
                    return
            except OSError:
                pass  # Fall through to system beep

        # Fall back to system beep
        self._play_system_beep()

    def _play_wav_file(self, file_path: str):
        """Play a WAV file using platform-appropriate method."""
        if not play_audio_file_async(file_path):
            self._play_system_beep()

    def _flash_window(self):
        """Flash the window to get user's attention."""
        try:
            # Flash the window by changing background colors briefly
            original_bg = self._fg_color

            def flash_on():
                self.configure(fg_color=status_text_color("warning"))
                self.after(300, flash_off)

            def flash_off():
                self.configure(fg_color=original_bg)
                self.after(300, flash_on2)

            def flash_on2():
                self.configure(fg_color=status_text_color("warning"))
                self.after(300, flash_off2)

            def flash_off2():
                self.configure(fg_color=original_bg)

            # Start the flash sequence
            self.after(100, flash_on)

            # Also try to raise the window to front
            self.lift()
            self.focus_force()
        except Exception as e:
            print(f"Error flashing window: {e}")

    def _update_status_label(self, text: str, color: str):
        """Update status label with optional track name."""
        if self.current_track_name:
            display_text = f"{text}\n♫ {self.current_track_name}"
        else:
            display_text = text
        resolved_color = status_text_color(color)
        # Reset font to normal unless it's a break notification
        if "BREAK" in text.upper():
            self.status_label.configure(text=display_text, text_color=resolved_color)
        else:
            self.status_label.configure(
                text=display_text, text_color=resolved_color, font=ctk.CTkFont(size=11))

    def _update_status_with_track(self):
        """Update the current status to include track information."""
        # Get current status text and color
        current_text = self.status_label.cget("text")
        current_color = self.status_label.cget("text_color")

        # Remove any existing track info
        if "\n♫" in current_text:
            current_text = current_text.split("\n♫")[0]

        # Update with track name
        self._update_status_label(current_text, current_color)

    def _play_system_beep(self):
        """Play system beep/alert sound."""
        play_system_beep()

    def _set_music_status(self, text: str, level: str = "muted"):
        """Show a music message in the timer window itself, not just the console."""
        try:
            if level == "muted":
                color = semantic_colors()["muted_text"]
            else:
                color = status_text_color(level)
            self.music_status_label.configure(text=text, text_color=color)
        except (tk.TclError, AttributeError):
            pass  # window torn down, or label not built yet

    def _start_music(self) -> bool:
        """Start background music. Returns True if playing, False otherwise.

        On any failure it sets the failure button/flag state and shows why, so
        callers must NOT assume success — check the return value before flipping
        the controls to a 'playing' state.
        """
        # Resolve a track (configured folder, else bundled) with an explicit status.
        selection = select_track(self.settings.music_folder)
        if selection.track is None:
            self._set_music_status(selection.message, "warning")
            print(f"[INFO] Music: {selection.message}")
            self.current_track_name = None
            self.music_is_playing = False
            self.music_play_button.configure(state="normal")
            self.music_pause_button.configure(state="disabled", text="⏸ Pause")
            return False

        music_file = selection.track
        self.current_music_file = music_file
        file_ext = Path(music_file).suffix.lower()

        try:
            import pygame
        except ImportError:
            msg = "pygame not installed — music unavailable."
            self._set_music_status(msg, "warning")
            self.music_is_playing = False
            self.music_play_button.configure(state="normal")
            self.music_pause_button.configure(state="disabled", text="⏸ Pause")
            print(f"[INFO] {msg} Install with: pip install pygame")
            return False

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)

            pygame.mixer.music.load(music_file)
            pygame.mixer.music.set_volume(self.settings.music_volume)
            pygame.mixer.music.play(-1)  # -1 loops indefinitely

            # Give playback a moment to actually start before checking.
            import time
            time.sleep(0.1)

            if not pygame.mixer.music.get_busy():
                self.current_track_name = None
                self.music_is_playing = False
                self.music_play_button.configure(state="normal")
                self.music_pause_button.configure(state="disabled", text="⏸ Pause")
                self._set_music_status(
                    f"Couldn't play {Path(music_file).name} — "
                    "try converting to MP3, WAV, or OGG.",
                    "error",
                )
                print(f"[ERROR] Loaded but won't play: {music_file}")
                return False

            # Playing.
            self.current_track_name = Path(music_file).name
            self.music_is_playing = True
            self.music_play_button.configure(state="disabled")
            self.music_pause_button.configure(state="normal", text="⏸ Pause")
            self._update_status_with_track()

            if selection.status == "fallback_only":
                self._set_music_status(
                    f"Playing {self.current_track_name} ({file_ext} may be "
                    "unreliable — MP3/WAV/OGG recommended).",
                    "warning",
                )
            else:
                self._set_music_status(f"♫ {self.current_track_name}", "success")
            print(f"[INFO] Playing music: {self.current_track_name}")
            return True
        except Exception as e:
            self.current_track_name = None
            self.music_is_playing = False
            self.music_play_button.configure(state="normal")
            self.music_pause_button.configure(state="disabled", text="⏸ Pause")
            self._set_music_status(f"Error playing music: {e}", "error")
            print(f"[ERROR] Error playing music: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _stop_music(self):
        """Stop playing music."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                self.current_track_name = None
                self.music_is_playing = False
                # Update button states
                self.music_play_button.configure(state="normal")
                self.music_pause_button.configure(
                    state="disabled", text="⏸ Pause")
                self._set_music_status("")
                print("[DEBUG] Music stopped")
        except ImportError:
            pass  # pygame not installed
        except Exception as e:
            print(f"[DEBUG] Error stopping music: {e}")

    def _pause_music(self):
        """Pause the currently playing music."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.pause()
                print("[DEBUG] Music paused")
        except ImportError:
            pass
        except Exception as e:
            print(f"[DEBUG] Error pausing music: {e}")

    def _resume_music(self):
        """Resume the paused music."""
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.unpause()
                print("[DEBUG] Music resumed")
        except ImportError:
            pass
        except Exception as e:
            print(f"[DEBUG] Error resuming music: {e}")

    def play_music(self):
        """Public method to play music - triggered by Play button."""
        if not self.music_is_playing:
            # Start fresh music. _start_music sets the button/flag state itself —
            # on success it shows "playing", on failure it shows why and leaves
            # the controls in the stopped state. Don't override that here.
            if self._start_music():
                print("[INFO] Music play button pressed - music started")
            else:
                print("[INFO] Music play button pressed - could not start music")
        else:
            # Resume paused music
            self._resume_music()
            # Update button states
            self.music_play_button.configure(state="disabled")
            self.music_pause_button.configure(state="normal", text="⏸ Pause")
            print("[INFO] Music play button pressed - music resumed")

    def pause_music(self):
        """Public method to pause/resume music - triggered by Pause button."""
        try:
            import pygame
            if pygame.mixer.get_init() and self.music_is_playing:
                if pygame.mixer.music.get_busy():
                    # Music is playing, pause it
                    self._pause_music()
                    self.music_pause_button.configure(text="▶ Resume")
                    self.music_play_button.configure(state="normal")
                    print("[INFO] Music pause button pressed - music paused")
                else:
                    # Music is paused, resume it
                    self._resume_music()
                    self.music_pause_button.configure(text="⏸ Pause")
                    self.music_play_button.configure(state="disabled")
                    print("[INFO] Music pause button pressed - music resumed")
        except ImportError:
            print("[INFO] pygame not installed - music control disabled")
        except Exception as e:
            print(f"[ERROR] Error controlling music: {e}")
