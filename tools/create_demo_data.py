#!/usr/bin/env python3
"""Create demo data for GetMoreDone application.

This is primarily for dev/testing.

It inserts demo items into whichever DB is currently selected by GetMoreDone:
- explicit db path (if provided by caller)
- GETMOREDONE_DB env var
- otherwise the default per-OS Application Support location
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from getmoredone.demo_data import load_demo_data


def create_demo_data():
    print("Creating demo data for GetMoreDone...")
    created = load_demo_data(db_path=None)
    print(f"\nDemo data created successfully! ({created} items)")
    print("Run the application with: python run.py")


if __name__ == "__main__":
    create_demo_data()
