@echo off
REM GetMoreDone startup script for Windows

echo 🚀 Starting GetMoreDone...

REM Check if virtual environment exists, create if not
if not exist "venv" (
    echo 📦 Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

REM Install/update requirements
echo 📥 Installing requirements...
pip install -q -r requirements.txt

REM Run the application
echo ✅ Launching GetMoreDone...
python run.py
