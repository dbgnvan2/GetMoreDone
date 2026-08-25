# Implementation plan — Tk window leak in the test suite

**Date:** 2026-08-24
**Status:** Awaiting approval — no code changed yet.

---

## 1. Findings

Static scan of every `CTk()` / `CTkToplevel()` / `tk.Tk()` / `tk.Toplevel()`
construction in `tests/` and `conftest.py`, checked against its teardown.

### F1 — 29 roots are created and never destroyed (this is the ~30 windows)

Five helper functions build a root, `withdraw()` it, and return it. Nothing
ever destroys them, so one OS window leaks per call:

| Helper | Calls per run | Leaked |
|---|---|---|
| `tests/test_date_picker.py::_root` | 13 | 13 |
| `tests/test_scheduler_project_attach.py::_build_screen` | 6 | 6 |
| `tests/test_today_pin_drag.py::_make_screen` | 5 | 5 |
| `tests/test_item_editor_sash.py::_make_dialog` | 3 | 3 |
| `tests/test_inline_date_offsets.py::_root` | 2 | 2 |
| | | **29** |

They are withdrawn, so they are invisible — which is exactly why this went
unnoticed. `withdraw()` hides a window; it does not release it. The count
matches the ~30 observed almost exactly.

### F2 — 4 tests leak only when they fail

`tests/test_ui_presence.py` calls `root.destroy()` as the last statement of
four tests, not in a `finally`. A failing assertion skips the destroy. This is
not theoretical: a failing `test_project_board_ui_elements_presence` leaked its
root earlier today, and the next test that needed an image died with
`image "pyimage31" doesn't exist`.

### F3 — raw `tkinter` bypasses the off-screen guard entirely

`_keep_tk_windows_off_screen` patches `ctk.CTk` and `ctk.CTkToplevel` only.
`tests/test_app_icon.py` uses `tk.Tk()` in three places. All three are properly
destroyed, so they are **not** part of the leak — but they get neither the
alpha-0 nor the `withdraw()`, so each one flashes a real window on screen.

One of them is worse than the others: `_tk_available()` runs while the module is
being **imported**, because pytest evaluates `skipif` decorators during
collection. That is before any fixture runs, so a fixture-based patch can never
cover it. The file's own docstring records this ("flashed a real window onto the
user's desktop twice per run").

### Checked and NOT a problem

- **Every window fixture is function-scoped** (bare `@pytest.fixture`), and
  pytest runs post-`yield` teardown even when the test fails. Those are sound; a
  function-scoped sweeper cannot destroy a window a later test still needs.
- **No module-scope or session-scope window creation** anywhere in `tests/`.
- **`conftest.py` creates no windows of its own.**
- `test_tk_offscreen.py`'s two newest tests make a root *and* a toplevel and
  destroy only the root. That is correct — destroying a root destroys its
  children — and is flagged by a naive count only.

---

## 2. Root cause

Two independent ones, and they need different fixes:

1. **No teardown discipline for helper-built windows.** A helper that returns a
   window has no natural place to destroy it, so nobody did. Fixing the five
   helpers fixes today's leak; it does nothing about the sixth one somebody adds
   next month.
2. **The guard hides rather than owns.** `_keep_tk_windows_off_screen`
   intercepts every window at construction — it already knows about every window
   in the run — but only adjusts appearance. It is one line away from being able
   to guarantee cleanup, and that is the durable fix.

---

## 3. Acceptance criteria → tests

| ID | Criterion | Test |
|---|---|---|
| WL-1 | A window created during a test and not destroyed by it is destroyed at that test's teardown | `tests/test_tk_offscreen.py::test_a_leaked_window_is_destroyed_at_teardown` |
| WL-2 | The sweeper destroys only windows created *during* the test, never pre-existing ones | `…::test_the_sweeper_leaves_earlier_windows_alone` |
| WL-3 | Destroying a root that already destroyed its children does not raise | `…::test_the_sweeper_survives_a_root_destroyed_with_its_children` |
| WL-4 | The five helpers destroy their windows | `…::test_no_test_helper_returns_an_undestroyed_window` (AST scan, exact list) |
| WL-5 | `tk.Tk` / `tk.Toplevel` are withdrawn and transparent like the ctk classes | `…::test_raw_tkinter_windows_are_hidden_too` |
| WL-6 | The collection-time window in `test_app_icon` is covered | `…::test_the_guard_is_installed_at_import_time_not_fixture_time` |
| WL-7 | No windows survive the run | Nested-pytest check, below |
| WL-8 | Existing guards intact: alpha, withdraw, silenced lift/focus_force/grab_set/-topmost, `mapped_windows`, `GETMOREDONE_NO_MAPPED_WINDOWS` | The existing `test_tk_offscreen.py` tests, unchanged |

---

## 4. The fix

**4a. Make the guard own every window it creates** (`conftest.py`)

The existing `_init` wrapper already runs for every window. Add each one to a
`WeakSet`, and add a **function-scoped autouse** fixture that destroys anything
created during that test and still alive at teardown. Snapshot by object
identity, not `id()` — recycled ids after GC would make it destroy the wrong
window. Swallow errors: destroying a child whose root has gone raises, and that
is fine.

This makes WL-1 true for every test that exists and every test anyone writes
later, including ones that fail an assertion (F2) — so `test_ui_presence` needs
no edit to be safe, though I will still add the `finally` blocks so the
intention is local and readable.

**4b. Fix the five helpers** (F1) — convert each to a function-scoped fixture
that yields and destroys, per the repo's existing pattern. This is the direct
fix; 4a is the net beneath it.

**4c. Cover raw tkinter** (F3) — wrap `tk.Tk` and `tk.Toplevel` with the same
alpha + withdraw treatment. **Install at conftest import time, not in the
fixture**, because `_tk_available()` runs during collection. `conftest.py` is
imported before test modules are collected, so an import-time patch covers it
and a fixture-based one cannot.

**4d. Regression test** (WL-7) — a nested `pytest` run over a temporary test
file that deliberately leaks a window, asserting the sweeper cleaned it up. The
repo already uses nested pytest for exactly this shape of guard-the-guard
(`tests/test_live_data_guard.py`).

---

## 5. Order

1. `conftest.py` — registry + sweeper + raw-tkinter wrap (4a, 4c)
2. `tests/test_tk_offscreen.py` — WL-1…WL-6 (proves 1 before touching the tests)
3. The five helpers (4b) and the four `finally` blocks (F2)
4. WL-7 nested-pytest regression test
5. Handoff note

---

## 6. Verification

- `pytest -q` — full suite green, exit 0.
- **The CGWindowList check you supplied**, run immediately after: `Python`
  owner count must be 0–1, not ~30. I will also run it *before* the fix to
  record the baseline, so the number is measured rather than asserted.
- Every new test proved by mutation against the verbatim original.

---

## 7. Risks

- **The sweeper destroying a window a later test needs.** Mitigated by every
  window fixture being function-scoped (verified above) and by snapshotting so
  only windows created during the test are touched. WL-2 pins it.
- **Import-time patching of `tk.Tk`** is process-wide and not restored until
  exit. Acceptable in a test process, but it means the patch must be harmless
  to a real display — it only sets alpha and withdraws, both of which the ctk
  wrapper already does.
- **Teardown ordering.** Destroying a root that owns still-registered children
  makes the child's own destroy raise. WL-3 pins the swallow.

## 8. Not in scope

No application code changes. No change to `mapped_windows`,
`GETMOREDONE_NO_MAPPED_WINDOWS`, the alpha/withdraw behaviour, or the silenced
focus calls — those are the UI-regression guardrail and stay exactly as they are.
