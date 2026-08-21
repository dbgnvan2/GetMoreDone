"""Packaging-resource tests for the downloadable release.

Purpose: prove that a frozen (PyInstaller) build carries every resource the app
         reads at runtime, and that theme resolution cannot raise on a bad name.
Spec:    docs/spec_2026-08-18_downloadable_release.md#r-m1
Tests:   this file

The load-bearing test here is ``test_rm1a_frozen_mode_resource_root_finds_bundled_themes``.
It materialises a temp directory laid out exactly as ``daVIPA.spec`` bundles
resources, points ``sys._MEIPASS`` at it, and then asks the real resolver for a
theme. That is finding F1: the spec bundled only ``assets``, so every binary the
release workflow ever produced died with ``FileNotFoundError`` inside
CustomTkinter's ``ThemeManager.load_theme`` before a window appeared.
"""

from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path

import pytest

from src.getmoredone import paths, theme

# This whole file asserts on the REPOSITORY — workflows, packaging, licences,
# docs, traceability — not on application behaviour. Marked `meta` so
# `pytest -m "not meta"` gives a fast app-only run. The default `pytest` run
# still includes it: the marker is for speed, never for skipping.
pytestmark = pytest.mark.meta

REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC_FILE = REPO_ROOT / "daVIPA.spec"


# --------------------------------------------------------------------------
# Reading the PyInstaller spec without executing it
# --------------------------------------------------------------------------

def _analysis_datas() -> list[tuple[Path, str]]:
    """Return the ``datas`` entries from daVIPA.spec as (source, dest) pairs.

    The spec cannot simply be imported — it references PyInstaller globals such
    as ``SPECPATH``, ``Analysis`` and ``COLLECT``. So the ``datas`` keyword is
    located with the AST and only that expression is evaluated, in a namespace
    holding the same ``PROJECT_ROOT`` the spec computes.
    """
    tree = ast.parse(SPEC_FILE.read_text(encoding="utf-8"), filename=str(SPEC_FILE))

    datas_node = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "Analysis":
            for kw in node.keywords:
                if kw.arg == "datas":
                    datas_node = kw.value
    assert datas_node is not None, "daVIPA.spec has no Analysis(datas=...) keyword"

    namespace = {"PROJECT_ROOT": REPO_ROOT, "Path": Path, "str": str}
    try:
        raw = eval(ast.unparse(datas_node), {"__builtins__": {}}, namespace)  # noqa: S307
    except NameError as exc:
        pytest.fail(
            f"daVIPA.spec datas= uses a name this test cannot evaluate ({exc}). "
            "Extend the namespace in _analysis_datas() rather than deleting this test."
        )
    return [(Path(src), str(dest)) for src, dest in raw]


def _spec_text() -> str:
    return SPEC_FILE.read_text(encoding="utf-8")


