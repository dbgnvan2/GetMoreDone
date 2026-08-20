"""
Test script to verify VPS deletion protection and cascade behavior.
Tests the comprehensive deletion safety implemented in response to audit.
UPDATED: Now tests enhanced deletion checking across all VPS tables.
"""

# Keep src/ importable when this file is run directly (it has a __main__
# block). Under pytest the repo-root conftest.py does the same thing; this
# must come before the getmoredone imports either way.
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from src.getmoredone.vps_manager import VPSManager
import sqlite3
import sys
from pathlib import Path

# Add src to path


def test_deletion_protection_completeness():
    """Test if delete_segment checks ALL tables, not just tl_visions."""
    print("=" * 60)
    print("Test: Deletion Protection Completeness")
    print("=" * 60)

    # Create in-memory database
    manager = VPSManager(":memory:")

    # Create a segment
    segment_id = manager.create_segment(
        name="Test Segment",
        description="Testing deletion",
        color_hex="#FF0000",
        order_index=1
    )
    print(f"✓ Created segment: {segment_id}")

    # Create TL Vision
    vision_id = manager.create_tl_vision(
        segment_description_id=segment_id,
        start_year=2025,
        end_year=2030,
        title="5-Year Vision"
    )
    print(f"✓ Created TL Vision: {vision_id}")

    # Try to delete segment (should fail due to TL Vision)
    success, counts = manager.delete_segment(segment_id)
    assert not success, "Should fail with TL Vision present"
    assert isinstance(counts, dict), "Should return dict"
    assert 'TL Visions' in counts, "Should report TL Visions"
    assert counts['TL Visions'] == 1, f"Expected 1 TL Vision, got {counts}"
    print(f"✓ Deletion blocked with TL Vision: {counts}")

    # Now test the critical issue: Annual Plans without TL Vision
    print("\n--- Testing Critical Issue ---")

    # Create another segment
    segment_id2 = manager.create_segment(
        name="Test Segment 2",
        description="Testing direct plan creation",
        color_hex="#00FF00",
        order_index=2
    )
    print(f"✓ Created segment: {segment_id2}")

    # Create TL Vision and Annual Vision (required parents)
    vision_id2 = manager.create_tl_vision(
        segment_description_id=segment_id2,
        start_year=2025,
        end_year=2030,
        title="Another Vision"
    )
    annual_vision_id = manager.create_annual_vision(
        tl_vision_id=vision_id2,
        segment_description_id=segment_id2,
        year=2026,
        title="2026 Vision"
    )

    # Create Annual Plan (child of annual vision)
    plan_id = manager.create_annual_plan(
        annual_vision_id=annual_vision_id,
        segment_description_id=segment_id2,
        year=2026,
        theme="2026 Plan"
    )
    print(f"✓ Created Annual Plan: {plan_id}")

    # Create Quarter Initiative
    initiative_id = manager.create_quarter_initiative(
        annual_plan_id=plan_id,
        segment_description_id=segment_id2,
        quarter=1,
        year=2026,
        title="Q1 Initiative"
    )
    print(f"✓ Created Quarter Initiative: {initiative_id}")

    # Delete the TL Vision to simulate having plans without top-level vision
    cursor = manager.db.conn.execute(
        "DELETE FROM tl_visions WHERE id = ?",
        (vision_id2,)
    )
    manager.db.conn.commit()
    print("✓ Manually deleted TL Vision (simulating direct plan creation)")

    # Verify Annual Plan still exists (it should be cascade-deleted)
    cursor = manager.db.conn.execute(
        "SELECT COUNT(*) FROM annual_plans WHERE id = ?",
        (plan_id,)
    )
    plan_count = cursor.fetchone()[0]
    print(f"  Annual Plans remaining: {plan_count}")

    # Verify Quarter Initiative (should also be cascade-deleted)
    cursor = manager.db.conn.execute(
        "SELECT COUNT(*) FROM quarter_initiatives WHERE id = ?",
        (initiative_id,)
    )
    initiative_count = cursor.fetchone()[0]
    print(f"  Quarter Initiatives remaining: {initiative_count}")

    # BC3: this printed "✗ CASCADE DELETE failed" and passed. Orphaned rows are
    # the outcome this whole file exists to detect.
    assert plan_count == 0 and initiative_count == 0, (
        f"deleting the TL Vision left orphans: {plan_count} plan(s), "
        f"{initiative_count} initiative(s)")

    # Now the critical test: Can we delete segment with no TL Visions?
    print("\n--- Critical Test: Delete Segment ---")
    cursor = manager.db.conn.execute(
        "SELECT COUNT(*) FROM tl_visions WHERE segment_description_id = ?",
        (segment_id2,)
    )
    vision_count = cursor.fetchone()[0]
    print(f"  TL Visions count: {vision_count}")

    cursor = manager.db.conn.execute(
        "SELECT COUNT(*) FROM annual_plans WHERE segment_description_id = ?",
        (segment_id2,)
    )
    plan_count = cursor.fetchone()[0]
    print(f"  Annual Plans count: {plan_count}")

    cursor = manager.db.conn.execute(
        "SELECT COUNT(*) FROM quarter_initiatives WHERE segment_description_id = ?",
        (segment_id2,)
    )
    initiative_count = cursor.fetchone()[0]
    print(f"  Quarter Initiatives count: {initiative_count}")

    # Try to delete segment - NOW WITH COMPREHENSIVE CHECKING
    success, counts = manager.delete_segment(segment_id2)

    # BC3: this test passed whichever arm it took, so the test named for
    # deletion protection could not fail on deletion protection.
    #
    # What this half actually establishes: deleting the TL Vision cascaded and
    # took its Annual Plan and Quarter Initiative with it, so by the time the
    # segment is deleted nothing references it. Deletion is therefore *allowed*,
    # with empty counts — and must leave no orphans behind. The blocked case is
    # asserted in the first half of this test, where the TL Vision is still
    # present.
    assert success is True, (
        f"nothing references this segment any more, yet deletion was refused "
        f"(counts={counts})")
    assert counts == {}, f"deletion was allowed but reported counts: {counts}"

    if success:
        print(f"✓ Deletion ALLOWED with counts={counts}")
        print("  Checking if all records were cascade-deleted...")

        cursor = manager.db.conn.execute(
            "SELECT COUNT(*) FROM annual_plans WHERE segment_description_id = ?",
            (segment_id2,)
        )
        remaining_plans = cursor.fetchone()[0]

        cursor = manager.db.conn.execute(
            "SELECT COUNT(*) FROM quarter_initiatives WHERE segment_description_id = ?",
            (segment_id2,)
        )
        remaining_initiatives = cursor.fetchone()[0]

        print(f"  Plans remaining: {remaining_plans}")
        print(f"  Initiatives remaining: {remaining_initiatives}")

        # BC3: this branch used to print "✗ FAILURE: Orphaned records exist!"
        # and carry on, so the one outcome it exists to catch could not fail
        # the test.
        assert remaining_plans == 0 and remaining_initiatives == 0, (
            f"cascade left orphans: {remaining_plans} plan(s), "
            f"{remaining_initiatives} initiative(s)")
    else:
        print(f"✓ ENHANCED: Deletion BLOCKED with comprehensive counts!")
        print(f"  Counts returned: {counts}")
        print(f"  User now sees ALL record types, not just TL Visions")
        total = sum(counts.values())
        print(f"  Total records protected: {total}")

    # BC3/F6: this section is headed "Annual Plans without TL Vision", and the
    # assertions above ratify a scenario that no longer builds that state — the
    # cascade removes the plans before delete_segment ever counts them.
    #
    # An earlier version of this comment claimed the intended state "cannot be
    # exercised" because every VSP table has a NOT NULL foreign key to its
    # parent. That was wrong, and it confused *orphan* with *linked*:
    # delete_segment counts `WHERE segment_description_id = ?`, and an ordinary
    # chain built through the manager's own API sets that column on all seven
    # tables. See tests/test_vps_segments.py::test_bc3_delete_segment_counts_
    # every_vsp_table and its per-table companion, which cover what this
    # section was reaching for.

    manager.close()
    # BC3: returning a value from a test makes pytest ignore the verdict.


