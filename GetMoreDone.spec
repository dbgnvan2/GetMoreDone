# -*- mode: python ; coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

# PyInstaller provides SPECPATH pointing at the directory containing this spec.
PROJECT_ROOT = Path(SPECPATH).resolve()
SRC_PATH = str(PROJECT_ROOT / "src")

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
    datas=[(str(PROJECT_ROOT / "assets"), "assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="GetMoreDone",
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
    icon=None,
    bundle_identifier=None,
)
