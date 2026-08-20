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

**The build is not signed with an Apple Developer certificate**, so macOS blocks it
the first time and may say the app "is damaged" or "cannot be opened because the
developer cannot be verified". The app is not damaged — macOS attaches a quarantine
flag to anything downloaded from a browser, and with no paid signing certificate
there is nothing for it to check the app against.

Unpack the zip and drag `GetMoreDone.app` to your Applications folder, then use
whichever of these suits you.

### macOS 15 (Sequoia) and later — System Settings

1. Double-click the app and let it get blocked.
2. Open **System Settings → Privacy & Security**.
3. Scroll down. There is a message naming GetMoreDone with an **Open Anyway** button.
4. Click it, authenticate, and open the app again.

The **Open Anyway** button only appears *after* a blocked launch attempt, and it
disappears again after about an hour. If you do not see it, try opening the app once
more and go straight back to Settings.

> **Control-clicking the app and choosing Open no longer works.** That was the standard
> trick for years, and Apple removed it in macOS 15 — an unsigned app can only be
> approved through System Settings now. If you remember doing it that way, that is why
> it stopped working.

### macOS 14 (Sonoma) and earlier — Control-click

Control-click (or right-click) the app, choose **Open**, then **Open** again in the
dialog that appears.

### Any version — the one-line alternative

If you would rather not click through any of that, remove the quarantine flag directly:

```bash
xattr -d com.apple.quarantine /Applications/GetMoreDone.app
```

Then open the app normally. You need this once per download, so again after installing
a new version.

To check whether a copy is even flagged:

```bash
xattr -p com.apple.quarantine /Applications/GetMoreDone.app
```

No output means no quarantine — it will open with no ceremony. Note that this is why a
build fetched with `curl` or `gh release download` often opens without any warning:
those tools do not set the flag, only browsers do.

### If you would rather not run an unsigned binary at all

Run from source instead — see below. There is no Gatekeeper involved, because there is
no binary to check.

> Builds can be signed and notarised, which removes all of the above and makes the app
> open on a double-click. It needs a paid Apple Developer account; the release workflow
> is already wired for it and turns itself on when the credentials are present. See
> [docs/CODE_SIGNING.md](docs/CODE_SIGNING.md).

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

`requirements.txt` is the runtime set. Contributors who also want to run the
test suite install `requirements-dev.txt` instead, which includes it.

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

   Create that folder if it does not exist — GetMoreDone does not create it for
   you, and it is the only place the app, the Gmail importer and the diagnostic
   scripts all look. The "credentials not found" message names the exact path
   it checked.

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
