$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

# Assumes you already created/activated a venv and have python on PATH.
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Run PyInstaller as a module of the active interpreter, so the build uses the
# same environment the dependencies were just installed into.
python -m PyInstaller --noconfirm --clean GetMoreDone.spec

# Prove the bundle actually starts before calling the build a success.
# A temp DB keeps the build from touching the developer's real database.
$SelftestDb = Join-Path ([System.IO.Path]::GetTempPath()) ("gmd-selftest-" + [guid]::NewGuid() + ".db")
$env:GETMOREDONE_DB = $SelftestDb
try {
    & "dist\GetMoreDone\GetMoreDone.exe" --selftest
} finally {
    Remove-Item -Path $SelftestDb -ErrorAction SilentlyContinue
    Remove-Item Env:\GETMOREDONE_DB -ErrorAction SilentlyContinue
}
if ($LASTEXITCODE -ne 0) { throw "Packaged build failed its selftest (exit $LASTEXITCODE)" }

Write-Host "Built: dist\GetMoreDone\GetMoreDone.exe"
