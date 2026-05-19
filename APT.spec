# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for AIVEX Processing Tool (APT).

Usage:
    pyinstaller APT.spec
"""

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hidden = (
    collect_submodules("apt")
    + collect_submodules("apt.workers")
    + collect_submodules("apt.dialogs")
    + collect_submodules("apt.widgets")
    + collect_submodules("apt.utils")
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('AiV_LOGO.ico', '.'),
        ('apt/resources/AiV_LOGO.ico', 'apt/resources'),
    ],
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='APT',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=['AiV_LOGO.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='APT',
)
