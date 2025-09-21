# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec to build the NeXroll Windows Service wrapper

import os

block_cipher = None
# Resolve spec directory as project root with repo-root fallback (mirrors neXroll.spec)
def _resolve_project_root():
    try:
        d = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        d = os.getcwd()
    if os.path.basename(d).lower() != "nexroll":
        cand = os.path.join(d, "NeXroll")
        if os.path.isdir(cand):
            d = cand
    return d

project_root = _resolve_project_root()

# App icon (embedded into EXE) with robust fallback
# Prefer dedicated icon pack under repo root: ../NeXroll_ICON
import os as _os
icon_dir = _os.path.abspath(_os.path.join(project_root, "..", "NeXroll_ICON"))
ico_path = None
try:
    if _os.path.isdir(icon_dir):
        # Prefer a 64x64 ICO if present, else any .ico in that folder
        cands = [_os.path.join(icon_dir, f) for f in _os.listdir(icon_dir) if f.lower().endswith("64x64.ico")]
        if not cands:
            cands = [_os.path.join(icon_dir, f) for f in _os.listdir(icon_dir) if f.lower().endswith(".ico")]
        if cands:
            ico_path = cands[0]
except Exception:
    ico_path = None

if not ico_path or not _os.path.exists(ico_path):
    # Fallback to frontend favicon if dedicated pack not found
    ico_path = _os.path.join(project_root, "frontend", "favicon.ico")
    if not _os.path.exists(ico_path):
        alt = _os.path.join(_os.getcwd(), "NeXroll", "frontend", "favicon.ico")
        if _os.path.exists(alt):
            ico_path = alt

a = Analysis(
    ['windows_service.py'],
    pathex=[project_root],
    binaries=[],
    datas=[
        (ico_path, 'frontend'),
    ] + (
        [ (icon_dir, 'NeXroll_ICON') ] if os.path.isdir(icon_dir) else []
    ),
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
    version=os.path.join(project_root, "version_info.txt"),
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