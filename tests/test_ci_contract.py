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
    """Installing an ad-hoc package list would defeat the point of the run."""
    text = TESTS_WORKFLOW.read_text(encoding="utf-8")
    assert "-r requirements.txt" in text, (
        "tests.yml must install from requirements.txt, so a missing or wrong "
        "dependency declaration fails CI instead of passing on a warm machine."
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
    """A checksum only in the Actions artifact does not help a downloader."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job]
        release_at = body.find("action-gh-release")
        assert release_at != -1, f"{job} has no release step"
        assert ".sha256" in body[release_at:], (
            f"{job} does not attach its .sha256 file to the GitHub Release"
        )


# R-M4.C — release body comes from CHANGELOG.md

def test_rm4c_release_body_sourced_from_changelog():
    """Typed-by-hand release notes drift from the repo; generated ones cannot."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = _code_only(jobs[job])
        assert "body_path" in body, f"{job} publishes a release with no notes"
        assert "extract_release_notes" in body, (
            f"{job} does not generate its notes from CHANGELOG.md"
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
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = jobs[job]
        assert body.index("extract_release_notes") < body.index("action-gh-release"), (
            f"{job} generates its release notes after publishing the release"
        )


# R-M4.D — LICENSE and notices travel inside the archive

REQUIRED_ARCHIVE_FILES = ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses")


def test_rm4d_archives_include_license_and_notices():
    """A notice that ships only in the repo never reaches a binary downloader,
    and the LGPL requires the licence text to accompany the distribution."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job in PACKAGED_EXECUTABLES:
        body = _code_only(jobs[job])
        for required in REQUIRED_ARCHIVE_FILES:
            assert required in body, (
                f"{job} does not put {required} inside its archive (R-M4.D)"
            )


def test_rm4d_licence_files_are_staged_before_the_archive_is_made():
    """Copying them after the zip step would ship an archive without them."""
    jobs = _job_blocks(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    for job, zip_marker in (("build-windows", "Compress-Archive"),
                            ("build-macos", "ditto -c -k")):
        body = jobs[job]
        assert body.index("THIRD_PARTY_NOTICES.md") < body.index(zip_marker), (
            f"{job} stages the licence files after zipping"
        )


def test_rm4d_required_archive_files_exist_in_the_repo():
    """The workflow copies these by name; a rename would fail the job."""
    missing = [f for f in REQUIRED_ARCHIVE_FILES if not (REPO_ROOT / f).exists()]
    assert not missing, f"the release workflow copies files that do not exist: {missing}"
