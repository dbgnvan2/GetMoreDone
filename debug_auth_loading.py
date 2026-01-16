#!/usr/bin/env python3
"""
Debug script to trace EXACTLY where credentials are being loaded from.
This will show us why we're getting the wrong client_id.
"""

import os
import sys
import json
import pickle
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

print("="*70)
print("DEBUG: Authentication Loading Trace")
print("="*70)

# Check environment
print("\n1. ENVIRONMENT:")
print(f"   HOME: {os.environ.get('HOME')}")
print(f"   PWD: {os.getcwd()}")
print(f"   USER: {os.environ.get('USER')}")
print(f"   Python executable: {sys.executable}")

# Check what GoogleCalendarManager will use
print("\n2. EXPECTED PATHS (by GoogleCalendarManager):")
data_dir = Path.home() / ".getmoredone"
credentials_file = str(data_dir / "credentials.json")
token_file = str(data_dir / "token.pickle")

print(f"   data_dir: {data_dir}")
print(f"   credentials_file: {credentials_file}")
print(f"   token_file: {token_file}")
print(f"   credentials exists: {os.path.exists(credentials_file)}")
print(f"   token exists: {os.path.exists(token_file)}")

# Read the credentials file that WILL be used
print("\n3. CREDENTIALS FILE THAT WILL BE USED:")
if os.path.exists(credentials_file):
    with open(credentials_file, 'r') as f:
        creds_data = json.load(f)
        client_id = creds_data.get('installed', {}).get('client_id', 'NOT FOUND')
        project_id = creds_data.get('installed', {}).get('project_id', 'NOT FOUND')
        redirect_uris = creds_data.get('installed', {}).get('redirect_uris', [])

    print(f"   File: {credentials_file}")
    print(f"   Project ID: {project_id}")
    print(f"   Client ID: {client_id}")
    print(f"   Redirect URIs: {redirect_uris}")

    # Check if it's the wrong one
    WRONG_CLIENT_ID = "888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com"
    CORRECT_CLIENT_ID = "592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com"

    if client_id == WRONG_CLIENT_ID:
        print("\n   ❌ THIS IS THE WRONG CLIENT_ID (Bowen1rag)!")
    elif client_id == CORRECT_CLIENT_ID:
        print("\n   ✅ This is the correct client_id (getmoredone)")
    else:
        print(f"\n   ⚠️  Unknown client_id")
else:
    print(f"   ❌ File not found: {credentials_file}")

# Check if there's a token file
print("\n4. TOKEN FILE CHECK:")
if os.path.exists(token_file):
    print(f"   ⚠️  TOKEN FILE EXISTS: {token_file}")
    print("   This token will be used INSTEAD of credentials.json!")

    try:
        with open(token_file, 'rb') as f:
            token_creds = pickle.load(f)
            token_client_id = getattr(token_creds, 'client_id', 'NOT AVAILABLE')
            token_valid = getattr(token_creds, 'valid', 'UNKNOWN')
            token_expired = getattr(token_creds, 'expired', 'UNKNOWN')

        print(f"   Token client_id: {token_client_id}")
        print(f"   Token valid: {token_valid}")
        print(f"   Token expired: {token_expired}")

        WRONG_CLIENT_ID = "888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com"
        CORRECT_CLIENT_ID = "592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com"

        if token_client_id == WRONG_CLIENT_ID:
            print("\n   🧟 ZOMBIE TOKEN DETECTED!")
            print("   This token is from the WRONG project (Bowen1rag)")
            print("   This is why you're seeing the wrong client_id in the OAuth URL!")
        elif token_client_id == CORRECT_CLIENT_ID:
            print("\n   ✅ Token has the correct client_id")
        else:
            print(f"\n   ⚠️  Unknown client_id in token")

    except Exception as e:
        print(f"   ❌ Failed to load token: {e}")
else:
    print(f"   ✅ No token file found (will use credentials.json)")

# Search for ALL credentials.json files
print("\n5. SEARCHING FOR ALL CREDENTIALS.JSON FILES:")
search_paths = [
    Path.home(),
    Path.cwd(),
    Path('/home/user'),
    Path('/root'),
]

found_creds = []
for search_path in search_paths:
    if search_path.exists():
        for cred_file in search_path.rglob('credentials.json'):
            if cred_file.is_file() and '/venv/' not in str(cred_file):
                found_creds.append(cred_file)

if found_creds:
    print(f"   Found {len(found_creds)} credentials.json file(s):")
    for cred_file in found_creds:
        try:
            with open(cred_file, 'r') as f:
                data = json.load(f)
                cid = data.get('installed', {}).get('client_id', 'N/A')
                print(f"   - {cred_file}")
                print(f"     Client ID: {cid[:50]}...")
        except:
            print(f"   - {cred_file} (failed to read)")

# Search for ALL token files
print("\n6. SEARCHING FOR ALL TOKEN FILES:")
found_tokens = []
for search_path in search_paths:
    if search_path.exists():
        for token_file_path in search_path.rglob('token.pickle'):
            if token_file_path.is_file():
                found_tokens.append(token_file_path)

if found_tokens:
    print(f"   Found {len(found_tokens)} token.pickle file(s):")
    for token_path in found_tokens:
        try:
            with open(token_path, 'rb') as f:
                token_data = pickle.load(f)
                tcid = getattr(token_data, 'client_id', 'N/A')
                print(f"   - {token_path}")
                print(f"     Client ID: {tcid}")
        except:
            print(f"   - {token_path} (failed to read)")
else:
    print("   ✅ No token.pickle files found")

print("\n" + "="*70)
print("Now attempting to import GoogleCalendarManager...")
print("="*70)

try:
    from getmoredone.google_calendar import GoogleCalendarManager
    print("\n✅ Successfully imported GoogleCalendarManager")

    # Try to initialize (this will show the actual OAuth URL)
    print("\nAttempting to initialize GoogleCalendarManager...")
    print("(This will open OAuth flow - watch the URL carefully!)")
    print("="*70)

    # Don't actually initialize, just show what would happen
    print("\nTo see the actual OAuth URL, run:")
    print("   python3 test_auth.py")

except Exception as e:
    print(f"\n❌ Failed to import: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("DEBUG COMPLETE")
print("="*70)
