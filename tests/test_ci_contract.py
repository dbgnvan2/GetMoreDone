"""Contract tests for the GitHub Actions workflows.

Purpose: keep CI honest — it must run the real suite on a blank machine, decide
         by exit code, and never hold a check that cannot be run locally.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m3
Tests:   this file

Two global rules drive this file:

* **Never put a check only in the workflow.** Every assertion lives in the suite,
  where it can fail *before* a push; the workflow only invokes that suite. A
  check written as inline YAML cannot be run locally.
* **Decide success from the exit code** (P24). `2 failed, 2181 passed` contains
  the word "passed"; any step that greps for it reports green on a red run.

Workflows are inspected as text rather than parsed YAML on purpose: PyYAML is
not a dependency of this project, and adding one so the tests can read CI config
would be a poor trade. Every assertion here is a presence/absence check that
text handles correctly.

R-M4.C (release body from CHANGELOG.md) and R-M4.D (LICENSE and
THIRD_PARTY_NOTICES.md inside every archive) were held back during Phase 4
because their input files did not exist yet — a permanently red suite is worse
than no CI. Phase 5 created them, so they are covered below.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = REPO_ROOT / ".github/workflows"
TESTS_WORKFLOW = WORKFLOW_DIR / "tests.yml"

# Tokens that appear in a tool's output on success *and* alongside failures.
PASS_TOKENS = ("passed", "ok", "success", "succeeded")


def _workflows() -> list[Path]:
    return sorted(WORKFLOW_DIR.glob("*.yml")) + sorted(WORKFLOW_DIR.glob("*.yaml"))


def _run_step_lines(text: str) -> list[str]:
    """Every line belonging to a `run:` block in a workflow.

    Coarse but sufficient: a run block is `run:` followed by an indented body,
    and the checks below only ask whether certain shell constructs appear.
    """
    lines = text.splitlines()
    collected: list[str] = []
    in_run = False
    run_indent = 0

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())

        if in_run:
            if indent > run_indent:
                collected.append(stripped)
                continue
            in_run = False

        if re.match(r"^-?\s*run:\s*\|?>?-?\s*$", stripped):
            in_run, run_indent = True, indent
        elif stripped.startswith("run:"):
            collected.append(stripped[len("run:"):].strip())
    return collected


def _code_only(text: str) -> str:
    """Drop `#` comments so a check judges what a file *does*, not what it says.

    These workflows and scripts carry comments naming the very constructs the
    tests prohibit (`$LASTEXITCODE`, `--onefile`) in order to explain *why* they
    are prohibited. Matching on the explanation would pressure the next person
    into deleting the reasoning to get back to green.
    """
    out = []
    for line in text.splitlines():
        if line.strip().startswith("#"):
            continue
        out.append(line.split("#", 1)[0])
    return "\n".join(out)


# --------------------------------------------------------------------------
# R-M3.A — the workflow exists and runs the real suite on a blank machine
# --------------------------------------------------------------------------

def test_rm3a_tests_workflow_exists():
    assert TESTS_WORKFLOW.exists(), (
        "No .github/workflows/tests.yml. A repo with a test suite pushed to "
        "GitHub gets one — the blank machine is what catches what this Mac hides."
    )


def test_rm3a_tests_workflow_runs_on_ubuntu():
    assert "ubuntu-latest" in TESTS_WORKFLOW.read_text(encoding="utf-8")


def test_rm3a_tests_workflow_installs_from_the_real_dependency_file():
    """Installing an ad-hoc package list would defeat the point of the run.

    requirements-dev.txt is accepted because it starts with
    ``-r requirements.txt`` — asserted by
    ``tests/test_release_licensing.py::test_bi2_dev_requirements_pulls_in_the_runtime_set``,
    so the runtime set is still what CI installs.
    """
    text = TESTS_WORKFLOW.read_text(encoding="utf-8")
    installs = re.findall(r"-r\s+(requirements(?:-dev)?\.txt)", text)
    assert installs, (
        "tests.yml must install from requirements.txt or requirements-dev.txt, "
        "so a missing or wrong dependency declaration fails CI instead of "
        "passing on a warm machine."
    )
    # Judge the code, not the comments; and allow pip's own flags before -r,
    # so `pip install -q -r requirements.txt` is not read as a named package.
    # Searched anywhere in the line, and pip[0-9]*: anchoring on an optional
    # "python -m " prefix made the guard blind to `python3 -m pip install X`,
    # `pip3 install X` and `sudo pip install X` — three spellings it used to
    # catch. A silent miss here is exactly what it exists to prevent.
    for line in _run_step_lines(_code_only(text)):
        match = re.search(r"\bpip[0-9]*\s+install\b(.*)$", line.strip())
        if not match:
            continue
        args = match.group(1).split()
        if args == ["--upgrade", "pip"]:
            continue
        # Reuses the licensing module's allowlist rather than keeping a second,
        # shorter enumeration of the same concept beside it (P5).
        from tests.test_release_licensing import (
            REQUIREMENT_OPTIONS_THAT_DECLARE_NOTHING as VALUE_TAKING,
        )
        named = [
            a for i, a in enumerate(args)
            if not a.startswith("-")
            and (i == 0 or args[i - 1].split("=", 1)[0] not in VALUE_TAKING)
        ]
        assert not named, (
            f"tests.yml installs {named} by name: {line!r}. Every dependency "
            "must come from a requirements file, or CI stops being the "
            "blank-machine check."
        )


def test_rm3a_tests_workflow_invokes_pytest():
    assert re.search(r"\bpytest\b", TESTS_WORKFLOW.read_text(encoding="utf-8"))


def test_rm3a_matrix_covers_the_python_version_the_readme_claims():
    """README says 3.11+; CI must at least run the claimed minimum."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    claimed = re.search(r"Python (\d+)\.(\d+)\+", readme)
    assert claimed, "README no longer states a claimed minimum Python version"
    minimum = f"{claimed.group(1)}.{claimed.group(2)}"

    text = TESTS_WORKFLOW.read_text(encoding="utf-8")
    versions = re.findall(r"['\"](\d+\.\d+)['\"]", text)
    assert minimum in versions, (
        f"README claims Python {minimum}+ but tests.yml does not run {minimum}. "
        f"Versions found: {sorted(set(versions))}"
    )


def test_rm3a_tests_workflow_runs_on_push_and_pull_request():
    text = TESTS_WORKFLOW.read_text(encoding="utf-8")
    assert "push:" in text and "pull_request:" in text, (
        "tests.yml should run on both push and pull_request; a suite that only "
        "runs on one is a suite half the changes never meet."
    )


# --------------------------------------------------------------------------
# R-M3.B — GUI tests must run, not silently skip
# --------------------------------------------------------------------------

def _gui_test_files() -> list[Path]:
    """Test files that construct a real Tk root."""
    found = []
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if "ctk.CTk()" in text or "tk.Tk()" in text:
            found.append(path)
    return found


def test_rm3b_there_are_gui_tests_to_protect():
    """If this ever hits zero, the guard below is guarding nothing."""
    assert _gui_test_files(), "no test file constructs a Tk root any more"


