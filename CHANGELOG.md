# Changelog

All notable changes to GetMoreDone are recorded here.

This project follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
conventions and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **The timer now rewards finishing a thing, not running out of time.** Give an
  action a **Deliverable** — the crisp "done = ..." for it, a checkable artifact
  rather than a time-box. "Draft section 2's opening paragraph", not "work on
  the report for 25 minutes". The field is on the item editor, and the timer
  asks for one when you start a session on an action that belongs to a Project.

- **A "Done — deliverable complete" button on the timer**, available the whole
  time a session is running rather than only when the clock stops. Pressing it
  is what completes the work, so the reward attaches to what you made instead
  of to how long you sat there.

- **A savor step after a completed deliverable.** It shows you what you set out
  to do, says it is done, and asks you to look at it for five seconds. Early on
  in a project it appears every time; after fifteen completed deliverables it
  drops to roughly two in five, because a signal that arrives every single time
  stops carrying information. There is no "good job" in it anywhere — the words
  point at the artifact and at the effort, which is the whole idea.

- **An occasional celebration** — confetti, balloons or a chime — on about one
  completion in five, at random, in every phase. It is never guaranteed and
  never replaces the savor step; the moment a surprise becomes predictable it
  is just a cue.

### Changed

- **The timer window is now three clear areas.** The **timer** (deliverable, clock,
  and ▶ Start / ⏸ Pause / ⏹ Stop laid out like a recorder), the **music** (play, pause,
  and the track name — which used to be appended to the timer's own status line), and
  the **session actions**.

- **The deliverable is on the timer window.** It was typed into a dialog at the start and
  then never shown again — the one thing the reward depends on was the one thing you
  could not see. It now sits at the top with an **Edit** button. If an item has no
  deliverable, starting the timer asks for one; if it has one already, you are not asked
  to retype it.

- **Music no longer starts by itself.** Starting the timer used to start the music,
  which decided for you that this was a session with music in it. Only the Play button
  starts it now.

- **Finished and Continue are gone, and what replaced them says what it does.** Both of
  them quietly completed the action item and closed the window, which looked from the
  outside like nothing had happened — the window vanished and the task left Today. A
  session is now a record of work *on* a task, and it ends one of three ways:
  **Save & Close** (records the session and the time, task stays open), **Cancel**
  (returns without a note — your time and your typed notes are still kept), and
  **Complete & Carry Forward →** (completes today's item and opens tomorrow's copy).
  Two of them close a task — Done, and Complete & Carry Forward — but **only "Done —
  deliverable complete" counts one towards a project's reward phase.**

- **The end of a break no longer ends the session.** It used to stop the timer
  and offer Finished/Continue, which quietly made the timer ringing the thing
  that decided your work was over. Now it asks: **Pause (rest)** or **Continue
  focus**, and neither completes anything. Stop still works exactly as before,
  and Finished/Continue still appear after you press it.

  Two consequences worth knowing. **Music now keeps playing through the end of a
  break** — it used to stop, because the break ending stopped the whole timer.
  That matches how Pause has always behaved (music is yours to control from the
  music buttons). And Finished/Continue are one click further away at the ring:
  press Stop first, or use **Done** if the deliverable is finished.

## [0.3.0] - 2026-08-21

### Changed

- **The app is now called daVIPA.** Same app, same data, new name — with the tagline
  *Vision · Planning · Action*. The window title, the sidebar and the app icon all
  follow it, and the downloads are now `daVIPA-mac.zip` and `daVIPA-win64.zip`.

  **Your existing items and settings are untouched and stay exactly where they are.**
  The folder they live in still reads `GetMoreDone` — on purpose and permanently.
  Renaming it would leave the app looking for your database in a place it had never
  written one, and everything would appear to be gone. The name on the outside
  changed; where your data lives did not.

### Added

- **A daVIPA colour theme**, selectable in Settings alongside the existing nine. It is
  built from the palette measured off the new app icon: a deep indigo ground, indigo
  and violet for surfaces and buttons, and crimson kept for things that are a signal
  rather than a surface — a ticked checkbox, a switch that is on. Every text-and-background
  pairing in it was checked for legibility; the weakest is comfortably past the accessibility
  standard and most are far past it.
- **The Windows app finally has its own icon.** Every Windows build until now shipped the
  generic one that PyInstaller supplies by default.

### Fixed

- **Choosing a theme now gives you that theme.** Selecting one that had been added
  recently silently reverted to Apple Grey on the next start, because the list of valid
  themes existed in two places and only one of them had been updated. There is now one
  list.
- **The main window's background now matches the theme you chose.** It had been painted
  in the theme from the *previous* launch — the window is created before the theme is
  applied, so it was always one behind. This affected every theme, and showed as a window
  background that did not match its own sidebar.

### Added

- **File an Action Item under a Project from the item editor.** A new **Set Project**
  button beside Set Wk Tactic opens a project picker that also creates a Project inline
  (**+ New Project**), so a new task and the project it belongs to can be created from one
  screen. **Clear Project** unfiles the item. Filing stamps the project's Annual Plan Element
  onto the item — the same rule as dragging onto a project in the Scheduler — and the link is
  only written when the selection actually changes, so an ordinary Save can never clear it.
- **An Action Plan block in the top left of the item editor**, showing the item's Project and
  Weekly Tactic together. The Weekly Tactic and Orig. Week fields moved here from the
  Organization tab, which now holds Group and Category only.
- **A follow-up inherits the original's Project**, the way it already inherited the weekly
  lineage. Previously a follow-up of a project task landed unfiled. It inherits exactly one
  project, since an Action Item belongs to exactly one — a follow-up of one of the older
  multi-filed rows lands on the first of them, and the drop is logged.

- **A Weekly Tactic link of its own.** `action_items.weekly_tactic_id` replaces the
  overloaded use of `parent_id`, which previously served both ordinary subtask nesting
  and the week bucket at the same time — so attaching a tactic silently destroyed a
  hierarchy, and setting a parent silently destroyed the tactic link. An item can now be
  both a subtask and week-filed. The migration moves existing week links across and
  leaves daily nesting untouched, reporting both counts.
- **One owner of week identity and week numbering** (`week_calendar.py`). Week numbers
  now carry their year: 2026-12-28 and 2027-01-01 are both ISO week 53, and a bare `53`
  cannot say which. A new **First week of year** rule (`iso`, `jan1`, `first_full`)
  defaults to `iso`, which is how every existing database was numbered.
- **Project start and end dates** on Project Boards. Informational only — never
  validated and never derived from the items on the board, because a project may span
  any timeframe.
- **`weekly_tactic_start_date`** on Action Items, recording the week an item was
  originally meant to start. Existing items are left blank; nothing is backfilled.
- **Changing an Action Item's start date re-files it into the right Weekly Tactic**,
  creating any missing Quarter, Month and Week records along the way — including across
  a year boundary. The item's dates move by whole weeks so a Thursday task stays on a
  Thursday, and an item never spans two weeks.
- **Completing an item re-files it to the week you completed it in**, while
  `weekly_tactic_start_date` goes on holding the week it was originally meant to start,
  so a push-out stays visible. Re-opening does not undo that.
- **A new year is built from your existing plan structure, not invented.** The vision
  element, segment and key field carry across; the editorial text — vision statement, key
  priorities, theme, objective — is left blank for you to write, and those rows are
  flagged so the app can tell a stub from something you wrote. When a save creates them,
  it says so.
- **A first-week-of-year setting** under Settings, and project start/end dates on Project
  Boards.

### Changed

- **The release workflow publishes once, after both builds succeed.** `build-windows`
  and `build-macos` each called `softprops/action-gh-release`, so a tagged run made two
  release calls. Whichever finished first created the public Release; if the other then
  failed, that Release stayed up carrying one platform's assets, because a failed job does
  not un-publish a Release another job already created. A single `publish` job now runs
  `needs: [build-windows, build-macos]`, downloads both artifacts and makes one release
  call, so a half-succeeded run publishes nothing. The release notes are generated once
  rather than once per platform.
- **Test-only dependencies moved to `requirements-dev.txt`.** `requirements.txt` is now the
  runtime set — the list that ships inside the binary. `requirements-dev.txt` includes it and
  adds pytest, so one install still gives a contributor everything. Two places had been
  carrying a hand-maintained copy of which packages were test-only: a `TEST_ONLY_PACKAGES`
  set in `tests/test_release_licensing.py` and a `grep -v '^pytest'` in `start.sh`. Both are
  gone; a third test-only package would have slipped past both and been treated as a shipped
  dependency.
- **`GoogleCalendarManager` reads its arguments before touching the filesystem.** Constructing
  it with explicit `credentials_file` and `token_file` created `~/.getmoredone` anyway and then
  never used it. The default location is now resolved by `paths.google_auth_dir()`, shared by
  the constructor and the two static checks that previously each hardcoded the path — changing
  only the constructor would have left `has_credentials()` looking somewhere else. The location is
  unchanged — always `~/.getmoredone`, which the Gmail importer, the launchd import job and the
  diagnostic scripts all share. The directory is created where the token is written, which also
  fixes an explicit `token_file` in a non-existent directory failing behind a warning and
  re-authenticating every run. `tools/diagnose_google_auth.py` now shares the same resolver instead
  of hardcoding the path, and the calendar dialog's "credentials not found" message names the path
  it actually checked rather than a hardcoded one.

- **An Action Item belongs to exactly one Project, on every screen.** The Projects
  screen's "Link Action Items" dialog used to *add* a project to an item while the
  Scheduler and the item editor *moved* it, so the same item could accumulate boards
  depending on which screen you used. Linking now moves the item everywhere. Because
  that means links get deleted, all three screens ask the same question before
  unfiling anything — naming the project you are filing under, how many links go, and
  what happens to the item's Annual Plan Element — and nothing is removed without an
  answer. Filing under a project replaces that plan element with the project's (or
  clears it, if the project has none); clearing the project clears it. All three were
  silent before.
