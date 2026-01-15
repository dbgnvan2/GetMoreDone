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

# Run the application
echo "✅ Launching GetMoreDone..."
python run.py
