#!/usr/bin/env python3
"""
Populate initial vision_segments table with sample data.
This creates Vision Elements (Segment + SubSegment + Category combinations).
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from getmoredone.vps_manager import VPSManager

def main():
    # Use default database path
    vps = VPSManager()

    print("📊 Current vision_segments count:")
    existing = vps.get_vision_segments()
    print(f"   Found {len(existing)} vision elements")

    if existing:
        print("\n⚠️  Vision elements already exist. Skipping population.")
        print("   Delete existing records first if you want to re-populate.")
        vps.close()
        return

    print("\n🔍 Loading segment_descriptions...")
    segments = vps.get_all_segments(active_only=True)
    print(f"   Found {len(segments)} segments")

    if not segments:
        print("❌ No segments found! Run VPS initialization first.")
        vps.close()
        return

    print("\n➕ Creating sample Vision Elements...")

    # Sample vision elements for each segment
    sample_elements = [
        # Creative
        ("Creative", "Writing", "APW Book"),
        ("Creative", "Music", "Composition"),

        # Purposeful Work
        ("Purposeful Work", "BTA Archive", "Archive"),
        ("Purposeful Work", "BTA Board", "Board"),
        ("Purposeful Work", "BTA Web", "Videos"),
        ("Purposeful Work", "Living Systems", "Archive"),
        ("Purposeful Work", "Living Systems", "Blog"),
        ("Purposeful Work", "Living Systems", "Website"),

        # Wellness/Health
        ("Health", "Physical", "Cardio"),
        ("Health", "Physical", "Strength"),
        ("Health", "Mental", "Meditation"),
    ]

    created_count = 0
    for seg_name, subseg, category in sample_elements:
        # Find segment ID
        seg = next((s for s in segments if s['name'].lower() == seg_name.lower()), None)
        if seg:
            try:
                vs_id = vps.create_vision_segment(
                    segment_id=seg['id'],
                    subsegment=subseg,
                    category=category,
                    order_index=created_count
                )
                print(f"   ✓ Created: {seg_name} / {subseg} / {category}")
                created_count += 1
            except Exception as e:
                print(f"   ✗ Failed: {seg_name} / {subseg} / {category} - {e}")
        else:
            print(f"   ⚠️  Segment not found: {seg_name}")

    print(f"\n✅ Created {created_count} vision elements")

    # Verify
    all_elements = vps.get_vision_segments()
    print(f"📊 Total vision elements now: {len(all_elements)}")

    vps.close()
    print("\n🎉 Done!")

if __name__ == "__main__":
    main()
