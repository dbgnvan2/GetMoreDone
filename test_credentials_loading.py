#!/usr/bin/env python3
"""
Direct test to see EXACTLY what credentials file is being loaded.
This will show us the actual client_id being used.
"""

import json
import sys
from pathlib import Path

print("="*70)
print("DIRECT CREDENTIALS LOADING TEST")
print("="*70)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Check what HOME is
import os
print(f"\n1. Environment:")
print(f"   HOME: {os.environ.get('HOME')}")
print(f"   PWD: {os.getcwd()}")

# Get the path that GoogleCalendarManager will use
data_dir = Path.home() / ".getmoredone"
credentials_file = data_dir / "credentials.json"

print(f"\n2. Expected credentials file:")
print(f"   Path: {credentials_file}")
print(f"   Exists: {credentials_file.exists()}")

if credentials_file.exists():
    print(f"\n3. Reading credentials file...")
    with open(credentials_file, 'r') as f:
        creds_data = json.load(f)

    client_id = creds_data['installed']['client_id']
    project_id = creds_data['installed']['project_id']

    print(f"   Project ID: {project_id}")
    print(f"   Client ID: {client_id}")

    EXPECTED = "592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com"
    WRONG = "888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com"

    if client_id == EXPECTED:
        print(f"   ✅ This is CORRECT!")
    elif client_id == WRONG:
        print(f"   ❌ This is WRONG!")
    else:
        print(f"   ⚠️  Unknown client_id")

# Now let's actually create the OAuth flow and see what client_id IT has
print(f"\n4. Creating OAuth flow from this file...")

try:
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = ['https://www.googleapis.com/auth/calendar']

    flow = InstalledAppFlow.from_client_secrets_file(
        str(credentials_file), SCOPES)

    # Check the flow's client_config
    print(f"\n5. OAuth Flow Configuration:")
    print(f"   Client ID from flow: {flow.client_config['client_id']}")
    print(f"   Project ID from flow: {flow.client_config.get('project_id', 'N/A')}")

    EXPECTED = "592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com"
    WRONG = "888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com"

    flow_client_id = flow.client_config['client_id']

    if flow_client_id == EXPECTED:
        print(f"   ✅ Flow has CORRECT client_id!")
    elif flow_client_id == WRONG:
        print(f"   ❌ Flow has WRONG client_id!")
        print(f"\n   🚨 THIS IS THE PROBLEM!")
        print(f"   The OAuth flow is somehow getting the wrong client_id")
        print(f"   even though the credentials file has the correct one.")
    else:
        print(f"   ⚠️  Flow has unknown client_id")

    # Generate the authorization URL to see what it contains
    print(f"\n6. Generating authorization URL...")
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')

    print(f"\n7. Authorization URL:")
    print(f"   {auth_url}")

    # Extract client_id from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(auth_url)
    params = urllib.parse.parse_qs(parsed.query)
    url_client_id = params.get('client_id', ['NOT FOUND'])[0]

    print(f"\n8. Client ID in URL:")
    print(f"   {url_client_id}")

    if url_client_id == EXPECTED:
        print(f"   ✅ URL has CORRECT client_id!")
    elif url_client_id == WRONG:
        print(f"   ❌ URL has WRONG client_id!")
        print(f"\n   🚨 THIS IS THE PROBLEM!")
    else:
        print(f"   ⚠️  URL has unknown client_id")

except Exception as e:
    print(f"   ❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
