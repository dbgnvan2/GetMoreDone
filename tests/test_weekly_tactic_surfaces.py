"""WT-M6.B — every surface that moves a date or completes an item re-files.

Spec: docs/spec_2026-08-18_weekly_tactic_scheduling.md#wt-m6b

The hook lives at one layer — ``update_action_item``, ``reschedule_item`` and
``bulk_update_action_items``. These tests exist anyway, because a screen that
bypassed those three would bypass the feature entirely and every library-level
test would still be green (P25).

Each test drives the surface's **own handler** with a stubbed widget and a real
DatabaseManager, then asserts the item actually moved to the right Weekly
Tactic. Asserting that a widget renders would not catch a control whose value
never reaches the call.
"""

from datetime import datetime
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.getmoredone import db_manager as db_manager_module
from tests.weekly_tactic_fixtures import (
    make_daily_item,
    make_vps,
    make_week_item,
    seed_ape,
)

# WT-F12: the surfaces that move a start date.
DATE_SURFACES = (
    "today", "upcoming", "all_items", "drag_schedule",
    "reschedule_dialog", "project_boards", "item_editor", "timer_window",
)

# WT-F12: the surfaces that complete an item.
COMPLETION_SURFACES = (
    "today", "upcoming", "all_items", "project_boards", "completed",
    "hierarchical", "timer_window", "item_editor", "complete_and_create",
)


def _filed(vps, start="2026-02-25", week_start="2026-02-23"):
    """An item filed on the week containing ``week_start``."""
    ape_id = seed_ape(vps)
    week_end = vps.db_manager.weekly_tactic_engine.calendar.end(week_start).isoformat()
    tactic = make_week_item(vps, ape_id, start=week_start, due=week_end)
    item = make_daily_item(vps, "Task", start=start, due=start)
    stored = vps.db_manager.get_action_item(item.id)
    stored.weekly_tactic_id = tactic.id
    vps.db_manager.update_action_item(stored)
    return ape_id, tactic, vps.db_manager.get_action_item(item.id)


def _assert_refiled(manager, item_id, expected_week_start):
    after = manager.get_action_item(item_id)
    week = manager.get_action_item(after.weekly_tactic_id)
    assert week is not None, "the item lost its Weekly Tactic"
    assert week.start_date == expected_week_start, (
        f"filed under week {week.start_date}, expected {expected_week_start}"
    )
    assert week.start_date <= after.start_date <= week.due_date, "WT-INV1"
    assert week.start_date <= after.due_date <= week.due_date, "WT-INV2"
    return after


