#!/usr/bin/env python3
"""
Test script to verify VPS database initialization.
"""

# Keep src/ importable when this file is run directly (it has a __main__
# block). Under pytest the repo-root conftest.py does the same thing; this
# must come before the getmoredone imports either way.
import sys
from pathlib import Path as _Path
sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

import sys
import os

# Add src to path

from src.getmoredone.database import Database
from src.getmoredone.vps_manager import VPSManager

def test_vps_init(tmp_path):
    """VPS schema initialisation, asserted rather than printed.

    This was a demonstration script: every check was a ``print("✓ ...")``, so
    it reported success whether the tables existed or not, and its final line
    claimed "All VPS database initialization tests passed!" without a single
    assertion behind it.

    It also wrote its database to the relative path ``data/test_vps.db`` — a
    file in whatever directory the suite happened to run from, left behind
    afterwards and offered to the reader to inspect. It now uses ``tmp_path``,
    like every other test.
    """
    test_db_path = str(tmp_path / "vps.db")

    db = Database(test_db_path)
    db.connect()
    db.initialize_schema()

    # The VPS tables exist.
    cursor = db.conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND (name LIKE '%segment%' OR name LIKE '%vision%'
                                OR name LIKE '%tactic%')
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    assert tables, "initialize_schema created no VPS tables at all"
    for required in ("segment_descriptions",):
        assert required in tables, f"{required} missing from {tables}"

    # The life segments are seeded.
    segment_count = db.conn.execute(
        "SELECT COUNT(*) FROM segment_descriptions"
    ).fetchone()[0]
    assert segment_count > 0, (
        "no life segments were seeded — the VPS screens open on an empty list"
    )

    # action_items carries the VPS columns the planning screens read.
    columns = [row[1] for row in db.conn.execute("PRAGMA table_info(action_items)")]
    vps_columns = [
        c for c in columns
        if any(k in c.lower() for k in ("habit", "percent", "week_action", "segment"))
    ]
    assert vps_columns, (
        f"action_items has no VPS columns; found {columns}"
    )
    db.close()

    # And the manager can round-trip a vision through that schema.
    vps_manager = VPSManager(test_db_path)
    try:
        segments = vps_manager.get_all_segments()
        assert len(segments) == segment_count, (
            f"manager sees {len(segments)} segments, the table holds {segment_count}"
        )

        first = segments[0]
        vision_id = vps_manager.create_tl_vision(
            segment_description_id=first["id"],
            start_year=2025,
            end_year=2030,
            title="Health & Vitality Vision",
            vision_statement="Achieve optimal physical and mental health",
        )
        assert vision_id, "create_tl_vision returned nothing"

        vision = vps_manager.get_tl_vision(vision_id)
        assert vision is not None, "the vision did not survive the round trip"
        assert vision["title"] == "Health & Vitality Vision"

        visions = vps_manager.get_tl_visions(segment_id=first["id"])
        assert any(v["id"] == vision_id for v in visions), (
            "the new vision is not returned when querying its own segment"
        )
    finally:
        vps_manager.close()


