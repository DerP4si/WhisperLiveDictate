# -*- mode: python ; coding: utf-8 -*-
import os
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs

# Absolute Pfadauflösung für den Ordner, in dem die .spec liegt
SPECPATH = os.path.abspath(os.path.dirname(SPEC))

datas = []
binaries = []
hiddenimports = ['faster_whisper', 'ctranslate2', 'sounddevice', 'pynput', 'customtkinter']

# Packages sammeln
packages_to_collect = ['faster_whisper', 'ctranslate2', 'customtkinter']
for pkg in packages_to_collect:
    tmp_datas, tmp_binaries, tmp_hidden = collect_all(pkg)
    datas.extend(tmp_datas)
    binaries.extend(tmp_binaries)
    hiddenimports.extend(tmp_hidden)

binaries.extend(collect_dynamic_libs('sounddevice'))

a = Analysis(
    ['main.py', 'utils.py'],  # <-- WICHTIG: utils.py hier direkt als zweite Einstiegs/Quell-Datei eintragen!
    pathex=[SPECPATH],
    binaries=binaries,
    datas=datas,
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
    a.binaries,
    a.datas,
    [],
    name='WhisperLiveDictate1.2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
)