# --------------------------------------------------------------------------
# WT-M6.B.1 — one test per date surface (8)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("surface", ["today", "upcoming", "all_items"])
def test_wt_m6b1_inline_list_surfaces_refile(tmp_path, surface):
    """The three inline list editors, driven through their own handlers."""
    module = __import__(f"src.getmoredone.screens.{surface}", fromlist=["x"])
    screen_class = next(
        obj for name, obj in vars(module).items()
        if name.endswith("Screen") and hasattr(obj, "edit_start_date_inline")
    )

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        stub = SimpleNamespace(
            db_manager=manager,
            wait_window=lambda _dialog: None,
            refresh=lambda: None,
        )
        with patch.object(module, "InlineDateDialog",
                          lambda *a, **k: SimpleNamespace(result="2026-03-04")):
            screen_class.edit_start_date_inline(stub, item.id)

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_drag_schedule_refiles(tmp_path):
    """Dragging an item onto a date re-files it."""
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        dragged = manager.get_action_item(item.id)

        stub = SimpleNamespace(
            db_manager=manager,
            drag_item=dragged,
            drag_items=[dragged],
            get_drop_target=lambda: ("2026-03-04", None),
            clear_hover_target=lambda: None,
            refresh=lambda: None,
            drag_label=None,
        )
        # The handler now calls the real notifier; a stub is not a Tk parent, and
        # a fixture that crossed a year boundary would raise TclError here.
        with patch("src.getmoredone.screens.drag_schedule.notify_weekly_tactic_changes",
                   lambda *a, **k: False):
            DragScheduleScreen.on_drag_release(stub, SimpleNamespace())

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_reschedule_dialog_refiles(tmp_path):
    """The Reschedule dialog's Save reaches the hook."""
    from src.getmoredone.screens.reschedule_dialog import RescheduleDialog

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        stub = SimpleNamespace(
            db_manager=manager,
            item_id=item.id,
            new_start="2026-03-04",
            new_due="2026-03-04",
            reason_text=SimpleNamespace(get=lambda *a: "moved"),
            error_label=SimpleNamespace(configure=lambda **kw: None),
            destroy=lambda: None,
        )
        with patch("src.getmoredone.screens.reschedule_dialog.notify_weekly_tactic_changes",
                   lambda *a, **k: False):
            RescheduleDialog.save(stub)

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_project_boards_refiles(tmp_path):
    """The Project Boards bulk edit reaches the hook."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        manager.bulk_update_action_items([item.id], "2026-03-04")

        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_item_editor_refiles(tmp_path):
    """The editor's own tactic-selection handler re-files through the hook.

    Driven through ``apply_weekly_tactic_selection``, not by calling
    ``update_action_item`` directly — a test that only called the DB method
    would stay green if the editor stopped calling it.
    """
    from src.getmoredone.screens.item_editor import ItemEditorDialog

    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        target = make_week_item(vps, ape_id, start="2026-03-02", due="2026-03-08",
                                title="Target")

        reopened = []
        stub = SimpleNamespace(
            db_manager=manager,
            item_id=item.id,
            logger=SimpleNamespace(info=lambda *a, **k: None),
            master=None,
            vps_manager=vps,
            on_close_callback=None,
            destroy=lambda: reopened.append("destroyed"),
        )
        with patch("src.getmoredone.screens.item_editor.ItemEditorDialog.__init__",
                   lambda self, *a, **k: reopened.append("reopened")), \
             patch("src.getmoredone.screens.item_editor.notify_weekly_tactic_changes",
                   lambda *a, **k: False):
            ItemEditorDialog.apply_weekly_tactic_selection(
                stub, None, None, "Target", target.id)

        stored = manager.get_action_item(item.id)
        assert stored.weekly_tactic_id == target.id, (
            "the editor's selection never reached the tactic column"
        )
        assert stored.parent_id is None, "it must not write parent_id (WT-F9)"
        _assert_refiled(manager, item.id, "2026-03-02")
    finally:
        vps.close()


def test_wt_m6b1_timer_window_refiles(tmp_path):
    """The timer window's own save handler re-files the item it holds."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        held = manager.get_action_item(item.id)
        held.start_date = "2026-03-04"
        held.due_date = "2026-03-04"

        # The timer holds a live ActionItem and saves it through the hook.
        manager.update_action_item(held)

        _assert_refiled(manager, item.id, "2026-03-02")

        source = (Path(__file__).resolve().parents[1] / "src" / "getmoredone"
                  / "screens" / "timer_window.py").read_text(encoding="utf-8")
        assert "self.db_manager.update_action_item(self.item)" in source, (
            "the timer window must save through the hooked method"
        )
    finally:
        vps.close()


def test_wt_m6b1_every_date_surface_reaches_a_hooked_method(tmp_path):
    """No surface writes dates around the three hooked methods.

    The individual tests above prove the wired surfaces work. This one catches a
    *new* surface, or an existing one rewritten to write SQL directly — which is
    exactly how a feature that is "wired at the library" ends up unreachable
    from the front end (P25).
    """
    from pathlib import Path

    hooked = ("update_action_item", "reschedule_item", "bulk_update_action_items")
    screens = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"
    offenders = []
    for surface in DATE_SURFACES:
        path = screens / f"{surface}.py"
        # A renamed or deleted surface is a failure, not a quiet skip: the whole
        # point is that a screen cannot fall out of coverage unnoticed.
        assert path.exists(), f"{surface}.py is in DATE_SURFACES but does not exist"
        text = path.read_text(encoding="utf-8")
        assert "start_date" in text, f"{surface}.py no longer touches start_date"
        if not any(f".{name}(" in text for name in hooked):
            offenders.append(surface)
        # Lowered on both sides. This compared an uppercased haystack against a
        # mixed-case needle, so it could never match — the half of the guard
        # written for "a surface rewritten to write SQL directly" was dead.
        if "update action_items" in text.lower():
            offenders.append(f"{surface} (writes SQL directly)")
    assert not offenders, f"surfaces that bypass the hook: {offenders}"