def test_rm3b_workflow_provides_a_virtual_display():
    """Without xvfb the GUI tests skip themselves and CI is green on nothing."""
    text = TESTS_WORKFLOW.read_text(encoding="utf-8")
    assert "xvfb" in text.lower(), (
        f"{len(_gui_test_files())} test files construct a Tk root and skip when "
        "no display exists. tests.yml must provide one (xvfb), or CI reports "
        "green while never running them."
    )


def test_rm3b_ui_tests_are_not_skipped_headless():
    """On CI, a Tk root must actually be constructible.

    The GUI tests skip on any exception from ``ctk.CTk()``. That is right
    locally, but on CI a silent skip is indistinguishable from a pass. This
    turns it into a loud failure.
    """
    if not os.environ.get("CI"):
        pytest.skip("only meaningful on CI, where a display must be provided")

    import customtkinter as ctk

    root = ctk.CTk()
    try:
        assert root.winfo_exists()
    finally:
        root.destroy()


# --------------------------------------------------------------------------
# R-M3.C — success comes from the exit code, never from scraping output (P24)
# --------------------------------------------------------------------------

def test_rm3c_no_workflow_greps_for_pass_token():
    """`2 failed, 2181 passed` matches a grep for "passed" and reads green."""
    offenders = []
    for wf in _workflows():
        for line in _run_step_lines(wf.read_text(encoding="utf-8")):
            lowered = line.lower()
            if "grep" not in lowered:
                continue
            if any(token in lowered for token in PASS_TOKENS):
                offenders.append(f"{wf.name}: {line}")
    assert not offenders, (
        "workflow steps decide success by grepping for a pass token, which also "
        f"matches on a failing run: {offenders}. Use the exit code."
    )


def test_rm3c_test_step_does_not_swallow_the_exit_code():
    """A trailing `|| true`, `continue-on-error`, or a pipe into another command
    hides a red suite."""
    text = TESTS_WORKFLOW.read_text(encoding="utf-8")
    assert "continue-on-error: true" not in text, (
        "continue-on-error on the test job makes a failing suite report green"
    )
    for line in _run_step_lines(text):
        if "pytest" in line:
            assert "|| true" not in line, f"exit code discarded: {line}"
            assert not re.search(r"pytest[^|]*\|[^|]", line), (
                f"pytest output piped into another command; the pipeline's exit "
                f"code is the last command's, not pytest's: {line}"
            )


# --------------------------------------------------------------------------
# R-M3.D — every test file is actually collected
# --------------------------------------------------------------------------

def test_rm3d_no_test_files_at_the_repo_root():
    strays = sorted(p.name for p in REPO_ROOT.glob("test_*.py"))
    assert not strays, (
        f"test files at the repo root: {strays}. Move them under tests/ so one "
        "run collects everything."
    )


def test_rm3d_all_test_files_are_collected():
    """Ask pytest what it collects and compare against what exists on disk."""
    on_disk = {
        p.relative_to(REPO_ROOT).as_posix()
        for p in REPO_ROOT.rglob("test_*.py")
        if not any(part in {"venv", ".venv", "dist", "build", ".git", "__pycache__"}
                   for part in p.parts)
    }
    assert on_disk, "no test files found at all — the glob is wrong"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600,
    )
    assert result.returncode == 0, f"collection failed:\n{result.stdout}\n{result.stderr}"

    collected = {
        line.split("::", 1)[0].strip()
        for line in result.stdout.splitlines()
        if "::" in line
    }
    missing = sorted(on_disk - collected)
    assert not missing, (
        f"test files that exist but are never collected: {missing}. They can "
        "rot silently — nothing runs them."
    )


def test_rm3d_every_test_file_is_importable_on_its_own():
    """Guards the bug the repo-root conftest.py fixed.

    Two relocated files imported ``getmoredone`` before their own sys.path
    insert ran, so they only worked when an alphabetically earlier file had
    already set the path. Run alone, they errored.
    """
    failures = []
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "--collect-only", "-q"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            failures.append(f"{path.name}: {result.stdout.strip().splitlines()[-1:]}")
    assert not failures, f"test files that cannot be collected alone: {failures}"


# --------------------------------------------------------------------------
# R-M3.E — no check lives only in the workflow
# --------------------------------------------------------------------------

def test_rm3e_workflows_contain_no_inline_assertions():
    """A check written as YAML cannot fail before a push."""
    offenders = []
    for wf in _workflows():
        for line in _run_step_lines(wf.read_text(encoding="utf-8")):
            if re.search(r"\bassert\b", line):
                offenders.append(f"{wf.name}: {line}")
            if re.search(r"\bpython3?\s+-c\b", line):
                offenders.append(f"{wf.name}: {line}")
    assert not offenders, (
        "workflow steps contain checks that cannot be run locally: "
        f"{offenders}. Move the assertion into the pytest suite and have the "
        "workflow invoke the suite."
    )


def test_rm3e_run_step_parser_actually_finds_run_blocks():
    """Adversarial: an empty parser would make every check above vacuous."""
    sample = "\n".join([
        "jobs:",
        "  build:",
        "    steps:",
        "      - name: One",
        "        run: echo hello",
        "      - name: Two",
        "        run: |",
        "          grep passed out.txt",
        "          assert something",
        "      - uses: actions/checkout@v4",
    ])
    lines = _run_step_lines(sample)
    assert "echo hello" in lines
    assert "grep passed out.txt" in lines
    assert "assert something" in lines
    assert "uses: actions/checkout@v4" not in lines

    # And it finds real content in the checked-in workflows.
    assert any(_run_step_lines(wf.read_text(encoding="utf-8")) for wf in _workflows())


# --------------------------------------------------------------------------
# R-M4 — release pipeline hardening
# --------------------------------------------------------------------------

RELEASE_WORKFLOW = WORKFLOW_DIR / "build-release.yml"

# Where each OS job's packaged executable lands, per GetMoreDone.spec.
PACKAGED_EXECUTABLES = {
    "build-macos": "dist/GetMoreDone.app/Contents/MacOS/GetMoreDone",
    "build-windows": "GetMoreDone.exe",
}

# BI1 — the single job that creates the public GitHub Release.
PUBLISH_JOB = "publish"

# The artifact each OS job uploads, and the archive inside it.
BUILD_ARTIFACTS = {
    "build-windows": "GetMoreDone-win64",
    "build-macos": "GetMoreDone-mac",
}
RELEASE_ARCHIVES = ("GetMoreDone-win64.zip", "GetMoreDone-mac.zip")


def _job_blocks(text: str) -> dict[str, str]:
    """Split a workflow into {job_name: job_text}."""
    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if l.rstrip() == "jobs:")
    except StopIteration:
        return {}

    jobs: dict[str, list[str]] = {}
    current = None
    for line in lines[start + 1:]:
        if not line.strip() or line.strip().startswith("#"):
            if current:
                jobs[current].append(line)
            continue
        indent = len(line) - len(line.lstrip())
        match = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
        if indent == 2 and match:
            current = match.group(1)
            jobs[current] = []
            continue
        if indent == 0:
            break
        if current:
            jobs[current].append(line)
    return {name: "\n".join(body) for name, body in jobs.items()}


