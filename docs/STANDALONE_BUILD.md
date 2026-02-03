# Standalone builds (Windows + macOS)

GetMoreDone is already a single-user, SQLite desktop app.

The main extra work for *standalone distribution* is:
- storing the DB + settings in a user-writable per-OS location (not inside the app bundle)
- bundling the Python runtime + dependencies into a single app (PyInstaller)

## 1) User data location

As of this change, GetMoreDone stores:
- SQLite DB: platform user data dir + `getmoredone.db`
- Settings: platform user data dir + `settings.json`

Examples:
- macOS: `~/Library/Application Support/GetMoreDone/getmoredone.db`
- Windows: `%APPDATA%\GetMoreDone\getmoredone.db`

(Exact location depends on `platformdirs`.)

## 2) Build with PyInstaller

There are two supported ways:
- Use the provided build scripts (`build_mac.sh`, `build_windows.ps1`) which call `GetMoreDone.spec`
- Or run PyInstaller commands manually

### Prereqs

```bash
pip install -r requirements.txt
pip install pyinstaller
```

### macOS (recommended)

From repo root:

```bash
./build_mac.sh
```

Result:
- `dist/GetMoreDone.app`

(Manual equivalent uses `pyinstaller --clean GetMoreDone.spec`.)

### Windows (recommended)

From repo root (PowerShell):

```powershell
.\build_windows.ps1
```

Result:
- `dist\GetMoreDone\GetMoreDone.exe`

(Manual equivalent uses `pyinstaller --clean GetMoreDone.spec`.)

## 3) Notes / gotchas

- If audio or SVG conversion fails in a frozen build, it’s usually a missing hidden-import. We can add a `.spec` file later if needed.
- If you want a true single-file executable (`--onefile`), it’s possible, but startup time is slower and debugging is harder. I recommend one-folder initially.
