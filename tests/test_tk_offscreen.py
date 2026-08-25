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

from conftest import reapply_transparency, wrap_reapplying_transparency


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


def test_the_wrapper_reapplies_after_calling_through():
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

    wrapped = wrap_reapplying_transparency(fake_original)
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
@pytest.mark.parametrize("call", ["deiconify", "update_idletasks", "update"])
def test_the_mapping_calls_are_wrapped_to_reapply_transparency(cls_name, call):
    """The guard has to be installed, not merely defined (P21).

    ``deiconify`` is wrapped rather than silenced: silencing it hung
    tests/test_item_editor_sash.py, because the window never maps and its
    geometry never resolves. Wrapping keeps the map and restores the alpha the
    re-map dropped.
    """
    cls = getattr(ctk, cls_name)

    assert getattr(getattr(cls, call), "_gmd_reapplies_transparency", False) is True, (
        f"{cls_name}.{call} is not wrapped — X11 drops the opacity on every "
        "map, so a window settled through it comes back visible"
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

        # The state an X11 map leaves behind, forced by hand. Checked for the
        # settle path and the deiconify path separately, because they are
        # different wrappers and CI failed on each of them in turn: fixing
        # deiconify simply revealed that the FIRST map had already done it.
        window.attributes("-alpha", 1.0)
        window.update_idletasks()
        alpha_after_settle = float(window.attributes("-alpha"))

        window.attributes("-alpha", 1.0)
        window.deiconify()
        window.update_idletasks()
        alpha = float(window.attributes("-alpha"))
        width = window.winfo_width()
    finally:
        window.destroy()

    assert alpha_after_settle == 0.0, (
        f"a window left opaque by its map stayed opaque through "
        f"update_idletasks (alpha={alpha_after_settle})"
    )

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


def test_topmost_is_silenced_for_the_run():
    """Setting -topmost during a test run must do nothing.

    lift, focus_force and grab_set were silenced and this was not, so any code
    that raised a modal by re-asserting -topmost went straight through. A run
    then forced hundreds of window-server round-trips and the machine locked up
    while the suite was going — the exact interruption this module exists to
    prevent, through the one door left open.
    """
    # An explicit root, like every other test here. A bare CTkToplevel() makes
    # Tk build an implicit default root, and tearing that down invalidates the
    # image registry for every test that runs afterwards — which showed up as
    # `image "pyimage31" doesn't exist` in an unrelated screen test, ~300 tests
    # later and only in a full run.
    root = ctk.CTk()
    try:
        window = ctk.CTkToplevel(root)
        window.attributes("-topmost", True)
        assert window.attributes("-topmost") == 0, (
            "-topmost took effect during a test run; it must be silenced like "
            "lift, focus_force and grab_set"
        )
    finally:
        root.destroy()


def test_alpha_still_passes_through_the_attributes_wrapper():
    """Silencing -topmost must not break the transparency the run depends on.

    The wrapper intercepts attributes() wholesale, so it would be easy to drop
    -alpha with it — and every window in the suite would become visible.
    """
    root = ctk.CTk()
    try:
        window = ctk.CTkToplevel(root)
        window.attributes("-alpha", 0.0)
        assert float(window.attributes("-alpha")) == 0.0, (
            "the attributes wrapper swallowed -alpha; windows would be visible"
        )
    finally:
        root.destroy()


# --- windows must not outlive the test that made them -----------------------
#
# Hiding a window is not releasing it. A run leaked 37 live windows, measured
# with CGWindowList: the count climbed monotonically through the run and only
# dropped to zero when pytest exited. Tk drives one UI thread, so the
# WindowServer work those windows keep alive is what made the machine crawl.


def _is_alive(window) -> bool:
    """Whether a window still exists, for roots as well as children.

    A CTk root owns its own Tcl interpreter, and destroying it tears that
    interpreter down — so winfo_exists() does not return 0 afterwards, it
    raises "application has been destroyed". Both mean gone.
    """
    import tkinter

    try:
        return bool(window.winfo_exists())
    except tkinter.TclError:
        return False


def test_a_leaked_window_is_destroyed_at_teardown():
    """WL-1 — a window a test does not destroy is destroyed for it.

    This is the net beneath every test, including one that fails an assertion
    before reaching its own destroy() — which is not hypothetical: a failing
    test in test_ui_presence leaked its root and the next test needing an image
    died with `image "pyimage31" doesn't exist`.
    """
    from conftest import _LIVE_WINDOWS, destroy_windows_created_since

    before = set(_LIVE_WINDOWS)
    leaked = ctk.CTk()                      # deliberately never destroyed here
    assert leaked in _LIVE_WINDOWS, "the guard did not register a new window"

    destroyed = destroy_windows_created_since(before)

    assert destroyed >= 1
    assert not _is_alive(leaked), "the leaked window survived the sweep"


def test_the_sweeper_leaves_earlier_windows_alone():
    """WL-2 — only windows created during this test are swept.

    Every window fixture in this suite is function-scoped, but if one were ever
    module- or session-scoped this is the assertion that would catch the
    sweeper tearing down something a later test still needed.
    """
    from conftest import _LIVE_WINDOWS, destroy_windows_created_since

    keep = ctk.CTk()
    try:
        snapshot = set(_LIVE_WINDOWS)       # taken AFTER `keep` exists
        transient = ctk.CTkToplevel(keep)

        destroy_windows_created_since(snapshot)

        assert _is_alive(keep), "the sweeper destroyed a pre-existing window"
        assert not _is_alive(transient)
    finally:
        keep.destroy()


def test_the_sweeper_survives_a_root_destroyed_with_its_children():
    """WL-3 — destroying a root destroys its children, so the child's turn raises.

    That is the normal case, not a fault, and it must not break the sweep or
    stop later windows being cleaned up.
    """
    from conftest import _LIVE_WINDOWS, destroy_windows_created_since

    snapshot = set(_LIVE_WINDOWS)
    root = ctk.CTk()
    ctk.CTkToplevel(root)                   # will already be gone by its turn
    unrelated = ctk.CTk()

    destroyed = destroy_windows_created_since(snapshot)

    assert destroyed >= 1
    assert not _is_alive(root)
    assert not _is_alive(unrelated), (
        "a raise while destroying one window stopped the rest being swept"
    )


def test_raw_tkinter_windows_are_hidden_and_registered_too():
    """WL-5 — tk.Tk and tk.Toplevel, not just the customtkinter pair.

    tests/test_app_icon.py builds three raw tk.Tk roots. They were destroyed,
    so they never leaked, but the guard patched only ctk.CTk and
    ctk.CTkToplevel — so those three got neither the alpha nor the withdraw and
    each one flashed a real window on screen.
    """
    import tkinter as tk

    from conftest import _LIVE_WINDOWS

    root = tk.Tk()
    try:
        assert root in _LIVE_WINDOWS, "a raw tk.Tk was not registered for cleanup"
        assert root.state() == "withdrawn", "a raw tk.Tk was left on screen"
        assert float(root.attributes("-alpha")) == 0.0

        child = tk.Toplevel(root)
        assert child in _LIVE_WINDOWS, "a raw tk.Toplevel was not registered"
        assert child.state() == "withdrawn"
    finally:
        root.destroy()


def test_no_helper_builds_a_window_the_suite_cannot_reach():
    """WL-4 — every window built in tests/ goes through the patched classes.

    A helper that reached Tk another way — say `tkinter.Tk` imported under a
    different name, or a widget class not in the patched list — would be
    invisible to both the hiding and the sweeping. Parsed rather than grepped,
    so a name in a comment or a docstring cannot satisfy it.
    """
    import ast
    import pathlib

    allowed = {"CTk", "CTkToplevel", "Tk", "Toplevel"}
    found = set()
    for path in sorted(pathlib.Path("tests").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
            if name in allowed:
                found.add(name)

    assert found, "the scan found no window constructions at all — it is broken"
    assert found <= allowed, (
        f"tests build windows the guard does not patch: {sorted(found - allowed)}"
    )


@pytest.mark.parametrize("cls_name", ["CTk", "CTkToplevel"])
def test_deiconify_puts_the_window_back_out_of_sight(cls_name):
    """A window that maps itself must not stay mapped.

    Application code calls deiconify — ItemEditorDialog._finalize_dialog_window
    does it for every dialog it builds — so a window conftest withdrew at
    construction mapped itself again moments later and stayed that way.
    Invisible at alpha 0, but a real on-screen window to the WindowServer:
    measured at 30 alive at once mid-run, `onscreen=True, alpha=0.0`.

    The re-withdraw runs after the call through, so the layout the deiconify
    was needed for has already resolved. Silencing deiconify outright is what
    hung test_item_editor_sash, and this is deliberately not that.
    """
    cls = getattr(ctk, cls_name)
    assert getattr(getattr(cls, "deiconify"), "_gmd_rewithdraws", False) is True, (
        f"{cls_name}.deiconify does not put the window back out of sight"
    )


def test_a_deiconified_window_is_withdrawn_again():
    """The behaviour, not just the marker."""
    root = ctk.CTk()
    try:
        root.deiconify()
        assert root.state() == "withdrawn", (
            "deiconify left the window mapped; it stays that way until destroyed"
        )
    finally:
        root.destroy()