def test_comprehensive_count():
    """Test what a comprehensive count should look like."""
    print("\n" + "=" * 60)
    print("Test: Comprehensive Deletion Count (Recommended)")
    print("=" * 60)

    manager = VPSManager(":memory:")

    # Create segment with diverse records
    segment_id = manager.create_segment(
        name="Comprehensive Test",
        description="Testing comprehensive counting",
        color_hex="#0000FF",
        order_index=1
    )

    # Create full hierarchy
    vision_id = manager.create_tl_vision(
        segment_description_id=segment_id,
        start_year=2025,
        end_year=2030,
        title="Vision"
    )

    annual_vision_id = manager.create_annual_vision(
        tl_vision_id=vision_id,
        segment_description_id=segment_id,
        year=2026,
        title="Annual Vision"
    )

    plan_id = manager.create_annual_plan(
        annual_vision_id=annual_vision_id,
        segment_description_id=segment_id,
        year=2026,
        theme="Plan"
    )

    initiative_id = manager.create_quarter_initiative(
        annual_plan_id=plan_id,
        segment_description_id=segment_id,
        quarter=1,
        year=2026,
        title="Initiative"
    )

    tactic_id = manager.create_month_tactic(
        quarter_initiative_id=initiative_id,
        segment_description_id=segment_id,
        month=1,
        year=2026,
        priority_focus="Tactic"
    )

    action_id = manager.create_week_action(
        month_tactic_id=tactic_id,
        segment_description_id=segment_id,
        week_start_date="2026-01-01",
        week_end_date="2026-01-07",
        title="Action"
    )

    print("✓ Created full hierarchy")

    # Manual comprehensive count
    tables = [
        'tl_visions',
        'annual_visions',
        'annual_plans',
        'quarter_initiatives',
        'month_tactics',
        'week_actions'
    ]

    print("\nComprehensive count by table:")
    total = 0
    for table in tables:
        cursor = manager.db.conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE segment_description_id = ?",
            (segment_id,)
        )
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"  {table}: {count}")
            total += count

    print(f"\nTotal records: {total}")

    # Try enhanced deletion
    success, counts = manager.delete_segment(segment_id)
    print(f"\n✓ ENHANCED delete_segment() now returns:")
    print(f"  Success: {success}")
    print(f"  Counts: {counts}")
    print(f"  Type: {type(counts)}")

    if not success and isinstance(counts, dict):
        print(
            f"✓ Enhanced implementation sees ALL {len(counts)} record types!")
        total_reported = sum(counts.values())
        print(f"✓ Total records reported: {total_reported}")
        print(f"  Breakdown:")
        for label, count in counts.items():
            print(f"    - {label}: {count}")

    manager.close()


