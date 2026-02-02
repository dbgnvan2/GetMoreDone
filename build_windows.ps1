$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

# Assumes you already created/activated a venv and have python on PATH.
python -m pip install -r requirements.txt
python -m pip install pyinstaller

pyinstaller --noconfirm --clean GetMoreDone.spec

Write-Host "Built: dist\GetMoreDone\GetMoreDone.exe"
