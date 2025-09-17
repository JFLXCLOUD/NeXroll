# -*- mode: python ; coding: utf-8 -*-
# Hardened PyInstaller spec for NeXroll production build

import os

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
ico_path = os.path.join(project_root, "frontend", "favicon.ico")
if not os.path.exists(ico_path):
    # fallback to repo-root based path if needed
    alt = os.path.join(os.getcwd(), "NeXroll", "frontend", "favicon.ico")
    if os.path.exists(alt):
        ico_path = alt

# App icon (used for embedded EXE icon and bundled as data)
# ico_path resolved above via project_root (with fallback if needed)

a = Analysis(
    ['backend/main.py'],
    pathex=[project_root, os.path.join(project_root, 'backend')],
    binaries=[],
    datas=[
        (os.path.join(project_root, 'backend', 'data'), 'data'),
        (os.path.join(project_root, 'frontend'), 'frontend'),
        (ico_path, 'frontend'),
    ],
    hiddenimports=[
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