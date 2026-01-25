"""
Action Timer Window.
Provides a countdown timer with pause/resume and completion workflows.
"""

import customtkinter as ctk
from datetime import datetime, timedelta, date
from typing import Optional, Callable
import random
import os
from pathlib import Path
from ..models import ActionItem, WorkLog
from ..db_manager import DatabaseManager
from ..app_settings import AppSettings
from ..date_utils import increment_date
from ..utils.icon_loader import load_music_note_icon


class TimerWindow(ctk.CTkToplevel):
    """Floating timer window for action items."""

    def __init__(self, parent, db_manager: DatabaseManager, item: ActionItem, on_close: Optional[Callable] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item = item
        self.on_close_callback = on_close
        self.settings = AppSettings.load()

        # Timer state
        self.timer_state = "stopped"  # stopped, running, paused, in_break
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
            text_color="green"
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
            fg_color="green",
            hover_color="darkgreen"
        )
        self.start_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.pause_button = ctk.CTkButton(
            controls_frame,
            text="Pause",
            command=self.pause_timer,
            state="disabled"
        )
        self.pause_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.stop_button = ctk.CTkButton(
            controls_frame,
            text="Stop",
            command=self.stop_timer,
            fg_color="red",
            hover_color="darkred",
            state="disabled"
        )
        self.stop_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

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
            fg_color="purple",
            hover_color="darkviolet",
            width=80
        )
        self.music_play_button.grid(row=0, column=1, padx=5, pady=5)

        # Music pause button
        self.music_pause_button = ctk.CTkButton(
            music_frame,
            text="⏸ Pause",
            command=self.pause_music,
            fg_color="purple",
            hover_color="darkviolet",
            width=80,
            state="disabled"
        )
        self.music_pause_button.grid(row=0, column=2, padx=5, pady=5)

        # Status label
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Ready to start",
            font=ctk.CTkFont(size=11),
            text_color="gray"
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
            fg_color="darkblue",
            hover_color="blue"
        )
        self.finished_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        self.continue_button = ctk.CTkButton(
            self.completion_frame,
            text="Continue",
            command=self.continue_action,
            fg_color="darkgreen",
            hover_color="green"
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
            fg_color="blue",
            hover_color="darkblue"
        )
        self.popout_notes_button.grid(row=0, column=1, padx=5)

        # Save notes button
        self.save_notes_button = ctk.CTkButton(
            next_steps_header,
            text="Save Notes",
            width=100,
            command=self.save_notes,
            fg_color="green",
            hover_color="darkgreen"
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
        """Start the countdown timer."""
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
        except ValueError:
            pass

        self.timer_state = "running"
        self.start_timestamp = datetime.now()
        self.last_tick_time = datetime.now()

        # Update UI
        self.start_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self.time_block_value.configure(state="disabled")
        self._update_status_label("Working...", "green")

        # Start music playback
        self._start_music()

        # Start timer loop
        self.tick()

    def pause_timer(self):
        """Pause the timer."""
        if self.timer_state == "running" or self.timer_state == "in_break":
            self.timer_state = "paused"
            self.pause_timestamp = datetime.now()
            self.pause_button.configure(text="Resume")
            self._update_status_label("Paused", "orange")

            # Music continues independently - user controls it separately

            # Cancel timer updates
            if self.update_timer_id:
                self.after_cancel(self.update_timer_id)
                self.update_timer_id = None

        elif self.timer_state == "paused":
            # Resume
            self.resume_timestamp = datetime.now()

            # Calculate pause duration and add to total elapsed (but not work time)
            if self.pause_timestamp:
                pause_duration = (self.resume_timestamp -
                                  self.pause_timestamp).total_seconds()
                # Note: pause duration is already excluded from work time in tick()

            self.timer_state = "running" if self.work_seconds_remaining > 0 else "in_break"
            self.pause_button.configure(text="Pause")
            status_text = "Working..." if self.timer_state == "running" else "Break time!"
            status_color = "green" if self.timer_state == "running" else "blue"
            self._update_status_label(status_text, status_color)

            # Music continues independently - user controls it separately

            self.last_tick_time = datetime.now()
            self.tick()

    def stop_timer(self):
        """Stop the timer."""
        self.timer_state = "stopped"

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
        self._update_status_label("Stopped", "red")

        # Show completion buttons
        self.completion_frame.grid()

    def tick(self):
        """Timer tick - called every second."""
        if self.timer_state not in ["running", "in_break"]:
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
        if self.timer_state == "running":
            self.work_seconds_remaining -= 1

            if self.work_seconds_remaining <= 0:
                # Work time finished, start break
                self.work_seconds_remaining = 0
                self.timer_state = "in_break"
                self._update_status_label("⏰ BREAK TIME! ⏰", "yellow")
                self.status_label.configure(
                    font=ctk.CTkFont(size=14, weight="bold"))
                self.update_title_bar()
                # Play break start sound
                self.play_sound(is_break_start=True)
                # Flash the window to get attention
                self._flash_window()

        elif self.timer_state == "in_break":
            self.break_seconds_remaining -= 1

            if self.break_seconds_remaining <= 0:
                # Break finished, auto-stop
                self.break_seconds_remaining = 0
                self._update_status_label("⏰ BREAK OVER! ⏰", "red")
                self.status_label.configure(
                    font=ctk.CTkFont(size=14, weight="bold"))
                # Play break end sound
                self.play_sound(is_break_start=False)
                # Flash the window
                self._flash_window()
                self.stop_timer()
                return

        # Update display
        self.update_display()

        # Schedule next tick
        self.update_timer_id = self.after(1000, self.tick)

    def update_display(self):
        """Update time display and title bar."""
        if self.timer_state == "in_break":
            self.time_remaining_label.configure(
                text=self.format_time(self.break_seconds_remaining),
                text_color="blue"
            )
        else:
            # Color based on time remaining
            if self.work_seconds_remaining < self.settings.timer_warning_minutes * 60:
                color = "green"
            else:
                color = "white"

            self.time_remaining_label.configure(
                text=self.format_time(self.work_seconds_remaining),
                text_color=color
            )

        self.update_title_bar()

    def update_title_bar(self):
        """Update window title with time remaining."""
        if self.timer_state == "in_break":
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
            # Show error to user - only if window still exists
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror(
                    "Error", f"Failed to complete action: {e}")
            except:
                # Window might be destroyed, just log the error
                print(f"[ERROR] Could not show error dialog: {e}")

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
                print(f"[DEBUG] Step 2: Current Action Item updated with notes")

            # Save references we'll need if window gets destroyed
            parent = self.master
            db_manager = self.db_manager
            item = self.item
            on_close_callback = self.on_close_callback
            start_timestamp = self.start_timestamp
            work_seconds_elapsed = self.work_seconds_elapsed

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

            # Step 4: Save Current Action Item as completed (with work log)
            if start_timestamp:
                work_log = WorkLog(
                    item_id=item.id,
                    started_at=start_timestamp.isoformat(),
                    ended_at=datetime.now().isoformat(),
                    minutes=work_seconds_elapsed // 60,
                    note=completion_note
                )
                db_manager.create_work_log(work_log)
                print(f"[DEBUG] Step 4: Work log saved")

            db_manager.complete_action_item(item.id)
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
            # Show error to user - only if window still exists
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror(
                    "Error", f"Failed to continue action: {e}")
            except:
                # Window might be destroyed, just log the error
                print(f"[ERROR] Could not show error dialog: {e}")

    def save_work_log(self, note: Optional[str] = None):
        """Save work log entry to database."""
        if not self.start_timestamp:
            return

        work_log = WorkLog(
            item_id=self.item.id,
            started_at=self.start_timestamp.isoformat(),
            ended_at=datetime.now().isoformat(),
            minutes=self.work_seconds_elapsed // 60,  # Convert to minutes
            note=note
        )

        self.db_manager.create_work_log(work_log)

    def on_window_close(self):
        """Handle window close event - treat as Stop."""
        if self.timer_state in ["running", "paused", "in_break"]:
            self.stop_timer()

        self.save_window_settings()

        if self.on_close_callback:
            self.on_close_callback()

        self._cleanup_and_destroy()

    def _cleanup_and_destroy(self):
        """Clean up resources and destroy window safely."""
        # Stop music if playing
        self._stop_music()

        # Cancel any pending timer callbacks
        if self.update_timer_id:
            try:
                self.after_cancel(self.update_timer_id)
            except:
                pass
            self.update_timer_id = None

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
            except Exception:
                pass  # Fall through to system beep

        # Fall back to system beep
        self._play_system_beep()

    def _play_wav_file(self, file_path: str):
        """Play a WAV file using platform-appropriate method."""
        import sys
        import os

        try:
            if sys.platform == "win32":
                # Windows
                import winsound
                winsound.PlaySound(
                    file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            elif sys.platform == "darwin":
                # macOS
                os.system(f'afplay "{file_path}" &')
            else:
                # Linux
                os.system(f'aplay "{file_path}" &')
        except Exception as e:
            print(f"Error playing sound file: {e}")
            # Fall back to system beep on error
            self._play_system_beep()

    def _flash_window(self):
        """Flash the window to get user's attention."""
        try:
            # Flash the window by changing background colors briefly
            original_bg = self._fg_color

            def flash_on():
                self.configure(fg_color="orange")
                self.after(300, flash_off)

            def flash_off():
                self.configure(fg_color=original_bg)
                self.after(300, flash_on2)

            def flash_on2():
                self.configure(fg_color="orange")
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
        # Reset font to normal unless it's a break notification
        if "BREAK" in text.upper():
            self.status_label.configure(text=display_text, text_color=color)
        else:
            self.status_label.configure(
                text=display_text, text_color=color, font=ctk.CTkFont(size=11))

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
        import sys
        import os

        try:
            if sys.platform == "win32":
                # Windows system beep
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            elif sys.platform == "darwin":
                # macOS system beep
                os.system('afplay /System/Library/Sounds/Glass.aiff &')
            else:
                # Linux - try multiple methods
                # Try paplay first (PulseAudio)
                result = os.system('which paplay > /dev/null 2>&1')
                if result == 0:
                    os.system(
                        'paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null &')
                else:
                    # Try aplay (ALSA)
                    result = os.system('which aplay > /dev/null 2>&1')
                    if result == 0:
                        os.system(
                            'aplay /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null &')
                    else:
                        # Try beep command
                        result = os.system('which beep > /dev/null 2>&1')
                        if result == 0:
                            os.system('beep -f 800 -l 500 2>/dev/null &')
                        else:
                            # Last resort: terminal bell
                            print('\a')
        except Exception as e:
            print(f"Error playing system beep: {e}")
            # Try terminal bell as last resort
            try:
                print('\a')  # Terminal bell
            except:
                pass  # Silently fail if nothing works
                pass  # Give up silently

    def _get_random_music_file(self) -> Optional[str]:
        """Get a random music file from the configured music folder."""
        if not self.settings.music_folder:
            return None

        music_folder = Path(self.settings.music_folder)
        if not music_folder.exists() or not music_folder.is_dir():
            return None

        # Supported audio formats (pygame has best support for these)
        # Note: M4A/AAC/WMA may not work reliably on all systems
        preferred_formats = {'.mp3', '.wav', '.ogg'}
        problematic_formats = {'.flac', '.m4a', '.aac', '.wma'}
        all_formats = preferred_formats | problematic_formats

        # Get all audio files in the folder
        music_files = [
            f for f in music_folder.iterdir()
            if f.is_file() and f.suffix.lower() in all_formats
        ]

        if not music_files:
            return None

        # Prefer well-supported formats
        preferred_files = [
            f for f in music_files if f.suffix.lower() in preferred_formats]
        if preferred_files:
            return str(random.choice(preferred_files))

        # Fall back to any file, but warn
        selected = random.choice(music_files)
        print(
            f"[WARNING] Selected {selected.suffix} file - this format may not play correctly")
        print(f"[WARNING] For best results, use MP3, WAV, or OGG files")
        return str(selected)

    def _start_music(self):
        """Start playing music from the configured folder."""
        try:
            # Check if music folder is configured
            if not self.settings.music_folder:
                print(
                    "[INFO] No music folder configured. Go to Settings > Timer & Audio to set up music playback.")
                return

            # Get a random music file
            music_file = self._get_random_music_file()
            if not music_file:
                print(
                    f"[INFO] No music files found in: {self.settings.music_folder}")
                print("[INFO] Supported formats: MP3, WAV, OGG, FLAC, M4A, AAC, WMA")
                return

            self.current_music_file = music_file

            # Initialize pygame mixer if not already initialized
            try:
                import pygame
                if not pygame.mixer.get_init():
                    # Initialize with better compatibility settings
                    # frequency=44100, size=-16, channels=2, buffer=512
                    pygame.mixer.init(44100, -16, 2, 512)
                    print(
                        f"[DEBUG] Pygame mixer initialized: {pygame.mixer.get_init()}")

                # Load and play the music file
                file_ext = Path(music_file).suffix.lower()
                pygame.mixer.music.load(music_file)

                # Set volume from settings
                volume = self.settings.music_volume
                pygame.mixer.music.set_volume(volume)
                print(f"[DEBUG] Music volume set to: {volume:.1%}")

                pygame.mixer.music.play(-1)  # -1 means loop indefinitely

                # Check if playback actually started
                # Give it a moment to start
                import time
                time.sleep(0.1)

                if not pygame.mixer.music.get_busy():
                    print(
                        f"[ERROR] Music file loaded but won't play: {file_ext} format may not be supported")
                    print(f"[ERROR] File: {Path(music_file).name}")
                    print(
                        f"[INFO] SOLUTION: Convert your music to MP3, WAV, or OGG format")
                    print(
                        f"[INFO] M4A/AAC files often don't work with pygame on macOS")
                    self.current_track_name = None
                    return

                # Store track name and update status
                self.current_track_name = Path(music_file).name
                self._update_status_with_track()
                print(f"[INFO] ✓ Playing music: {self.current_track_name}")
                print(f"[INFO] Volume: {volume:.0%}")

                # Update music state and button states
                self.music_is_playing = True
                self.music_play_button.configure(state="disabled")
                self.music_pause_button.configure(
                    state="normal", text="⏸ Pause")

                if file_ext in ['.m4a', '.aac', '.wma', '.flac']:
                    print(
                        f"[INFO] Note: {file_ext} format may have playback issues")
                    print(
                        f"[INFO] If you hear clicks/silence, convert to MP3 or WAV")
            except ImportError:
                print("[INFO] pygame not installed - music playback disabled")
                print("[INFO] Install pygame with: pip install pygame")
            except Exception as e:
                print(f"[ERROR] Error playing music: {e}")
                print(
                    f"[ERROR] File: {Path(music_file).name if music_file else 'unknown'}")
                if 'music_file' in locals():
                    file_ext = Path(music_file).suffix.lower()
                    if file_ext in ['.m4a', '.aac', '.wma']:
                        print(
                            f"[ERROR] {file_ext} format is not well-supported by pygame")
                        print(
                            f"[INFO] Convert to MP3, WAV, or OGG for reliable playback")
                import traceback
                traceback.print_exc()

        except Exception as e:
            print(f"[ERROR] Error starting music: {e}")
            import traceback
            traceback.print_exc()

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
            # Start fresh music
            self._start_music()
            self.music_is_playing = True
            # Update button states
            self.music_play_button.configure(state="disabled")
            self.music_pause_button.configure(state="normal", text="⏸ Pause")
            print("[INFO] Music play button pressed - music started")
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
        self.grab_set()

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
            fg_color="green",
            hover_color="darkgreen"
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            button_frame,
            text="Skip",
            command=self.skip
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


class NextActionWindow(ctk.CTkToplevel):
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
            fg_color="green",
            hover_color="darkgreen"
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

            print(f"[DEBUG] Notes saved for item: {self.item.id}")

            # Refresh the parent window (TimerWindow) if it exists
            if self.parent_window and self.parent_window.winfo_exists():
                self.parent_window.refresh_notes()

            # Visual feedback - briefly change button color
            self.save_button.configure(text="✓ Saved")
            self.after(2000, lambda: self.save_button.configure(
                text="Save Notes"))
        except Exception as e:
            print(f"[ERROR] Failed to save notes: {e}")
            import traceback
            traceback.print_exc()
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to save notes: {e}")

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
        self.grab_set()

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
            self.start_date_entry, 0)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame_start, text="+1", width=50, command=lambda: self.adjust_date(
            self.start_date_entry, 1)).pack(side="left", padx=2)

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
            self.due_date_entry, 0)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame_due, text="+1", width=50, command=lambda: self.adjust_date(
            self.due_date_entry, 1)).pack(side="left", padx=2)

        # Error label
        self.error_label = ctk.CTkLabel(main_frame, text="", text_color="red")
        self.error_label.pack(pady=5)

        # Buttons
        button_frame = ctk.CTkFrame(main_frame)
        button_frame.pack(pady=10, padx=10, fill="x")

        ctk.CTkButton(
            button_frame,
            text="Save",
            command=self.save,
            fg_color="green",
            hover_color="darkgreen"
        ).pack(side="left", expand=True, padx=5)

        ctk.CTkButton(
            button_frame,
            text="Skip",
            command=self.skip
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
