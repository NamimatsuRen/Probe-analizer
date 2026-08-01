# -*- mode: python ; coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, copy_metadata


project_root = Path(SPECPATH).parent
datas = collect_data_files("pyqtgraph") + copy_metadata("probe-analizer")
hiddenimports = [
    "PySide6.QtPrintSupport",
    "PySide6.QtSvg",
    "scipy.optimize",
    "scipy.signal",
]

analysis = Analysis(
    [str(project_root / "src/probe_app/main.py")],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="Probe-Analizer",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
collection = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    name="Probe-Analizer",
)

if sys.platform == "darwin":
    app = BUNDLE(
        collection,
        name="Probe Analizer.app",
        icon=None,
        bundle_identifier="jp.namimatsuren.probe-analizer",
        info_plist={
            "CFBundleShortVersionString": "0.8.0",
            "NSHighResolutionCapable": True,
        },
    )