def test_rm4_job_splitter_finds_both_os_jobs():
    """Adversarial: an empty splitter makes every R-M4 check below vacuous."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    assert set(PACKAGED_EXECUTABLES).issubset(jobs), (
        f"expected jobs {sorted(PACKAGED_EXECUTABLES)}, found {sorted(jobs)}"
    )
    for name in PACKAGED_EXECUTABLES:
        assert "pyinstaller" in jobs[name].lower(), f"{name} body looks empty"


# R-M4.A — the packaged bundle must prove it starts

def test_rm4a_release_workflow_runs_selftest_on_the_packaged_bundle():
    """Every OS job must run --selftest against the BUILT executable.

    This is the automated guard against F1 recurring. Running
    `python run.py --selftest` instead would test the source tree, which is
    exactly the thing that was never broken.
    """
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job, executable in PACKAGED_EXECUTABLES.items():
        body = jobs[job]
        assert "--selftest" in body, f"{job} never runs --selftest on its build"
        assert executable in body, (
            f"{job} runs --selftest but not against {executable}"
        )


def test_rm4a_selftest_does_not_run_from_source():
    """`python run.py --selftest` in a release job would prove nothing."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        assert not re.search(r"python\s+run\.py\s+--selftest", jobs[job]), (
            f"{job} selftests the source tree, not the packaged bundle"
        )


def test_rm4a_selftest_runs_after_the_build():
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job]
        assert body.lower().index("pyinstaller") < body.index("--selftest"), (
            f"{job} runs --selftest before it builds anything"
        )


def test_rm4a_selftest_runs_before_anything_is_published():
    """A bundle that cannot start must never reach an artifact or a release."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job]
        selftest_at = body.index("--selftest")
        for publish in ("upload-artifact", "action-gh-release"):
            if publish in body:
                assert selftest_at < body.index(publish), (
                    f"{job} publishes via {publish} before the selftest runs"
                )


def test_rm4a_windows_job_waits_for_the_windowed_exe_and_reads_its_exit_code():
    """GetMoreDone.exe is console=False, so `& app.exe` does not wait for it.

    Observed on run 32191324517: the step threw "Packaged build failed its
    selftest (exit )" — $LASTEXITCODE unset — while the selftest was still
    running, and it then reported 4/4 checks passed. The shell had already
    moved on. Only Start-Process -Wait -PassThru yields a real exit code for a
    windowed-subsystem process.
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))["build-windows"])
    selftest_at = body.index("--selftest")
    # Look at the step containing the selftest, not the whole job.
    step = body[max(0, selftest_at - 800):selftest_at + 800]

    assert "Start-Process" in step and "-Wait" in step, (
        "the Windows selftest must use Start-Process -Wait: a windowed exe "
        "launched with & returns immediately and the job checks nothing"
    )
    assert "PassThru" in step and "ExitCode" in step, (
        "the Windows selftest must read .ExitCode from the waited process"
    )


def test_rm4a_windows_selftest_does_not_rely_on_lastexitcode():
    """$LASTEXITCODE is empty after launching a windowed exe, so `-ne 0` is
    always true and the step fails even on a healthy build."""
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))["build-windows"])
    selftest_at = body.index("--selftest")
    step = body[max(0, selftest_at - 800):selftest_at + 800]
    assert "LASTEXITCODE" not in step, (
        "the Windows selftest step still consults $LASTEXITCODE, which a "
        "windowed exe never sets"
    )


def test_rm4a_local_windows_build_script_waits_too():
    """Same bug class in build_windows.ps1 — fix one, fix the siblings (P5)."""
    script = _code_only((REPO_ROOT / "build_windows.ps1").read_text(encoding="utf-8"))
    if "--selftest" not in script:
        pytest.skip("build_windows.ps1 does not run a selftest")
    assert "Start-Process" in script and "-Wait" in script and "ExitCode" in script, (
        "build_windows.ps1 launches the windowed exe without waiting for it, so "
        "its selftest check is decorative"
    )
    assert "LASTEXITCODE" not in script, (
        "build_windows.ps1 still consults $LASTEXITCODE for a windowed exe"
    )


def test_rm4a_selftest_uses_a_scratch_database():
    """The selftest must not be pointed at whatever default path the runner has."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        assert "GETMOREDONE_DB" in jobs[job], (
            f"{job} should give --selftest an explicit scratch DB path"
        )


# R-M4.B — checksums published beside each artifact

def test_rm4b_release_workflow_publishes_checksums():
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job].lower()
        assert "sha256" in body, f"{job} publishes no SHA-256 checksum"


def test_rm4b_checksum_files_are_uploaded_as_artifacts():
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job]
        assert ".sha256" in body, (
            f"{job} computes a checksum but never uploads a .sha256 file"
        )


def test_rm4b_checksums_reach_the_github_release():
    """A checksum only in the Actions artifact does not help a downloader.

    Since BI1 there is one release step, in the publish job, so this asserts
    every platform's .sha256 is attached by it — the per-job form of this check
    would now pass while the publish job attached only one platform's.
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    release_at = body.find("action-gh-release")
    assert release_at != -1, "the publish job has no release step"
    attached = body[release_at:]
    for archive in RELEASE_ARCHIVES:
        assert f"{archive}.sha256" in attached, (
            f"{archive}.sha256 is not attached to the GitHub Release"
        )


# R-M4.C — release body comes from CHANGELOG.md

def test_rm4c_release_body_sourced_from_changelog():
    """Typed-by-hand release notes drift from the repo; generated ones cannot."""
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    assert "body_path" in body, "the publish job publishes a release with no notes"
    assert "extract_release_notes" in body, (
        "the publish job does not generate its notes from CHANGELOG.md"
    )


def test_rm4c_extractor_script_exists_and_is_not_inline_yaml():
    """R-M3.E: the logic must be runnable and testable outside CI."""
    script = REPO_ROOT / "tools/extract_release_notes.py"
    assert script.exists(), (
        "the workflow calls tools/extract_release_notes.py but it does not exist"
    )
    assert (REPO_ROOT / "tests/test_release_notes.py").exists(), (
        "the extractor has no tests, so CI is the only place it is exercised"
    )


def test_rm4c_notes_are_generated_before_the_release_step():
    # _code_only: the job's comment explains the two-release defect by name,
    # and matching the explanation would order the prose, not the steps.
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    assert body.index("extract_release_notes") < body.index("action-gh-release"), (
        "the publish job generates its release notes after publishing the release"
    )


# R-M4.D — LICENSE and notices travel inside the archive

REQUIRED_ARCHIVE_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses")


def test_rm4d_licence_files_reach_every_archive():
    """Two routes, one requirement.

    macOS relies on GetMoreDone.spec, which bundles the files into
    Contents/Resources. Windows adds a copy at the folder root as well, because
    a user who unzips sees only GetMoreDone.exe and _internal/ — a licence
    buried in there is not "included" in any useful sense.
    """
    spec = _code_only((REPO_ROOT / "GetMoreDone.spec").read_text(encoding="utf-8"))
    for required in REQUIRED_ARCHIVE_FILES:
        assert required in spec, (
            f"GetMoreDone.spec must bundle {required} — it is the only route "
            "that puts it inside the macOS archive (R-M4.D)"
        )

    windows = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))["build-windows"])
    for required in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        assert required in windows, (
            f"the Windows job should place {required} beside the executable"
        )


