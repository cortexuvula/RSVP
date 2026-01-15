# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for RSVP Reader."""

import sys
from pathlib import Path

block_cipher = None

# Determine platform-specific settings
if sys.platform == 'win32':
    icon_file = 'icon.ico' if Path('icon.ico').exists() else None
    console = False
elif sys.platform == 'darwin':
    icon_file = 'icon.icns' if Path('icon.icns').exists() else None
    console = False
else:
    icon_file = None
    console = False

a = Analysis(
    ['rsvp/main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RSVP Reader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=console,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='RSVP Reader.app',
        icon=icon_file,
        bundle_identifier='com.rsvp.reader',
        info_plist={
            'NSHighResolutionCapable': 'True',
            'CFBundleShortVersionString': '1.0.0',
        },
    )
