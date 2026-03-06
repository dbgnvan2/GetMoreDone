from datetime import datetime
import sqlite3

from src.getmoredone.database import Database
from src.getmoredone.vps_manager import VPSManager


def _seed_legacy_schema(db_path: str):
    conn = sqlite3.connect(db_path)
    now = datetime.now().isoformat()

    conn.execute(
        """
        CREATE TABLE segment_descriptions (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            color_hex TEXT NOT NULL,
            order_index INTEGER,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        INSERT INTO segment_descriptions
        (id, name, description, color_hex, order_index, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?)
        """,
        ("seg-health", "Health", "Legacy test segment", "#4CAF50", 1, now, now),
    )

    conn.execute(
        """
        CREATE TABLE vision_segments (
            id TEXT PRIMARY KEY,
            segment_id TEXT REFERENCES segment_descriptions(id) ON DELETE CASCADE,
            subsegment TEXT NOT NULL,
            category TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE annual_vision_segment_items (
            id TEXT PRIMARY KEY,
            vision_segment_id TEXT NOT NULL REFERENCES vision_segments(id) ON DELETE CASCADE,
            year INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(vision_segment_id, year)
        )
        """
    )

    conn.execute(
        """
        INSERT INTO vision_segments
        (id, segment_id, subsegment, category, order_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-vs-1", "seg-health", "Physical", "Cardio", 1, now, now),
    )
    conn.execute(
        """
        INSERT INTO vision_segments
        (id, segment_id, subsegment, category, order_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-vs-2", "seg-health", "Physical", "Strength", 2, now, now),
    )
    conn.execute(
        """
        INSERT INTO annual_vision_segment_items
        (id, vision_segment_id, year, created_at)
        VALUES (?, ?, ?, ?)
        """,
        ("legacy-avsi-1", "legacy-vs-1", 2026, now),
    )

    conn.commit()
    conn.close()


def test_legacy_vision_schema_migrates_to_current_tables(tmp_path):
    db_path = tmp_path / "legacy_vision_schema.db"
    _seed_legacy_schema(str(db_path))

    db = Database(str(db_path))
    db.connect()
    db.initialize_schema()
    conn = db.conn

    vision_segment_cols = [row[1] for row in conn.execute("PRAGMA table_info(vision_segments)").fetchall()]
    assert "name" in vision_segment_cols
    assert "segment_id" not in vision_segment_cols

    legacy_tables = conn.execute(
        """
        SELECT name FROM sqlite_master
        WHERE type = 'table' AND name IN ('vision_segments_legacy', 'annual_vision_segment_items_legacy')
        """
    ).fetchall()
    assert legacy_tables == []

    key_fields = [
        row["key_field"]
        for row in conn.execute("SELECT key_field FROM vision_elements ORDER BY key_field").fetchall()
    ]
    assert key_fields == ["Health|Physical|Cardio", "Health|Physical|Strength"]

    annual_rows = conn.execute(
        "SELECT year, key_field FROM annual_vision_elements ORDER BY year, key_field"
    ).fetchall()
    assert len(annual_rows) == 1
    assert annual_rows[0]["year"] == 2026
    assert annual_rows[0]["key_field"] == "Health|Physical|Cardio"

    db.close()


def test_taxonomy_sync_creates_vision_elements_for_annual_workflow(tmp_path):
    manager = VPSManager(str(tmp_path / "taxonomy_sync.db"))
    try:
        segment_name = manager.get_all_segments(active_only=False)[0]["name"]
        manager.create_vision_subsegment(segment_name, "Fitness")
        manager.create_vision_category(segment_name, "Fitness", "Cardio")

        elements = manager.get_vision_elements()
        match = next(
            (
                row
                for row in elements
                if row["segment_name"] == segment_name
                and row["subsegment_name"] == "Fitness"
                and row["category_name"] == "Cardio"
            ),
            None,
        )
        assert match is not None

        ids = manager.create_annual_records_from_vision_element(2026, match["id"])
        assert ids["annual_vision_element_id"]
        annual_rows = manager.get_annual_vision_elements(2026)
        assert any(row["vision_element_id"] == match["id"] for row in annual_rows)
    finally:
        manager.close()