- **Removing an item from a project removes only the project link.** Its Annual
  Plan Element stays, because you may be on the way to filing it under a different
  project and losing your place in the plan in between helps nobody. The Projects
  screen's **Unlink** button always behaved this way; **Clear Project** and dragging
  onto **No Project** used to clear the plan element as well, so the same intention
  had two outcomes depending on which control you reached for. Filing an item under
  a project still stamps that project's plan element onto it.
- **An Annual Plan Element can only be deleted when nothing is on it.** Deleting one
  used to detach every Action Item pointing at it — silently for an ordinary item,
  and leaving a Weekly Tactic in a state the app refuses to save. It now says which
  items are in the way, and deletes nothing until you have moved them.
- **A project decides its items' Annual Plan Element, including when it has none.**
  Moving an item to a project with no plan element used to leave the *previous*
  project's on the item, so it went on claiming a place in the plan belonging to a
  project it was no longer on — visible as the wrong Segment and Category in every
  list view.
- **Items already filed under several projects are reported, not quietly cleaned up.**
  The Projects screen names them above the board list, with how many projects each
  sits on, and the count appears at start-up. Nothing is deleted for you: each one is
  resolved the next time you choose a project for it.
- **Creating an Action Item from a Weekly Tactic uses the title you typed.** It used
  to prepend the tactic's context (`PW|LS|Blog - W34 - your title`) for tactics with
  an older-style title. The item's place in the plan comes from its Annual Plan
  Element and its parent tactic, not from the title text.
