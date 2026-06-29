# -*- mode: python ; coding: utf-8 -*-
#
# Ricetta PyInstaller per l'EDITOR (un unico file eseguibile).
#
#   pip install pyinstaller
#   pyinstaller editor.spec
#
# Il risultato finisce in dist/.  Da lanciare SU ciascun sistema operativo di
# destinazione (PyInstaller non fa cross-compilazione).

import os

RADICE = SPECPATH

a = Analysis(
    [os.path.join(RADICE, 'gui', 'editor.py')],
    pathex=[RADICE],
    binaries=[],
    datas=[(os.path.join(RADICE, 'avventure'), 'avventure'),
           (os.path.join(RADICE, 'gui', 'assets'), os.path.join('gui', 'assets'))],
    hiddenimports=['advcore', 'gui'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Pasifae-Editor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(RADICE, 'gui', 'assets', 'pasifae.ico'),
)
