# Handoff — Downloadable release, Phase 6 (slimming, hygiene, release)

**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_downloadable_release.md` — R-M7, plus a size reduction outside the spec
**Agent:** Code

## Summary

Excluded everything an end user does not need from the download, tidied the
repository root, and published **v0.2.0** — the first release whose binaries
actually run.

## The download is 68 MB instead of 160 MB

PyInstaller was collecting a Google API discovery document for **every Google
API in existence**: 569 files, roughly 93 MB, in an app that builds exactly two
services (`calendar v3`, `gmail v1`). Also dropped:

- `themes/base_dark_blue.json` — input to `tools/generate_ctk_themes.py`, absent
  from `theme.THEME_NAMES`, so no user could ever select it
- `licenses/README.md` — provenance note for a maintainer
- `.DS_Store` / `Thumbs.db` / `desktop.ini` — build-machine debris

The filter lives in `tools/packaging_filters.py`, not inline in the spec: a spec
file cannot be imported or unit-tested, and dropping the wrong file breaks a
feature **in the packaged app only**, where no source-run test would see it.
The keep list is derived from the `build()` calls in the source, so adding a
third Google service fails a test rather than silently losing that service.

`licenses/pygame-LGPL-2.1.txt` is explicitly never droppable — shipping it is a
licence requirement, not a size decision, and a test says so.

## Repo hygiene (R-M7)

Root went from 36 tracked files to 21. Seven auth diagnostics to
`tools/diagnostics/`, three utilities to `tools/`, six troubleshooting and
agent-facing docs to `docs/`. References were rewritten **relative to each
referencing file**, so links between docs that are now siblings stayed bare.

The Phase 3 handoff note was deliberately reverted after the sweep touched it:
it records where those files were *at the time*, and rewriting history turned
it into nonsense (`../CLEAR_BROWSER_CACHE.md`).

`.gitignore copy` deleted — untracked, a strict subset of `.gitignore`.

**R-M7.B found a real defect.** The new test asks `git check-ignore` whether
anything the spec bundles would be excluded, and immediately flagged
`assets/.DS_Store`: gitignored, present only on this Mac, and therefore baked
into local builds but absent from CI ones. Now excluded from the bundle.

## v0.2.0, not v0.1.0

`v0.1.0`, `v0.1.2` and `v0.1.05` already existed as tags **and published GitHub
Releases** from February 2026, with `v0.1.05` marked Latest. Those are the
builds that crash on launch. Reusing `v0.1.0` would have meant force-moving a
published tag and overwriting a published release, so this went to 0.2.0 —
cleanly above all three however `0.1.05` is parsed. The CHANGELOG says why.

## Verification of the published release

| Check | Result |
|---|---|
| Full suite | **652 passed, 2 skipped — exit 0** |
| CI (`tests.yml`) | **653 passed, 1 skipped** on Python 3.11, 3.12 and 3.13 |
| Release run `32194895332` | Both jobs green |
| **R-M4.C executed for the first time** | The "Extract release notes" step ran (✓, not skipped) — it is tag-conditional and every prior dry-run was tagless |
| Release body | Generated from `CHANGELOG.md`, renders correctly on the release page |
| Assets | `GetMoreDone-mac.zip` (33.5 MB), `GetMoreDone-win64.zip` (38.8 MB), plus both `.sha256` |
| **Downloaded from the public release page** | Both checksums verify with `shasum -c` |
| **Released app selftest** | `4/4 checks passed, exit 0` |
| **Released app GUI** | Launches, runs 10s, clean log |
| Legal files inside the released app | `Contents/Resources/{LICENSE, THIRD_PARTY_NOTICES.md, licenses/pygame-LGPL-2.1.txt}` |
| `v0.2.0` is Latest | Yes |

## Still open

1. **The licence wording** — drafted by an AI assistant from a template, not
   reviewed by a lawyer. `LICENSE` carries a warning header and a test protects
   it. Needs review before the first paid sale.
2. **Read `INSTALL.md` once as a first-time user.**
3. **Gatekeeper on a Mac that has never run GetMoreDone.** Verified here only
   with `xattr` already applied, on a machine that trusts its own builds.
4. **The three February releases still offer broken binaries.** `v0.1.0`,
   `v0.1.2` and `v0.1.05` remain published and downloadable. Anyone landing on
   them gets an app that dies before showing a window. Deleting or annotating a
   published release is an outward-facing act, so it was left to the copyright
   holder to decide.
5. **`learning-qa` was not run.** The plan scheduled it for this phase; this
   session is configured not to invoke agents unless asked. Worth running over
   the whole diff before the next release.
6. **Node 20 deprecation** on `checkout@v4`, `setup-python@v5`,
   `upload-artifact@v4` and `action-gh-release@v2` across all three workflows.
   Flagged since Phase 3, still unfixed; it will become a failure.

## Adjacent issues found, not fixed

- `tests/test_vps_segments.py` has two tests that `return` a bool instead of
  asserting — they can pass while asserting nothing.
- `requirements.txt` mixes test-only and runtime dependencies, so
  `test_release_licensing.py` carries a hardcoded `TEST_ONLY_PACKAGES` set.
- `GoogleCalendarManager.__init__` creates `~/.getmoredone` before reading its
  own arguments; tests redirect `Path.home()` to work around it.
- Both archives still carry `*.dist-info/licenses/` folders from PyInstaller
  collecting dependency metadata, which `THIRD_PARTY_NOTICES.md` does not
  enumerate.
