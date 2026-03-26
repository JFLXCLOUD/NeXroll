# -*- mode: python ; coding: utf-8 -*-


import os
spec_root = os.path.abspath(SPECPATH)
project_root = os.path.dirname(spec_root)
frontend_build = os.path.join(project_root, 'NeXroll', 'frontend', 'build')

a = Analysis(
    ['..\\NeXroll\\backend\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (frontend_build, 'frontend/build'),
        (os.path.join(project_root, 'NeXroll', 'CHANGELOG.md'), '.'),
        (os.path.join(project_root, 'docs', 'lefty-blue-wednesday-main-version-36162-02-38.mp3'), 'docs'),
    ],
    hiddenimports=['backend.radarr_connector', 'backend.dynamic_preroll', 'httpx', 'httpx._transports', 'httpx._transports.default', 'httpcore', 'h11', 'h2', 'hpack', 'hyperframe', 'yt_dlp'],
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
    name='NeXroll',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disabled - causes ordinal 380 error with Python 3.10+
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=os.path.join(project_root, 'NeXroll', 'version_info.txt'),
    icon=['NeXroll_ICON\\icon_1758297097_48x48.ico'],
)
