#!/bin/bash
# daVIPA startup script

echo "🚀 Starting daVIPA..."

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

# Install/update requirements. requirements.txt is runtime-only since the
# requirements-dev.txt split, so this no longer greps the test packages out of
# it by name — a third test-only package used to slip straight through that.
echo "📥 Installing runtime requirements..."
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-$(pwd)/.pip-cache}"
"$VENV_PY" -m pip install -q -r requirements.txt
PIP_STATUS=$?
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

echo "✅ Launching daVIPA..."
echo "   DB: ${GETMOREDONE_DB}"
"$VENV_PY" run.py