def _without_comments(text: str) -> str:
    """Strip ``#`` comments so these tests judge what a file *does*, not what it says.

    Both files below carry comments that name the very thing being prohibited
    (``--onefile``, ``./venv/bin/pyinstaller``) in order to explain why it is
    prohibited. A naive substring search would flag the explanation as the
    offence and pressure the next person to delete the reasoning.
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


# --------------------------------------------------------------------------
# R-M1.A.1 — every runtime resource is bundled
# --------------------------------------------------------------------------

def test_rm1a1_spec_bundles_themes_dir():
    """themes/ must reach the frozen bundle — this is finding F1."""
    dests = {dest.strip("/") for _src, dest in _analysis_datas()}
    assert "themes" in dests, (
        "daVIPA.spec does not bundle themes/. Every frozen build will "
        f"crash on launch loading its color theme. Bundled: {sorted(dests)}"
    )


def test_rm1a1_bundled_data_sources_exist_in_the_repo():
    """A datas entry pointing at a missing folder bundles nothing, silently."""
    missing = [str(src) for src, _dest in _analysis_datas() if not src.exists()]
    assert not missing, f"daVIPA.spec bundles paths that do not exist: {missing}"


def test_rm1a1_every_selectable_theme_resolves_to_existing_file():
    """Every theme reachable from Settings resolves to a real file on disk."""
    unresolved = [
        name for name in theme.THEME_NAMES
        if not paths.resolve_theme_path(name).exists()
    ]
    assert not unresolved, f"Selectable themes with no theme file: {unresolved}"


def test_rm1a1_selectable_theme_names_all_have_a_matching_json():
    """THEME_NAMES and themes/*.json must not drift apart."""
    on_disk = {p.stem for p in (REPO_ROOT / "themes").glob("*.json")}
    offered_but_absent = sorted(set(theme.THEME_NAMES) - on_disk)
    assert not offered_but_absent, (
        f"Settings offers themes with no JSON file: {offered_but_absent}"
    )


# --------------------------------------------------------------------------
# R-M1.A.2 — a bad theme name can never crash the app
# --------------------------------------------------------------------------

@pytest.mark.parametrize("bad_name", ["", "   ", "nope", "APPLE_GREY!!", None])
def test_rm1a2_unknown_theme_name_falls_back_to_existing_file(bad_name):
    resolved = paths.resolve_theme_path(bad_name)
    assert resolved.exists(), f"{bad_name!r} resolved to a non-existent file: {resolved}"


@pytest.mark.parametrize("bad_name", ["", "nope", None, 17])
def test_rm1a2_apply_theme_settings_never_raises_on_bad_name(bad_name):
    """apply_theme_settings is called before any window exists — it must not raise."""

    class _Settings:
        appearance_mode = "dark"
        theme_name = bad_name
        list_row_font_size = 14

    mode, name = theme.apply_theme_settings(_Settings())
    assert mode in theme.APPEARANCE_MODES
    assert name in theme.THEME_NAMES


def test_rm1a2_apply_theme_settings_never_raises_when_themes_dir_is_empty(tmp_path, monkeypatch):
    """With the themes folder gone entirely, startup must degrade, not crash.

    This is the frozen-build failure mode: nothing to load, so the app keeps
    CustomTkinter's built-in default rather than dying before the first window.
    """
    monkeypatch.setattr(paths, "bundled_themes_dir", lambda: tmp_path / "themes")

    class _Settings:
        appearance_mode = "dark"
        theme_name = "apple_grey"
        list_row_font_size = 14

    mode, name = theme.apply_theme_settings(_Settings())
    assert (mode, name) == ("dark", "apple_grey")


# --------------------------------------------------------------------------
# R-M1.A.3 — bundled audio is optional (D3: no audio ships)
# --------------------------------------------------------------------------

def test_rm1a3_absent_audio_dir_returns_none(tmp_path, monkeypatch):
    from src.getmoredone.utils import music_library

    monkeypatch.setattr(paths, "resource_root", lambda: tmp_path)
    monkeypatch.setattr(music_library, "bundled_audio_dir", lambda: tmp_path / "audio")

    assert music_library.resolve_music_folder(None) is None
    assert music_library.resolve_music_folder("   ") is None


def test_rm1a3_selftest_does_not_require_bundled_audio(tmp_path, monkeypatch):
    """No audio ships (D3), so its absence must not be a selftest failure."""
    from src.getmoredone import selftest

    monkeypatch.setenv("GETMOREDONE_RESOURCE_ROOT", str(REPO_ROOT))
    monkeypatch.setenv("GETMOREDONE_DB", str(tmp_path / "selftest.db"))
    assert "audio" not in [name for name, _fn in selftest.CHECKS], (
        "the selftest must not require bundled audio — no music ships (D3)"
    )
    assert selftest.run_selftest() == 0


# --------------------------------------------------------------------------
# R-M1.A.* — the frozen-mode test. This is the one that would have caught F1.
# --------------------------------------------------------------------------

def _materialise_frozen_bundle(tmp_path: Path) -> Path:
    """Build a temp dir laid out exactly as daVIPA.spec bundles resources."""
    meipass = tmp_path / "_MEIPASS"
    meipass.mkdir()
    for src, dest in _analysis_datas():
        target = meipass / dest.strip("/")
        if src.is_dir():
            shutil.copytree(src, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
    return meipass


def test_rm1a_frozen_mode_resource_root_finds_bundled_themes(tmp_path, monkeypatch):
    """In a frozen build, every selectable theme must resolve inside _MEIPASS.

    Regression test for F1: the packaged app read themes from ``sys._MEIPASS/themes``
    while the spec bundled only ``assets``.
    """
    meipass = _materialise_frozen_bundle(tmp_path)

    monkeypatch.delenv("GETMOREDONE_RESOURCE_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    assert paths.resource_root() == meipass.resolve()

    missing = [
        name for name in theme.THEME_NAMES
        if not paths.resolve_theme_path(name).exists()
    ]
    assert not missing, (
        "Frozen build cannot find these themes — the app crashes on launch: "
        f"{missing}. Add the folder to datas= in daVIPA.spec."
    )


def test_rm1a_frozen_bundled_themes_are_parseable_json(tmp_path, monkeypatch):
    """Present is not enough — CustomTkinter json.loads() the file it opens."""
    meipass = _materialise_frozen_bundle(tmp_path)

    monkeypatch.delenv("GETMOREDONE_RESOURCE_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)

    for name in theme.THEME_NAMES:
        path = paths.resolve_theme_path(name)
        loaded = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(loaded, dict) and loaded, f"{name} theme is empty or not an object"


def test_rm1a_resource_root_env_override_wins(tmp_path, monkeypatch):
    """GETMOREDONE_RESOURCE_ROOT lets tests and CI point at a specific layout."""
    monkeypatch.setenv("GETMOREDONE_RESOURCE_ROOT", str(tmp_path))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "never-used"), raising=False)

    assert paths.resource_root() == tmp_path.resolve()


# --------------------------------------------------------------------------
# R-M1.C — the build scripts' fallback path must actually work (F6)
# --------------------------------------------------------------------------

def test_rm1c_build_scripts_do_not_hardcode_venv_pyinstaller():
    """build_mac.sh falls back to python3 when venv/ is absent, then called
    ./venv/bin/pyinstaller anyway — the fallback could never have worked."""
    offenders = []
    for script in ("build_mac.sh", "build_windows.ps1"):
        path = REPO_ROOT / script
        if not path.exists():
            continue
        if "venv/bin/pyinstaller" in _without_comments(path.read_text(encoding="utf-8")):
            offenders.append(script)
    assert not offenders, (
        f"{offenders} hardcode ./venv/bin/pyinstaller after falling back to a "
        "system interpreter. Invoke PyInstaller through the chosen interpreter."
    )


def test_rm1c_build_scripts_invoke_pyinstaller_through_the_chosen_interpreter():
    text = (REPO_ROOT / "build_mac.sh").read_text(encoding="utf-8")
    assert "-m PyInstaller" in text or "-m pyinstaller" in text, (
        "build_mac.sh should run PyInstaller as a module of $PY so the venv/"
        "system-python fallback holds for the build step too."
    )


# --------------------------------------------------------------------------
# R-M1.D — one-folder packaging (required by F3: pygame is LGPL)
# --------------------------------------------------------------------------

def test_rm1d_spec_uses_onefolder_not_onefile():
    """LGPL relinking (pygame) requires one-folder output, not --onefile."""
    text = _spec_text()
    assert "COLLECT(" in text, "daVIPA.spec must use COLLECT (one-folder mode)"
    assert "onefile" not in _without_comments(text).lower(), (
        "daVIPA.spec must not build --onefile: pygame is LGPL and the user "
        "must be able to relink it."
    )


def test_rm1d_spec_records_why_onefile_is_prohibited():
    """A bare absence is easy to undo by accident; the reason must be written down."""
    text = _spec_text().lower()
    assert "lgpl" in text, (
        "daVIPA.spec should carry a comment explaining that one-folder "
        "packaging is an LGPL requirement, so nobody 'optimises' it to --onefile."
    )
