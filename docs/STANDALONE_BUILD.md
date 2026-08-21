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
- Use the provided build scripts (`build_mac.sh`, `build_windows.ps1`) which call `daVIPA.spec`
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
- `dist/daVIPA.app`

(Manual equivalent uses `pyinstaller --clean daVIPA.spec`.)

### Windows (recommended)

From repo root (PowerShell):

```powershell
.\build_windows.ps1
```

Result:
- `dist\GetMoreDone\daVIPA.exe`

(Manual equivalent uses `pyinstaller --clean daVIPA.spec`.)

## 3) Notes / gotchas

- `daVIPA.spec` is the supported build definition and is checked in. It is the only supported path — both build scripts and the release workflow use it. If a frozen build fails on a missing module, add it to `hiddenimports` there; if it fails on a missing *file*, add the folder to `datas` (that omission is what made every pre-0.1.0 binary crash on launch).
- **Do not switch to `--onefile`.** Beyond the slower startup, pygame is LGPL and one-folder packaging is what keeps its libraries separately replaceable, as that licence requires. See `THIRD_PARTY_NOTICES.md`; `tests/test_packaging_resources.py` enforces it.

## 4) Verifying a build

Both build scripts run the packaged app's selftest and fail if it does not
start. To check a build by hand:

```bash
./dist/daVIPA.app/Contents/MacOS/GetMoreDone --selftest
```

It prints one line per check and exits non-zero on failure. On Windows the
executable is built windowed, so a console will not wait for it or report its
exit code — use `Start-Process -Wait -PassThru` as `build_windows.ps1` does.

The release workflow runs this on both platforms before publishing anything.
