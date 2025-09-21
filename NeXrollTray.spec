# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec to build the NeXroll system tray application (onefile)

import os

block_cipher = None

# Resolve spec directory as project root with repo-root fallback
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
entry_script = os.path.join(project_root, "tray_app.py")

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

a = Analysis(
    [entry_script],
    pathex=[project_root],
    binaries=[],
    datas=[
        (ico_path, 'frontend'),
    ] + (
        [ (icon_dir, 'NeXroll_ICON') ] if os.path.isdir(icon_dir) else []
    ),
    hiddenimports=[
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NeXrollTray',
    icon=ico_path,
    version=os.path.join(project_root, "version_info.txt"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # tray app should be background/GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = [exe]