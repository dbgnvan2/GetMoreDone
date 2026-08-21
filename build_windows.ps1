$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

# Assumes you already created/activated a venv and have python on PATH.
python -m pip install -r requirements.txt
python -m pip install pyinstaller

# Run PyInstaller as a module of the active interpreter, so the build uses the
# same environment the dependencies were just installed into.
python -m PyInstaller --noconfirm --clean daVIPA.spec

# Prove the bundle actually starts before calling the build a success.
# A temp DB keeps the build from touching the developer's real database.
# daVIPA.exe is built console=False (windowed subsystem): `& app.exe`
# returns immediately without waiting and never sets $LASTEXITCODE. Use
# Start-Process -Wait -PassThru for a real exit code, and redirect the output
# because a windowed process has no console to write to.
$SelftestDb = Join-Path ([System.IO.Path]::GetTempPath()) ("gmd-selftest-" + [guid]::NewGuid() + ".db")
$SelftestOut = Join-Path ([System.IO.Path]::GetTempPath()) ("gmd-selftest-" + [guid]::NewGuid() + ".log")
$env:GETMOREDONE_DB = $SelftestDb
try {
    $proc = Start-Process -FilePath "dist\daVIPA\daVIPA.exe" `
        -ArgumentList "--selftest" -Wait -PassThru `
        -RedirectStandardOutput $SelftestOut
    if (Test-Path $SelftestOut) { Get-Content $SelftestOut }
    if ($proc.ExitCode -ne 0) { throw "Packaged build failed its selftest (exit $($proc.ExitCode))" }
} finally {
    Remove-Item -Path $SelftestDb, $SelftestOut -ErrorAction SilentlyContinue
    Remove-Item Env:\GETMOREDONE_DB -ErrorAction SilentlyContinue
}

Write-Host "Built: dist\daVIPA\daVIPA.exe"
