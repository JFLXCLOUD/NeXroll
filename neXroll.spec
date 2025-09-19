# -*- mode: python ; coding: utf-8 -*-
# Hardened PyInstaller spec for NeXroll production build

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_all

block_cipher = None

# Robustly resolve project root (folder that contains backend/, frontend/)
def _resolve_project_root():
    try:
        d = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        d = os.getcwd()
    # If this spec is executed from repo root, hop into NeXroll/
    if os.path.basename(d).lower() != "nexroll":
        cand = os.path.join(d, "NeXroll")
        if os.path.isdir(cand):
            d = cand
    return d

project_root = _resolve_project_root()
launcher = os.path.join(project_root, "launcher.py")
# Ensure 'backend' is importable when collect_submodules('backend') runs
if project_root not in sys.path:
    sys.path.insert(0, project_root)
# Collect backend package (datas, binaries, hiddenimports) fully to ensure proper packaging
_backend_datas, _backend_bins, _backend_hidden = collect_all('nexroll_backend')

ico_path = os.path.join(project_root, "frontend", "favicon.ico")
if not os.path.exists(ico_path):
    # fallback to repo-root based path if needed
    alt = os.path.join(os.getcwd(), "NeXroll", "frontend", "favicon.ico")
    if os.path.exists(alt):
        ico_path = alt

# App icon (used for embedded EXE icon and bundled as data)
# ico_path resolved above via project_root (with fallback if needed)

# Prefer built React assets if available; fall back to source 'frontend'
fe_dir = os.path.join(project_root, 'frontend', 'build')
if not os.path.isdir(fe_dir):
    fe_dir = os.path.join(project_root, 'frontend')

a = Analysis(
    [launcher],
    pathex=[project_root],
    binaries=_backend_bins,
    datas=[
        (os.path.join(project_root, 'nexroll_backend', 'data'), 'data'),
        (fe_dir, 'frontend'),
        (ico_path, 'frontend'),
    ] + _backend_datas,
    hiddenimports=(_backend_hidden + [
        'nexroll_backend',
        'uvicorn',
        'uvicorn.config',
        'uvicorn.importer',
        'fastapi',
        'starlette',
        'sqlalchemy.dialects.sqlite',
        'sqlalchemy.ext.asyncio',
        'anyio',
        'h11',
        'sniffio',
        'jinja2',
        'requests',
        'ffmpeg',
        'plexapi',
    ]),
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
    name='NeXroll',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = [exe]