def test_rm4d_macos_job_does_not_restage_what_the_spec_already_bundles():
    """Regression: `cp -R licenses dest/licenses` when dest/licenses already
    exists copies *into* it, producing Resources/licenses/licenses/.

    Observed in run 32193099401. The spec is the single source on macOS.
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))["build-macos"])
    assert "cp -R licenses" not in body, (
        "the macOS job copies licenses/ into a directory the spec already "
        "created, which nests it one level deeper"
    )
    assert "Contents/Resources/licenses" not in body, (
        "the macOS job stages into Contents/Resources/licenses, which the spec "
        "already populates"
    )


def test_rm4d_windows_licence_files_are_staged_before_the_archive_is_made():
    """Copying them after the zip step would ship an archive without them."""
    body = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))["build-windows"]
    assert body.index("THIRD_PARTY_NOTICES.md") < body.index("Compress-Archive"), (
        "the Windows job stages the licence files after zipping"
    )


def test_rm4d_required_archive_files_exist_in_the_repo():
    """The workflow copies these by name; a rename would fail the job."""
    missing = [f for f in REQUIRED_ARCHIVE_FILES if not (REPO_ROOT / f).exists()]
    assert not missing, f"the release workflow copies files that do not exist: {missing}"


def test_no_workflow_disables_the_mapped_window_tests():
    """The local focus-stealing opt-out must never become a CI default.

    ``GETMOREDONE_NO_MAPPED_WINDOWS`` makes the three tests that read real
    Tk geometry skip, so the suite can run on a machine someone is working on.
    Set in CI it would turn the only coverage of the sash-drag and pin-drag
    contracts into a permanent silent skip.
    """
    offenders = [
        wf.name for wf in _workflows()
        if "GETMOREDONE_NO_MAPPED_WINDOWS" in wf.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{offenders} set GETMOREDONE_NO_MAPPED_WINDOWS. That variable is a "
        "local convenience for not stealing focus; in CI it silently skips the "
        "geometry tests."
    )


def test_the_mapped_window_opt_out_is_off_by_default():
    """A default-on escape hatch is the same silent skip by another route.

    Driven as a real subprocess rather than by matching strings in conftest.py.
    The string form of this test passed with the condition INVERTED — the
    substring it looked for, ``os.environ.get(NO_MAPPED_WINDOWS_ENV)``, is
    still present in ``if not os.environ.get(...)`` — which would have skipped
    the three geometry tests on every machine, CI included, leaving a skip
    count as the only signal. That is the exact failure this test exists to
    prevent, so it has to assert the behaviour.
    """
    # This test's OFF cases deliberately map a real window, so it must honour
    # the opt-out it guards — otherwise setting the variable to work in peace
    # still put two windows over the user's desktop on every full run, which is
    # the whole point of the variable.
    # CI coverage is unaffected: test_no_workflow_disables_the_mapped_window_tests
    # guarantees no workflow ever sets it.
    if os.environ.get("GETMOREDONE_NO_MAPPED_WINDOWS", "").strip().lower() \
            not in ("", "0", "false", "no", "off", "n"):
        pytest.skip(
            "GETMOREDONE_NO_MAPPED_WINDOWS is set: this test maps real windows "
            "in its OFF cases and would take keyboard focus. CI never sets it, "
            "so this always runs there."
        )

    target = "tests/test_tk_offscreen.py::test_a_test_can_ask_for_a_mapped_window"

    def _run(env_value):
        env = dict(os.environ)
        env.pop("GETMOREDONE_NO_MAPPED_WINDOWS", None)
        if env_value is not None:
            env["GETMOREDONE_NO_MAPPED_WINDOWS"] = env_value
        # No -rs here on purpose: pytest.ini's addopts must be what produces
        # the skip reason, so deleting that line fails this test rather than
        # silently restoring a bare "3 skipped".
        return subprocess.run(
            [sys.executable, "-m", "pytest", target, "-q", "--no-header"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=300, env=env,
        )

    def _describe(result):
        return (
            f"exit={result.returncode}\n"
            f"--- stdout ---\n{result.stdout[-1500:]}\n"
            f"--- stderr ---\n{result.stderr[-1500:]}"
        )

    # Success is the EXIT CODE, not a token in stdout — this file's own
    # docstring forbids the latter (P24), and this repo's pytest_sessionfinish
    # sets a non-zero status with no FAILURES section, so a nested run that
    # trips the user-data guard prints "1 passed" and would have passed here.
    unset = _run(None)
    assert unset.returncode == 0, (
        "with GETMOREDONE_NO_MAPPED_WINDOWS unset the geometry test must RUN "
        f"and pass.\n{_describe(unset)}"
    )
    assert "1 passed" in unset.stdout, (
        f"expected the geometry test to run, not skip.\n{_describe(unset)}"
    )

    on = _run("1")
    assert on.returncode == 0, (
        f"a skipped test must still exit 0.\n{_describe(on)}"
    )
    assert "1 skipped" in on.stdout, (
        f"GETMOREDONE_NO_MAPPED_WINDOWS=1 must skip it.\n{_describe(on)}"
    )
    assert "GETMOREDONE_NO_MAPPED_WINDOWS" in on.stdout, (
        "the skip REASON must be printed, so a suppressed run cannot be "
        "mistaken for a passing one. This depends on addopts = -rs in "
        f"pytest.ini.\n{_describe(on)}"
    )

    off = _run("0")
    assert off.returncode == 0 and "1 passed" in off.stdout, (
        "GETMOREDONE_NO_MAPPED_WINDOWS=0 must mean OFF. A bare truthiness "
        f"check makes '0' turn the opt-out ON.\n{_describe(off)}"
    )


# --------------------------------------------------------------------------
# BI1 (D1) — one release call, gated on every build succeeding
# --------------------------------------------------------------------------
#
# A GitHub Release is public and permanent the moment it is created, and a
# later job failing does not un-publish it. Two release calls therefore had a
# failure mode with no rollback: the first job to finish created the Release,
# the second failed, and the download page kept serving one platform's assets
# under a version number claiming both.
#
# None of this can be tested by running it. These assertions over the YAML are
# the only check that exists before a real tagged run.

def test_bi1_exactly_one_job_publishes_the_release():
    """The whole of BI1. Two calls is the defect; one is the fix."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    publishers = sorted(
        name for name, body in jobs.items()
        if "action-gh-release" in _code_only(body)
    )
    assert publishers == [PUBLISH_JOB], (
        f"expected only {PUBLISH_JOB!r} to call action-gh-release, found "
        f"{publishers}. Two publishing jobs can leave a public Release "
        "carrying one platform's assets when the other build fails."
    )


def test_bi1_publish_job_waits_for_every_build_job():
    """`needs:` is what makes a half-succeeded run publish nothing.

    Derived from the job list rather than a written-out pair, so a third OS
    job added later fails this until it is added to `needs:` too.
    """
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    body = _code_only(jobs[PUBLISH_JOB])
    match = re.search(r"needs:\s*\[([^\]]*)\]", body)
    assert match, f"the {PUBLISH_JOB} job declares no needs: [...]"
    declared = {n.strip() for n in match.group(1).split(",") if n.strip()}

    build_jobs = set(PACKAGED_EXECUTABLES)
    missing = sorted(build_jobs - declared)
    assert not missing, (
        f"the {PUBLISH_JOB} job does not wait for {missing}. Without it that "
        "build can fail while the Release is published anyway."
    )