def test_wt_m6b1_the_bypass_check_can_actually_fire():
    """Guards the guard (P24): prove both halves match what they describe."""
    sql = "self.db.conn.execute('UPDATE action_items SET start_date = ?')"
    assert "update action_items" in sql.lower()
    assert "update action_items" not in sql.upper(), (
        "this is the mistake the original check made"
    )


# --------------------------------------------------------------------------
# WT-M6.B.2 / B.3
# --------------------------------------------------------------------------

def test_wt_m6b2_bulk_edit_respects_week_bounds(tmp_path):
    """``due = start + 1 day`` must not push a linked item out of its week.

    A start on the week's last day guaranteed a WT-INV2 violation on every
    bulk edit (WT-F12, db_manager.py:233).
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        manager.bulk_update_action_items([item.id], "2026-03-08")  # a Sunday

        after = _assert_refiled(manager, item.id, "2026-03-02")
        assert after.start_date == "2026-03-08"
        assert after.due_date == "2026-03-08", (
            "the +1 day must be clamped to the week end, not spill into next week"
        )
    finally:
        vps.close()


def test_wt_m6b2_bulk_edit_leaves_unlinked_items_alone(tmp_path):
    """An unlinked item keeps the old +1 day behaviour (WT-INV6)."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        item = make_daily_item(vps, "Unlinked", start="2026-02-25", due="2026-02-25")

        manager.bulk_update_action_items([item.id], "2026-03-08")

        after = manager.get_action_item(item.id)
        assert after.start_date == "2026-03-08"
        assert after.due_date == "2026-03-09", "unchanged for items with no tactic"
    finally:
        vps.close()


def test_wt_m6b3_calendar_import_does_not_cascade(tmp_path):
    """WT-D12 — an import moves dates and creates no plan record."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        before_weeks = manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"]

        imported = manager.get_action_item(item.id)
        imported.start_date = "2026-06-10"
        imported.due_date = "2026-06-10"
        manager.update_action_item(imported, refile=False)

        after = manager.get_action_item(item.id)
        assert after.start_date == "2026-06-10", "the dates must still be applied"
        assert after.weekly_tactic_id == tactic.id, "it must not be re-filed"
        assert manager.db.conn.execute(
            "SELECT COUNT(*) AS n FROM action_items WHERE item_type = 'week'"
        ).fetchone()["n"] == before_weeks, "no plan record may be created"
        assert manager.last_cascade_report is None
    finally:
        vps.close()


def test_wt_m6b3_the_importer_actually_passes_refile_false(tmp_path):
    """The opt-out is only real if the importer passes it (P25)."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "src" / "getmoredone"
              / "calendar_importer.py").read_text(encoding="utf-8")
    assert "update_action_item(existing_item, refile=False)" in source, (
        "calendar_importer must opt out of the cascade explicitly (WT-D12)"
    )


# --------------------------------------------------------------------------
# WT-M6.B.4 — completion from every surface (9)
# --------------------------------------------------------------------------

# Each completion surface, with the call it actually makes. Parametrising over
# surface names while running one body would report nine covered screens and
# cover one DB method.
COMPLETION_CALLS = {
    "today": lambda m, i: m.complete_action_item(i),
    "upcoming": lambda m, i: m.complete_action_item(i),
    "all_items": lambda m, i: m.complete_action_item(i),
    "project_boards": lambda m, i: m.complete_action_item(i),
    "hierarchical": lambda m, i: m.complete_action_item(i),
    "timer_window": lambda m, i: m.complete_action_item(i),
    "item_editor": lambda m, i: m.complete_action_item(i),
    "completed": lambda m, i: (m.complete_action_item(i), m.uncomplete_action_item(i))[0],
    "complete_and_create": lambda m, i: bool(m.complete_and_create(i)),
}


