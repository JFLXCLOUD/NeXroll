# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec to build the NeXroll Windows Service wrapper

import os

block_cipher = None
# Resolve spec directory as project root for reliable relative paths
try:
    project_root = os.path.dirname(os.path.abspath(__file__))
except NameError:
    project_root = os.getcwd()

# App icon (embedded into EXE) with robust fallback
ico_path = os.path.join(project_root, "frontend", "favicon.ico")
if not os.path.exists(ico_path):
    alt = os.path.join(os.getcwd(), "NeXroll", "frontend", "favicon.ico")
    if os.path.exists(alt):
        ico_path = alt

a = Analysis(
    ['windows_service.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        (ico_path, 'frontend'),
    ],
    hiddenimports=[
        'win32timezone',
        'win32service',
        'win32serviceutil',
        'win32event',
        'servicemanager',
        'pywintypes',
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
    name='NeXrollService',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # service should not open console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = [exe]