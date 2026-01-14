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
        next_steps_label = ctk.CTkLabel(
            main_frame,
            text="Next Steps:",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        next_steps_label.grid(row=5, column=0, pady=(20, 5), padx=10, sticky="w")

        self.next_steps_text = ctk.CTkTextbox(
            main_frame,
            height=100,
            wrap="word"
        )
        self.next_steps_text.grid(row=6, column=0, pady=5, padx=10, sticky="nsew")

        # Populate next steps
        description = self.item.description or "No description provided."
        self.next_steps_text.insert("1.0", description)
        self.next_steps_text.configure(state="disabled")

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
                self.status_label.configure(text="Break time!", text_color="blue")
                self.update_title_bar()

        elif self.state == "in_break":
            self.break_seconds_remaining -= 1

            if self.break_seconds_remaining <= 0:
                # Break finished, auto-stop
                self.break_seconds_remaining = 0
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
        # Prompt for completion note
        dialog = CompletionNoteDialog(self, "Completion Note")
        self.wait_window(dialog)

        completion_note = dialog.result

        # Create work log
        self.save_work_log(completion_note)

        # Complete the action item
        self.db_manager.complete_action_item(self.item.id)

        # Close window
        self.save_window_settings()
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

    def continue_action(self):
        """Handle Continue workflow: complete current, duplicate for next day."""
        # Prompt for completion note
        completion_dialog = CompletionNoteDialog(self, "Completion Note")
        self.wait_window(completion_dialog)
        completion_note = completion_dialog.result

        # Prompt for next steps note
        next_steps_dialog = CompletionNoteDialog(self, "Next Steps Note")
        self.wait_window(next_steps_dialog)
        next_steps_note = next_steps_dialog.result

        # Save work log for current action
        self.save_work_log(completion_note)

        # Complete current action
        self.db_manager.complete_action_item(self.item.id)

        # Create duplicate for next day
        from datetime import date, timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        new_item = ActionItem(
            who=self.item.who,
            title=self.item.title,
            description=next_steps_note or self.item.description,
            contact_id=self.item.contact_id,
            start_date=tomorrow,
            due_date=tomorrow,
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

        # Close timer and open editor for new item
        self.save_window_settings()
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

        # Open editor for new item
        from .item_editor import ActionItemEditor
        editor = ActionItemEditor(self.master, self.db_manager, new_item.id)

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


class CompletionNoteDialog(ctk.CTkToplevel):
    """Simple dialog for entering completion notes."""

    def __init__(self, parent, title: str):
        super().__init__(parent)

        self.result = None

        self.title(title)
        self.geometry("400x250")
        self.transient(parent)
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
