"""
Tests for Project Board drag-and-drop database logic.
"""

import pytest
import tempfile
import os
from src.getmoredone.db_manager import DatabaseManager
from src.getmoredone.vps_manager import VPSManager
from src.getmoredone.models import ActionItem, ProjectBoard

@pytest.fixture
def db_manager():
    """Create a temporary database and VPS manager for testing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_file.close()

    db_mgr = DatabaseManager(temp_file.name)
    vps_mgr = VPSManager(temp_file.name)
    
    yield db_mgr, vps_mgr

    db_mgr.close()
    vps_mgr.close()
    if os.path.exists(temp_file.name):
        os.unlink(temp_file.name)

def _seed_ape(vps_mgr: VPSManager, segment_name: str, subsegment: str, category: str) -> str:
    """Helper to seed APE data."""
    vps_mgr.create_vision_subsegment(segment_name, subsegment)
    ve_id = vps_mgr.create_or_get_vision_element(segment_name, subsegment, category)
    ids = vps_mgr.create_annual_records_from_vision_element(2026, ve_id)
    return ids["annual_plan_element_id"]

def test_link_item_to_project_exclusive(db_manager):
    db_mgr, vps_mgr = db_manager
    
    # 1. Seed two APEs and their boards
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id1 = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    ape_id2 = _seed_ape(vps_mgr, seg_name, "Sub 2", "Cat 2")
    
    # ensure_project_board_for_ape is called during seeding or we call it manually
    board_id1 = db_mgr.ensure_project_board_for_ape(ape_id1)
    board_id2 = db_mgr.ensure_project_board_for_ape(ape_id2)
    
    # 2. Create an action item
    item = ActionItem(who="TestUser", title="Task to Link")
    item_id = db_mgr.create_action_item(item, apply_defaults=False)
    
    # 3. Link to project 1
    db_mgr.link_item_to_project_exclusive(board_id1, item_id)
    
    # Verify link and APE sync
    links = db_mgr.get_project_board_ids_for_item(item_id)
    assert links == [board_id1]
    
    updated_item = db_mgr.get_action_item(item_id)
    assert updated_item.annual_plan_element_id == ape_id1
    
    # 4. Link to project 2 (replaces project 1)
    db_mgr.link_item_to_project_exclusive(board_id2, item_id)
    
    # Verify link replaced and APE updated
    links = db_mgr.get_project_board_ids_for_item(item_id)
    assert links == [board_id2]
    
    updated_item = db_mgr.get_action_item(item_id)
    assert updated_item.annual_plan_element_id == ape_id2

def test_get_unlinked_action_items(db_manager):
    db_mgr, vps_mgr = db_manager
    
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    board_id = db_mgr.ensure_project_board_for_ape(ape_id)
    
    # Create one linked item
    item_linked = ActionItem(who="Test", title="Linked Task")
    item_linked_id = db_mgr.create_action_item(item_linked, apply_defaults=False)
    db_mgr.link_action_item_to_project_board(board_id, item_linked_id)
    
    # Create one unlinked item
    item_unlinked = ActionItem(who="Test", title="Unlinked Task")
    item_unlinked_id = db_mgr.create_action_item(item_unlinked, apply_defaults=False)
    
    unlinked_items = db_mgr.get_unlinked_action_items()
    unlinked_ids = [it.id for it in unlinked_items]
    
    assert item_unlinked_id in unlinked_ids
    assert item_linked_id not in unlinked_ids

def test_clear_item_project_links(db_manager):
    db_mgr, vps_mgr = db_manager
    
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    board_id = db_mgr.ensure_project_board_for_ape(ape_id)
    
    item = ActionItem(who="Test", title="Task to Clear", annual_plan_element_id=ape_id)
    item_id = db_mgr.create_action_item(item, apply_defaults=False)
    db_mgr.link_action_item_to_project_board(board_id, item_id)
    
    # Verify it is linked
    assert len(db_mgr.get_project_board_ids_for_item(item_id)) == 1
    
    # Clear links
    db_mgr.clear_item_project_links(item_id)
    
    # Verify unlinked and APE cleared
    assert len(db_mgr.get_project_board_ids_for_item(item_id)) == 0
    updated_item = db_mgr.get_action_item(item_id)
    assert updated_item.annual_plan_element_id is None


# ----------------------------------------------------------------- BP5


def _seed_unlinked(db_mgr, count: int, prefix: str = "Unlinked") -> list[str]:
    """Real-scale fixture: enough open unlinked items that the cap bites (P9)."""
    ids = []
    for i in range(count):
        item = ActionItem(who="Test", title=f"{prefix} {i:04d}")
        ids.append(db_mgr.create_action_item(item, apply_defaults=False))
    return ids


def test_bp5_unlinked_items_are_capped_and_the_drop_is_countable(db_manager):
    """The Scheduler's list is capped; the count query still sees everything.

    Spec: docs/implementation_plan_2026-08-19_backlog_clearance.md#bp5

    Real-scale: the default cap is 500, so the fixture has to exceed it or the
    cap never fires and the test proves nothing (P9).
    """
    db_mgr, _vps_mgr = db_manager
    total = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT + 25
    _seed_unlinked(db_mgr, total)

    capped = db_mgr.get_unlinked_action_items(status_filter="open")
    assert len(capped) == DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT

    counted = db_mgr.count_unlinked_action_items(status_filter="open")
    assert counted == total, "the count must see what the cap dropped"
    assert counted > len(capped), "the cap did not bite — this test proves nothing"


def test_bp5_count_matches_the_uncapped_list(db_manager):
    """The count and the list must agree about what "unlinked" means.

    Two queries with two WHERE clauses is exactly how a count and a list drift,
    so they share one FROM/WHERE fragment and this pins the result.
    """
    db_mgr, vps_mgr = db_manager
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    board_id = db_mgr.ensure_project_board_for_ape(ape_id)

    unlinked_ids = _seed_unlinked(db_mgr, 7)
    linked_ids = _seed_unlinked(db_mgr, 3, prefix="Linked")
    for item_id in linked_ids:
        db_mgr.link_item_to_project_exclusive(board_id, item_id)

    # A completed item is not "unlinked open work" either.
    done_id = _seed_unlinked(db_mgr, 1, prefix="Done")[0]
    db_mgr.complete_action_item(done_id)

    listed = db_mgr.get_unlinked_action_items(status_filter="open", limit=None)
    assert db_mgr.count_unlinked_action_items(status_filter="open") == len(listed)
    assert sorted(it.id for it in listed) == sorted(unlinked_ids)

    # And with no status filter at all, both still agree.
    all_listed = db_mgr.get_unlinked_action_items(status_filter="", limit=None)
    assert db_mgr.count_unlinked_action_items(status_filter="") == len(all_listed)
    assert done_id in {it.id for it in all_listed}


def test_bp5_limit_none_restores_the_whole_list(db_manager):
    """The cap is a default, not a ceiling — a caller can still ask for all."""
    db_mgr, _vps_mgr = db_manager
    total = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT + 10
    _seed_unlinked(db_mgr, total)

    assert len(db_mgr.get_unlinked_action_items(limit=None)) == total


def test_bp5_the_scheduler_asks_for_a_count_not_a_list(db_manager):
    """The "No Project" box wanted a number and was loading every row for it.

    Drives the real ``load_items`` through a stub and intercepts the boundary
    calls, so a rewrite that goes back to ``len(get_unlinked_action_items(...))``
    fails here rather than merely reading differently (P25).
    """
    from types import SimpleNamespace
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    db_mgr, _vps_mgr = db_manager
    total = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT + 5
    _seed_unlinked(db_mgr, total)

    calls = {"list": 0, "count": 0, "rows_loaded": 0}
    real_list = db_mgr.get_unlinked_action_items
    real_count = db_mgr.count_unlinked_action_items

    def spy_list(*args, **kwargs):
        calls["list"] += 1
        rows = real_list(*args, **kwargs)
        calls["rows_loaded"] += len(rows)
        return rows

    def spy_count(*args, **kwargs):
        calls["count"] += 1
        return real_count(*args, **kwargs)

    db_mgr.get_unlinked_action_items = spy_list
    db_mgr.count_unlinked_action_items = spy_count
    try:
        stub = SimpleNamespace(
            db_manager=db_mgr,
            days_var=SimpleNamespace(get=lambda: "7"),
            who_var=SimpleNamespace(get=lambda: "All"),
            selected_date_filter=None,
            selected_project_id="__none__",
            segment_filter_var=SimpleNamespace(get=lambda: "All"),
            subsegment_filter_var=SimpleNamespace(get=lambda: "All"),
            UNLINKED_FILTERED_LIMIT=DragScheduleScreen.UNLINKED_FILTERED_LIMIT,
        )
        stub._lineage_filter_active = lambda: DragScheduleScreen._lineage_filter_active(stub)
        stub._item_matches_filters = lambda item: True
        stub._load_unlinked_items = lambda who: DragScheduleScreen._load_unlinked_items(stub, who)
        items = DragScheduleScreen.load_items(stub)
    finally:
        db_mgr.get_unlinked_action_items = real_list
        db_mgr.count_unlinked_action_items = real_count

    assert calls["count"] == 1, "the total came from somewhere other than the count query"
    assert len(items) == DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT
    assert calls["rows_loaded"] == DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT, (
        "every unlinked row was loaded despite the cap")
    assert stub.unlinked_shown == DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT
    assert stub.unlinked_total == total


def test_bp5_the_box_says_showing_n_of_m_when_capped(db_manager):
    """A truncated list must say so; an untruncated one must not."""
    from types import SimpleNamespace
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    def box(shown=None, total=None, lineage_filtered=False, **kw):
        stub = SimpleNamespace(unlinked_shown=shown, unlinked_total=total, **kw)
        stub._lineage_filter_active = lambda: lineage_filtered
        return stub

    assert DragScheduleScreen._unlinked_box_text(box(500, 525), 525) == (
        "showing 500 of 525 unlinked items")
    assert DragScheduleScreen._unlinked_box_text(box(12, 12), 12) == "12 unlinked items"

    # Before this load wrote anything (another project box is selected) there
    # is nothing to qualify — and the stale pair must not leak through (S2-5).
    assert DragScheduleScreen._unlinked_box_text(box(), 12) == "12 unlinked items"

    # ...but if a lineage filter is on, the number in front of the user is the
    # only one on the row that the filter did not narrow, so it says which it
    # is (sweep pass 3).
    assert DragScheduleScreen._unlinked_box_text(box(lineage_filtered=True), 12) == (
        "12 unlinked items (unfiltered)")

    # A lineage filter that searched a capped slice does not know its own
    # total, and must not borrow the unfiltered one (S2-3).
    assert DragScheduleScreen._unlinked_box_text(box(3, None), 5000) == (
        "showing 3 (filtered, not all items searched)")


def test_bp5_the_cap_is_announced_in_the_log(db_manager, caplog):
    """Dropping 25 items silently is the failure this cap could have created."""
    import logging
    from types import SimpleNamespace
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    db_mgr, _vps_mgr = db_manager
    total = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT + 25
    _seed_unlinked(db_mgr, total)

    stub = SimpleNamespace(
        db_manager=db_mgr,
        days_var=SimpleNamespace(get=lambda: "7"),
        who_var=SimpleNamespace(get=lambda: "All"),
        selected_date_filter=None,
        selected_project_id="__none__",
        segment_filter_var=SimpleNamespace(get=lambda: "All"),
        subsegment_filter_var=SimpleNamespace(get=lambda: "All"),
        UNLINKED_FILTERED_LIMIT=DragScheduleScreen.UNLINKED_FILTERED_LIMIT,
    )
    stub._lineage_filter_active = lambda: DragScheduleScreen._lineage_filter_active(stub)
    stub._item_matches_filters = lambda item: True
    stub._load_unlinked_items = lambda who: DragScheduleScreen._load_unlinked_items(stub, who)

    with caplog.at_level(logging.WARNING, logger="src.getmoredone.screens.drag_schedule"):
        DragScheduleScreen.load_items(stub)

    messages = [record.getMessage() for record in caplog.records]
    assert any("capped" in message for message in messages), (
        f"the cap dropped {total - DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT} "
        f"items without a word; log said {messages}")
    assert any("500 of 525" in message for message in messages), messages


# --------------------------------------------------- sweep findings


def _unlinked_stub(db_mgr, who="All", segment="All"):
    from types import SimpleNamespace
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    stub = SimpleNamespace(
        db_manager=db_mgr,
        days_var=SimpleNamespace(get=lambda: "7"),
        who_var=SimpleNamespace(get=lambda: who),
        selected_date_filter=None,
        selected_project_id="__none__",
        segment_filter_var=SimpleNamespace(get=lambda: segment),
        subsegment_filter_var=SimpleNamespace(get=lambda: "All"),
        UNLINKED_FILTERED_LIMIT=DragScheduleScreen.UNLINKED_FILTERED_LIMIT,
    )
    stub._lineage_filter_active = lambda: DragScheduleScreen._lineage_filter_active(stub)
    stub._item_matches_filters = lambda item: True
    stub._load_unlinked_items = lambda w: DragScheduleScreen._load_unlinked_items(stub, w)
    stub.load_items = lambda: DragScheduleScreen.load_items(stub)
    return stub


def test_f3_the_who_filter_runs_before_the_cap_not_after(db_manager):
    """A capped list filtered in Python drops rows the filter would have kept.

    Sweep F3. The cap takes the top 500 by priority; filtering that slice for
    one person hides everyone that person owns from rank 501 down, while the
    box goes on announcing a total for the *unfiltered* population.
    """
    db_mgr, _vps_mgr = db_manager
    cap = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT

    # Everyone else outranks Ana, so she is entirely below the cap. All four
    # factors are set because create_action_item recomputes priority_score from
    # them and zeroes it if any is missing — with every score equal the ORDER BY
    # falls through to title, "Ana" sorts first and lands inside the cap, and
    # the fixture proves nothing.
    for i in range(cap + 20):
        db_mgr.create_action_item(
            ActionItem(who="Bob", title=f"Bob {i:04d}",
                       importance=20, urgency=20, size=16, value=16),
            apply_defaults=False)
    for i in range(4):
        db_mgr.create_action_item(
            ActionItem(who="Ana", title=f"Ana {i}",
                       importance=1, urgency=1, size=2, value=2),
            apply_defaults=False)

    # The fixture only bites if Ana really is below the cap.
    top = db_mgr.get_unlinked_action_items(status_filter="open")
    assert not any(item.who == "Ana" for item in top), (
        "Ana is inside the top 500, so this test cannot detect the bug")

    items = _unlinked_stub(db_mgr, who="Ana").load_items()

    assert len(items) == 4, (
        "Ana's items fell below the cap and were filtered out of a slice that "
        "never contained them")
    assert {item.who for item in items} == {"Ana"}


def test_f3_the_announced_total_describes_the_same_population_as_the_list(db_manager):
    """"showing N of M" has to be N and M of the *same* set."""
    db_mgr, _vps_mgr = db_manager
    for i in range(30):
        db_mgr.create_action_item(
            ActionItem(who="Bob", title=f"Bob {i}"), apply_defaults=False)
    for i in range(4):
        db_mgr.create_action_item(
            ActionItem(who="Ana", title=f"Ana {i}"), apply_defaults=False)

    stub = _unlinked_stub(db_mgr, who="Ana")
    items = stub.load_items()

    assert stub.unlinked_total == len(items) == 4, (
        f"the box would announce {stub.unlinked_total} for a list of {len(items)}")


def test_f3_a_segment_filtered_view_searches_past_the_default_cap(db_manager):
    """A lineage filter cannot go into SQL, so the query fetches wider.

    Wider, not unbounded: the first fix used ``limit=None`` and reinstated the
    whole-table load BP5 exists to remove (S2-4).
    """
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    db_mgr, _vps_mgr = db_manager
    cap = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT
    for i in range(cap + 15):
        db_mgr.create_action_item(
            ActionItem(who="Bob", title=f"Bob {i:04d}"), apply_defaults=False)

    # Intercept the boundary call: asserting the *constant* would stay green
    # through a regression back to limit=None, because an unbounded query also
    # returns all cap + 15 rows on this fixture (sweep pass 3, P10).
    limits = []
    real = db_mgr.get_unlinked_action_items

    def spy(*args, **kwargs):
        limits.append(kwargs.get("limit", "not-passed"))
        return real(*args, **kwargs)

    db_mgr.get_unlinked_action_items = spy
    try:
        filtered = _unlinked_stub(db_mgr, segment="Personal")
        assert len(filtered.load_items()) == cap + 15, (
            "the segment filter only ever saw the top 500 rows")
        assert limits == [DragScheduleScreen.UNLINKED_FILTERED_LIMIT], (
            f"the filtered path asked for limit={limits} — None means the "
            "whole-table load BP5 removed is back")

        # ...and with no lineage filter active the cap is still doing its job.
        limits.clear()
        plain = _unlinked_stub(db_mgr)
        assert len(plain.load_items()) == cap
        assert limits == [DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT]
    finally:
        db_mgr.get_unlinked_action_items = real

    assert DragScheduleScreen.UNLINKED_FILTERED_LIMIT == cap * 10


def test_s2_3_a_filtered_box_counts_the_rows_it_shows(db_manager):
    """"N unlinked items" must be the N on screen, not an unfiltered total.

    Sweep pass 2. ``unlinked_shown`` was recorded before ``_item_matches_filters``
    ran, so a segment filter showing three rows announced thirty (P19).
    """
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    db_mgr, _vps_mgr = db_manager
    for i in range(30):
        db_mgr.create_action_item(
            ActionItem(who="Bob", title=f"Bob {i}"), apply_defaults=False)

    stub = _unlinked_stub(db_mgr, segment="Personal")
    kept = {f"Bob {i}" for i in range(3)}
    stub._item_matches_filters = lambda item: item.title in kept

    items = stub.load_items()
    assert len(items) == 3
    assert stub.unlinked_shown == 3, (
        f"the box would announce {stub.unlinked_shown} beside 3 rows")
    assert DragScheduleScreen._unlinked_box_text(stub, 30) == "3 unlinked items"


def test_s2_5_a_stale_shown_count_does_not_survive_into_another_view(db_manager):
    """Selecting a project box must not leave the No-Project label mid-sentence."""
    from src.getmoredone.screens.drag_schedule import DragScheduleScreen

    db_mgr, vps_mgr = db_manager
    cap = DatabaseManager.UNLINKED_ITEMS_DEFAULT_LIMIT
    for i in range(cap + 5):
        db_mgr.create_action_item(
            ActionItem(who="Bob", title=f"Bob {i:04d}"), apply_defaults=False)

    stub = _unlinked_stub(db_mgr)
    stub.load_items()
    assert stub.unlinked_shown == cap

    # Now the user clicks a real project box: load_items takes the other branch
    # and must clear what the No-Project branch left behind.
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    stub.selected_project_id = db_mgr.ensure_project_board_for_ape(ape_id)
    stub.load_items()

    assert stub.unlinked_shown is None
    assert DragScheduleScreen._unlinked_box_text(stub, cap + 5) == (
        f"{cap + 5} unlinked items")


def test_f7_the_multi_link_report_ignores_orphaned_link_rows(db_manager):
    """One query answers both "how many" and "which", so they cannot disagree.

    Sweep F7 gave a separate count query the same JOIN as its list sibling;
    sweep pass 2 (S2-7) then removed the count query altogether, because after
    F4 every caller loads the rows anyway and two queries were only a second
    way for the banner and its names to disagree (P19). What remains to pin is
    that the surviving query does not count a link row whose item is gone —
    the banner would otherwise name a number nothing could show.
    """
    db_mgr, vps_mgr = db_manager
    seg_name = vps_mgr.get_all_segments(active_only=False)[0]["name"]
    ape_id = _seed_ape(vps_mgr, seg_name, "Sub 1", "Cat 1")
    board_a = db_mgr.ensure_project_board_for_ape(ape_id)
    ape_id2 = _seed_ape(vps_mgr, seg_name, "Sub 2", "Cat 2")
    board_b = db_mgr.ensure_project_board_for_ape(ape_id2)

    item_id = db_mgr.create_action_item(
        ActionItem(who="Test", title="Two boards"), apply_defaults=False)
    db_mgr.link_action_item_to_project_board(board_a, item_id)
    db_mgr.link_action_item_to_project_board(board_b, item_id)

    reported = db_mgr.get_items_on_multiple_project_boards()
    assert [(row["title"], row["board_count"]) for row in reported] == [("Two boards", 2)]

    # Orphan the link rows. Cascade delete makes this unreachable through the
    # app; the point is that the query answers from action_items, so it cannot
    # report an item that is not there.
    db_mgr.db.conn.execute("PRAGMA foreign_keys = OFF")
    try:
        db_mgr.db.conn.execute("DELETE FROM action_items WHERE id = ?", (item_id,))
        db_mgr.db.conn.commit()
        orphans = db_mgr.db.conn.execute(
            "SELECT COUNT(*) AS n FROM project_board_items WHERE item_id = ?",
            (item_id,)).fetchone()["n"]
        assert orphans == 2, "the delete cascaded, so this test proves nothing"
        assert db_mgr.get_items_on_multiple_project_boards() == []
    finally:
        db_mgr.db.conn.execute("PRAGMA foreign_keys = ON")


def test_s2_1_the_who_filter_matches_non_ascii_and_odd_whitespace(db_manager):
    """The SQL filter must keep every row the Python predicate it replaced kept.

    Sweep pass 2 (S2-1). ``LOWER(TRIM(ai.who)) = ?`` lowered the left side in
    SQLite (ASCII-only) and the right side in Python (full Unicode), so a
    stored "JOSÉ" stopped matching a filter of "JOSÉ" and the whole "No
    Project" box read zero with no log line (P2).
    """
    db_mgr, _vps_mgr = db_manager
    db_mgr.create_action_item(
        ActionItem(who="JOSÉ", title="Accented"), apply_defaults=False)
    db_mgr.create_action_item(
        ActionItem(who="Ana\t", title="Trailing tab"), apply_defaults=False)
    db_mgr.create_action_item(
        ActionItem(who="Bob", title="Plain"), apply_defaults=False)

    for who, expected in (("JOSÉ", "Accented"), ("josé", "Accented"),
                          ("Ana", "Trailing tab"), ("Bob", "Plain")):
        rows = db_mgr.get_unlinked_action_items(status_filter="open", who_filter=who)
        assert [r.title for r in rows] == [expected], (
            f"who_filter={who!r} returned {[r.title for r in rows]}")
        assert db_mgr.count_unlinked_action_items(
            status_filter="open", who_filter=who) == 1, (
            f"the count disagrees with the list for who_filter={who!r}")

    # A row with no owner at all is not swept in by another owner's filter...
    db_mgr.create_action_item(ActionItem(who="", title="Nobody"), apply_defaults=False)
    assert db_mgr.count_unlinked_action_items(
        status_filter="open", who_filter="Bob") == 1

    # ...nor reachable by a blank filter. The Python predicate this replaced
    # was `item.who and ...`, so an owner-less row never matched (sweep pass 3).
    for blank in ("   ", "\t"):
        assert db_mgr.get_unlinked_action_items(
            status_filter="open", who_filter=blank) == []
        assert db_mgr.count_unlinked_action_items(
            status_filter="open", who_filter=blank) == 0