- **The Scheduler's "Unlinked (No Project)" box no longer loads every unlinked item
  in the database to show a count**, and says "showing N of M" if there are more than
  it fetched.

### Removed

- **Push to Next Day (the Reschedule dialog) and complete-and-create.** Neither had
  been reachable from anywhere in the app; both were kept alive only by their own
  tests. Rescheduling is unchanged — drag an item in the Scheduler, or edit its dates.

### Fixed

- **The test suite no longer flashes a window onto the screen on Linux.** Test
  windows are made fully transparent so they can be laid out and measured without
  being seen, but on Linux the transparency was lost whenever a window was
  re-shown — so a window appeared and took focus. It is now re-applied at that
  moment. This affected continuous integration, not the released app, and it is
  why the build had been failing since 20 August.

- **Renaming a life segment to a name another one already has, differing only in
  capitalisation, is now refused.** Creating one that way was already refused;
  renaming was not, so the same state could be reached through the segment editor.
  It matters because the two cannot be told apart afterwards: every link that
  resolves a segment by name gives up on both of them, permanently, and the startup
  check reports them as needing attention at every launch. The editor now explains
  the refusal and keeps the dialog open with what you typed, rather than saving or
  failing silently. A segment can still keep its own name, change its capitalisation,
  or take any name not already taken — and if your database already contains such a
  pair from before this check existed, both segments remain fully editable: you can
  still change their colour, description, order, retire one, or rename one of them to
  something free — which is the way out of the situation. What is refused is any save
  that would pull a *further* segment into the same trap.
