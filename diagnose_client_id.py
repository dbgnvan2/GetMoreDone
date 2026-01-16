#!/usr/bin/env python3
"""
Comprehensive diagnostic tool to identify client_id mismatches.

This script checks:
1. credentials.json client_id
2. All cached token files and their client_ids
3. Provides detailed information about the mismatch
"""

import json
import pickle
import os
import sys
from pathlib import Path

# Color codes
class Colors:
    BLUE = '\033[0;34m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

EXPECTED_CLIENT_ID = "592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com"
WRONG_CLIENT_ID = "888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com"

def print_header(text):
    """Print a colored header."""
    print(f"\n{Colors.BLUE}{'='*70}{Colors.NC}")
    print(f"{Colors.BLUE}{text}{Colors.NC}")
    print(f"{Colors.BLUE}{'='*70}{Colors.NC}\n")

def print_success(text):
    """Print success message."""
    print(f"{Colors.GREEN}✅ {text}{Colors.NC}")

def print_error(text):
    """Print error message."""
    print(f"{Colors.RED}❌ {text}{Colors.NC}")

def print_warning(text):
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.NC}")

def check_credentials_json(file_path):
    """Check credentials.json and return client_id info."""
    print(f"{Colors.BOLD}Checking: {file_path}{Colors.NC}")

    if not file_path.exists():
        print_error(f"File not found: {file_path}")
        return None

    try:
        with open(file_path, 'r') as f:
            data = json.load(f)

        client_id = data.get('installed', {}).get('client_id')
        project_id = data.get('installed', {}).get('project_id')
        redirect_uris = data.get('installed', {}).get('redirect_uris', [])

        if not client_id:
            print_error("No client_id found in credentials.json")
            return None

        print(f"  Project ID:    {project_id}")
        print(f"  Client ID:     {client_id}")
        print(f"  Redirect URIs: {', '.join(redirect_uris)}")

        # Check if it matches expected or wrong client_id
        if client_id == EXPECTED_CLIENT_ID:
            print_success("This is the CORRECT client_id (getmoredone project)")
            return {'status': 'correct', 'client_id': client_id, 'project_id': project_id}
        elif client_id == WRONG_CLIENT_ID:
            print_error("This is the WRONG client_id (Bowen1rag project)")
            return {'status': 'wrong', 'client_id': client_id, 'project_id': project_id}
        else:
            print_warning(f"This is an UNKNOWN client_id")
            return {'status': 'unknown', 'client_id': client_id, 'project_id': project_id}

    except Exception as e:
        print_error(f"Failed to parse credentials.json: {e}")
        return None

def check_token_file(file_path):
    """Check a token pickle file and return client_id info."""
    print(f"{Colors.BOLD}Checking: {file_path}{Colors.NC}")

    if not file_path.exists():
        print_warning(f"Token file not found: {file_path}")
        return None

    try:
        with open(file_path, 'rb') as f:
            creds = pickle.load(f)

        client_id = getattr(creds, 'client_id', None)
        token_uri = getattr(creds, 'token_uri', None)
        scopes = getattr(creds, 'scopes', None)
        valid = getattr(creds, 'valid', None)
        expired = getattr(creds, 'expired', None)

        print(f"  Client ID:  {client_id or 'Not available'}")
        print(f"  Token URI:  {token_uri or 'Not available'}")
        print(f"  Scopes:     {scopes or 'Not available'}")
        print(f"  Valid:      {valid}")
        print(f"  Expired:    {expired}")

        if not client_id:
            print_warning("Could not extract client_id from token")
            return {'status': 'unknown', 'client_id': None}

        # Check if it matches expected or wrong client_id
        if client_id == EXPECTED_CLIENT_ID:
            print_success("This token has the CORRECT client_id")
            return {'status': 'correct', 'client_id': client_id}
        elif client_id == WRONG_CLIENT_ID:
            print_error("This token has the WRONG client_id (Bowen1rag)")
            return {'status': 'wrong', 'client_id': client_id}
        else:
            print_warning("This token has an UNKNOWN client_id")
            return {'status': 'unknown', 'client_id': client_id}

    except Exception as e:
        print_error(f"Failed to load token file: {e}")
        return None

