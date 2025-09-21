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

# Prefer dedicated icon pack under repo root: ../NeXroll_ICON
icon_dir = os.path.abspath(os.path.join(project_root, "..", "NeXroll_ICON"))
ico_path = None
try:
    if os.path.isdir(icon_dir):
        # Prefer a 64x64 ICO if present, else any .ico in that folder
        cands = [os.path.join(icon_dir, f) for f in os.listdir(icon_dir) if f.lower().endswith("64x64.ico")]
        if not cands:
            cands = [os.path.join(icon_dir, f) for f in os.listdir(icon_dir) if f.lower().endswith(".ico")]
        if cands:
            ico_path = cands[0]
except Exception:
    ico_path = None

if not ico_path or not os.path.exists(ico_path):
    # Fallback to frontend favicon if dedicated pack not found
    ico_path = os.path.join(project_root, "frontend", "favicon.ico")
    if not os.path.exists(ico_path):
        alt = os.path.join(os.getcwd(), "NeXroll", "frontend", "favicon.ico")
        if os.path.exists(alt):
            ico_path = alt

# App icon (used for embedded EXE icon and bundled as data)
# ico_path resolved above via project_root (with fallback if needed)

# Prefer built React assets if available; fall back to source 'frontend'
fe_dir = os.path.join(project_root, 'frontend', 'build')
if not os.path.isdir(fe_dir):
    fe_dir = os.path.join(project_root, 'frontend')

# Ensure favicon.ico in the served frontend is our dedicated icon (if available)
try:
    if ico_path and os.path.isfile(ico_path):
        import shutil
        tgt = os.path.join(fe_dir, 'favicon.ico')
        os.makedirs(os.path.dirname(tgt), exist_ok=True)
        shutil.copy2(ico_path, tgt)
except Exception:
    pass

# Optional bundled default assets (only if present in repo)
_data_dir_cand = os.path.join(project_root, 'nexroll_backend', 'data')
_extra_datas = []
if os.path.isdir(_data_dir_cand):
    _extra_datas.append((_data_dir_cand, 'nexroll_backend/data'))

a = Analysis(
    [launcher],
    pathex=[project_root],
    binaries=_backend_bins,
    datas=[
        (fe_dir, 'frontend'),
        (ico_path, 'frontend'),
    ] + (
        [ (icon_dir, 'NeXroll_ICON') ] if os.path.isdir(icon_dir) else []
    ) + _backend_datas + _extra_datas,
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
    version=os.path.join(project_root, "version_info.txt"),
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