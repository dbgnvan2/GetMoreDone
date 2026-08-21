# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# PyInstaller provides SPECPATH pointing at the directory containing this spec.
PROJECT_ROOT = Path(SPECPATH).resolve()
SRC_PATH = str(PROJECT_ROOT / "src")

# Which collected files belong in a distribution is decided in a real module so
# it can be unit-tested; a spec file cannot be imported. See
# tests/test_packaging_filters.py.
sys.path.insert(0, str(PROJECT_ROOT))
from tools.packaging_filters import filter_datas

# Be conservative with hidden imports; GUI + google libs sometimes need nudging.
hiddenimports = []
hiddenimports += collect_submodules("getmoredone")
hiddenimports += collect_submodules("google")
hiddenimports += collect_submodules("googleapiclient")

# pygame is notoriously hooky across platforms; include its submodules.
hiddenimports += collect_submodules("pygame")


a = Analysis(
    ["run.py"],
    pathex=[SRC_PATH],
    binaries=[],
    # Every folder the app reads through paths.resource_root() at runtime must
    # appear here, or the frozen build dies before its first window. themes/ was
    # missing until 2026-08-18 and every binary ever released crashed on launch
    # (FileNotFoundError inside CustomTkinter's ThemeManager.load_theme).
    # Guarded by tests/test_packaging_resources.py::test_rm1a_frozen_mode_resource_root_finds_bundled_themes
    # No audio/ entry: no music ships (spec D3); users point Settings at their own folder.
    datas=[
        (str(PROJECT_ROOT / "assets"), "assets"),
        (str(PROJECT_ROOT / "themes"), "themes"),
        # Licence texts must accompany the distribution — the LGPL requires it
        # for pygame. Guarded by tests/test_release_licensing.py.
        (str(PROJECT_ROOT / "licenses"), "licenses"),
        (str(PROJECT_ROOT / "LICENSE"), "."),
        (str(PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"), "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

# Drop what an end user running the app does not need. Overwhelmingly this is
# googleapiclient's discovery cache: PyInstaller collects a discovery document
# for every Google API (~93 MB, 569 files) and this app builds exactly two
# services. Report the drop rather than shrinking the build silently.
a.datas, _dropped = filter_datas(a.datas)
print(f"[packaging] excluded {len(_dropped)} file(s) not needed at runtime; "
      f"{len(a.datas)} remain")

# The Windows .exe carries its own icon resource; the macOS .app takes its
# icon from BUNDLE below and ignores this one. EXE had no icon= at all, so the
# Windows build has been shipping PyInstaller's default console icon.
EXE_ICON = (
    str(PROJECT_ROOT / "assets" / "icons" / "davipa.ico")
    if sys.platform == "win32"
    else None
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GetMoreDone",
    icon=EXE_ICON,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

# One-folder output (COLLECT), never --onefile. pygame ships under the LGPL,
# which permits use in a proprietary product only if the user can replace/relink
# the library — that requires the shared libraries to stay as separate files.
# Guarded by tests/test_packaging_resources.py::test_rm1d_spec_uses_onefolder_not_onefile
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="GetMoreDone",
)

app = BUNDLE(
    coll,
    name="GetMoreDone.app",
    icon=str(PROJECT_ROOT / "assets" / "icons" / "davipa.icns"),
    bundle_identifier=None,
)
