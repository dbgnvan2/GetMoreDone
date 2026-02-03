#!/bin/bash
#
# GetMoreDone - Fix Client ID Mismatch
#
# This script diagnoses and fixes the issue where the OAuth URL shows
# the wrong client ID (888606952491... "Bowen1rag" instead of 592866309318... "getmoredone")
#

set -e

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  GetMoreDone - Client ID Mismatch Diagnostic & Fix${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Configuration
GETMOREDONE_DIR="$HOME/.getmoredone"
CREDENTIALS_FILE="$GETMOREDONE_DIR/credentials.json"
TOKEN_FILE="$GETMOREDONE_DIR/token.pickle"
EXPECTED_CLIENT_ID="592866309318-7r1aor9ln8von3vlbqgrineslrl91e6u.apps.googleusercontent.com"
WRONG_CLIENT_ID="888606952491-5anpt1nbript6ls1l02jmtqds2ufaqfg.apps.googleusercontent.com"

echo -e "${YELLOW}PROBLEM:${NC}"
echo "  OAuth URL shows wrong client_id:"
echo "    Found:    ${WRONG_CLIENT_ID} (Bowen1rag)"
echo "    Expected: ${EXPECTED_CLIENT_ID} (getmoredone)"
echo ""

# Step 1: Check credentials.json
echo -e "${BLUE}Step 1: Checking credentials.json...${NC}"
if [ ! -f "$CREDENTIALS_FILE" ]; then
    echo -e "${RED}❌ ERROR: credentials.json not found at ${CREDENTIALS_FILE}${NC}"
    exit 1
fi

ACTUAL_CLIENT_ID=$(python3 -c "import json; print(json.load(open('$CREDENTIALS_FILE'))['installed']['client_id'])" 2>/dev/null || echo "ERROR")

if [ "$ACTUAL_CLIENT_ID" = "ERROR" ]; then
    echo -e "${RED}❌ ERROR: Could not parse credentials.json${NC}"
    exit 1
fi

if [ "$ACTUAL_CLIENT_ID" = "$EXPECTED_CLIENT_ID" ]; then
    echo -e "${GREEN}✅ credentials.json has CORRECT client_id${NC}"
    echo "   Client ID: ${ACTUAL_CLIENT_ID}"
else
    echo -e "${RED}❌ ERROR: credentials.json has WRONG client_id${NC}"
    echo "   Found:    ${ACTUAL_CLIENT_ID}"
    echo "   Expected: ${EXPECTED_CLIENT_ID}"
    echo ""
    echo "Please replace credentials.json with the correct file from:"
    echo "  Google Cloud Console > getmoredone project > OAuth credentials"
    exit 1
fi
echo ""

# Step 2: Check for cached tokens
echo -e "${BLUE}Step 2: Checking for cached authentication tokens...${NC}"

FOUND_TOKENS=0

# Check main token location
if [ -f "$TOKEN_FILE" ]; then
    echo -e "${YELLOW}⚠️  Found token file: ${TOKEN_FILE}${NC}"

    # Try to extract client_id from token
    TOKEN_CLIENT_ID=$(python3 -c "
import pickle
try:
    with open('$TOKEN_FILE', 'rb') as f:
        creds = pickle.load(f)
        print(getattr(creds, 'client_id', 'unknown'))
except:
    print('error')
" 2>/dev/null)

    if [ "$TOKEN_CLIENT_ID" != "unknown" ] && [ "$TOKEN_CLIENT_ID" != "error" ]; then
        if [ "$TOKEN_CLIENT_ID" = "$WRONG_CLIENT_ID" ]; then
            echo -e "${RED}   ⚠️  This token has the WRONG client_id: ${TOKEN_CLIENT_ID}${NC}"
            FOUND_TOKENS=1
        elif [ "$TOKEN_CLIENT_ID" = "$EXPECTED_CLIENT_ID" ]; then
            echo -e "${GREEN}   ✅ This token has the correct client_id${NC}"
        else
            echo -e "${YELLOW}   ⚠️  This token has an unknown client_id: ${TOKEN_CLIENT_ID}${NC}"
            FOUND_TOKENS=1
        fi
    fi
fi

# Check for other common token locations
for dir in "$HOME/.credentials" "$HOME/.config/getmoredone" "$(pwd)"; do
    if [ -d "$dir" ]; then
        for token in $(find "$dir" -name "*.pickle" -o -name "token.json" 2>/dev/null); do
            echo -e "${YELLOW}⚠️  Found token file: ${token}${NC}"
            FOUND_TOKENS=1
        done
    fi
done

if [ $FOUND_TOKENS -eq 0 ]; then
    echo -e "${GREEN}✅ No cached token files found${NC}"
fi
echo ""

# Step 3: Delete cached tokens if found
if [ $FOUND_TOKENS -eq 1 ]; then
    echo -e "${BLUE}Step 3: Delete cached tokens?${NC}"
    echo ""
    echo "Cached tokens from the wrong project will cause authentication to fail."
    echo ""
    read -p "Delete all cached tokens and re-authenticate? (y/N): " -n 1 -r
    echo ""

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if [ -f "$TOKEN_FILE" ]; then
            rm -f "$TOKEN_FILE"
            echo -e "${GREEN}✅ Deleted: ${TOKEN_FILE}${NC}"
        fi

        # Delete any other tokens found
        for dir in "$HOME/.credentials" "$HOME/.config/getmoredone" "$(pwd)"; do
            if [ -d "$dir" ]; then
                find "$dir" -name "*.pickle" -delete 2>/dev/null && echo -e "${GREEN}✅ Deleted tokens in ${dir}${NC}" || true
            fi
        done

        echo ""
        echo -e "${GREEN}✅ All cached tokens deleted${NC}"
        echo ""
    else
        echo -e "${YELLOW}⚠️  Keeping existing tokens. Authentication may fail.${NC}"
        echo ""
    fi
else
    echo -e "${BLUE}Step 3: No cached tokens to delete${NC}"
    echo ""
fi

# Step 4: Clear browser OAuth cache
echo -e "${BLUE}Step 4: Clear browser OAuth cache${NC}"
echo ""
echo "The wrong client_id in the OAuth URL can also come from:"
echo "  • Browser cached OAuth sessions"
echo "  • Browser cookies for accounts.google.com"
echo ""
echo "To fix this:"
echo "  1. Open your browser"
echo "  2. Go to: chrome://settings/cookies (or your browser's cookie settings)"
echo "  3. Search for: accounts.google.com"
echo "  4. Delete all cookies for accounts.google.com"
echo "  5. Close ALL browser windows"
echo ""
read -p "Press Enter once you've cleared browser cache..."
echo ""

# Step 5: Test authentication
echo -e "${BLUE}Step 5: Test authentication${NC}"
echo ""
echo "Now let's test authentication with the correct credentials..."
echo ""

if [ -f "test_auth.py" ]; then
    python3 test_auth.py
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo ""
        echo -e "${GREEN}================================================================${NC}"
        echo -e "${GREEN}✅ SUCCESS! Authentication is now working correctly${NC}"
        echo -e "${GREEN}================================================================${NC}"
        echo ""
        echo "The OAuth URL should now show the correct client_id:"
        echo "  ${EXPECTED_CLIENT_ID}"
        echo ""
        echo "If you still see the wrong client_id, ensure:"
        echo "  1. Browser cache is completely cleared"
        echo "  2. All browser windows are closed and reopened"
        echo "  3. You're using an incognito/private window"
        echo ""
    else
        echo ""
        echo -e "${RED}❌ Authentication test failed${NC}"
        echo ""
        echo "Troubleshooting:"
        echo "  1. Verify credentials.json is from the 'getmoredone' project"
        echo "  2. Check that Google Calendar API is enabled"
        echo "  3. Verify OAuth consent screen is configured"
        echo "  4. Make sure your email is added as a test user"
        echo "  5. Try using an incognito/private browser window"
        echo ""
    fi
else
    echo -e "${YELLOW}⚠️  test_auth.py not found. Run manually:${NC}"
    echo "    python3 test_auth.py"
    echo ""
fi

echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}  Diagnostic Complete${NC}"
echo -e "${BLUE}================================================================${NC}"
