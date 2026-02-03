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

# Install/update requirements
echo "📥 Installing requirements..."
pip install -q -r requirements.txt

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
python run.py
