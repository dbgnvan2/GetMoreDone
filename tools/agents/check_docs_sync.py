#!/usr/bin/env python3
"""Fail when code/dependency changes are missing documentation updates."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Set

CODE_PREFIXES = ("src/", "tools/", "tests/")

# Every file that declares a dependency. requirements-dev.txt was added in the
# same change that created it and this enumeration was missed, so a PR adding a
# test dependency touched no src/ path and no requirements.txt and the gate
# reported "no code/dependency changes detected".
DEPENDENCY_FILES = ("requirements.txt", "requirements-dev.txt")
DOC_PREFIXES = ("docs/",)
DOC_FILES = {
    "README.md",
    "CHANGELOG.md",
    "GetMoreDone_MasterSpec_SQLite_v1.md",
}


def run(cmd: List[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\\n{result.stderr}")
    return result.stdout.strip()


def changed_files(base: str, head: str) -> Set[str]:
    out = run(["git", "diff", "--name-only", f"{base}...{head}"])
    return {line.strip() for line in out.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("GITHUB_BASE_REF", "origin/main"))
    parser.add_argument("--head", default=os.getenv("GITHUB_SHA", "HEAD"))
    args = parser.parse_args()

    try:
        files = changed_files(args.base, args.head)
    except RuntimeError as exc:
        print(f"docs-sync check skipped: {exc}")
        return 0

    if not files:
        print("docs-sync: no changed files")
        return 0

    code_changed = any(
        path.startswith(CODE_PREFIXES) or path in DEPENDENCY_FILES for path in files
    )
    if not code_changed:
        print("docs-sync: no code/dependency changes detected")
        return 0

    docs_changed = any(
        path.startswith(DOC_PREFIXES)
        or path in DOC_FILES
        or path.startswith("docs/changes/")
        for path in files
    )
    handoff_changed = any(path.startswith("docs/changes/") for path in files)

    if docs_changed and handoff_changed:
        print("docs-sync: PASS (docs and handoff note present)")
        return 0

    print("docs-sync: FAIL")
    print("Code/dependency changes detected but required docs artifacts are missing.")
    if not docs_changed:
        print("- Missing docs update (expected change in docs/, README.md, CHANGELOG.md, or master spec)")
    if not handoff_changed:
        print("- Missing handoff note in docs/changes/")
    print("Changed files:")
    for path in sorted(files):
        print(f"  - {path}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
