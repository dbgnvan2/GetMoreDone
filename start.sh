#!/bin/bash
# GetMoreDone startup script

echo "🚀 Starting GetMoreDone..."

# Check if virtual environment exists, create if not
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Use venv interpreter directly (avoids system Python/pip issues)
VENV_PY="$(pwd)/venv/bin/python"
if [ ! -x "$VENV_PY" ]; then
    echo "❌ Virtual environment Python not found at $VENV_PY"
    echo "   Delete ./venv and re-run ./start.sh"
    exit 1
fi
echo "🔧 Using virtual environment: $VENV_PY"

# Install/update requirements (skip test deps for startup)
echo "📥 Installing runtime requirements..."
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$(pwd)/.pip-cache}"
RUNTIME_REQ="$(mktemp /tmp/getmoredone-req.XXXXXX)"
grep -v -E '^\s*#|^\s*$|^pytest\b|^pytest-cov\b' requirements.txt > "$RUNTIME_REQ"
"$VENV_PY" -m pip install -q -r "$RUNTIME_REQ"
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

# Default to production DB path unless overridden
if [ -z "${GETMOREDONE_DB:-}" ]; then
    export GETMOREDONE_DB="${HOME}/Library/Application Support/GetMoreDone/getmoredone.db"
fi

echo "✅ Launching GetMoreDone..."
echo "   DB: ${GETMOREDONE_DB}"
"$VENV_PY" run.py
