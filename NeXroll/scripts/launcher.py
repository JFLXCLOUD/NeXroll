# -*- coding: utf-8 -*-
"""
PyInstaller launcher for NeXroll.
Imports backend.main which auto-starts the FastAPI server when frozen.
"""
import sys  # noqa: F401

# Preload backend submodules to ensure PyInstaller includes them
try:
    import backend.database  # noqa: F401
    import backend.models  # noqa: F401
    import backend.scheduler  # noqa: F401
    import backend.plex_connector  # noqa: F401
except Exception as e:
    print(f"Preload failed: {e}")

# Importing backend.main is enough; it self-starts uvicorn when sys.frozen is True.
try:
    import backend.main as _backend_main  # noqa: F401
except Exception as e:
    # Surface import failures to console for troubleshooting in portable runs.
    print(f"Launcher failed to import backend.main: {e}")
    raise