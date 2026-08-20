"""No test may put a window where the user is working, or take their focus.

A full run builds real Tk windows on purpose — that is the only way to prove a
control is wired to the database rather than merely rendered (P25). On macOS
each of those appears, raises itself and grabs the keyboard, so a run threw
dozens of modals over whatever the user was doing.

They are withdrawn on creation, and the calls that would pull one back —
``lift``, ``focus_force``, ``grab_set`` — are no-ops for the run. Moving them
off-screen instead does not work on macOS, which clamps a window back onto the
display. The few tests that read real geometry ask for the ``mapped_windows``
fixture, because ``winfo_width()`` on a withdrawn window returns 1.

This is the guard on the guard (P24): a fixture that quietly stopped working
would look exactly like a passing suite.
"""

import customtkinter as ctk

def test_a_new_root_is_withdrawn():
    root = ctk.CTk()
    try:
        assert root.state() == "withdrawn", (
            "a test root is on screen — the conftest fixture is not applied")
    finally:
        root.destroy()


def test_a_new_dialog_is_withdrawn():
    root = ctk.CTk()
    try:
        dialog = ctk.CTkToplevel(root)
        try:
            root.update()
            assert dialog.state() == "withdrawn", (
                "a dialog is on screen and will land over the user's work")
        finally:
            dialog.destroy()
    finally:
        root.destroy()


def test_the_focus_stealing_calls_are_neutralised():
    """lift/focus_force/grab_set must not pull a window to the front."""
    root = ctk.CTk()
    try:
        dialog = ctk.CTkToplevel(root)
        try:
            dialog.lift()
            dialog.focus_force()
            dialog.grab_set()
            root.update()
            assert dialog.state() == "withdrawn"
            assert dialog.grab_current() in (None, ""), (
                "a test took a modal grab and will block the user's input")
        finally:
            dialog.destroy()
    finally:
        root.destroy()


def test_a_test_can_ask_for_a_mapped_window(mapped_windows):
    """The opt-out has to actually work, or the geometry tests silently rot."""
    root = ctk.CTk()
    try:
        dialog = ctk.CTkToplevel(root)
        try:
            dialog.geometry("400x300")
            dialog.update()
            assert dialog.state() != "withdrawn"
            assert dialog.winfo_width() > 1, (
                "a mapped window still has no layout, so the geometry tests "
                "that depend on this fixture cannot work")
        finally:
            dialog.destroy()
    finally:
        root.destroy()


def test_every_test_that_needs_a_mapped_window_asks_for_one():
    """A test that drives real Tk events must request ``mapped_windows``.

    ``event_generate`` followed by ``update()`` deadlocks on a withdrawn
    window — it does not fail, it hangs, and a hung suite gives no clue which
    test caused it. This is a source check rather than a behavioural one
    because the alternative is discovering it by waiting for a timeout.
    """
    import re
    from pathlib import Path

    tests_dir = Path(__file__).resolve().parent
    offenders = []
    for path in sorted(tests_dir.glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "event_generate" not in text and "withdraw=False" not in text:
            continue
        if "mapped_windows" not in text:
            offenders.append(path.name)
    assert not offenders, (
        "these files drive real Tk events but no test in them requests the "
        f"mapped_windows fixture, so the suite will hang: {offenders}"
    )
