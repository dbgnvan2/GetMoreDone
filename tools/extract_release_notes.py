#!/usr/bin/env python3
"""Extract one version's section from CHANGELOG.md for a GitHub Release body.

Purpose: make the published release notes come from the repo, so the two cannot
         drift apart.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m4c
Tests:   tests/test_release_notes.py

Usage:
    python tools/extract_release_notes.py v0.1.0 --output RELEASE_NOTES.md
    python tools/extract_release_notes.py 0.1.0            # prints to stdout

This is a script rather than a few lines of inline YAML because a check that
lives only in a workflow cannot be run — or tested — before a push.

It exits non-zero when the requested version has no section. Publishing a
release with an empty body because a heading was renamed is exactly the silent
producer/consumer drift this is meant to prevent (P19): "found nothing" and
"the format changed" must not look the same.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHANGELOG = REPO_ROOT / "CHANGELOG.md"

# Matches "## [0.1.0] - 2026-08-18" and "## [0.1.0]".
VERSION_HEADING = re.compile(r"^##\s*\[(?P<version>[^\]]+)\]", re.MULTILINE)


def normalise_version(raw: str) -> str:
    """Accept `v0.1.0`, `0.1.0`, or `refs/tags/v0.1.0`."""
    version = (raw or "").strip()
    if version.startswith("refs/tags/"):
        version = version[len("refs/tags/"):]
    return version.lstrip("vV")


def available_versions(changelog: str) -> list[str]:
    return [m.group("version") for m in VERSION_HEADING.finditer(changelog)]


def extract_section(changelog: str, version: str) -> str:
    """Return the body of one version's section, without its heading.

    Raises:
        KeyError: the version has no section.
        ValueError: the section exists but is empty.
    """
    wanted = normalise_version(version)

    matches = list(VERSION_HEADING.finditer(changelog))
    for index, match in enumerate(matches):
        if normalise_version(match.group("version")) != wanted:
            continue
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        body = changelog[start:end]
        # Drop the remainder of the heading line (the date), keep the rest.
        body = body.split("\n", 1)[1] if "\n" in body else ""
        # Trailing link-reference definitions belong to the file, not the release.
        body = re.sub(r"^\[[^\]]+\]:\s*http\S+\s*$", "", body, flags=re.MULTILINE)
        body = body.strip()
        if not body:
            raise ValueError(f"CHANGELOG section for {wanted} is empty")
        return body

    raise KeyError(wanted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("version", help="release tag or version, e.g. v0.1.0")
    parser.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG)
    parser.add_argument("--output", type=Path, default=None,
                        help="write here instead of stdout")
    args = parser.parse_args(argv)

    if not args.changelog.exists():
        print(f"error: no changelog at {args.changelog}", file=sys.stderr)
        return 2

    text = args.changelog.read_text(encoding="utf-8")
    try:
        body = extract_section(text, args.version)
    except KeyError:
        print(
            f"error: CHANGELOG.md has no section for {args.version!r}. "
            f"Available: {available_versions(text)}",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.output:
        args.output.write_text(body + "\n", encoding="utf-8")
        print(f"wrote {len(body)} chars to {args.output}")
    else:
        print(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