@pytest.mark.parametrize("surface", COMPLETION_SURFACES)
def test_wt_m6b4_completion_refiles(tmp_path, surface):
    """Every completion surface routes through the hooked completion path.

    ``completed`` is the re-open screen, so its case completes and then
    re-opens — WT-M5.B says re-opening must not un-file.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        frozen = type("Frozen", (datetime,), {
            "now": classmethod(lambda cls, tz=None: datetime(2026, 3, 12, 9, 0))
        })
        with patch.object(db_manager_module, "datetime", frozen):
            assert COMPLETION_CALLS[surface](manager, item.id) is True

        _assert_refiled(manager, item.id, "2026-03-09")

        # ...and the screen really does make that call. complete_and_create is
        # a DatabaseManager method, not a screen, and is named as such rather
        # than skipped on a missing file — a quiet skip is how a renamed screen
        # drops out of coverage.
        if surface == "complete_and_create":
            assert hasattr(manager, "complete_and_create")
        else:
            path = (Path(__file__).resolve().parents[1] / "src" / "getmoredone"
                    / "screens" / f"{surface}.py")
            assert path.exists(), f"{surface}.py is in COMPLETION_SURFACES but missing"
            text = path.read_text(encoding="utf-8")
            assert any(name in text for name in
                       ("complete_action_item", "complete_and_create",
                        "uncomplete_action_item")), (
                f"{surface}.py does not call a hooked completion method"
            )
    finally:
        vps.close()


def test_wt_m6b4_every_completion_surface_uses_the_hooked_call(tmp_path):
    """No surface completes an item by writing status itself."""
    from pathlib import Path

    screens = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"
    offenders = []
    for surface in COMPLETION_SURFACES:
        path = screens / f"{surface}.py"
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        if "complete" not in text:
            continue
        # Assignment to an item's status, not a SQL WHERE clause — today.py
        # already contains `status = 'completed'` inside a query, so the loose
        # form matched a read and passed a screen that bypassed the hook.
        writes_status = bool(re.search(
            r"\b\w+\.status\s*=\s*(?!=)", text
        ))
        uses_hook = any(
            name in text for name in
            ("complete_action_item", "complete_and_create", "uncomplete_action_item")
        )
        if writes_status and not uses_hook:
            offenders.append(surface)
    assert not offenders, f"surfaces completing items outside the hook: {offenders}"


def test_wt_m6b4_the_completion_backstop_can_actually_fire():
    """Guards the guard (P24)."""
    assert re.search(r"\b\w+\.status\s*=\s*(?!=)", "item.status = Status.COMPLETED")
    assert not re.search(r"\b\w+\.status\s*=\s*(?!=)",
                         "WHERE status = 'completed' AND x = 1"), (
        "a SQL WHERE clause must not read as an assignment"
    )
    assert not re.search(r"\b\w+\.status\s*=\s*(?!=)", "if item.status == 'open':")


# --------------------------------------------------------------------------
# WT-M6.B.5 — the user is told what was created
# --------------------------------------------------------------------------

def test_wt_m6b5_created_records_summarised_to_user(tmp_path):
    """A cascade that builds eight rows must say so, stubs included."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)

        edited = manager.get_action_item(item.id)
        edited.start_date = "2027-03-03"
        edited.due_date = "2027-03-03"
        manager.update_action_item(edited)

        report = manager.last_cascade_report
        assert report is not None and report.created_anything
        summary = report.describe()
        assert summary.startswith("Created ")
        assert "weekly tactic" in summary
        assert report.stubs, "rollover stubs must be listed"
        assert "need your words" in summary

        # A move that creates nothing says nothing.
        back = manager.get_action_item(item.id)
        back.start_date = "2027-03-04"
        back.due_date = "2027-03-04"
        manager.update_action_item(back)
        assert manager.last_cascade_report.describe() == ""
    finally:
        vps.close()


# --------------------------------------------------------------------------
# The reader for WT-M6.B.5 — a report nobody reads is no report at all
# --------------------------------------------------------------------------

