"""
Action Timer Window.
Provides a countdown timer with pause/resume and completion workflows.
"""

import customtkinter as ctk
from datetime import datetime, timedelta
from typing import Optional, Callable
from ..models import ActionItem, WorkLog
from ..db_manager import DatabaseManager
from ..app_settings import AppSettings


class TimerWindow(ctk.CTkToplevel):
    """Floating timer window for action items."""

    def __init__(self, parent, db_manager: DatabaseManager, item: ActionItem, on_close: Optional[Callable] = None):
        super().__init__(parent)

        self.db_manager = db_manager
        self.item = item
        self.on_close_callback = on_close
        self.settings = AppSettings.load()

        # Timer state
        self.state = "stopped"  # stopped, running, paused, in_break
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

        # Window setup
        self.setup_window()
        self.create_widgets()
        self.update_display()

        # Handle window close as Stop
        self.protocol("WM_DELETE_WINDOW", self.on_window_close)

    def setup_window(self):
        """Configure window properties."""
        self.title(f"{self.item.title} - {self.format_time(self.work_seconds_remaining)}")

        # Set size from settings
        width = self.settings.timer_window_width
        height = self.settings.timer_window_height

        # Set position if saved, otherwise center
        if self.settings.timer_window_x and self.settings.timer_window_y:
            self.geometry(f"{width}x{height}+{self.settings.timer_window_x}+{self.settings.timer_window_y}")
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
        main_frame.grid_rowconfigure(6, weight=1)  # Next steps section expands
        main_frame.grid_columnconfigure(0, weight=1)

        # Action title
        self.title_label = ctk.CTkLabel(
            main_frame,
            text=self.item.title,
            font=ctk.CTkFont(size=18, weight="bold"),
            wraplength=400
        )
        self.title_label.grid(row=0, column=0, pady=(10, 20), padx=10, sticky="ew")

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
        ctk.CTkLabel(time_frame, text="min").grid(row=0, column=2, padx=5, pady=3, sticky="w")

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
        self.time_remaining_label.grid(row=1, column=1, columnspan=2, padx=5, pady=3, sticky="w")

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

        # Status label
        self.status_label = ctk.CTkLabel(
            main_frame,
            text="Ready to start",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self.status_label.grid(row=3, column=0, pady=5, padx=10)

        # Completion controls (hidden until stopped)
        self.completion_frame = ctk.CTkFrame(main_frame)
        self.completion_frame.grid(row=4, column=0, pady=10, padx=10, sticky="ew")
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
        next_steps_header.grid(row=5, column=0, pady=(20, 5), padx=10, sticky="ew")
        next_steps_header.grid_columnconfigure(0, weight=1)

        next_steps_label = ctk.CTkLabel(
            next_steps_header,
            text="Notes:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        next_steps_label.grid(row=0, column=0, sticky="w")

        # Save notes button
        self.save_notes_button = ctk.CTkButton(
            next_steps_header,
            text="Save Notes",
            width=100,
            command=self.save_notes,
            fg_color="green",
            hover_color="darkgreen"
        )
        self.save_notes_button.grid(row=0, column=1, padx=5)

        self.next_steps_text = ctk.CTkTextbox(
            main_frame,
            height=100,
            wrap="word"
        )
        self.next_steps_text.grid(row=6, column=0, pady=5, padx=10, sticky="nsew")

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

            # Visual feedback - briefly change button color
            self.save_notes_button.configure(text="✓ Saved")
            self.after(2000, lambda: self.save_notes_button.configure(text="Save Notes"))
        except Exception as e:
            print(f"[ERROR] Failed to save notes: {e}")
            import traceback
            traceback.print_exc()
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to save notes: {e}")

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

        self.state = "running"
        self.start_timestamp = datetime.now()
        self.last_tick_time = datetime.now()

        # Update UI
        self.start_button.configure(state="disabled")
        self.pause_button.configure(state="normal", text="Pause")
        self.stop_button.configure(state="normal")
        self.time_block_value.configure(state="disabled")
        self.status_label.configure(text="Working...", text_color="green")

        # Start timer loop
        self.tick()

    def pause_timer(self):
        """Pause the timer."""
        if self.state == "running" or self.state == "in_break":
            self.state = "paused"
            self.pause_timestamp = datetime.now()
            self.pause_button.configure(text="Resume")
            self.status_label.configure(text="Paused", text_color="orange")

            # Cancel timer updates
            if self.update_timer_id:
                self.after_cancel(self.update_timer_id)
                self.update_timer_id = None

        elif self.state == "paused":
            # Resume
            self.resume_timestamp = datetime.now()

            # Calculate pause duration and add to total elapsed (but not work time)
            if self.pause_timestamp:
                pause_duration = (self.resume_timestamp - self.pause_timestamp).total_seconds()
                # Note: pause duration is already excluded from work time in tick()

            self.state = "running" if self.work_seconds_remaining > 0 else "in_break"
            self.pause_button.configure(text="Pause")
            self.status_label.configure(
                text="Working..." if self.state == "running" else "Break time!",
                text_color="green" if self.state == "running" else "blue"
            )
            self.last_tick_time = datetime.now()
            self.tick()

    def stop_timer(self):
        """Stop the timer."""
        self.state = "stopped"

        # Cancel timer updates
        if self.update_timer_id:
            self.after_cancel(self.update_timer_id)
            self.update_timer_id = None

        # Update UI
        self.start_button.configure(state="normal")
        self.pause_button.configure(state="disabled", text="Pause")
        self.stop_button.configure(state="disabled")
        self.time_block_value.configure(state="normal")
        self.status_label.configure(text="Stopped", text_color="red")

        # Show completion buttons
        self.completion_frame.grid()

    def tick(self):
        """Timer tick - called every second."""
        if self.state not in ["running", "in_break"]:
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
                self.total_seconds_elapsed = int((now - self.start_timestamp).total_seconds())

        self.last_tick_time = now

        # Countdown
        if self.state == "running":
            self.work_seconds_remaining -= 1

            if self.work_seconds_remaining <= 0:
                # Work time finished, start break
                self.work_seconds_remaining = 0
                self.state = "in_break"
                self.status_label.configure(text="⏰ BREAK TIME! ⏰", text_color="yellow", font=ctk.CTkFont(size=14, weight="bold"))
                self.update_title_bar()
                # Play break start sound
                self.play_sound(is_break_start=True)
                # Flash the window to get attention
                self._flash_window()

        elif self.state == "in_break":
            self.break_seconds_remaining -= 1

            if self.break_seconds_remaining <= 0:
                # Break finished, auto-stop
                self.break_seconds_remaining = 0
                self.status_label.configure(text="⏰ BREAK OVER! ⏰", text_color="red", font=ctk.CTkFont(size=14, weight="bold"))
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
        if self.state == "in_break":
            self.time_remaining_label.configure(
                text=self.format_time(self.break_seconds_remaining),
                text_color="blue"
            )
        else:
            # Color based on time remaining
            if self.work_seconds_remaining < self.settings.timer_warning_minutes * 60:
                color = "green"
            else:
                color="white"

            self.time_remaining_label.configure(
                text=self.format_time(self.work_seconds_remaining),
                text_color=color
            )

        self.update_title_bar()

    def update_title_bar(self):
        """Update window title with time remaining."""
        if self.state == "in_break":
            title = f"{self.item.title} - BREAK {self.format_time(self.break_seconds_remaining)}"
        else:
            title = f"{self.item.title} - {self.format_time(self.work_seconds_remaining)}"

        self.title(title)

    def finished_action(self):
        """Handle Finished workflow: complete action and close."""
        try:
            print(f"[DEBUG] Finished button clicked for item: {self.item.id}")

            # Prompt for completion note
            dialog = CompletionNoteDialog(self, "Completion Note")
            self.wait_window(dialog)

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
            self.destroy()
            print(f"[DEBUG] Timer window closed")
        except Exception as e:
            print(f"[ERROR] Finished action failed: {e}")
            import traceback
            traceback.print_exc()
            # Show error to user
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to complete action: {e}")

    def continue_action(self):
        """Handle Continue workflow: complete current, duplicate for next day."""
        try:
            print(f"[DEBUG] Continue button clicked for item: {self.item.id}")

            # Prompt for completion note
            completion_dialog = CompletionNoteDialog(self, "Completion Note")
            self.wait_window(completion_dialog)
            completion_note = completion_dialog.result
            print(f"[DEBUG] Completion note: {completion_note}")

            # Prompt for next steps note with date selection
            next_steps_dialog = NextStepsDialog(self)
            self.wait_window(next_steps_dialog)
            next_steps_result = next_steps_dialog.result

            if not next_steps_result:
                # User cancelled, abort continue workflow
                print("[DEBUG] User cancelled next steps dialog")
                return

            next_steps_note = next_steps_result['note']
            start_date = next_steps_result['start_date']
            due_date = next_steps_result['due_date']
            print(f"[DEBUG] Next steps: {next_steps_note}, start: {start_date}, due: {due_date}")

            # Save work log for current action
            self.save_work_log(completion_note)
            print(f"[DEBUG] Work log saved")

            # Complete current action
            self.db_manager.complete_action_item(self.item.id)
            print(f"[DEBUG] Current action completed")

            # Create duplicate with user-selected dates
            new_item = ActionItem(
                who=self.item.who,
                title=self.item.title,
                description=next_steps_note or self.item.description,
                contact_id=self.item.contact_id,
                start_date=start_date,
                due_date=due_date,
                importance=self.item.importance,
                urgency=self.item.urgency,
                size=self.item.size,
                value=self.item.value,
                group=self.item.group,
                category=self.item.category,
                planned_minutes=self.item.planned_minutes,
                status="open"
            )

            self.db_manager.create_action_item(new_item)
            print(f"[DEBUG] New item created with ID: {new_item.id}")

            # Save parent and db_manager before destroying window
            parent = self.master
            db_manager = self.db_manager
            new_item_id = new_item.id

            # Close timer and open editor for new item
            self.save_window_settings()
            if self.on_close_callback:
                self.on_close_callback()
            self.destroy()
            print(f"[DEBUG] Timer window closed")

            # Open editor for new item
            from .item_editor import ItemEditorDialog
            ItemEditorDialog(parent, db_manager, new_item_id)
            print(f"[DEBUG] Item editor opened")
        except Exception as e:
            print(f"[ERROR] Continue action failed: {e}")
            import traceback
            traceback.print_exc()
            # Show error to user
            import tkinter.messagebox as messagebox
            messagebox.showerror("Error", f"Failed to continue action: {e}")

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
        if self.state in ["running", "paused", "in_break"]:
            self.stop_timer()

        self.save_window_settings()

        if self.on_close_callback:
            self.on_close_callback()

        self.destroy()

    def save_window_settings(self):
        """Save window position and size to settings."""
        self.settings.timer_window_width = self.winfo_width()
        self.settings.timer_window_height = self.winfo_height()
        self.settings.timer_window_x = self.winfo_x()
        self.settings.timer_window_y = self.winfo_y()
        self.settings.save()

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
                winsound.PlaySound(file_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
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
                    os.system('paplay /usr/share/sounds/freedesktop/stereo/complete.oga 2>/dev/null &')
                else:
                    # Try aplay (ALSA)
                    result = os.system('which aplay > /dev/null 2>&1')
                    if result == 0:
                        os.system('aplay /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null &')
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


class CompletionNoteDialog(ctk.CTkToplevel):
    """Simple dialog for entering completion notes."""

    def __init__(self, parent, title: str):
        super().__init__(parent)

        self.result = None

        self.title(title)
        self.geometry("400x250")
        self.transient(parent)
        self.attributes('-topmost', True)  # Appear above always-on-top timer window
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 400) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 250) // 2
        self.geometry(f"+{x}+{y}")

        # Widgets
        label = ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=14, weight="bold"))
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