def test_bi1_publish_job_downloads_every_build_artifact():
    """A release call that names a file no step produced publishes nothing.

    ``fail_on_unmatched_files: true`` turns that into a failed job rather than
    an empty Release, but only after the tag exists. This catches it here.
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    assert "download-artifact" in body, (
        "the publish job never downloads the builds it is publishing"
    )
    for job, artifact in BUILD_ARTIFACTS.items():
        assert f"name: {artifact}" in body, (
            f"the publish job does not download {artifact}, uploaded by {job}"
        )


def test_bi1_uploaded_artifact_names_match_what_publish_downloads():
    """Producer/consumer contract (P19).

    The upload name and the download name are one contract across two jobs.
    A rename on either side yields "artifact not found" at release time — after
    both builds have run, on a tag that already exists.
    """
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job, artifact in BUILD_ARTIFACTS.items():
        assert f"name: {artifact}" in _code_only(jobs[job]), (
            f"{job} does not upload an artifact named {artifact}, which the "
            "publish job downloads by that name"
        )


def test_bi1_every_built_archive_is_attached_to_the_release():
    """Both platforms, one Release. The point of the change."""
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    release_at = body.find("action-gh-release")
    attached = body[release_at:]
    for archive in RELEASE_ARCHIVES:
        # Anchored on the archive ENDING the line: a bare `archive in attached`
        # is satisfied by the ".sha256" entry alone.
        assert re.search(rf"{re.escape(archive)}\s*$", attached, re.MULTILINE), (
            f"{archive} is not attached to the Release (its .sha256 alone does "
            "not count). A run that publishes one platform, or only checksums, "
            "is the failure BI1 exists to prevent."
        )


def test_bi1_no_os_job_publishes_a_release():
    """State it from the other side too.

    ``test_bi1_exactly_one_job_publishes_the_release`` is the general rule;
    this names the specific regression, so a diff that reintroduces a release
    step inside build-windows gets a message that says so.
    """
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        assert "action-gh-release" not in _code_only(jobs[job]), (
            f"{job} publishes a GitHub Release. Publishing belongs in the "
            f"{PUBLISH_JOB} job, which runs only after every build succeeded."
        )


def test_bi1_publish_job_is_gated_on_a_tag():
    """Without the gate, every push to a branch would cut a Release."""
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    assert re.search(r"^\s*if:", body, re.MULTILINE), (
        f"the {PUBLISH_JOB} job has no if: condition at all"
    )
    # Not anchored to the `if:` line: a block scalar puts the expression on the
    # lines beneath it.
    assert "refs/tags/v" in body, (
        f"the {PUBLISH_JOB} job has no tag condition"
    )


def test_bi1_selftest_still_gates_publication_through_needs():
    """The guarantee moved from step order to job order — check it still holds.

    Each OS job asserts its selftest runs before its upload
    (``test_rm4a_selftest_runs_before_anything_is_published``). With the release
    step now in another job, `needs:` is the only thing carrying that guarantee
    forward to publication, so both halves have to be true at once.
    """
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job]
        assert body.index("--selftest") < body.index("upload-artifact"), (
            f"{job} uploads its artifact before proving the bundle starts"
        )
    needs = re.search(r"needs:\s*\[([^\]]*)\]", _code_only(jobs[PUBLISH_JOB]))
    assert needs and set(PACKAGED_EXECUTABLES) <= {
        n.strip() for n in needs.group(1).split(",") if n.strip()
    }, "publication no longer depends on the jobs that run the selftest"


def test_bi1_download_path_matches_the_release_file_prefix():
    """Tie the two halves together, or both can be individually "correct".

    ``test_bi1_publish_job_downloads_every_build_artifact`` checks artifact
    NAMES; ``test_bi1_every_built_archive_is_attached_to_the_release`` checks
    archive BASENAMES. Change ``path: release-assets`` to anything else — or
    delete it, so download-artifact defaults to the workspace root — and both
    still pass while the release step matches nothing.
    ``fail_on_unmatched_files: true`` makes that a red job rather than an empty
    Release, so the outcome is a burned tag, not a bad Release. Still a hole in
    "these tests are the only check before a real v* tag".
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])

    # Counted, not set-collapsed: two identical `path:` values collapse to one,
    # so deleting the path from ONE of the two download steps left len == 1 and
    # passed while that artifact landed in the workspace root instead.
    download_steps = len(re.findall(r"uses:\s*actions/download-artifact@", body))
    declared = re.findall(r"^\s*path:\s*(\S+)\s*$", body, re.MULTILINE)
    assert len(declared) == download_steps, (
        f"{download_steps} download steps but {len(declared)} path: entries — "
        "a download with no path: lands in the workspace root, where the "
        "release step's files: prefix will not match it"
    )
    unique = {p.strip("\"'") for p in declared}
    assert len(unique) == 1, (
        f"the downloads land in different directories {sorted(unique)}; the "
        "release step can only carry one prefix"
    )
    download_dir = unique.pop()

    release_at = body.find("action-gh-release")
    attached = body[release_at:]
    for archive in RELEASE_ARCHIVES:
        for suffix in ("", ".sha256"):
            expected = f"{download_dir}/{archive}{suffix}"
            # Line-anchored, not a substring. "…/GetMoreDone-mac.zip" IS a
            # substring of "…/GetMoreDone-mac.zip.sha256", so the substring
            # form passed a files: block containing ONLY the two checksums —
            # which satisfies fail_on_unmatched_files: true and publishes a
            # public, permanent Release with correct notes and no downloadable
            # archives. Verified by mutation.
            assert re.search(rf"^\s*{re.escape(expected)}\s*$", attached, re.MULTILINE), (
                f"the release step does not attach {expected!r} on a line of "
                f"its own. The downloads land in {download_dir!r}, so every "
                "files: entry must start with it."
            )