def find_all_token_files():
    """Find all potential token files on the system."""
    token_files = []

    # Common locations to check
    search_paths = [
        Path.home() / ".getmoredone",
        Path.home() / ".credentials",
        Path.home() / ".config" / "getmoredone",
        Path.cwd(),  # Current directory
    ]

    for search_path in search_paths:
        if search_path.exists():
            for pattern in ["*.pickle", "token*", "*.json"]:
                for file in search_path.rglob(pattern):
                    if file.is_file() and "credentials.json" not in file.name:
                        token_files.append(file)

    return token_files

def main():
    """Run diagnostic."""
    print_header("GetMoreDone - Client ID Diagnostic Tool")

    print("This tool will help identify why the OAuth URL shows the wrong client_id.\n")

    # Define file paths
    getmoredone_dir = Path.home() / ".getmoredone"
    credentials_file = getmoredone_dir / "credentials.json"
    token_file = getmoredone_dir / "token.pickle"

    # Track issues
    issues_found = []

    # Step 1: Check credentials.json
    print_header("Step 1: Check credentials.json")
    creds_info = check_credentials_json(credentials_file)

    if creds_info is None:
        issues_found.append("credentials.json not found or invalid")
    elif creds_info['status'] == 'wrong':
        issues_found.append(f"credentials.json has wrong client_id: {creds_info['client_id']}")
    elif creds_info['status'] == 'unknown':
        issues_found.append(f"credentials.json has unknown client_id: {creds_info['client_id']}")

    # Step 2: Check main token file
    print_header("Step 2: Check main token file")
    token_info = check_token_file(token_file)

    if token_info and token_info['status'] == 'wrong':
        issues_found.append(f"token.pickle has wrong client_id: {token_info['client_id']}")
    elif token_info and token_info['status'] == 'unknown':
        issues_found.append(f"token.pickle has unknown client_id: {token_info['client_id']}")

    # Step 3: Search for other token files
    print_header("Step 3: Search for other token files")
    other_tokens = find_all_token_files()

    if other_tokens:
        print(f"Found {len(other_tokens)} potential token file(s):\n")
        for token in other_tokens:
            if token != token_file:
                info = check_token_file(token)
                if info and info['status'] == 'wrong':
                    issues_found.append(f"{token} has wrong client_id")
                print()  # Add spacing
    else:
        print_success("No other token files found")

    # Step 4: Summary and recommendations
    print_header("Summary & Recommendations")

    if not issues_found:
        print_success("No issues found!")
        print("\nYour credentials.json has the correct client_id.")
        print("If you're still seeing the wrong client_id in OAuth URLs, try:")
        print("  1. Clear browser cache and cookies for accounts.google.com")
        print("  2. Close all browser windows and restart")
        print("  3. Use an incognito/private browser window")
        print("  4. Check if there's a different app instance running")
    else:
        print_error(f"Found {len(issues_found)} issue(s):\n")
        for i, issue in enumerate(issues_found, 1):
            print(f"  {i}. {issue}")

        print("\n" + "="*70)
        print(f"{Colors.BOLD}RECOMMENDED ACTIONS:{Colors.NC}")
        print("="*70 + "\n")

        # Provide specific recommendations based on issues
        if any("credentials.json" in issue for issue in issues_found):
            print("📋 FIX credentials.json:")
            print("  1. Go to: https://console.cloud.google.com/")
            print("  2. Select the 'getmoredone' project")
            print("  3. Go to: APIs & Services > Credentials")
            print("  4. Download the OAuth client credentials")
            print(f"  5. Save as: {credentials_file}")
            print()

        if any("token" in issue.lower() for issue in issues_found):
            print("🗑️  DELETE cached tokens:")
            print(f"  rm -f {token_file}")
            for token in other_tokens:
                if token != token_file:
                    print(f"  rm -f {token}")
            print()

        print("🧪 TEST authentication:")
        print("  python3 test_auth.py")
        print()

        print("🌐 CLEAR browser cache:")
        print("  • Delete cookies for accounts.google.com")
        print("  • Close all browser windows")
        print("  • Use incognito/private mode for testing")
        print()

    print_header("Diagnostic Complete")

    # Exit with appropriate code
    return 1 if issues_found else 0

if __name__ == "__main__":
    sys.exit(main())
