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
