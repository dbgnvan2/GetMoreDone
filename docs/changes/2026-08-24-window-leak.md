# Handoff Note

- Date: 2026-08-24
- Agent: Code
- Topic: Tk window leak in the test suite

## Summary

A full `pytest` run kept 37 Python-owned windows alive at its peak, climbing
monotonically and dropping to zero only when pytest exited. 30 of them were
**mapped** (`onscreen=True`) at `alpha=0.0`, named "Edit Action Item" and "New
Action Item". They saturated the WindowServer, which is what made the machine
beach-ball mid-run.

Two mechanisms, both needed:

1. **Windows were re-mapped after being withdrawn.** `conftest` withdraws every
   window at construction, and then application code maps it again —
   `ItemEditorDialog._finalize_dialog_window()` calls `deiconify()` for every
   dialog it builds. `deiconify` was wrapped to re-apply the alpha that a re-map
   drops on X11, and that wrapper deliberately left the window mapped, because
   silencing `deiconify` outright once hung `test_item_editor_sash` by never
   letting the geometry resolve. It now calls through, lets the layout settle,
   and withdraws again.
2. **Windows were never destroyed.** Five helpers build a root, withdraw it and
   return it, with nothing anywhere to destroy it — 29 by static count. A
   function-scoped autouse fixture now destroys anything created during a test
   and still alive at its end.

**The first diagnosis was wrong, and only the measurement caught it.** The five
helpers looked like the whole story. Adding the teardown sweep alone changed the
peak not at all — 37 before, 37 after, the same curve — because the windows were
not merely undestroyed, they were mapped, and that is where the cost is.

## Files changed

- `conftest.py` — `_LIVE_WINDOWS` registry, `destroy_windows_created_since`,
  the autouse `_destroy_windows_left_behind_by_this_test` fixture, `tk.Tk` /
  `tk.Toplevel` added to the patched classes, and the re-withdraw on `deiconify`
- `tests/test_tk_offscreen.py` — 8 new tests
- 5 test helpers annotated with what owns their teardown

## Verification

- Command: `pytest -q` → **1496 passed, 7 skipped, exit 0**
- Command: `python run.py --selftest` → **4/4, exit 0**
- CGWindowList sampled every 4s across a full run, before and after:

| | Before | After |
|---|---|---|
| Mapped (`onscreen=True`) | **30** | **0 for the whole run** |
| Total, shape | 15→31→35→37, only ever climbing | 22→30→6→9→**0**, rises and falls |

## Risks / Known gaps

- The re-withdraw on `deiconify` is the riskiest part: silencing that call
  outright previously hung a test. It is applied *after* the call through, so
  the layout has already resolved, and `mapped_windows` still bypasses it via
  `_WINDOWS_MAY_BE_MAPPED`. The three geometry tests were run to confirm.
- **Deviation from the approved plan (step 4b):** the five helpers were
  annotated, not converted to fixtures. Converting means editing 29 call sites
  in working tests, and the conftest sweep already covers them including on
  failure paths. Called out rather than quietly taken.

## Next agent actions

- The sibling resource classes are logged in `BACKLOG.md` under "What else may
  be leaking" — `pygame.mixer.init()` with no `quit()` anywhere, 24 uncancelled
  `after()` callbacks in screens, and 11 test sites building a `DatabaseManager`
  without closing it.
