# Installing GetMoreDone

GetMoreDone is a desktop app for macOS and Windows. Everything it stores stays
on your own machine — there is no account, no server, and no telemetry.

- [Download a build](#download-a-build) — the quickest route
- [macOS: first launch](#macos-first-launch) — **required**, the build is unsigned
- [Windows: first launch](#windows-first-launch)
- [Run from source](#run-from-source) — Linux, or if you'd rather not run a binary
- [Verify your download](#verify-your-download)
- [Optional: Google Calendar](#optional-google-calendar)
- [Optional: background music](#optional-background-music)
- [Where your data is stored](#where-your-data-is-stored)
- [Uninstalling](#uninstalling)

---

## Download a build

Go to the [Releases page](https://github.com/dbgnvan2/GetMoreDone/releases) and
take the archive for your system:

| System | File | Unpacks to |
|---|---|---|
| macOS | `GetMoreDone-mac.zip` | `GetMoreDone.app` |
| Windows | `GetMoreDone-win64.zip` | a `GetMoreDone` folder containing `GetMoreDone.exe` |

Each release also carries a `.sha256` file — see
[Verify your download](#verify-your-download).

There is no Linux build. Linux is supported from source; see
[Run from source](#run-from-source).

---

## macOS: first launch

**The build is not signed with an Apple Developer certificate**, so macOS will
refuse to open it the first time and say the app "is damaged" or "cannot be
opened because the developer cannot be verified". The app is not damaged —
macOS attaches a quarantine flag to anything downloaded from the internet, and
without a paid signing certificate there is nothing to check it against.

Unpack the zip, drag `GetMoreDone.app` to your Applications folder, then run:

```bash
xattr -d com.apple.quarantine /Applications/GetMoreDone.app
```

Then open it normally. You only need to do this once per download — but you'll
need it again after installing a new version.

If you prefer not to run that command, right-click the app, choose **Open**, and
confirm at the prompt. On recent macOS versions you may instead need
**System Settings → Privacy & Security**, then **Open Anyway** next to the
blocked-app message.

If you'd rather not run an unsigned binary at all, run from source instead.

---

## Windows: first launch

Unpack `GetMoreDone-win64.zip` anywhere you like — your user folder is fine —
and run `GetMoreDone.exe` from inside the unpacked `GetMoreDone` folder.

Keep the folder together. `GetMoreDone.exe` needs the `_internal` folder beside
it; moving the .exe out on its own will stop it working.

SmartScreen may warn that the publisher is unrecognised, for the same reason
macOS does: the build is unsigned. Choose **More info → Run anyway** if you're
happy to proceed.

---

## Run from source

Works on macOS, Windows, and Linux. Requires **Python 3.11 or newer**.

```bash
git clone https://github.com/dbgnvan2/GetMoreDone.git
cd GetMoreDone
./start.sh
```

`start.sh` creates a virtual environment, installs dependencies, and launches
the app. On Windows use `start.bat`. To do it by hand:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

On Linux you may need your distribution's Tk package first, e.g.
`sudo apt install python3-tk`.

---

## Verify your download

Each release archive ships with a `.sha256` file next to it. To check an archive
matches:

```bash
shasum -a 256 -c GetMoreDone-mac.zip.sha256
```

On Windows, in PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 GetMoreDone-win64.zip
```

and compare the result with the contents of `GetMoreDone-win64.zip.sha256`.

---

## Optional: Google Calendar

GetMoreDone runs fully without this. If you skip it, calendar features report
that they're unavailable and explain what's missing — nothing breaks.

To enable it you need your own Google Cloud OAuth credentials:

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable the **Google Calendar API**
3. Create an **OAuth client ID** of type **Desktop app**
4. Download the JSON and save it as `credentials.json` at:
   - macOS/Linux: `~/.getmoredone/credentials.json`
   - Windows: `%USERPROFILE%\.getmoredone\credentials.json`

The first calendar action opens a browser to authorise. If sign-in misbehaves,
run `python3 tools/diagnose_google_auth.py` from a source checkout.

---

## Optional: background music

The timer can play background music while you work. **No music ships with
GetMoreDone** — point it at a folder of your own in
**Settings → Timer & Audio → Music folder**.

Supported formats: `.mp3`, `.wav`, `.ogg`, `.aif`, `.aiff`, `.flac`, `.m4a`.
With no folder set, the timer simply runs without music.

---

## Where your data is stored

Your database and settings live outside the app, so upgrading by replacing the
app does not touch your data:

| System | Location |
|---|---|
| macOS | `~/Library/Application Support/GetMoreDone/` |
| Windows | `%APPDATA%\GetMoreDone\` |
| Linux | `~/.local/share/GetMoreDone/` |

That folder holds `getmoredone.db` (all your items) and `settings.json`. Google
credentials, if you set them up, live separately in `~/.getmoredone/`.

**Back up `getmoredone.db` yourself.** GetMoreDone does not back it up for you.

To run against a different database — for testing, or to keep work and personal
separate — set `GETMOREDONE_DB` to a path of your choosing.

---

## Uninstalling

1. Delete the app: `GetMoreDone.app` on macOS, or the unpacked folder on Windows.
2. Delete your data folder from the table above — **this permanently deletes
   every item you have entered**, so copy `getmoredone.db` somewhere first if you
   might want it back.
3. If you set up Google access, delete `~/.getmoredone/`.

Nothing is installed anywhere else. There are no registry entries, no background
services, and no login items.

---

## Something went wrong

- **macOS says the app is damaged** → the quarantine flag; see
  [macOS: first launch](#macos-first-launch).
- **Windows: the app won't start after moving the .exe** → keep `_internal`
  beside it.
- **Calendar features are greyed out** → no `credentials.json`; see
  [Optional: Google Calendar](#optional-google-calendar).
- **No music plays** → no music folder set; see
  [Optional: background music](#optional-background-music).

If you're running from source, `python run.py --selftest` checks that resources
and the database are in order and prints a line per check.

Licence terms are in [LICENSE](LICENSE); third-party components are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
