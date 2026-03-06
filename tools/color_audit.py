#!/usr/bin/env python3
"""Generate docs/ui_color_inventory.md from deterministic ripgrep scans.

Usage:
  ./venv/bin/python tools/color_audit.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "ui_color_inventory.md"

SCAN_COMMANDS: Dict[str, List[str]] = {
    "widget": [
        "rg",
        "-n",
        "fg_color=|hover_color=|text_color=|border_color=|button_color=|progress_color=|selected_color=|corner_radius=|highlight_color=",
        ".",
        "-g",
        "!docs/ui_color_inventory.md",
    ],
    "hex": [
        "rg",
        "-n",
        "#[0-9a-fA-F]{6}\\b|#[0-9a-fA-F]{3}\\b",
        ".",
        "-g",
        "!docs/ui_color_inventory.md",
    ],
    "named": [
        "rg",
        "-n",
        "-i",
        r'"(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)"|\'(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\'',
        ".",
        "-g",
        "!docs/ui_color_inventory.md",
    ],
    "theme_api": [
        "rg",
        "-n",
        "set_default_color_theme\\(|set_appearance_mode\\(",
        ".",
        "-g",
        "!docs/ui_color_inventory.md",
    ],
    "tuples": [
        "rg",
        "-n",
        "(fg_color|hover_color|text_color|border_color|button_color|progress_color|selected_color|highlight_color)\\s*=\\s*(\\(|\\[)",
        ".",
        "-g",
        "!docs/ui_color_inventory.md",
    ],
    "app_settings": [
        "rg",
        "-n",
        "color|theme|appearance_mode|theme_name|drag_schedule_date_text_color|color_hex",
        "src/getmoredone/app_settings.py",
    ],
    "theme_files": [
        "rg",
        "-n",
        "#[0-9a-fA-F]{6}\\b|#[0-9a-fA-F]{3}\\b|\"(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\"|\'(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\'",
        "themes",
        "-g",
        "*.json",
    ],
}

HEX_RE = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
NAMED_RE = re.compile(
    r"(?i)(?:\"|')(?P<c>darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)(?:\"|')"
)
WIDGET_PROP_RE = re.compile(
    r"(fg_color|hover_color|text_color|border_color|button_color|progress_color|selected_color|corner_radius|highlight_color)="
)


@dataclass(frozen=True)
class Entry:
    path: str
    line: int
    snippet: str


def run_rg(cmd: Sequence[str]) -> List[str]:
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    # rg returns 1 when no matches; that is fine.
    if result.returncode not in (0, 1):
        raise RuntimeError(f"Command failed ({result.returncode}): {' '.join(cmd)}\\n{result.stderr}")
    return [ln for ln in result.stdout.splitlines() if ln.strip()]


def parse_line(line: str) -> Entry | None:
    parts = line.split(":", 2)
    if len(parts) < 3:
        return None
    path, line_s, snippet = parts
    if path.startswith("./"):
        path = path[2:]
    try:
        line_no = int(line_s)
    except ValueError:
        return None
    return Entry(path=path, line=line_no, snippet=snippet.strip())


def md_escape(value: str) -> str:
    return value.replace("|", "\\|")


def build_report(lines: Dict[str, List[str]]) -> str:
    hex_occ: List[str] = []
    named_occ: List[str] = []

    for src in ("hex", "theme_files"):
        for line in lines[src]:
            hex_occ.extend(color.lower() for color in HEX_RE.findall(line))

    for src in ("named", "theme_files"):
        for line in lines[src]:
            named_occ.extend(match.group("c").lower() for match in NAMED_RE.finditer(line))

    widget_props = Counter()
    for line in lines["widget"]:
        for prop in WIDGET_PROP_RE.findall(line):
            widget_props[prop] += 1

    occurrences: Dict[str, List[Entry]] = defaultdict(list)
    seen: set[Tuple[str, str, int, str]] = set()

    for src in ("hex", "named", "theme_files"):
        for line in lines[src]:
            entry = parse_line(line)
            if not entry:
                continue
            color_values = [h.lower() for h in HEX_RE.findall(line)]
            color_values.extend(m.group("c").lower() for m in NAMED_RE.finditer(line))
            for value in color_values:
                key = (value, entry.path, entry.line, entry.snippet)
                if key in seen:
                    continue
                seen.add(key)
                occurrences[value].append(entry)

    for value in list(occurrences):
        occurrences[value] = sorted(occurrences[value], key=lambda e: (e.path, e.line, e.snippet))

    theme_api_entries = sorted(
        (entry for entry in (parse_line(line) for line in lines["theme_api"]) if entry),
        key=lambda e: (e.path, e.line),
    )
    tuple_entries = [entry for entry in (parse_line(line) for line in lines["tuples"]) if entry]

    out: List[str] = []
    out.append("# UI Color Inventory")
    out.append("")
    out.append("Generated via deterministic `rg` scans from repo root.")
    out.append("")
    out.append("## Scan Commands")
    out.append("```bash")
    out.append('rg -n "fg_color=|hover_color=|text_color=|border_color=|button_color=|progress_color=|selected_color=|corner_radius=|highlight_color=" .')
    out.append('rg -n "#[0-9a-fA-F]{6}\\b|#[0-9a-fA-F]{3}\\b" .')
    out.append(r'rg -n -i "\"(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\"|\'(darkgreen|green|red|orange|blue|teal|cyan|yellow|white|black|gray|grey)\'" .')
    out.append('rg -n "set_default_color_theme\\(|set_appearance_mode\\(" .')
    out.append("```")
    out.append("")
    out.append("## 1) Summary Counts By Type")
    out.append("")
    out.append(f"- Hex colors (match count): **{len(hex_occ)}**")
    out.append(f"- Named colors (match count): **{len(named_occ)}**")
    out.append(f"- Tuple colors / appearance tuples (match count): **{len(lines['tuples'])}**")
    out.append(
        "- CustomTkinter theme API usage (`set_default_color_theme`/`set_appearance_mode`) "
        f"line count: **{len(lines['theme_api'])}**"
    )
    out.append(f"- Widget explicit overrides (line count): **{len(lines['widget'])}**")
    out.append("")
    out.append("Widget override property breakdown:")
    out.append("")
    out.append("| Property | Count |")
    out.append("|---|---:|")
    for prop, count in sorted(widget_props.items()):
        out.append(f"| `{prop}` | {count} |")
    out.append("")
    out.append("AppSettings persisted color/theme fields:")
    out.append("")
    out.append("```text")
    out.extend(lines["app_settings"])
    out.append("```")
    out.append("")
    out.append("Hex top values:")
    out.append("")
    out.append("| Color | Count |")
    out.append("|---|---:|")
    for color, count in Counter(hex_occ).most_common(20):
        out.append(f"| `{color}` | {count} |")
    out.append("")
    out.append("Named top values:")
    out.append("")
    out.append("| Color | Count |")
    out.append("|---|---:|")
    for color, count in Counter(named_occ).most_common():
        out.append(f"| `{color}` | {count} |")
    out.append("")
    out.append("## 2) Complete Occurrence Table (Grouped by Color Value, then File)")
    out.append("")
    out.append("Each row is from grep output and includes `file:line` and a short snippet.")
    out.append("")
    for color in sorted(occurrences.keys()):
        out.append(f"### `{color}`")
        out.append("")
        out.append("| File:Line | Snippet |")
        out.append("|---|---|")
        for entry in occurrences[color]:
            snippet = md_escape(entry.snippet)[:180]
            out.append(f"| `{entry.path}:{entry.line}` | `{snippet}` |")
        out.append("")

    out.append("### Theme API Occurrences")
    out.append("")
    out.append("| File:Line | Snippet |")
    out.append("|---|---|")
    for entry in theme_api_entries:
        snippet = md_escape(entry.snippet)[:200]
        out.append(f"| `{entry.path}:{entry.line}` | `{snippet}` |")
    out.append("")

    out.append("### Tuple / Appearance Tuple Occurrences")
    out.append("")
    out.append("| File:Line | Snippet |")
    out.append("|---|---|")
    for entry in tuple_entries:
        snippet = md_escape(entry.snippet)[:200]
        out.append(f"| `{entry.path}:{entry.line}` | `{snippet}` |")
    out.append("")

    out.append("## 3) Replace Plan")
    out.append("")
    out.append("Recommended migration targets:")
    out.append("")
    out.append("- **Theme defaults (JSON-driven):**")
    out.append("- Base CTk widget palette defaults (`CTkButton`, `CTkFrame`, `CTkEntry`, `CTkCheckBox`, `CTkSwitch`, etc.) should stay in `/themes/*.json`.")
    out.append("- Remove one-off color literals that duplicate core palette choices.")
    out.append("- **Semantic tokens (code-level):**")
    out.append("- Route UI state colors through semantic names in `src/getmoredone/theme.py` (e.g., `primary`, `primary_hover`, `ghost_hover`, `selected_tint`, `critical_tint`, `success_tint`, `muted_text`, `border`).")
    out.append("- Convert direct `fg_color`/`hover_color`/`text_color` literals in screens to semantic token lookups.")
    out.append("- **Allowed data-driven colors:**")
    out.append("- Keep `segment_descriptions.color_hex` as the only domain data-driven color source.")
    out.append("- Restrict segment colors to accent/chip/stripe/icon usage; avoid full-row fills.")
    out.append("- **Persisted settings:**")
    out.append("- Keep only settings-level color fields that are user-configurable and intentional (`drag_schedule_date_text_color`) plus theme selectors (`appearance_mode`, `theme_name`).")
    out.append("")
    out.append("## 4) Hard Rule")
    out.append("")
    out.append("**No new hard-coded colors except data-driven segment colors (`segment_descriptions.color_hex`).**")
    out.append("")
    out.append("Enforcement recommendation: run the same `rg` commands in CI and diff this inventory after refactors.")
    out.append("")

    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    scan_results: Dict[str, List[str]] = {}
    for name, cmd in SCAN_COMMANDS.items():
        scan_results[name] = run_rg(cmd)

    report = build_report(scan_results)
    output_path = args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"Wrote {output_path}")
    print(f"Hex matches: {len(scan_results['hex'])}")
    print(f"Named matches: {len(scan_results['named'])}")
    print(f"Widget override lines: {len(scan_results['widget'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
