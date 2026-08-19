# Code signing and notarisation (macOS)

The release workflow can sign and notarise the macOS build, so it opens on a
double-click with no Gatekeeper prompt at all. **It is off until you add the
secrets below**, and with them absent every signing step is skipped and the
build comes out exactly as it does today — unsigned, needing the steps in
`INSTALL.md`.

Nothing here is required to ship. It removes friction for the people who
download the app, and it stops mattering only if you never distribute to
anyone else.

---

## What it costs

| | |
|---|---|
| Apple Developer Program | **99 USD/year** |
| Setup time | An hour or two, once |
| Per-release cost | None — the workflow does it |
| Build time added | 2–10 minutes, mostly waiting on Apple's notary service |

Notarisation itself is free once you are in the programme.

## What it changes for users

| | Unsigned (today) | Signed + notarised |
|---|---|---|
| macOS 15+ | Blocked; approve in System Settings → Privacy & Security | Opens |
| macOS 14 and earlier | Blocked; Control-click → Open | Opens |
| "App is damaged" message | Common | Never |
| `xattr` workaround needed | Yes | No |

---

## Setting it up

### 1. Join the Apple Developer Program

<https://developer.apple.com/programs/> — 99 USD/year. An individual
membership is fine; you do not need an organisation.

### 2. Create a Developer ID Application certificate

This is the certificate for apps distributed **outside** the App Store. In
Xcode: **Settings → Accounts → Manage Certificates → + → Developer ID
Application**. Or create it in the Developer portal under Certificates.

Export it from Keychain Access as a `.p12` with a password, then base64 it:

```bash
base64 -i DeveloperID.p12 | pbcopy
```

Find the exact identity string — you need it verbatim:

```bash
security find-identity -v -p codesigning
```

It looks like `Developer ID Application: Your Name (A1B2C3D4E5)`.

### 3. Create an App Store Connect API key for notarisation

In App Store Connect: **Users and Access → Integrations → App Store Connect
API → +**. Give it the **Developer** role. Download the `.p8` — **you only get
one chance to download it**. Note the Key ID and the Issuer ID shown on that
page.

```bash
base64 -i AuthKey_XXXXXXXXXX.p8 | pbcopy
```

An App Store Connect key is used rather than an Apple ID and app-specific
password because it does not break when you change your Apple ID password, and
it can be scoped and revoked on its own.

### 4. Add six repository secrets

**Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|---|---|
| `APPLE_CERTIFICATE_P12_BASE64` | base64 of the `.p12` from step 2 |
| `APPLE_CERTIFICATE_PASSWORD` | the password you set when exporting it |
| `APPLE_SIGNING_IDENTITY` | e.g. `Developer ID Application: Your Name (A1B2C3D4E5)` |
| `APPLE_NOTARY_KEY_BASE64` | base64 of the `.p8` from step 3 |
| `APPLE_NOTARY_KEY_ID` | the Key ID |
| `APPLE_NOTARY_ISSUER_ID` | the Issuer ID (a UUID) |

The workflow checks for the certificate, the identity and the notary key. If
any of those three is missing it skips signing entirely and prints a notice
saying the build is unsigned — it does not half-sign and it does not fail.

### 5. Run it

Trigger **Build binaries** from the Actions tab, or push a tag. Watch the
"Verify the signature and notarisation" step: it runs `spctl --assess`, which
is what Gatekeeper itself runs, so a pass there means a real Mac will open the
app without complaint.

Then download the artifact **through a browser** — not `curl` or
`gh release download`, neither of which sets the quarantine flag — and confirm
it opens with no prompt on a Mac that has never run GetMoreDone.

---

## How it behaves

- **No secrets** → all signing steps skipped, unsigned build, job green, a
  notice in the log saying so. Identical to the current behaviour.
- **Secrets present, signing succeeds** → signed, notarised, stapled, verified
  against `spctl`.
- **Secrets present, anything fails** → the job fails. It will never publish an
  unsigned build while looking like it signed one; that would be the worst of
  both outcomes, since nobody would notice until a user complained.

The signing keychain is created fresh in `RUNNER_TEMP` and deleted in an
`if: always()` step, so a failure mid-way does not leave a certificate behind
on the runner.

## Entitlements

`packaging/entitlements.plist` grants exactly three, all forced by CPython
under the hardened runtime that notarisation requires: `allow-jit`,
`allow-unsigned-executable-memory`, and `disable-library-validation` (the
bundle loads `.so` modules signed with your Developer ID, not Apple's).

No privacy-sensitive entitlement is granted. Google Calendar works over HTTPS
with the user's own OAuth credentials and needs none.

## Windows

Not wired up. SmartScreen is the equivalent nuisance and the fix is an
Authenticode certificate:

- **OV certificate** (~200–400 USD/year) — warnings persist until the binary
  accumulates download reputation, which for a low-volume app can take a while.
- **EV certificate** (more, and requires a hardware token or a cloud HSM) —
  immediate SmartScreen reputation.

Worth doing at the same time as macOS if you start charging for the app;
otherwise the "More info → Run anyway" path in `INSTALL.md` is serviceable.

## Renewal

- The **Developer Program membership** lapses yearly; when it does, notarisation
  starts failing and the release job goes red.
- The **Developer ID certificate** is valid for five years.
- Rotate the App Store Connect key by creating a new one and updating the three
  notary secrets. Old keys can be revoked without touching the certificate.
