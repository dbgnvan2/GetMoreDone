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
import pytest

from conftest import reapply_transparency, wrap_deiconify


class _FakeWindow:
    """Stands in for a Tk window whose re-map dropped its opacity.

    X11 behaviour cannot be reproduced on macOS, and the real check needs a
    mapped window — so the reapplication is tested here against a stub, and
    against a real window by
    ``test_a_mapped_window_is_invisible_but_still_measurable``, which is the
    one CI was failing.
    """

    def __init__(self, alpha=1.0, raises=False):
        self.alpha = alpha
        self.raises = raises
        self.calls = []

    def attributes(self, name, value=None):
        self.calls.append((name, value))
        if self.raises:
            raise RuntimeError("window has been destroyed")
        if value is not None:
            self.alpha = value
        return self.alpha


def test_reapply_transparency_sets_alpha_to_zero():
    """A window that came back opaque is made transparent again.

    Setting alpha once at creation is not enough: on X11 the attribute is the
    ``_NET_WM_WINDOW_OPACITY`` property and re-mapping drops it, so
    ``deiconify()`` restores full opacity. That is what put a window on screen
    in CI while the same run was clean on macOS.
    """
    window = _FakeWindow(alpha=1.0)

    reapply_transparency(window)

    assert window.alpha == 0.0, "the window was left opaque"
    assert ("-alpha", 0.0) in window.calls


def test_reapply_transparency_survives_a_destroyed_window():
    """A window destroyed between the deiconify and this call is not an error."""
    window = _FakeWindow(raises=True)

    reapply_transparency(window)  # must not raise

    assert window.calls == [("-alpha", 0.0)]


def test_the_deiconify_wrapper_reapplies_after_calling_through():
    """It must do BOTH: map the window, then take the opacity back off.

    Silencing deiconify hung tests/test_item_editor_sash.py — the window never
    maps and its geometry never resolves — so calling through is load-bearing.
    Reapplying is load-bearing too, because the re-map is what drops the
    opacity on X11. A wrapper doing only one of the two is useless, and which
    one it does cannot be seen from the installed method without a real mapped
    window.
    """
    calls = []

    def fake_original(window, *args, **kwargs):
        calls.append("mapped")
        window.alpha = 1.0          # what an X11 re-map does to the opacity
        return "deiconified"

    wrapped = wrap_deiconify(fake_original)
    window = _FakeWindow(alpha=0.0)

    assert wrapped(window) == "deiconified", "the return value was swallowed"
    assert calls == ["mapped"], (
        "the real deiconify was not called — silencing it hangs the sash test"
    )
    assert window.alpha == 0.0, (
        "the window was mapped and left opaque: the re-map dropped the alpha "
        "and the wrapper did not put it back"
    )


@pytest.mark.parametrize("cls_name", ["CTk", "CTkToplevel"])
def test_deiconify_is_wrapped_to_reapply_transparency(cls_name):
    """The guard has to be installed, not merely defined (P21).

    ``deiconify`` is wrapped rather than silenced: silencing it hung
    tests/test_item_editor_sash.py, because the window never maps and its
    geometry never resolves. Wrapping keeps the map and restores the alpha the
    re-map dropped.
    """
    cls = getattr(ctk, cls_name)

    assert getattr(cls.deiconify, "_gmd_reapplies_transparency", False) is True, (
        f"{cls_name}.deiconify is not wrapped — a window that deiconifies will "
        "come back opaque on any platform that drops opacity on re-map"
    )


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


def test_a_remapped_window_is_made_transparent_again(mapped_windows):
    """A real window that came back opaque is put back, on any platform.

    The neighbouring test caught this on CI and not on macOS, because only X11
    actually drops ``_NET_WM_WINDOW_OPACITY`` when a window is re-mapped — so
    it is a check that only fires on one of the two platforms the suite runs
    on, and it fired five pushes late.

    Forcing the alpha back to 1.0 by hand produces the same STATE the X11
    re-map produces, which is what the wrapper has to recover from. That makes
    the assertion platform-independent: it fails on macOS too if the wrapper
    stops working, instead of waiting for CI to notice.

    Asserts the width as well, because recovering the opacity by refusing to
    map the window would satisfy the first half and hang the sash test.
    """
    import customtkinter as ctk

    window = ctk.CTk()
    try:
        window.geometry("400x300")
        window.update_idletasks()
        window.attributes("-alpha", 1.0)     # exactly what an X11 re-map leaves
        window.update_idletasks()

        window.deiconify()
        window.update_idletasks()

        alpha = float(window.attributes("-alpha"))
        width = window.winfo_width()
    finally:
        window.destroy()

    assert alpha == 0.0, (
        f"a re-mapped window was left visible (alpha={alpha}) — it will appear "
        "over the user's work and take their keyboard"
    )
    assert width > 1, (
        f"the window is not laid out (width={width}); transparency was bought "
        "by not mapping it, which hangs the tests that read real geometry"
    )


def test_a_mapped_window_is_invisible_but_still_measurable(mapped_windows):
    """The three tests that need real geometry must not put anything on screen.

    Withdrawing a window makes ``winfo_width()`` return 1, so the geometry
    contracts cannot be checked without mapping it — and a mapped window on
    macOS appears and takes keyboard focus, interrupting whoever is using the
    machine. Moving it off-screen does not help: macOS clamps it back onto the
    display.

    Full transparency does. Tk lays the window out normally, so geometry and
    real events work, and nothing is drawn. This asserts both halves, because
    each without the other is useless: alpha 0 on a withdrawn window measures
    nothing, and a measurable window at alpha 1 is the problem.
    """
    import customtkinter as ctk

    window = ctk.CTk()
    try:
        window.geometry("400x300")
        window.update_idletasks()
        alpha = float(window.attributes("-alpha"))
        width = window.winfo_width()
        # deiconify must not undo it either: a screen calling deiconify after
        # construction put its window back on the display.
        window.deiconify()
        window.update_idletasks()
        alpha_after_deiconify = float(window.attributes("-alpha"))
    finally:
        window.destroy()
    assert alpha_after_deiconify == 0.0, (
        "deiconify() made the window visible again"
    )

    assert alpha == 0.0, (
        f"a mapped window is visible (alpha={alpha}). It will appear over the "
        "user's work and take their keyboard."
    )
    assert width > 1, (
        f"geometry is unusable (winfo_width={width}). Transparency must not be "
        "implemented by withdrawing the window, or the tests that need real "
        "measurements silently start asserting on 1."
    )
