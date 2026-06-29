# -*- mode: python ; coding: utf-8 -*-


import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata

spec_root = os.path.abspath(SPECPATH)
project_root = os.path.dirname(spec_root)
frontend_build = os.path.join(project_root, 'NeXroll', 'frontend', 'build')

# yt-dlp discovers PO-token plugins (bgutil) via the `yt_dlp_plugins` namespace
# package at runtime. In a frozen build those submodules aren't picked up
# automatically, so collect them explicitly — otherwise the installed app can't
# mint PO tokens and YouTube trailer downloads fall back to the bot wall.
_potoken_hidden = collect_submodules('yt_dlp_plugins')
# include_py_files=True is essential: yt-dlp discovers plugins by scanning the
# yt_dlp_plugins namespace package's path for modules. Without the .py files on
# disk a frozen build ships only the EMPTY namespace package, so the bgutil
# plugin never loads and PO-token downloads silently fail (the provider server
# runs, but yt-dlp can't talk to it).
_potoken_datas = collect_data_files('yt_dlp_plugins', include_py_files=True)
try:
    _potoken_datas += copy_metadata('bgutil-ytdlp-pot-provider')
except Exception:
    pass

# Bundle the NeXroll Intros (Jellyfin) plugin zip so the running app can serve it
# for download from the Connect page (/jellyfin/plugin/download). Built by
# Plugins/NeXroll.Jellyfin/package.ps1 before this spec runs; harmless if absent.
import glob as _glob
_plugin_datas = [
    (z, 'plugins')
    for z in _glob.glob(os.path.join(project_root, 'Plugins', 'NeXroll.Jellyfin', 'NeXroll.Jellyfin*.zip'))
]

a = Analysis(
    ['..\\NeXroll\\backend\\main.py'],
    pathex=[],
    binaries=[],
    datas=[
        (frontend_build, 'frontend/build'),
        (os.path.join(project_root, 'NeXroll', 'CHANGELOG.md'), '.'),
        (os.path.join(project_root, 'docs', 'lefty-blue-wednesday-main-version-36162-02-38.mp3'), 'docs'),
    ] + _potoken_datas + _plugin_datas,
    hiddenimports=['backend.radarr_connector', 'backend.dynamic_preroll', 'httpx', 'httpx._transports', 'httpx._transports.default', 'httpcore', 'h11', 'h2', 'hpack', 'hyperframe', 'yt_dlp', 'yt_dlp_plugins', 'yt_dlp_plugins.extractor', 'yt_dlp_plugins.extractor.getpot_bgutil', 'yt_dlp_plugins.extractor.getpot_bgutil_http', 'yt_dlp_plugins.extractor.getpot_bgutil_script'] + _potoken_hidden,
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
