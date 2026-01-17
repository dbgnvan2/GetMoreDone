#!/usr/bin/env python3
"""
Test script to verify VPS database initialization.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from getmoredone.database import Database
from getmoredone.vps_manager import VPSManager

def test_vps_init():
    """Test VPS database initialization."""
    print("Testing VPS database initialization...")

    # Initialize database with test path
    test_db_path = "data/test_vps.db"

    # Remove existing test database
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
        print(f"Removed existing test database: {test_db_path}")

    # Initialize database
    db = Database(test_db_path)
    db.connect()
    db.initialize_schema()
    print("✓ Database schema initialized")

    # Check if VPS tables exist
    cursor = db.conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE '%segment%' OR name LIKE '%vision%' OR name LIKE '%tactic%'
        ORDER BY name
    """)
    tables = [row[0] for row in cursor.fetchall()]
    print(f"✓ Found {len(tables)} VPS tables: {', '.join(tables)}")

    # Check if segments are seeded
    cursor = db.conn.execute("SELECT COUNT(*) FROM segment_descriptions")
    segment_count = cursor.fetchone()[0]
    print(f"✓ Found {segment_count} life segments")

    # Check if action_items has VPS columns
    cursor = db.conn.execute("PRAGMA table_info(action_items)")
    columns = [row[1] for row in cursor.fetchall()]
    vps_columns = [col for col in columns if 'habit' in col.lower() or 'percent' in col.lower() or 'week_action' in col.lower() or 'segment' in col.lower()]
    print(f"✓ Found VPS columns in action_items: {', '.join(vps_columns)}")

    db.close()

    print("\n✅ All VPS database initialization tests passed!")

    # Test VPS manager
    print("\nTesting VPS manager...")
    vps_manager = VPSManager(test_db_path)

    # Get all segments
    segments = vps_manager.get_all_segments()
    print(f"✓ Retrieved {len(segments)} segments via manager")
    for seg in segments[:3]:  # Show first 3
        print(f"  - {seg['name']}: {seg['color_hex']}")

    # Create a test TL Vision
    health_segment = segments[0]  # Health
    vision_id = vps_manager.create_tl_vision(
        segment_description_id=health_segment['id'],
        start_year=2025,
        end_year=2030,
        title="Health & Vitality Vision",
        vision_statement="Achieve optimal physical and mental health through consistent habits"
    )
    print(f"✓ Created test TL Vision: {vision_id}")

    # Retrieve the vision
    vision = vps_manager.get_tl_vision(vision_id)
    print(f"✓ Retrieved TL Vision: {vision['title']}")

    # Get visions for segment
    visions = vps_manager.get_tl_visions(segment_id=health_segment['id'])
    print(f"✓ Found {len(visions)} visions for {health_segment['name']} segment")

    vps_manager.close()

    print("\n✅ All VPS manager tests passed!")
    print(f"\nTest database created at: {test_db_path}")
    print("You can inspect it with: sqlite3 data/test_vps.db")

if __name__ == "__main__":
    test_vps_init()
