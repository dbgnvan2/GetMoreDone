# Gmail Import Troubleshooting

Use these steps whenever the Gmail → daVIPA importer stops working (for example, the OAuth token is revoked or launchd stops pulling emails).

## 1. Reset the Gmail token

```bash
rm ~/.getmoredone/gmail_token.json
```

- This forces Google to prompt for authorization the next time the importer runs.
- Leave `~/.getmoredone/credentials.json` in place (that file contains the OAuth client ID/secret).

## 2. Run the importer manually

```bash
cd /Users/davemini2/ProjectsLocal/daVIPA
python3 tools/import_gmd_from_gmail.py
```

- A browser window will open; sign in with the account connected to the importer and approve Gmail access.
- The script prints `Imported N email(s)...` when it succeeds.

## 3. Restart the launchd job (optional but recommended)

```bash
cd /Users/davemini2/ProjectsLocal/daVIPA
python3 tools/update_launchd_importer.py --reload prod
```

- This rewrites the LaunchAgent plist under `~/Library/LaunchAgents/` and reloads it so the scheduled importer uses the new token and settings.

## 4. Check logs if it fails again

- Standard output: `/tmp/getmoredone-gmailimport-com.getmoredone.gmailimport.prod.out.log`
- Errors/exceptions: `/tmp/getmoredone-gmailimport-com.getmoredone.gmailimport.prod.err.log`

## 5. Quick checklist

- Settings → Email Import → “Enable Gmail import” must be checked.
- Trigger / Processed labels match the labels inside Gmail.
- The `venv` dependencies (`google-auth`, `google-auth-oauthlib`, `google-api-python-client`) are installed with `pip install -r requirements.txt`.

Following the sequence above (delete token → run importer once → reload launchd) resolves expired-token and label-mismatch issues without needing to dig into the code.***