- **A failed segment rename no longer leaves half of itself behind.** The name and the
  linked Vision Segment were written separately, so if the second write failed the
  first had already happened and the next unrelated save committed it — leaving one
  segment recorded under two different names. Both now succeed together or neither
  does, and a name clash the check could not foresee is explained in words rather than
  as a database error.

- **A plan element's Annual Initiative is found by its id and nothing else.** The
  lookup resolved by id — correct — and then also required the initiative's annual
  plan to carry the same year as the plan element. A plan element id identifies one
  plan element and a plan element carries one year, so that extra condition could
  never find a *different* initiative; it could only hide the right one. The year is
  stored separately on the plan, the plan element and the initiative, so any path
  that updates one without the others makes them disagree — and when they disagreed
  the initiative went invisible and the next assignment built a duplicate, which is
  the very bug this lookup was rewritten to prevent.

  Where the initiative is matched by its **title** instead — the one-time repair and
  the upgrade step, both used only for rows that have no id yet — the plan's year is
  now a tie-break rather than a requirement. An initiative whose plan agrees about the
  year is preferred; the wider set is only consulted when none does. Dropping the
  requirement outright would have let a same-titled initiative on a stale plan take
  the link, or made the repair see two candidates, decline to choose, and leave the
  caller to create a third.
- **A database upgraded from the oldest Vision Segment layout keeps the life segment
  each row was already attached to.** The upgrade knew the segment's id — the old row
  carried it — but wrote only the name and let a later step look the id up again from
  that name. If two life segments' names differed only in capitalisation, the lookup
  could not choose between them, so the row was left unlinked and reported as needing
  a human decision that the data had already made. The upgrade now keeps the id it
  was given, and still leaves a row unlinked when it genuinely points at a segment
  that no longer exists — or when two old rows collapse into one and disagree about
  which life segment they meant, which is reported for a person to settle rather than
  decided in favour of whichever row happened to sort first.

- **Renaming anything no longer breaks a link.** A segment, sub-segment, category,
  vision element key field, Project or Weekly Tactic can be renamed and every link
  survives. Renaming a segment used to make an ordinary date change on a filed Action
  Item **raise** — the item silently did not move — because the re-filing cascade
  resolved the segment by name, and `rename_vision_segment` updated only one of the
  two tables holding that name. Renaming a key field made the next assignment build a
  **second** Annual Initiative and Quarter Initiative for the same plan element,
  which accumulated silently.

  Four nullable id columns now hold those links (`annual_plan_elements` and
  `annual_vision_elements` gain `segment_description_id`, `vision_segments` gains one
  too, and `annual_initiatives` gains `annual_plan_element_id`). A migration backfills
  them from the current name once, at first launch. **It never guesses**: a row whose
  name matches nothing — or matches two segments differing only by case — is left
  unlinked and named in the report, because a wrong link is invisible where a missing
  one is not.

  Names are still shown, and a rename now refreshes every stored copy, including the
  Annual Initiative's derived title — unless you have edited that title yourself, in
  which case it is left alone.

  A user who has already renamed gets a report at startup naming every plan element
  with no resolvable segment, every orphaned initiative and every duplicate pair.
  Nothing ambiguous is repaired automatically: which of two duplicates holds work
  worth keeping is not a decision the app should make.

- **The test suite no longer has to steal keyboard focus.** Three tests build a real
  on-screen window to read geometry. `GETMOREDONE_NO_MAPPED_WINDOWS=1` now skips them, with a
  skip reason naming the variable so a suppressed run cannot be mistaken for a passing one.
  It is opt-in and `tests/test_ci_contract.py` asserts no workflow ever sets it.

- **A Weekly Tactic can no longer be filed under a Project**, which was never
  intended — the item editor already refused, the Projects screen's "Link Action
  Items" dialog did not. Filing one under a project with no Annual Plan Element
  stripped the tactic's own, leaving a row the app then refused to save.
- **The item editor no longer says "Saved" when it saved nothing.** If the item was
  deleted elsewhere while its editor was open — from a list, or a second editor
  window — Save reported success, closed the window and discarded every edit. It now
  says the item no longer exists and stays open.
