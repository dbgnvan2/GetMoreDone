#!/usr/bin/env python3
"""Test script for Google Calendar authentication."""

import os
import sys
import pickle
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from getmoredone.google_calendar import GoogleCalendarManager

def main():
    """Test Google Calendar authentication."""
    print("Testing Google Calendar Authentication...")
    print("=" * 60)

    # Check if credentials exist
    config_dir = Path.home() / ".getmoredone"
    credentials_file = config_dir / "credentials.json"
    token_file = config_dir / "token.pickle"

    print(f"\nConfig directory: {config_dir}")
    print(f"Credentials file: {credentials_file}")
    print(f"Token file: {token_file}")
    print()

    if not credentials_file.exists():
        print("❌ ERROR: credentials.json not found!")
        print(f"   Please place credentials.json at: {credentials_file}")
        return 1

    print("✅ credentials.json found")

    if token_file.exists():
        print("✅ token.pickle found")
    else:
        print("⚠️  token.pickle not found - first-time authentication needed")

    print("\nAttempting to initialize Google Calendar Manager...")

    try:
        manager = GoogleCalendarManager()
        print("✅ GoogleCalendarManager initialized successfully!")

        # Try to list calendars to verify authentication
        print("\nTesting API access...")
        service = manager.service
        calendar_list = service.calendarList().list().execute()

        print("✅ Successfully authenticated with Google Calendar API!")
        print(f"\nFound {len(calendar_list.get('items', []))} calendars:")

        for calendar in calendar_list.get('items', [])[:3]:  # Show first 3
            print(f"  - {calendar['summary']}")

        if token_file.exists():
            print(f"\n✅ token.pickle created successfully at: {token_file}")

        return 0

    except FileNotFoundError as e:
        print(f"❌ ERROR: {e}")
        return 1
    except Exception as e:
        print(f"❌ ERROR during authentication: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