def test_bi1_downloaded_archives_are_checksum_verified_before_publishing():
    """The guarantee that used to be free inside one job (P6).

    The zip and its .sha256 were once produced and attached from the same
    directory in the same job. They now round-trip through the artifact store
    and are attached by a third job, so a corrupted round-trip would publish an
    asset that does not match the checksum file beside it, green.
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    assert "sha256sum -c" in body, (
        "the publish job attaches checksums it never verified against the "
        "archives it downloaded"
    )
    assert body.index("sha256sum -c") < body.index("action-gh-release"), (
        "the checksum verification runs after the Release is published"
    )
    for archive in RELEASE_ARCHIVES:
        assert f"sha256sum -c {archive}.sha256" in body, (
            f"{archive} is published without its checksum being verified"
        )


def test_bi1_checksum_files_are_written_in_the_format_the_verifier_reads():
    """Producer/consumer contract across three jobs and two platforms (P19).

    The publish job runs GNU ``sha256sum -c`` on files written by PowerShell on
    Windows and ``shasum`` on macOS. Drop ``-NoNewline`` from the Windows step
    and PowerShell emits CRLF; ``sha256sum`` then parses the filename as
    ``GetMoreDone-win64.zip\r`` and the publish job fails — on a real tag,
    after both builds have run. Nothing asserted the format, only that the
    verification was called.
    """
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))

    windows = _code_only(jobs["build-windows"])
    assert "-NoNewline" in windows, (
        "the Windows checksum step must write without a trailing newline; "
        "PowerShell otherwise emits CRLF, which GNU sha256sum -c cannot parse"
    )
    assert "-Encoding ascii" in windows, (
        "the Windows checksum step must write ASCII; a UTF-16 or BOM-prefixed "
        "file is unreadable to sha256sum -c"
    )
    assert '"$hash  GetMoreDone' in windows, (
        "the Windows checksum step must use the two-space separator that "
        "sha256sum -c and shasum both expect"
    )

    macos = _code_only(jobs["build-macos"])
    assert "shasum -a 256" in macos, (
        "the macOS checksum step must use shasum -a 256, whose output format "
        "the publish job's sha256sum -c reads"
    )


def test_bi1_publish_job_does_not_run_on_a_failed_build():
    """`needs:` only implies success while no status function overrides it.

    Adding `always() && ...` to the job's `if:` would restore the exact defect
    BI1 removed — both builds could fail and the Release would still be cut —
    and every other BI1 test would stay green.
    """
    body = _code_only(_job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))[PUBLISH_JOB])
    # The whole job body, not just the remainder of the `if:` line. A block
    # scalar (`if: >` with `always() && ...` on the following line) put the
    # override outside a single-line capture and left this green.
    condition = re.search(r"^\s*if:(.*)$", body, re.MULTILINE)
    assert condition, "the publish job has no if: condition"
    for override in ("always(", "failure(", "cancelled("):
        assert override not in body, (
            f"the publish job's if: uses {override}), which overrides the "
            "implicit success requirement of needs: and lets a failed build "
            "publish a Release"
        )


def test_bi1_release_notes_are_generated_once():
    """Two copies of the notes agreed only because nothing made them differ."""
    text = _code_only(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    calls = text.count("extract_release_notes.py")
    assert calls == 1, (
        f"extract_release_notes.py is called {calls} times; one Release needs "
        "one set of notes"
    )


# --------------------------------------------------------------------------
# Action versions — pinned, and consistent across every workflow
# --------------------------------------------------------------------------

# `uses:` forms that are legitimately not a versioned marketplace action.
LOCAL_USES_PREFIXES = ("./", "../", "docker://")

_USES_LINE = re.compile(r"\buses:\s*(\S+)")
_VERSIONED_ACTION = re.compile(r"^['\"]?([\w.-]+/[\w.-]+)@([^'\"\s]+)['\"]?$")


def _uses_lines() -> list[tuple[str, str]]:
    """Every `uses:` value in every workflow, as (workflow name, raw value)."""
    found = []
    for wf in _workflows():
        for line in _code_only(wf.read_text(encoding="utf-8")).splitlines():
            match = _USES_LINE.search(line)
            if match:
                found.append((wf.name, match.group(1)))
    return found


def _action_uses() -> dict[str, set[str]]:
    """{action name: {versions used}} across every workflow."""
    found: dict[str, set[str]] = {}
    for _wf, raw in _uses_lines():
        match = _VERSIONED_ACTION.match(raw)
        if match:
            found.setdefault(match.group(1), set()).add(match.group(2))
    return found


def test_every_uses_line_is_recognised_by_the_action_parser():
    """An unparsed `uses:` line is invisible to every check below it.

    The parser used to require an unquoted `owner/repo@ver`, so
    `uses: 'actions/checkout@v4'` — ordinary YAML, and what a reformatter may
    well emit — matched nothing and was silently exempt from the version,
    pinning and drift checks. Unrecognised input must be loud one level up too,
    not only inside the checks it feeds.
    """
    unrecognised = [
        f"{wf}: {raw}" for wf, raw in _uses_lines()
        if not _VERSIONED_ACTION.match(raw)
        and not raw.strip("'\"").startswith(LOCAL_USES_PREFIXES)
    ]
    assert not unrecognised, (
        f"`uses:` lines the action checks cannot see: {unrecognised}. Either "
        "pin them as owner/repo@version, or extend LOCAL_USES_PREFIXES."
    )


def test_action_parser_handles_quoted_and_local_uses_forms():
    """Adversarial: prove the parser change actually covers the missed forms."""
    assert _VERSIONED_ACTION.match("actions/checkout@v7").group(1) == "actions/checkout"
    assert _VERSIONED_ACTION.match("'actions/checkout@v7'").group(1) == "actions/checkout"
    assert _VERSIONED_ACTION.match('"actions/checkout@v7"').group(2) == "v7"
    assert _VERSIONED_ACTION.match("./.github/actions/local") is None
    assert _VERSIONED_ACTION.match("docker://alpine:3.19") is None


def test_actions_are_used_at_one_version_across_all_workflows():
    """Three workflows drifting apart is how one gets left on a dead runtime.

    The Node 20 deprecation landed on all three at once; bumping only the one
    being edited would have left the others behind.
    """
    drifted = {a: sorted(v) for a, v in _action_uses().items() if len(v) > 1}
    assert not drifted, (
        f"the same action is pinned to different versions in different "
        f"workflows: {drifted}"
    )


def test_actions_are_pinned_to_a_version_not_a_branch():
    """`@main` silently changes under you; a major tag does not."""
    floating = {
        f"{action}@{version}"
        for action, versions in _action_uses().items()
        for version in versions
        if version in {"main", "master", "latest", "HEAD"}
    }
    assert not floating, f"actions pinned to a moving ref: {sorted(floating)}"


# Every action used anywhere in .github/workflows must appear here, with the
# last major that ran on the deprecated Node 20 runtime. An action missing from
# this table fails its own test rather than being skipped.
#
# Values are ints, deliberately. An earlier draft allowed None for "no Node 20
# lineage", which put the silent skip back one step out as a documented
# one-word opt-out — and typing None is the path of least resistance when CI
# goes red on a newly added action. Use 0 instead: the comparison still runs
# and simply never fires.
KNOWN_ACTION_MAJORS: dict[str, int] = {
    "actions/checkout": 4,
    "actions/setup-python": 5,
    "actions/upload-artifact": 4,
    "actions/download-artifact": 4,
    "actions/cache": 3,
    "softprops/action-gh-release": 2,
}

# A commit-SHA pin is good practice, but it hides the major from this check.
# Record what each pinned SHA corresponds to so the check still applies.
SHA_PINNED_MAJORS: dict[str, int] = {}


def _parsed_major(version: str) -> int | None:
    match = re.fullmatch(r"v?(\d+)(?:\.\d+)*", version)
    return int(match.group(1)) if match else None


def test_every_action_used_is_declared_in_the_version_table():
    """An unlisted action must be a red test, not a silent skip."""
    unknown = sorted(set(_action_uses()) - set(KNOWN_ACTION_MAJORS))
    assert not unknown, (
        f"workflows use actions absent from KNOWN_ACTION_MAJORS: {unknown}. "
        "Add each one with the last major that ran on Node 20, or 0 if it has "
        "no Node 20 lineage — never None, which would skip the check."
    )


def test_action_version_table_holds_only_integers():
    """A None here would silently exempt that action from the check below."""
    bad = {a: v for a, v in KNOWN_ACTION_MAJORS.items() if not isinstance(v, int)}
    assert not bad, (
        f"KNOWN_ACTION_MAJORS entries that are not ints: {bad}. Use 0 for "
        "'no Node 20 lineage' so the comparison still runs."
    )


def test_every_action_version_is_checkable():
    r"""A version this test cannot parse must fail, not fall through.

    `re.match(r"v(\d+)", ...)` returned None for a SHA pin, and a None match
    hit no assertion at all — so SHA-pinning every action, the standard next
    hardening step, would have disabled this guard entirely.
    """
    unparseable = sorted(
        f"{action}@{version}"
        for action, versions in _action_uses().items()
        for version in versions
        if _parsed_major(version) is None
        and f"{action}@{version}" not in SHA_PINNED_MAJORS
    )
    assert not unparseable, (
        f"action versions this check cannot interpret: {unparseable}. If these "
        "are commit-SHA pins, add 'action@sha': <major> to SHA_PINNED_MAJORS so "
        "the Node 20 check still applies to them."
    )


def _stale_actions(uses: dict[str, set[str]]) -> list[str]:
    """Actions in `uses` sitting on a deprecated Node 20 major.

    Extracted from the test so the adversarial test below can drive it with
    synthetic input. Asserting on a helper's return value proves nothing about
    the guard; this is the guard.
    """
    stale = []
    for action, versions in uses.items():
        limit = KNOWN_ACTION_MAJORS.get(action)
        for version in versions:
            major = _parsed_major(version)
            if major is None:
                major = SHA_PINNED_MAJORS.get(f"{action}@{version}")
            # "unknown action" and "unparseable version" each have their own
            # test above; here they are simply not judgeable.
            if limit is None or major is None:
                continue
            if major <= limit:
                stale.append(f"{action}@{version}")
    return sorted(stale)


def test_no_workflow_uses_a_node20_action_version():
    """GitHub force-runs Node 20 actions on Node 24 with a deprecation warning
    today, and will stop running them.

    Verified against the actions' own latest releases on 2026-08-18:
    checkout v7.0.1, setup-python v7.0.0, upload-artifact v7.0.1,
    action-gh-release v3.0.2.
    """
    stale = _stale_actions(_action_uses())
    assert not stale, (
        f"actions on a deprecated Node 20 runtime: {stale}. "
        "Bump them across every workflow, not just the one being edited."
    )


def test_node20_guard_actually_rejects_the_cases_it_used_to_skip():
    """Drive the guard itself with the four cases that previously passed green.

    An earlier version of this test only asserted `_parsed_major` return values
    and dict membership. It never called the guard, so it stayed green with the
    silent-skip branch still in the loop, and green when `<=` was mutated to
    `<`. It now exercises `_stale_actions` directly.
    """
    # A recognised action on a Node 20 major is flagged.
    assert _stale_actions({"actions/cache": {"v3"}}) == ["actions/cache@v3"]
    assert _stale_actions({"actions/download-artifact": {"v4"}}) == [
        "actions/download-artifact@v4"]
    # Bare major, no leading v.
    assert _stale_actions({"actions/checkout": {"4"}}) == ["actions/checkout@4"]
    # A current major is not flagged.
    assert _stale_actions({"actions/checkout": {"v7"}}) == []
    # Boundary: the guard must flag the last Node 20 major itself, not just below it.
    assert _stale_actions({"actions/checkout": {"v4"}}) == ["actions/checkout@v4"]
    # A SHA pin is not judgeable here; test_every_action_version_is_checkable
    # is what makes it red.
    sha = "11bd71901bbe5b1630ceea73d27597364c9af683"
    assert _stale_actions({"actions/checkout": {sha}}) == []
    assert _parsed_major(sha) is None


def test_node20_guard_is_sensitive_to_the_comparison_operator():
    """Mutation check: `<=` must not be silently weakenable to `<`.

    With the real workflows both operators yield [], so the previous test could
    not tell them apart. This case distinguishes them.
    """
    at_the_limit = {"actions/setup-python": {"v5"}}   # 5 == last Node 20 major
    assert _stale_actions(at_the_limit) == ["actions/setup-python@v5"], (
        "the guard stopped flagging the last Node 20 major itself"
    )


# --------------------------------------------------------------------------
# R-M4.A/B — the publish steps must fail rather than publish nothing
# --------------------------------------------------------------------------

def test_upload_artifact_fails_when_no_files_match():
    """`if-no-files-found` defaults to 'warn': a glob matching nothing would
    log a warning and leave the job green with no artifact attached."""
    text = _code_only(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    uploads = text.count("actions/upload-artifact@")
    assert uploads == 2, f"expected 2 upload steps, found {uploads}"
    assert text.count("if-no-files-found: error") == uploads, (
        "every upload-artifact step must set if-no-files-found: error, or a "
        "build can report success having uploaded nothing"
    )


def test_release_upload_fails_when_no_files_match():
    """`fail_on_unmatched_files` defaults to false, which would publish a
    public, permanent Release with correct notes and zero assets."""
    text = _code_only(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    releases = text.count("softprops/action-gh-release@")
    assert releases == 1, (
        f"expected exactly 1 release step, found {releases} — see "
        "test_bi1_exactly_one_job_publishes_the_release"
    )
    assert text.count("fail_on_unmatched_files: true") == releases, (
        "every action-gh-release step must set fail_on_unmatched_files: true"
    )


def test_publish_hardening_is_present_in_both_os_jobs():
    """Per-job, not just per-file: a count can be satisfied by two in one job."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = _code_only(jobs[job])
        assert "if-no-files-found: error" in body, f"{job} upload is not hardened"
    assert "fail_on_unmatched_files: true" in _code_only(jobs[PUBLISH_JOB]), (
        "the publish job's release step is not hardened"
    )


