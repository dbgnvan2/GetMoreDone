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

REM Default dev DB to repo-local data\getmoredone.db unless overridden
if "%GETMOREDONE_DB%"=="" set GETMOREDONE_DB=%cd%\data\getmoredone.db

echo ✅ Launching GetMoreDone...
echo    DB: %GETMOREDONE_DB%
python run.py
