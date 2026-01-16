#!/usr/bin/env python3
"""Test script for Google Calendar authentication."""

import os
import sys
import json
import pickle
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from getmoredone.google_calendar import GoogleCalendarManager

def check_for_zombie_token(credentials_file, token_file):
    """Check if token.pickle is from a different project (zombie token)."""
    if not token_file.exists():
        return False, None

    try:
        # Get project ID from credentials.json
        with open(credentials_file, 'r') as f:
            creds_data = json.load(f)
            creds_project_id = creds_data.get('installed', {}).get('project_id', 'unknown')
            creds_client_id = creds_data.get('installed', {}).get('client_id', 'unknown')

        # Get client ID from token.pickle
        with open(token_file, 'rb') as f:
            token_creds = pickle.load(f)
            token_client_id = getattr(token_creds, 'client_id', 'unknown')

        # Compare client IDs
        if creds_client_id != token_client_id:
            return True, {
                'credentials_project': creds_project_id,
                'credentials_client_id': creds_client_id[:30] + '...',
                'token_client_id': token_client_id[:30] + '...' if token_client_id != 'unknown' else 'unknown'
            }

        return False, None

    except Exception as e:
        print(f"⚠️  Warning: Could not verify token/credentials match: {e}")
        return False, None

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

    # Check for zombie token
    force_reauth = False
    if token_file.exists():
        print("✅ token.pickle found")

        is_zombie, zombie_info = check_for_zombie_token(credentials_file, token_file)
        if is_zombie:
            print("\n" + "=" * 60)
            print("🧟 ZOMBIE TOKEN DETECTED!")
            print("=" * 60)
            print("\nYour token.pickle is from a DIFFERENT project than credentials.json!")
            print(f"\nCredentials project: {zombie_info['credentials_project']}")
            print(f"Credentials client:  {zombie_info['credentials_client_id']}")
            print(f"Token client:        {zombie_info['token_client_id']}")
            print("\nThis will cause authentication to fail with the wrong project name.")
            print("\nDo you want to delete the old token and re-authenticate? (y/N): ", end='')

            response = input().strip().lower()
            if response in ('y', 'yes'):
                print(f"\n🗑️  Deleting zombie token: {token_file}")
                os.remove(token_file)
                force_reauth = True
                print("✅ Zombie token deleted. Will force re-authentication.\n")
            else:
                print("⚠️  Keeping zombie token. Authentication will likely fail.\n")
    else:
        print("⚠️  token.pickle not found - first-time authentication needed")

    print("\nAttempting to initialize Google Calendar Manager...")

    try:
        manager = GoogleCalendarManager(force_reauth=force_reauth)
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

        # Check if this might be a zombie token issue
        if "bowen1rag" in str(e).lower() or "different project" in str(e).lower():
            print("\n" + "=" * 60)
            print("🧟 This looks like a ZOMBIE TOKEN problem!")
            print("=" * 60)
            print("\nYour token.pickle is from a different project.")
            print("Run this script again and choose 'y' to delete the zombie token.")
            print(f"\nOr manually delete: rm {token_file}")

        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