# --------------------------------------------------------------------------
# macOS code signing — optional, but it must fail loudly when it is on
# --------------------------------------------------------------------------

SIGNING_GATE = "steps.signing.outputs.available == 'true'"
SIGNING_SECRETS = (
    "APPLE_CERTIFICATE_P12_BASE64",
    "APPLE_CERTIFICATE_PASSWORD",
    "APPLE_SIGNING_IDENTITY",
    "APPLE_NOTARY_KEY_BASE64",
    "APPLE_NOTARY_KEY_ID",
    "APPLE_NOTARY_ISSUER_ID",
)


def _macos_steps() -> list[dict]:
    """The macOS job's steps, as (name, if, body) dicts parsed from the YAML text.

    Hand-parsed for the same reason as everything else in this file: PyYAML is
    not a project dependency.
    """
    body = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))["build-macos"]
    steps, current = [], None
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- name:") or stripped.startswith("- uses:"):
            current = {"name": stripped.split(":", 1)[1].strip(),
                       "if": "", "body": [], "raw": []}
            steps.append(current)
        elif current is not None:
            if stripped.startswith("if:"):
                current["if"] = stripped.split(":", 1)[1].strip()
            current["raw"].append(stripped)
            # `body` excludes comments: several of these steps explain in a
            # comment the very construct the tests prohibit ("rather than
            # --deep"), and matching the explanation instead of the code would
            # pressure the next person into deleting the reasoning.
            if not stripped.startswith("#"):
                current["body"].append(stripped)
    for step in steps:
        step["body"] = "\n".join(step["body"])
        step["raw"] = "\n".join(step["raw"])
    return steps