- **A search in "Link Action Items" no longer leaves items selected that you cannot
  see.** Typing in the search box rebuilt the list with every checkbox cleared while
  the selection was kept behind the scenes, so "Link Selected" could re-file items
  that had scrolled out of the list entirely.
- **The item editor's Save and its Create Note both build a new item the same way.**
  They assembled the fields separately and had already disagreed twice about what a
  new item gets, so which button you pressed could change what was stored — most
  visibly the Annual Plan Element when a project and a weekly tactic were chosen
  together.
- **A Weekly Tactic left mid-week is now repaired instead of surviving forever.**
  When a tactic could not be moved onto its week start — because a duplicate
  already held that date — it was left where it was and never merged, because
  the dedupe grouped tactics by their raw start date. It now groups by the week
  a tactic belongs to, merges the duplicate, and moves the survivor onto the
  week start. The migration log says how many were moved.
- **Startup can no longer be blocked by an unreadable date.** A week item whose
  start date is not a date used to be able to make the unique-index step raise
  out of schema initialisation, and since nothing commits before that point,
  every later launch met the same state. Such rows are now reported and left
  alone rather than merged, and the index step declines with a reason instead of
  crashing.
- **The test suite no longer touches your real data.** One test opened the live
  database and ran migrations against it; several rewrote your real
  `settings.json`. Both are isolated now, with a session-level guard that fails
  the run if the real settings file is written. No data was lost.

- **The Who field works again.** Typing in Who did nothing — no contact dropdown, no
  error — because the autocomplete read three attributes (`suggestions_hide_job`,
  `contact_suggestions_frame`, `selected_contact_id`) that nothing ever initialised, so
  the first keystroke raised inside a Tk callback, where the traceback goes to stderr and
  the app carries on. The same hole could make saving a brand-new item fail with only a
  generic error message. The state now lives on the mixin that reads it.

- **Duplicate Weekly Tactics are merged**, one per Annual Plan Element per week, and a
  unique index keeps it that way. The surviving tactic keeps whichever row held more
  children, every reference is moved onto it before the other is deleted, and its title
  is re-derived — the real duplicate in the wild was titled `W8` for a week that is
  ISO week 9, so keeping the older row alone would have kept a wrong number.
- **A Weekly Tactic that cannot move now says so.** Only one tactic can occupy a week
  for a plan element, and a move onto an occupied week used to be reported as a clean
  save while nothing happened. The Today, Upcoming, All Items and Reschedule surfaces
  now tell you, and the reschedule history records where the item actually landed
  rather than where it was asked to go.
- **The weekly-items drag path reports what happened.** Dragging a plan element onto a
  week that already had a tactic produced no refresh, no message and no sign of
  rejection; the same drag with no week selected did nothing at all.



- **Two release-workflow steps could have succeeded while publishing nothing.**
  `actions/upload-artifact` defaults `if-no-files-found` to `warn`, and
  `softprops/action-gh-release` defaults `fail_on_unmatched_files` to `false` — so a
  glob matching nothing would have produced a green run with a missing artifact, or a
  public Release with correct notes and zero downloadable assets. Both now fail. The
  two are not equally strict — `if-no-files-found` fires only when a step's whole path
  set matches nothing, while `fail_on_unmatched_files` is per-pattern.

### Added

- **The release workflow can now sign and notarise the macOS build**, which removes the
  Gatekeeper prompt entirely. It is off until six Apple credentials are configured as
  repository secrets, and skips itself cleanly when they are absent — see
  `docs/CODE_SIGNING.md`. With credentials present, any signing failure fails the build
  rather than quietly publishing an unsigned one.

### Changed

- **Changing the project on an item that sits on several boards now asks first.**
  Filing is exclusive, so it removes the others; that used to be visible only as
  the "(+N more)" marker quietly disappearing. The project picker also says that
  filing an item files it under the project's Annual Plan Element.
- **The Context box is gone from the Item Editor, and the Context column from Today,
  Upcoming, All Items, Completed and Hierarchical.** Context was never a field of its
  own — only the front half of the Title string, rejoined on save — and it only read
  back out of titles whose prefix ended in a week marker (`W8`), so most items showed
  it empty while their title still carried the prefix. Title now holds and saves the
  whole title verbatim; no stored title changes. The Scheduler still colours rows by
  segment and subsegment, which is derived from the same title prefix.

