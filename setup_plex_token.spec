# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for packaging setup_plex_token.py as a standalone CLI tool

import os

block_cipher = None
project_root = os.getcwd()
script_path = os.path.join(project_root, "NeXroll", "setup_plex_token.py")
ico_path = os.path.join(project_root, "NeXroll", "frontend", "favicon.ico")

a = Analysis(
    [script_path],
    pathex=[os.path.join(project_root, "NeXroll")],
    binaries=[],
    datas=[
        (ico_path, 'frontend'),
    ],
    hiddenimports=[
        # stdlib modules are discovered automatically; keep list minimal
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    icon=ico_path,
    name='setup_plex_token',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # interactive prompts shown in console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = [exe]