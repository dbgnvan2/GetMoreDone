# Gmail → GetMoreDone automation (Spark-friendly)

This implements **Option 1**: use a Gmail label as the trigger, and a local script that imports labeled emails into GetMoreDone’s SQLite DB.

## Desired workflow (Dave)

- You use Spark with multiple accounts.
- For the automation account (`davebgalloway@gmail.com`), you:
  1) put an email into label/folder **`GMD`**
  2) the importer creates a GetMoreDone Action Item
  3) then the importer “moves” the email by removing label `GMD` and applying label **`GMD/moved`**

## Field mapping

Imported Action Item fields:
- **who**: `Email`
- **title**: Gmail Subject
- **description (NOTES)**: full email body (plain text if available) + From/Date metadata
- **start_date**: Today
- **due_date**: Today + 1
- **group**: `EMAIL`
- Priority factors: defaults

## One-time setup (OAuth)

1) Create OAuth credentials in Google Cloud Console for Gmail API (Desktop app)
2) Download the JSON and save it to:

`~/.getmoredone/credentials.json`

(If `~/.getmoredone/` doesn’t exist, create it.)

First run will open a browser to authorize and will store a token at:

`~/.getmoredone/gmail_token.json`

## Dev vs Prod DB selection

GetMoreDone supports two modes:
- **Dev (repo)**: set `GETMOREDONE_DB` to a repo-local DB (e.g. `.../GetMoreDone/data/getmoredone.db`)
- **Prod (installed app)**: do not set `GETMOREDONE_DB` → uses `~/Library/Application Support/GetMoreDone/getmoredone.db`

The Gmail importer uses the same rule.

## Run manually

From repo root:

```bash
source venv/bin/activate
python tools/import_gmd_from_gmail.py
```

Dry run (does not write to DB and does not change Gmail labels):

```bash
python tools/import_gmd_from_gmail.py --dry-run
```

## Run automatically on macOS (launchd)

Create a LaunchAgent plist at:

`~/Library/LaunchAgents/com.getmoredone.gmailimport.plist`

Example (DEV instance; edit paths to your repo/venv):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.getmoredone.gmailimport</string>

  <key>ProgramArguments</key>
  <array>
    <string>/Users/davemini2/ProjectsLocal/GetMoreDone/venv/bin/python</string>
    <string>/Users/davemini2/ProjectsLocal/GetMoreDone/tools/import_gmd_from_gmail.py</string>
  </array>

  <key>EnvironmentVariables</key>
  <dict>
    <key>GETMOREDONE_DB</key>
    <string>/Users/davemini2/ProjectsLocal/GetMoreDone/data/getmoredone.db</string>
  </dict>

  <key>StartInterval</key>
  <integer>60</integer>

  <key>StandardOutPath</key>
  <string>/tmp/getmoredone-gmailimport.out.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/getmoredone-gmailimport.err.log</string>

  <key>RunAtLoad</key>
  <true/>
</dict>
</plist>
```

Then load it:

```bash
launchctl load ~/Library/LaunchAgents/com.getmoredone.gmailimport.plist
```

Uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.getmoredone.gmailimport.plist
rm ~/Library/LaunchAgents/com.getmoredone.gmailimport.plist
```

## Notes / limitations

- Gmail labels are per-account. This automation runs for the authorized account only (recommended).
- If the email only has HTML body, we do a very rough HTML→text conversion.
- If you want duplicate protection beyond “move the message after import”, we can store Gmail Message-ID in a dedicated table.
