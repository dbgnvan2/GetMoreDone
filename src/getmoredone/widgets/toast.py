"""Non-blocking toast notifications to replace modal messageboxes."""

import customtkinter as ctk


_active_toasts = []


def show_toast(widget, message, level="info", duration=4000):
    """Show a non-blocking, auto-dismissing notification banner.

    level: "error" | "warning" | "info" | "success"
    """
    colors = {
        "error":   ("#b02020", "#ffffff"),
        "warning": ("#b06000", "#ffffff"),
        "info":    ("#1a5ea8", "#ffffff"),
        "success": ("#1a7a30", "#ffffff"),
    }
    bg, fg = colors.get(level, colors["info"])

    try:
        root = widget.winfo_toplevel()
    except Exception:
        return

    # Clean up any destroyed toasts
    _active_toasts[:] = [t for t in _active_toasts if t.winfo_exists()]

    toast = ctk.CTkToplevel(root)
    toast.overrideredirect(True)
    toast.wm_attributes("-topmost", True)

    frame = ctk.CTkFrame(toast, fg_color=bg, corner_radius=8, border_width=0)
    frame.pack(fill="both", expand=True, padx=0, pady=0)

    label = ctk.CTkLabel(
        frame,
        text=message,
        text_color=fg,
        wraplength=480,
        justify="left",
        anchor="w",
    )
    label.pack(padx=16, pady=10)

    def dismiss(event=None):
        try:
            toast.destroy()
        except Exception:
            pass
        if toast in _active_toasts:
            _active_toasts.remove(toast)

    frame.bind("<Button-1>", dismiss)
    label.bind("<Button-1>", dismiss)

    # Position: stack from top of root window, offset by existing toasts
    root.update_idletasks()
    toast.update_idletasks()
    offset_y = 24 + sum(
        (t.winfo_height() + 6) for t in _active_toasts if t.winfo_exists()
    )
    rx = root.winfo_x()
    ry = root.winfo_y()
    rw = root.winfo_width()
    tw = toast.winfo_width()
    x = rx + (rw - tw) // 2
    y = ry + offset_y
    toast.geometry(f"+{x}+{y}")

    _active_toasts.append(toast)
    toast.after(duration, dismiss)
