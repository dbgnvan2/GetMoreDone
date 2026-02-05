#!/bin/bash
# GetMoreDone startup script

echo "🚀 Starting GetMoreDone..."

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update requirements (skip test deps for startup)
echo "📥 Installing runtime requirements..."
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$(pwd)/.pip-cache}"
RUNTIME_REQ="$(mktemp /tmp/getmoredone-req.XXXXXX)"
grep -v -E '^\s*#|^\s*$|^pytest\b|^pytest-cov\b' requirements.txt > "$RUNTIME_REQ"
python -m pip install -q -r "$RUNTIME_REQ"
PIP_STATUS=$?
rm -f "$RUNTIME_REQ"
if [ $PIP_STATUS -ne 0 ]; then
    echo "❌ Failed to install requirements. Check your network/DNS and try again."
    echo "   Tip: If you are offline, connect to the internet and re-run ./start.sh"
    exit $PIP_STATUS
fi

# Clear Python cache to avoid import issues
echo "🧹 Clearing Python cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -name "*.pyc" -delete 2>/dev/null

# Default dev DB to repo-local data/getmoredone.db unless overridden
if [ -z "${GETMOREDONE_DB:-}" ]; then
    export GETMOREDONE_DB="$(pwd)/data/getmoredone.db"
fi

echo "✅ Launching GetMoreDone..."
echo "   DB: ${GETMOREDONE_DB}"
python3 run.py