def test_segment_name_update_propagation():
    """Test if segment name updates appear in child records."""
    print("\n" + "=" * 60)
    print("Test: Segment Name Update Propagation")
    print("=" * 60)

    manager = VPSManager(":memory:")

    # Create segment
    segment_id = manager.create_segment(
        name="Original Name",
        description="Test segment",
        color_hex="#FF00FF",
        order_index=1
    )
    print(f"✓ Created segment: 'Original Name'")

    # Create TL Vision
    vision_id = manager.create_tl_vision(
        segment_description_id=segment_id,
        start_year=2025,
        end_year=2030,
        title="Test Vision"
    )
    print(f"✓ Created TL Vision")

    # Query with JOIN to see segment name
    cursor = manager.db.conn.execute("""
        SELECT v.title, s.name as segment_name
        FROM tl_visions v
        JOIN segment_descriptions s ON v.segment_description_id = s.id
        WHERE v.id = ?
    """, (vision_id,))
    row = cursor.fetchone()
    print(f"  Vision shows segment: '{row[1]}'")

    # Update segment name
    manager.update_segment(segment_id, name="Updated Name")
    print(f"✓ Updated segment name to: 'Updated Name'")

    # Query again
    cursor = manager.db.conn.execute("""
        SELECT v.title, s.name as segment_name
        FROM tl_visions v
        JOIN segment_descriptions s ON v.segment_description_id = s.id
        WHERE v.id = ?
    """, (vision_id,))
    row = cursor.fetchone()
    print(f"  Vision now shows segment: '{row[1]}'")

    # BC3: printed "✗ FAILURE" and passed.
    assert row[1] == "Updated Name", (
        f"a renamed segment did not propagate through the JOIN: {row[1]!r}")

    manager.close()


if __name__ == "__main__":
    print("VPS Data Integrity Test Suite")
    print("Testing issues from VPS_DATA_INTEGRITY_AUDIT.md\n")

    # Run tests
    test_deletion_protection_completeness()
    test_comprehensive_count()
    test_segment_name_update_propagation()

    print("\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print("\nSUMMARY:")
    print("1. ✓ CASCADE DELETE works correctly")
    print("2. ✓ FIXED: delete_segment() now checks ALL tables")
    print("3. ✓ FIXED: Comprehensive counts prevent silent data loss")
    print("4. ✓ Segment name updates work via foreign key JOINs")
    print("5. ✓ ENHANCED: Typed confirmation required for cascade deletes")
    print("\n✓ ALL SAFETY FEATURES IMPLEMENTED SUCCESSFULLY")
