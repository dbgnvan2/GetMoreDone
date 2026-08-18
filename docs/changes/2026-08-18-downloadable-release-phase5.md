# Handoff — Downloadable release, Phase 5 (licensing, first run, docs)

**Date:** 2026-08-18
**Spec:** `docs/spec_2026-08-18_downloadable_release.md` — R-M2.A/C/D, R-M4.C/D, R-M5, R-M6
**Plan:** `docs/implementation_plan_2026-08-18_downloadable_release.md` — Phase 5
**Agent:** Code

## Summary

Closes the legal blocker (F4) and the release documentation, and completes the
two criteria Phase 4 had to leave open because their input files did not exist.

The plan called for a pause after drafting `LICENSE` for review. The copyright
holder waived it and asked to proceed, so the draft is in the tree — carrying a
warning header saying it has not been reviewed by a lawyer, with a test that
fails if that header is removed. **The licence wording still needs a real
review before the first paid sale.**

## Files added

| File | Purpose |
|---|---|
| `LICENSE` | Proprietary, source-available, per decision D1 (R-M2.A) |
| `THIRD_PARTY_NOTICES.md` | Every runtime dependency + pygame LGPL notice (R-M2.C) |
| `licenses/pygame-LGPL-2.1.txt` | Verbatim LGPL text, vendored from pygame's own wheel |
| `licenses/README.md` | Why the folder exists and where its contents came from |
| `INSTALL.md` | Download, Gatekeeper, source, checksums, Google, music, data, uninstall (R-M6.A, R-M5.D) |
| `CHANGELOG.md` | v0.1.0 entry incl. known limitations (R-M6.D) |
| `tools/extract_release_notes.py` | CHANGELOG → release body (R-M4.C) |
| `tests/test_first_run.py` | 16 tests (R-M5) |
| `tests/test_release_docs.py` | 24 tests (R-M5.D, R-M6) |
| `tests/test_release_notes.py` | 18 tests (R-M4.C) |

Modified: `GetMoreDone.spec` (bundles the licence files), `README.md`
(Download-first, links licence/install/notices), `docs/STANDALONE_BUILD.md`
(stale claim removed, `--onefile` warning added), `.github/workflows/build-release.yml`,
`tests/test_ci_contract.py`, `tests/test_release_licensing.py`.

## Two false claims caught by checking artifacts, not documents

**1. The LGPL text was not actually shipping.** The notices draft said pygame's
licence text "ships inside the application folder". Grepping the real archives
from run `32191656386` showed no licence file anywhere in either one. The LGPL
requires the licence to accompany the distribution, so the fix was to make the
claim true — `licenses/pygame-LGPL-2.1.txt` is now vendored verbatim from
pygame's own wheel (`pygame/docs/generated/LGPL.txt`, verified byte-identical)
and bundled by the spec.

**2. The macOS bundle nested the folder.** Run `32193099401` produced
`Contents/Resources/licenses/licenses/pygame-LGPL-2.1.txt`. The spec already
bundles `licenses/` into `Contents/Resources`, and `cp -R licenses dest/licenses`
copies *into* `dest` when it exists. macOS now relies on the spec alone; Windows
keeps its root-level copies, whose target (`dist/GetMoreDone/`) does not collide
with the spec's (`_internal/`), which is why Windows never nested.

Neither would have been found by reading the workflow. Both came from unzipping
what CI actually produced.

## Test / verification status

| Check | Result |
|---|---|
| Full suite | **614 passed, 2 skipped — exit 0** (+76 new) |
| Local rebuild with the new spec | Licence files land in the bundle; packaged selftest **4/4, exit 0** |
| Dry-run `32193479111` | Both jobs green |
| macOS archive layout | `Contents/Resources/{LICENSE, THIRD_PARTY_NOTICES.md, licenses/pygame-LGPL-2.1.txt}`; **0** nested `licenses/licenses/` |
| Windows archive layout | `LICENSE`, `THIRD_PARTY_NOTICES.md`, `licenses/pygame-LGPL-2.1.txt` beside `GetMoreDone.exe` |
| Paths in the notices match the artifacts | Verified against both archives, per platform |
| First-run tests | Pass without Google credentials, without music, on an empty DB and on a populated one (P8) |

## Criteria

| ID | Status | Notes |
|---|---|---|
| R-M2.A | done | `LICENSE`, linked from README; 5 tests |
| R-M2.C | done | Notices cover every runtime dep; LGPL text bundled and verified verbatim |
| R-M2.D | done | No audio tracked in git; spec bundles no audio folder |
| R-M4.C | **partial** | Script + wiring done and tested; **the workflow step has never executed** — it is tag-conditional and no tag has been pushed |
| R-M4.D | done | Verified inside both real archives |
| R-M5.A | done | Google features degrade with a typed error naming the missing file; `has_credentials`/`is_available` return real booleans (P14) |
| R-M5.B | done | Covered here and in `test_packaging_resources.py` |
| R-M5.C | done | Empty DB, populated DB (dirty-state), and idempotence across runs |
| R-M5.D | done | Exact `xattr` command in `INSTALL.md` **and** `README.md` |
| R-M6.A–D | done | 24 tests, incl. link-resolution checks on both docs |

## Still needing a human

These cannot be closed by code, and are not closed:

1. **The licence wording.** Drafted from a template by an AI assistant. Not
   legal advice. Needs a lawyer before the first paid sale. The warning header
   in `LICENSE` should be removed only by someone who has had it reviewed —
   `test_rm2a_license_carries_the_unreviewed_draft_warning` will fail when it
   goes, which is the prompt to delete that test in the same commit.
2. **Read `INSTALL.md` once as a first-time user.** The tests assert that
   specific strings are present; they cannot tell whether the document is any
   good.
3. **Gatekeeper behaviour on a Mac that has never run GetMoreDone.** This
   machine trusts its own builds, so the documented quarantine step is unproven
   here. Confirm on the first real download.

## Follow-ups

- **R-M4.C needs a tagged run to be proven.** The extractor has 18 tests
  including one that invokes it exactly as CI does, but the workflow step itself
  is skipped without a tag. Tagging `v0.1.0` (Phase 6 step 28) is what exercises
  it — check the release body renders before announcing anything.
- Phase 6 remains: repo hygiene (R-M7), the `learning-qa` pass over the whole
  diff, `docs/spec_coverage.md`, then the tag.
- The Node 20 deprecation on `checkout@v4` / `setup-python@v5` /
  `upload-artifact@v4` is still flagged and unfixed across all three workflows.

## Adjacent issues found, not fixed

- Carried forward: `tests/test_vps_segments.py` has two tests that `return` a
  bool instead of asserting; `themes/base_dark_blue.json` ships in both archives
  but is absent from `theme.THEME_NAMES`; `requirements.txt` mixes test and
  runtime dependencies.
- `GoogleCalendarManager.__init__` calls `(Path.home() / ".getmoredone").mkdir()`
  before it looks at its own arguments, so merely constructing it creates a
  directory in the real home. Tests now redirect `Path.home()` to work around
  it; the constructor itself is unchanged.
- Both archives carry `_internal/*.dist-info/licenses/` folders from PyInstaller
  collecting dependency metadata. Harmless, and arguably useful, but it means
  the archives contain licence files that `THIRD_PARTY_NOTICES.md` does not
  enumerate.