def test_signing_step_parser_finds_the_macos_steps():
    """Adversarial: an empty parser makes every signing assertion vacuous."""
    steps = _macos_steps()
    names = [s["name"] for s in steps]
    assert len(steps) >= 10, f"parsed only {len(steps)} steps: {names}"
    assert any("Build (PyInstaller)" in n for n in names), names


def test_signing_is_optional_and_defaults_to_skipped():
    """With no credentials the job must behave exactly as it did before.

    Every signing step carries the same gate, so absent secrets produce an
    unsigned build and a green job rather than a failure.
    """
    gated = [s for s in _macos_steps() if SIGNING_GATE in s["if"]]
    assert len(gated) >= 4, (
        f"expected the signing steps to be gated on credentials, found "
        f"{len(gated)}: {[s['name'] for s in gated]}"
    )


def test_every_signing_step_is_gated():
    """An ungated signing step would fail every build that has no certificate."""
    ungated = [
        s["name"] for s in _macos_steps()
        if any(k in s["name"].lower() for k in ("sign", "notaris", "notariz", "keychain"))
        and SIGNING_GATE not in s["if"]
        and "credentials configured" not in s["name"].lower()
    ]
    assert not ungated, (
        f"signing steps that run unconditionally: {ungated}. Without secrets "
        "these fail, breaking builds for anyone without a certificate."
    )


def test_signing_gate_does_not_interpolate_secrets_into_the_script():
    """A secret pasted into a shell body can break on quotes or leak in traces.

    It must arrive through `env:` instead.
    """
    offenders = []
    for step in _macos_steps():
        for line in step["body"].splitlines():
            if "secrets." not in line:
                continue
            # The only acceptable shape is an env mapping: NAME: ${{ secrets.X }}
            if not re.match(r"^[A-Z][A-Z0-9_]*:\s*\$\{\{\s*secrets\.", line):
                offenders.append(f"{step['name']}: {line}")
    assert not offenders, (
        "secrets interpolated somewhere other than an env: mapping — a value "
        f"containing quotes or newlines would break or leak: {offenders}"
    )

    gate = next(s for s in _macos_steps() if "credentials configured" in s["name"].lower())
    assert "env:" in gate["body"], (
        "the credential check should read secrets via env, not inline them"
    )
    assert 'echo "available=' in gate["body"], "the gate must publish a step output"


def test_signing_runs_before_the_archive_is_made():
    """Signing after zipping would ship the unsigned bundle."""
    names = [s["name"] for s in _macos_steps()]
    sign_at = next(i for i, n in enumerate(names) if "Sign the app" in n)
    zip_at = next(i for i, n in enumerate(names) if "Zip macOS app" in n)
    assert sign_at < zip_at, f"signing happens after zipping: {names}"


def test_selftest_runs_after_signing_so_it_exercises_the_shipped_bundle():
    """Signing rewrites the binary; the selftest should see the final artifact."""
    names = [s["name"] for s in _macos_steps()]
    staple_at = next(i for i, n in enumerate(names) if "Notaris" in n or "Notariz" in n)
    selftest_at = next(i for i, n in enumerate(names) if "packaged bundle starts" in n)
    assert staple_at < selftest_at, (
        "the selftest runs before notarisation, so it does not exercise the "
        "bundle that actually ships"
    )


def test_signing_is_verified_against_the_artifact():
    """P6: trusting codesign's exit code is not the same as asking Gatekeeper.

    `spctl --assess` is what Gatekeeper itself runs, and `stapler validate`
    proves the ticket is embedded rather than merely issued.
    """
    body = " ".join(s["body"] for s in _macos_steps())
    assert "spctl --assess" in body, "nothing runs spctl to confirm Gatekeeper accepts it"
    assert "stapler validate" in body, "nothing confirms the notarisation ticket stapled"


def test_signing_keychain_is_always_cleaned_up():
    """A failure mid-signing must not leave a certificate on the runner."""
    cleanup = [s for s in _macos_steps() if "keychain" in s["name"].lower()
               and "clean" in s["name"].lower()]
    assert cleanup, "no keychain cleanup step"
    assert "always()" in cleanup[0]["if"], (
        f"keychain cleanup is not unconditional: {cleanup[0]['if']}"
    )


def test_signing_does_not_use_codesign_deep_for_the_bundle():
    """Apple documents --deep as unsuitable for real bundles; a PyInstaller app
    needs its nested .so/.dylib files signed individually."""
    sign_step = next(s for s in _macos_steps() if "Sign the app" in s["name"])
    assert "--deep" not in sign_step["body"], (
        "signing uses --deep, which Apple advises against for distribution; "
        "sign nested binaries inside-out instead"
    )


def test_signing_entitlements_exist_and_are_minimal():
    """Hardened runtime forces a few entitlements; it must not grant more."""
    plist = REPO_ROOT / "packaging/entitlements.plist"
    assert plist.exists(), "the workflow references packaging/entitlements.plist"
    text = plist.read_text(encoding="utf-8")

    for required in ("com.apple.security.cs.allow-jit",
                     "com.apple.security.cs.allow-unsigned-executable-memory",
                     "com.apple.security.cs.disable-library-validation"):
        assert required in text, f"CPython needs {required} under hardened runtime"

    for forbidden in ("com.apple.security.device.camera",
                      "com.apple.security.device.microphone",
                      "com.apple.security.personal-information.location",
                      "com.apple.security.personal-information.addressbook",
                      "com.apple.security.cs.disable-executable-page-protection"):
        assert forbidden not in text, (
            f"{forbidden} is granted but nothing in the app needs it"
        )


def test_signing_setup_is_documented():
    """Six secrets nobody can guess; the doc is the only way in."""
    doc = REPO_ROOT / "docs/CODE_SIGNING.md"
    assert doc.exists(), "no docs/CODE_SIGNING.md"
    text = doc.read_text(encoding="utf-8")
    missing = [s for s in SIGNING_SECRETS if s not in text]
    assert not missing, f"docs/CODE_SIGNING.md does not name these secrets: {missing}"


def test_documented_secrets_match_the_ones_the_workflow_reads():
    """Doc-vs-artifact drift: a documented secret the workflow ignores, or a
    secret the workflow needs and the doc never mentions, both waste an hour."""
    workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    used = set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow))
    documented = set(
        re.findall(r"\b(APPLE_[A-Z0-9_]+)\b",
                   (REPO_ROOT / "docs/CODE_SIGNING.md").read_text(encoding="utf-8"))
    )
    assert used, "the workflow reads no secrets at all"
    assert used <= documented, (
        f"the workflow reads secrets the doc never explains: {sorted(used - documented)}"
    )
