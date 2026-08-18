"""Repo hygiene tests.

Purpose: keep the repository root readable as a product, and stop a required
         resource being silently excluded from the distribution.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m7
Tests:   this file

R-M7.B is the important one. `.gitignore` carries a blanket `*.json` rule with
a handful of `!` exceptions. That is the same shape as finding F1: a resource
the app loads at runtime can be excluded from the repo — and therefore from
every build — without anybody noticing, because the app keeps working on the
machine where the untracked file still exists locally.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.splitlines()


def _tracked_root_files() -> list[str]:
    return [f for f in _tracked_files() if "/" not in f]


# --------------------------------------------------------------------------
# R-M7.A — no stray scripts at the repo root
# --------------------------------------------------------------------------

STRAY_PREFIXES = ("test_", "diagnose_", "fix_", "debug_", "verify_")


def test_rm7a_repo_root_has_no_stray_scripts():
    """Diagnostics live in tools/diagnostics/, tests live in tests/."""
    strays = sorted(
        f for f in _tracked_root_files()
        if f.lower().startswith(STRAY_PREFIXES)
    )
    assert not strays, (
        f"scripts at the repo root that belong in tools/diagnostics/ or tests/: "
        f"{strays}"
    )


def test_rm7a_diagnostics_folder_exists_and_is_populated():
    """Guard on the guard: the test above passes trivially if everything was
    deleted rather than relocated."""
    diagnostics = REPO_ROOT / "tools/diagnostics"
    assert diagnostics.is_dir(), "tools/diagnostics/ does not exist"
    contents = list(diagnostics.iterdir())
    assert len(contents) >= 5, f"tools/diagnostics/ looks empty: {contents}"


def test_rm7a_no_python_entry_points_lost_from_the_root():
    """run.py and conftest.py must stay where the tooling expects them."""
    for required in ("run.py", "conftest.py"):
        assert (REPO_ROOT / required).exists(), f"{required} is missing from the root"


# --------------------------------------------------------------------------
# R-M7.C — the root reads as a product, not as an agent workspace
# --------------------------------------------------------------------------

# Docs that belong at the root of any repository, plus the two agent-config
# files whose tooling reads them from the root and nowhere else.
ROOT_DOC_ALLOWLIST = {
    "README.md",
    "LICENSE",
    "INSTALL.md",
    "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md",
    "CLAUDE.md",       # Claude Code loads this from the repo root
    "AGENTS.md",       # multi-agent workflow contract
    "BACKLOG.md",
    "NOTES.md",
    "codex.md",
    "GetMoreDone_MasterSpec_SQLite_v1.md",
}


def test_rm7c_repo_root_doc_allowlist():
    """Troubleshooting and agent-facing docs belong under docs/."""
    root_docs = {f for f in _tracked_root_files() if f.endswith(".md") or f == "LICENSE"}
    unexpected = sorted(root_docs - ROOT_DOC_ALLOWLIST)
    assert not unexpected, (
        f"root-level docs not on the allowlist: {unexpected}. Move them under "
        "docs/, or add them to ROOT_DOC_ALLOWLIST with a reason."
    )


def test_rm7c_allowlisted_root_docs_all_exist():
    """A stale allowlist entry hides a file that was deleted or moved."""
    missing = sorted(
        name for name in ROOT_DOC_ALLOWLIST if not (REPO_ROOT / name).exists()
    )
    assert not missing, f"ROOT_DOC_ALLOWLIST names files that do not exist: {missing}"


# --------------------------------------------------------------------------
# R-M7.B — the blanket *.json ignore cannot silently drop a shipped resource
# --------------------------------------------------------------------------

def test_rm7b_no_gitignore_copy_file():
    assert not (REPO_ROOT / ".gitignore copy").exists(), (
        "'.gitignore copy' is back; it was a duplicate of .gitignore"
    )


def test_rm7b_gitignore_still_has_the_blanket_json_rule_documented():
    """If the blanket rule is ever removed this test should be removed too —
    but while it exists, it must be visible rather than incidental."""
    text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "*.json" in text
    assert "!themes/*.json" in text, (
        "the themes exception is gone from .gitignore — every theme would be "
        "untracked and every build would lose them (finding F1)"
    )


def test_rm7b_required_json_resources_are_tracked():
    """Every JSON the app loads at runtime must be tracked by git.

    This is the F1 class. `*.json` is ignored wholesale, so a resource added
    later is untracked by default — it keeps working locally, where the file
    exists, and vanishes from every clone and every build.
    """
    tracked = set(_tracked_files())

    required: list[Path] = sorted((REPO_ROOT / "themes").glob("*.json"))
    assert required, "no theme JSON files found at all"
    required.append(REPO_ROOT / "src/getmoredone/email_cleaning_rules.json")

    untracked = [
        str(p.relative_to(REPO_ROOT))
        for p in required
        if p.exists() and str(p.relative_to(REPO_ROOT)) not in tracked
    ]
    assert not untracked, (
        f"JSON resources the app loads at runtime are NOT tracked by git: "
        f"{untracked}. The blanket *.json ignore swallowed them — add a "
        "'!' exception in .gitignore."
    )


def test_rm7b_tracked_json_resources_are_valid_json():
    """A tracked-but-corrupt resource fails at launch, not at commit time."""
    broken = []
    for rel in _tracked_files():
        if not rel.endswith(".json"):
            continue
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as exc:
            broken.append(f"{rel}: {exc}")
    assert not broken, f"tracked JSON files that do not parse: {broken}"


def test_rm7b_ignore_rules_do_not_exclude_a_bundled_resource():
    """Ask git directly whether it would ignore each file the spec bundles.

    Checks behaviour rather than reading the rules, so a future rule change
    that shadows an exception is caught (P16: diagnose the running system).
    """
    from tests.test_packaging_resources import _analysis_datas

    from tools.packaging_filters import should_bundle

    candidates: list[Path] = []
    for src, dest in _analysis_datas():
        if src.is_dir():
            for p in src.rglob("*"):
                # Judge what actually ships: the packaging filter runs first,
                # so a file it drops cannot be missing from a build.
                if p.is_file() and should_bundle(f"{dest}/{p.relative_to(src).as_posix()}"):
                    candidates.append(p)
        elif src.is_file() and should_bundle(src.name):
            candidates.append(src)

    assert candidates, "the spec bundles nothing — the datas parse failed"

    result = subprocess.run(
        ["git", "check-ignore", "--stdin"],
        cwd=str(REPO_ROOT),
        input="\n".join(str(p.relative_to(REPO_ROOT)) for p in candidates),
        capture_output=True, text=True, timeout=120,
    )
    # check-ignore exits 0 when it found ignored paths, 1 when it found none.
    ignored = [line for line in result.stdout.splitlines() if line.strip()]
    assert not ignored, (
        f"GetMoreDone.spec bundles files that .gitignore excludes, so they are "
        f"missing from every clone and every CI build: {ignored}"
    )
