# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for packaging setup_plex_token.py as a standalone CLI tool

import os

block_cipher = None

# Resolve project root to the NeXroll directory regardless of launch CWD
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
script_path = os.path.join(project_root, "setup_plex_token.py")

# Icon: prefer dedicated icon pack if present, else fallback to frontend favicon
import os as _os
icon_dir = _os.path.abspath(_os.path.join(project_root, "..", "NeXroll_ICON"))
ico_path = None
try:
    if _os.path.isdir(icon_dir):
        cands = [_os.path.join(icon_dir, f) for f in _os.listdir(icon_dir) if f.lower().endswith("64x64.ico")]
        if not cands:
            cands = [_os.path.join(icon_dir, f) for f in _os.listdir(icon_dir) if f.lower().endswith(".ico")]
        if cands:
            ico_path = cands[0]
except Exception:
    ico_path = None

if not ico_path or not _os.path.exists(ico_path):
    ico_path = os.path.join(project_root, "frontend", "favicon.ico")
    if not os.path.exists(ico_path):
        alt = os.path.join(os.getcwd(), "NeXroll", "frontend", "favicon.ico")
        if os.path.exists(alt):
            ico_path = alt

a = Analysis(
    [script_path],
    pathex=[project_root],
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