- **The item editor's Duplicate button is gone; Add Follow-up is the one copy path.** A
  follow-up is a copy that also keeps the link back to the original, and it now saves the
  edits on screen before copying — a guard the Duplicate path had and the follow-up path
  did not, so a follow-up used to be built from the stored row while on-screen edits were
  left behind.
- **Item editor buttons re-paired**: Cancel sits beside Timer, Add Follow-up beside Add
  Subtasks (renamed from "Add Sub-tasks"), Set Parent beside Show Related, and Set Wk Tactic
  beside Set Project.
- Gatekeeper instructions now lead with the macOS 15 (Sequoia) System Settings route.
  Apple removed the Control-click override in macOS 15, so the old advice was wrong for
  every current Mac.
- All GitHub Actions moved off the deprecated Node 20 runtime: `actions/checkout` v7,
  `actions/setup-python` v7, `actions/upload-artifact` v7,
  `softprops/action-gh-release` v3.

## [0.2.0] - 2026-08-18

The first release whose binaries actually run.

Versions v0.1.0, v0.1.2 and v0.1.05 (February 2026) shipped binaries that
crashed on launch before showing a window — see "Fixed" below. This release
skips to 0.2.0 rather than reusing a version number that already has a
published release.

### Added

- **Downloadable builds for macOS and Windows**, published on the Releases page
  with a SHA-256 checksum beside each archive.
- **`LICENSE`** — proprietary and source-available: free to use, copyright
  retained, redistribution and commercial use reserved.
- **`THIRD_PARTY_NOTICES.md`** — every runtime dependency with its licence, plus
  the pygame LGPL notice and relink statement. A verbatim copy of the LGPL ships
  with the application.
- **`INSTALL.md`** — download, the macOS Gatekeeper step, run-from-source,
  checksum verification, optional Google and music setup, where data is stored,
  and how to uninstall.
- **`run.py --selftest`** — a headless startup check (resources, themes, theme
  application, database) that exits non-zero when a build is broken. CI runs it
  against the packaged binary on both platforms, so a bundle that cannot start
  never becomes a release.
- **Test CI** (`.github/workflows/tests.yml`) — the full suite on Python 3.11,
  3.12 and 3.13, headless under xvfb so the GUI tests genuinely run.

### Fixed

- **Every previously built binary crashed on launch.** `GetMoreDone.spec`
  bundled only `assets/`, while the app loads its colour theme from
  `themes/`, so packaged builds died with `FileNotFoundError` before showing a
  window. Themes are now bundled, and a broken bundle degrades to the built-in
  theme instead of crashing.
- **Windows builds were never verified.** The release workflow now runs the
  packaged executable's selftest on a real Windows runner before publishing.
- Two test files passed only when collected after another file that happened to
  set up `sys.path` first; run alone they errored.
- `build_mac.sh` fell back to the system Python when no virtualenv was present,
  then invoked `./venv/bin/pyinstaller` regardless — the fallback could never
  have worked.
- An unknown or corrupt theme name in `settings.json` could raise during
  startup, before any window existed to report it.

### Changed

- **The download is 68 MB instead of 160 MB.** PyInstaller was bundling a
  Google API discovery document for every Google API in existence — 569 files,
  around 93 MB — while the app uses exactly two of them.
- **The date picker no longer uses `tkcalendar`**, which is GPLv3 and cannot
  ship inside a binary under this licence. It is reimplemented on Python's
  standard `calendar` module, keeps the same interface, honours the
  first-day-of-week setting, and now follows the active theme instead of
  hard-coded colours.
- The Google auth diagnostic moved from `test_auth.py` at the repository root to
  `tools/diagnose_google_auth.py`. It was never a test.
- Root-level test files moved under `tests/`.

### Known limitations

- **Builds are unsigned.** macOS requires a one-time quarantine step, documented
  in `INSTALL.md`; Windows may show a SmartScreen warning.
- No Linux binary. Linux runs from source.
- No auto-update. New versions are downloaded manually.
- No bundled music. Point Settings at a folder of your own.

[Unreleased]: https://github.com/dbgnvan2/daVIPA/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/dbgnvan2/daVIPA/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/dbgnvan2/daVIPA/releases/tag/v0.2.0