class NextStepsDialog(ctk.CTkToplevel):
    """Dialog for entering next steps note with date selection."""

    def __init__(self, parent):
        super().__init__(parent)

        self.result = None  # Will be dict with 'note', 'start_date', 'due_date'

        self.title("Next Steps Note")
        self.geometry("450x400")
        self.transient(parent)
        self.attributes('-topmost', True)  # Appear above always-on-top timer window
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() - 450) // 2
        y = parent.winfo_y() + (parent.winfo_height() - 400) // 2
        self.geometry(f"+{x}+{y}")

        # Main container
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        # Title label
        label = ctk.CTkLabel(main_frame, text="Next Steps Note", font=ctk.CTkFont(size=14, weight="bold"))
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
        ctk.CTkLabel(date_frame, text="Start Date:", width=80).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.start_date_entry = ctk.CTkEntry(date_frame, width=120)
        self.start_date_entry.insert(0, tomorrow)
        self.start_date_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Start date quick buttons
        btn_frame_start = ctk.CTkFrame(date_frame)
        btn_frame_start.grid(row=0, column=2, padx=5, pady=5)
        ctk.CTkButton(btn_frame_start, text="Today", width=60, command=lambda: self.set_date(self.start_date_entry, 0)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame_start, text="+1", width=50, command=lambda: self.adjust_date(self.start_date_entry, 1)).pack(side="left", padx=2)

        # Due Date
        ctk.CTkLabel(date_frame, text="Due Date:", width=80).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.due_date_entry = ctk.CTkEntry(date_frame, width=120)
        self.due_date_entry.insert(0, tomorrow)
        self.due_date_entry.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # Due date quick buttons
        btn_frame_due = ctk.CTkFrame(date_frame)
        btn_frame_due.grid(row=1, column=2, padx=5, pady=5)
        ctk.CTkButton(btn_frame_due, text="Today", width=60, command=lambda: self.set_date(self.due_date_entry, 0)).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame_due, text="+1", width=50, command=lambda: self.adjust_date(self.due_date_entry, 1)).pack(side="left", padx=2)

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
        """Set date to today + offset."""
        from datetime import date, timedelta
        new_date = (date.today() + timedelta(days=days_offset)).isoformat()
        entry.delete(0, "end")
        entry.insert(0, new_date)

    def adjust_date(self, entry: ctk.CTkEntry, days: int):
        """Adjust current date by days."""
        from datetime import datetime, timedelta
        current = entry.get().strip()
        if not current:
            self.set_date(entry, days)
            return

        try:
            current_date = datetime.strptime(current, "%Y-%m-%d").date()
            new_date = (current_date + timedelta(days=days)).isoformat()
            entry.delete(0, "end")
            entry.insert(0, new_date)
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
                self.error_label.configure(text="Due date must be >= Start date")
                return

        except ValueError:
            self.error_label.configure(text="Invalid date format (use YYYY-MM-DD)")
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
