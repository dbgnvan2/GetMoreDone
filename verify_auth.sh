#!/bin/bash
#
# GetMoreDone - Authentication Verification Script
#
# This script checks your Google Calendar authentication setup and helps
# diagnose any issues.
#

set -e

echo "================================================================"
echo "  GetMoreDone - Authentication Verification"
echo "================================================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
}

# Step 1: Check Python version
echo "1. Checking Python version..."
if python3 --version &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    check_pass "Python installed: $PYTHON_VERSION"
else
    check_fail "Python 3 not found"
    exit 1
fi
echo ""

# Step 2: Check dependencies
echo "2. Checking Google Calendar dependencies..."
DEPS_OK=true

for package in google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client; do
    if pip show "$package" &> /dev/null; then
        VERSION=$(pip show "$package" | grep Version | cut -d' ' -f2)
        check_pass "$package installed (v$VERSION)"
    else
        check_fail "$package NOT installed"
        DEPS_OK=false
    fi
done

if [ "$DEPS_OK" = false ]; then
    echo ""
    echo "To install missing dependencies:"
    echo "  pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client"
    exit 1
fi
echo ""

# Step 3: Check credentials directory
echo "3. Checking credentials directory..."
CONFIG_DIR="$HOME/.getmoredone"

if [ -d "$CONFIG_DIR" ]; then
    check_pass "Config directory exists: $CONFIG_DIR"

    # Check permissions
    PERMS=$(stat -c "%a" "$CONFIG_DIR")
    if [ "$PERMS" = "700" ]; then
        check_pass "Directory permissions correct (700)"
    else
        check_warn "Directory permissions: $PERMS (should be 700)"
        echo "  Fix with: chmod 700 $CONFIG_DIR"
    fi
else
    check_warn "Config directory doesn't exist: $CONFIG_DIR"
    echo "  It will be created automatically on first run"
fi
echo ""

# Step 4: Check credentials.json
echo "4. Checking credentials.json..."
CREDS_FILE="$CONFIG_DIR/credentials.json"

if [ -f "$CREDS_FILE" ]; then
    check_pass "credentials.json exists"

    # Check permissions
    PERMS=$(stat -c "%a" "$CREDS_FILE")
    if [ "$PERMS" = "600" ]; then
        check_pass "File permissions correct (600)"
    else
        check_warn "File permissions: $PERMS (should be 600)"
        echo "  Fix with: chmod 600 $CREDS_FILE"
    fi

    # Check if valid JSON
    if python3 -c "import json; json.load(open('$CREDS_FILE'))" 2>/dev/null; then
        check_pass "credentials.json is valid JSON"

        # Check if it's the right type
        TYPE=$(python3 -c "import json; print(list(json.load(open('$CREDS_FILE')).keys())[0])" 2>/dev/null)
        if [ "$TYPE" = "installed" ]; then
            check_pass "Credentials type: $TYPE (correct for desktop app)"
        else
            check_warn "Credentials type: $TYPE (expected 'installed')"
        fi
    else
        check_fail "credentials.json is not valid JSON"
    fi
else
    check_fail "credentials.json NOT found at: $CREDS_FILE"
    echo ""
    echo "  You need to download OAuth credentials from Google Cloud Console."
    echo "  See: docs/google-calendar-setup.md for instructions"
    exit 1
fi
echo ""

# Step 5: Check token.pickle
echo "5. Checking token.pickle..."
TOKEN_FILE="$CONFIG_DIR/token.pickle"

if [ -f "$TOKEN_FILE" ]; then
    check_pass "token.pickle exists (already authenticated)"

    # Check permissions
    PERMS=$(stat -c "%a" "$TOKEN_FILE")
    if [ "$PERMS" = "600" ]; then
        check_pass "File permissions correct (600)"
    else
        check_warn "File permissions: $PERMS (should be 600)"
        echo "  Fix with: chmod 600 $TOKEN_FILE"
    fi
else
    check_warn "token.pickle NOT found (first-time authentication needed)"
    echo "  This file will be created automatically when you first authenticate"
fi
echo ""

# Step 6: Test authentication (optional)
echo "6. Testing authentication..."
echo "   Would you like to test Google Calendar authentication now? (y/N)"
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo ""
    echo "Running test authentication..."
    python3 test_auth.py
else
    echo "   Skipped (run 'python3 test_auth.py' to test manually)"
fi
echo ""

# Summary
echo "================================================================"
echo "  Summary"
echo "================================================================"
echo ""

if [ -f "$CREDS_FILE" ] && [ -f "$TOKEN_FILE" ] && [ "$DEPS_OK" = true ]; then
    check_pass "All checks passed! Authentication should work."
    echo ""
    echo "Next steps:"
    echo "  1. Launch GetMoreDone: python3 -m getmoredone"
    echo "  2. Open an action item and click '📅 Calendar' to create an event"
elif [ -f "$CREDS_FILE" ] && [ "$DEPS_OK" = true ]; then
    check_warn "Setup is mostly complete, but needs first-time authentication"
    echo ""
    echo "Next steps:"
    echo "  1. Launch GetMoreDone: python3 -m getmoredone"
    echo "  2. Open an action item and click '📅 Calendar'"
    echo "  3. Complete the OAuth authentication in your browser"
    echo "  4. token.pickle will be created automatically"
else
    check_warn "Setup incomplete - please follow the instructions above"
    echo ""
    echo "See docs/EMAIL-AUTH-TROUBLESHOOTING.md for detailed help"
fi
echo ""
echo "For troubleshooting, see: docs/EMAIL-AUTH-TROUBLESHOOTING.md"
echo "================================================================"
