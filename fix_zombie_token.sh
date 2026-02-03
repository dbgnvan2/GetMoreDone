#!/bin/bash
#
# GetMoreDone - Zombie Token Fix Script
#
# This script fixes the "Zombie Token" problem where your token.pickle
# is from a different Google Cloud project than your credentials.json
#

set -e

echo "================================================================"
echo "  GetMoreDone - Zombie Token Fix"
echo "================================================================"
echo ""

TOKEN_FILE="$HOME/.getmoredone/token.pickle"

if [ ! -f "$TOKEN_FILE" ]; then
    echo "No token.pickle found at: $TOKEN_FILE"
    echo "No zombie token to fix!"
    exit 0
fi

echo "Found token.pickle at: $TOKEN_FILE"
echo ""
echo "This script will DELETE your existing token.pickle file."
echo "You will need to re-authenticate with Google Calendar."
echo ""
echo "⚠️  Are you sure you want to delete the token? (y/N): "
read -r response

if [[ ! "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo "Cancelled. Token not deleted."
    exit 0
fi

echo ""
echo "🗑️  Deleting zombie token: $TOKEN_FILE"
rm -f "$TOKEN_FILE"

if [ ! -f "$TOKEN_FILE" ]; then
    echo "✅ Token deleted successfully!"
    echo ""
    echo "Next steps:"
    echo "  1. Run: python3 test_auth.py"
    echo "  2. Complete the authentication in your browser"
    echo "  3. A new token.pickle will be created with the correct project"
    echo ""
else
    echo "❌ Failed to delete token file"
    exit 1
fi