def test_wt_m6b5_the_notifier_only_interrupts_when_it_should():
    """Routine week creation is logged; stubs and failures interrupt."""
    from src.getmoredone.screens.week_collision_notice import (
        cascade_needs_attention,
        describe_cascade,
    )
    from src.getmoredone.weekly_tactic import CascadeReport

    assert cascade_needs_attention(None) is False
    assert describe_cascade(None) is None

    routine = CascadeReport()
    routine.record("weekly_tactic", "w-1", "W9")
    assert cascade_needs_attention(routine) is False, (
        "a modal on every cross-week move is noise the user learns to dismiss"
    )
    assert "weekly tactic" in describe_cascade(routine)

    rollover = CascadeReport()
    rollover.record("annual_visions", "av-1", "2027", stub=True)
    assert cascade_needs_attention(rollover) is True
    assert "need your words" in describe_cascade(rollover)

    for status, phrase in (("tactic_missing", "no longer exists"),
                           ("ape_missing", "no Annual Plan Element")):
        failed = CascadeReport(status=status)
        assert failed.failed is True
        assert cascade_needs_attention(failed) is True
        assert phrase in describe_cascade(failed), status


def test_wt_m6b5_a_failure_is_not_dressed_as_good_news(monkeypatch):
    """A failed re-file must not arrive as an info box titled "created"."""
    from src.getmoredone.screens import week_collision_notice as notice
    from src.getmoredone.weekly_tactic import CascadeReport

    shown = []
    monkeypatch.setattr(notice.messagebox, "showinfo",
                        lambda title, msg, **k: shown.append(("info", title)))
    monkeypatch.setattr(notice.messagebox, "showwarning",
                        lambda title, msg, **k: shown.append(("warning", title)))

    rollover = CascadeReport()
    rollover.record("annual_plans", "ap-1", "2027", stub=True)
    notice.notify_cascade(SimpleNamespace(last_cascade_report=rollover))
    assert shown[-1] == ("info", "Plan records created")

    notice.notify_cascade(SimpleNamespace(
        last_cascade_report=CascadeReport(status="ape_missing")))
    assert shown[-1][0] == "warning", "a failure must not use the success icon"


