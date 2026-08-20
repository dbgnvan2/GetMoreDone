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


def _seed_legacy_schema_with_case_colliding_segments(db_path: str):
    """A legacy database whose segment_descriptions differ only by case.

    ``segment_descriptions.name`` is UNIQUE, but SQLite's UNIQUE is
    case-SENSITIVE, so 'Health' and 'health' are both legal and older
    databases can hold the pair. ``create_segment`` refuses to make a new one
    now; it cannot un-make the ones already there.

    The legacy ``vision_segments`` row points at ONE of them by id, so which
    is meant is not in doubt.
    """
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
    for seg_id, name, order in (("seg-upper", "Health", 1), ("seg-lower", "health", 2)):
        conn.execute(
            """
            INSERT INTO segment_descriptions
            (id, name, description, color_hex, order_index, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (seg_id, name, "", "#4CAF50", order, now, now),
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
        INSERT INTO vision_segments
        (id, segment_id, subsegment, category, order_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-vs-1", "seg-upper", "Physical", "Cardio", 1, now, now),
    )
    conn.commit()
    conn.close()


def test_rn_m1c_legacy_migration_keeps_the_id_the_legacy_row_carried(tmp_path):
    """The legacy row's segment_id must survive the migration (RN-M1.C).

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-m1c

    The legacy row holds the real ``segment_descriptions`` id. The migration
    used to insert the new ``vision_segments`` row by NAME only and let the
    link-integrity backfill re-derive the id from that name a moment later.
    That round trip is lossy: with two descriptions differing only by case the
    name resolves to neither, the row is left NULL and reported as needing a
    human — about something the legacy row already answered unambiguously.

    Deriving a link from a display string is what this whole change removes
    (RN-INV3), and here the id was in hand and thrown away.
    """
    db_path = tmp_path / "legacy_case_collision.db"
    _seed_legacy_schema_with_case_colliding_segments(str(db_path))

    db = Database(str(db_path))
    db.connect()
    db.initialize_schema()
    try:
        row = db.conn.execute(
            "SELECT id, name, segment_description_id FROM vision_segments "
            "WHERE LOWER(name) = 'health'"
        ).fetchone()

        assert row is not None, "the legacy segment did not migrate at all"
        assert row["segment_description_id"] == "seg-upper", (
            "the migration lost the id the legacy row carried and fell back to "
            f"the name: got {row['segment_description_id']!r}"
        )

        report = db.link_integrity_report["backfill_vision_segments"]
        assert report["ambiguous"] == [], (
            "a row whose id was known was reported as needing a human: "
            f"{report['ambiguous']}"
        )
    finally:
        db.close()


def test_rn_m1c_two_legacy_rows_that_collapse_are_not_given_one_of_the_two_ids(tmp_path):
    """When the collapse is ambiguous, report it — never pick a side (RN-INV5).

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-inv5

    The migration keys its segment cache by LOWERED name, so two legacy rows
    pointing at two descriptions whose names differ only by case collapse into
    ONE new vision_segments row. Stamping the first row's id onto it asserts a
    link that is false for the other row's work: the second legacy row's
    sub-segment and category end up under a life segment they never belonged
    to, and the report that used to name both candidates comes back clean.

    link_integrity states the rule this breaks — "a wrong link is worse than a
    missing one: a missing one is visible in the report, and a wrong one
    silently attaches a user's work to someone else's plan element". Stamping
    is only safe when every legacy row that collapses into a row agrees on
    which description it means.
    """
    db_path = tmp_path / "legacy_two_rows_one_name.db"
    _seed_legacy_schema_with_case_colliding_segments(str(db_path))
    conn = sqlite3.connect(str(db_path))
    now = datetime.now().isoformat()
    # A second legacy row under the OTHER description of the colliding pair.
    conn.execute(
        """
        INSERT INTO vision_segments
        (id, segment_id, subsegment, category, order_index, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("legacy-vs-2", "seg-lower", "Mental", "Focus", 2, now, now),
    )
    conn.commit()
    conn.close()

    db = Database(str(db_path))
    db.connect()
    db.initialize_schema()
    try:
        rows = db.conn.execute(
            "SELECT id, name, segment_description_id FROM vision_segments "
            "WHERE LOWER(name) = 'health'"
        ).fetchall()
        assert rows, "the legacy segments did not migrate at all"

        stamped = [r["segment_description_id"] for r in rows if r["segment_description_id"]]
        assert stamped == [], (
            "a segment two legacy rows disagree about was given one of the two "
            f"ids: {stamped}"
        )

        report = db.link_integrity_report["backfill_vision_segments"]
        assert report["ambiguous"], (
            "the ambiguity was resolved silently instead of being reported"
        )
    finally:
        db.close()


def test_rn_m1c_legacy_migration_does_not_stamp_a_dangling_id(tmp_path):
    """A legacy segment_id pointing at nothing must not be written through.

    Spec: docs/spec_2026-08-19_rename_safe_links.md#rn-inv5

    ``l.segment_id`` is the obvious thing to stamp and the wrong one: the
    legacy table's own FK is not enforced retroactively, so the column can
    name a description that has since been deleted. The migration stamps
    ``sd.id`` from the LEFT JOIN instead, which is NULL exactly when the
    legacy id resolves to nothing — the same rows the migration files under
    'Uncategorized'.

    What stamping the raw value actually costs is worth stating precisely,
    because it is not a bad row: ``segment_description_id`` carries
    ``REFERENCES segment_descriptions(id)`` and ``PRAGMA foreign_keys`` is ON,
    so SQLite raises ``FOREIGN KEY constraint failed`` **inside
    initialize_schema** — the app fails to launch. Mutating the stamp to
    ``row["legacy_segment_id"]`` reddens this test that way, before either
    assertion is reached. The assertions below cover the other half: that the
    row still migrates, and that no vision_segments row ends up pointing at a
    description that is not there.
    """
    db_path = tmp_path / "legacy_dangling.db"
    _seed_legacy_schema_with_case_colliding_segments(str(db_path))
    conn = sqlite3.connect(str(db_path))
    # Dangling, not absent: a value is there, it just resolves to nothing.
    conn.execute(
        "UPDATE vision_segments SET segment_id = 'seg-deleted-long-ago' "
        "WHERE id = 'legacy-vs-1'"
    )
    conn.commit()
    conn.close()

    db = Database(str(db_path))
    db.connect()
    db.initialize_schema()
    try:
        row = db.conn.execute(
            "SELECT name, segment_description_id FROM vision_segments "
            "WHERE name = 'Uncategorized'"
        ).fetchone()

        assert row is not None, "the dangling legacy row did not migrate"
        assert row["segment_description_id"] is None, (
            "a dangling legacy id was written through as a real link: "
            f"{row['segment_description_id']!r}"
        )
        orphans = db.conn.execute(
            """
            SELECT COUNT(*) AS n FROM vision_segments vs
            LEFT JOIN segment_descriptions sd ON sd.id = vs.segment_description_id
            WHERE vs.segment_description_id IS NOT NULL AND sd.id IS NULL
            """
        ).fetchone()["n"]
        assert orphans == 0, f"{orphans} vision_segments point at a missing description"
    finally:
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
