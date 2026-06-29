# -*- mode: python ; coding: utf-8 -*-
#
# Ricetta PyInstaller per il PLAYER (un unico file eseguibile).
#
#   pip install pyinstaller
#   pyinstaller player.spec
#
# Il risultato finisce in dist/.  Ricorda: PyInstaller NON fa cross-compilazione,
# quindi questo va lanciato SU ciascun sistema operativo di destinazione
# (Windows per il .exe, macOS per il .app, Linux per il binario Linux).

import os

# SPECPATH è la cartella di questo file: lo usiamo per riferimenti assoluti,
# così lo spec funziona da qualunque cartella tu lanci pyinstaller.
RADICE = SPECPATH

a = Analysis(
    [os.path.join(RADICE, 'gui', 'player.py')],
    pathex=[RADICE],
    binaries=[],
    # PUNTO CIECO di PyInstaller: i file dati non vengono visti dagli import,
    # quindi includiamo a mano la cartella delle avventure.
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
    name='Pasifae-Play',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    runtime_tmpdir=None,
    console=False,            # è una GUI: niente finestra di terminale
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(RADICE, 'gui', 'assets', 'pasifae.ico'),
)