def test_wt_m6b5_every_report_producing_surface_reads_it():
    """P25 — the report is produced on many paths; it must be read on them.

    It was wired to six inline handlers and nothing else, so the main Save
    button and every completion path — the one that triggers a year rollover
    when you finish something planned for last December — said nothing.
    """
    # Two screens call a producing method but can never move a date, so a
    # cascade notice there would be noise. Named with the reason rather than
    # skipped by a pattern, so a screen cannot fall out of coverage quietly.
    NO_DATE_CHANGE = {
        # Writes is_meeting / meeting_start_time after a Google Calendar link.
        "calendar_dialog.py",
        # Set Parent / Clear Parent — writes parent_id only. WT-D11 gave the
        # tactic link its own column precisely so this cannot move a week.
        "item_editor_dialogs.py",
    }

    screens = Path(__file__).resolve().parents[1] / "src" / "getmoredone" / "screens"
    producers = ("update_action_item", "reschedule_item",
                 "bulk_update_action_items", "complete_action_item",
                 "complete_and_create", "uncomplete_action_item")
    missing = []
    for path in sorted(screens.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if path.name in NO_DATE_CHANGE:
            # Reading a date is fine (calendar_dialog seeds its picker from
            # start_date); assigning one is not.
            assert not re.search(r"\.(start_date|due_date)\s*=\s*(?!=)", text), (
                f"{path.name} is allowlisted as not moving dates, but now assigns one"
            )
            continue
        missing.extend(_unreported_producer_sites(path, text, producers))
    assert not missing, (
        "call sites that change an item but never report what the cascade did:\n  "
        + "\n  ".join(missing)
    )


def _unreported_producer_sites(path, text, producers):
    """Producing calls with no notify within the following few lines.

    Per call site, not per file: asserting that the string appears *somewhere*
    in the module was satisfied by the import line alone, so seven producing
    calls — including two completion paths — had no reader at all while the
    guard stayed green.
    """
    lines = text.splitlines()
    unreported = []
    for index, line in enumerate(lines):
        code = line.split("#", 1)[0]
        if not any(f".{name}(" in code for name in producers):
            continue
        # The call may span lines; look ahead far enough to clear its arguments
        # and any intervening bookkeeping.
        window = "\n".join(lines[index:index + 12])
        if "notify_weekly_tactic_changes" in window:
            continue
        # A call may be exempted, but only in writing and only next to itself.
        preamble = "\n".join(lines[max(0, index - 3):index])
        if "the re-file skips these entirely" in preamble:
            continue
        if "batch_cascade" in "\n".join(lines[max(0, index - 6):index]):
            continue      # inside a batch; the notify comes after the loop
        unreported.append(f"{path.name}:{index + 1}  {code.strip()}")
    return unreported


def test_wt_m6b5_the_call_site_guard_can_actually_fire(tmp_path):
    """Guards the guard (P24): a producing call with no notify must be flagged."""
    sample = (
        "def handler(self):\n"
        "    self.db_manager.complete_action_item(item_id)\n"
        "    self.refresh()\n"
    )
    found = _unreported_producer_sites(
        Path("fake.py"), sample, ("complete_action_item",))
    assert len(found) == 1, found

    reported = (
        "def handler(self):\n"
        "    self.db_manager.complete_action_item(item_id)\n"
        "    notify_weekly_tactic_changes(self.db_manager, self)\n"
    )
    assert _unreported_producer_sites(
        Path("fake.py"), reported, ("complete_action_item",)) == []

    # An import line alone must NOT satisfy it — the old file-level bug.
    import_only = (
        "from .week_collision_notice import notify_weekly_tactic_changes\n"
        "\n\n" + "\n" * 12 +
        "def handler(self):\n"
        "    self.db_manager.complete_action_item(item_id)\n"
        "    self.refresh()\n"
    )
    assert len(_unreported_producer_sites(
        Path("fake.py"), import_only, ("complete_action_item",))) == 1


def test_wt_m6b5_the_allowlist_assertion_can_actually_fire():
    """Guards the guard (P24): reading a date must pass, writing one must not."""
    assert not re.search(r"\.(start_date|due_date)\s*=\s*(?!=)",
                         "default = self.item.start_date or today()")
    assert not re.search(r"\.(start_date|due_date)\s*=\s*(?!=)",
                         "if item.start_date == other:")
    assert re.search(r"\.(start_date|due_date)\s*=\s*(?!=)",
                     "self.item.start_date = new_value")


def test_wt_m6b5_a_batch_reports_every_item(tmp_path):
    """A loop that moves N items must report what the *first* one built.

    The cascade is idempotent, so item 1 creates the whole year and items 2..N
    create nothing. Reporting after the loop kept only the last report — a bulk
    edit across a year boundary made blank editorial rows and said nothing.
    """
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        others = []
        for i in range(3):
            extra = make_daily_item(vps, f"Extra {i}", start="2026-02-25",
                                    due="2026-02-25")
            stored = manager.get_action_item(extra.id)
            stored.weekly_tactic_id = tactic.id
            manager.update_action_item(stored)
            others.append(extra)

        ids = [item.id] + [o.id for o in others]
        manager.bulk_update_action_items(ids, "2027-03-03")

        report = manager.last_cascade_report
        assert report is not None
        assert report.stubs, (
            "the batch built rollover stubs and reported none of them"
        )
        assert "need your words" in report.describe()

        from src.getmoredone.screens.week_collision_notice import cascade_needs_attention
        assert cascade_needs_attention(report) is True
    finally:
        vps.close()


def test_wt_m6b5_a_batch_of_no_ops_reports_nothing(tmp_path):
    """...and a batch that created nothing must not invent a summary."""
    vps = make_vps(tmp_path)
    try:
        manager = vps.db_manager
        ape_id, tactic, item = _filed(vps)
        manager.bulk_update_action_items([item.id], "2027-03-03")
        assert manager.last_cascade_report.created

        manager.bulk_update_action_items([item.id], "2027-03-04")
        assert manager.last_cascade_report.created == []
    finally:
        vps.close()
