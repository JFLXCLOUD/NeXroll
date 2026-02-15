# -*- coding: utf-8 -*-
"""
PyInstaller launcher for NeXroll.
Imports backend.main which auto-starts the FastAPI server when frozen.
"""
import sys  # noqa: F401
import ctypes

# Single-instance check for the backend server
MUTEX_NAME = "Global\\NeXroll_Backend_SingleInstance_Mutex"

def _check_single_instance():
    """Check if another backend instance is running. Exit if so."""
    try:
        kernel32 = ctypes.windll.kernel32
        ERROR_ALREADY_EXISTS = 183
        
        mutex = kernel32.CreateMutexW(None, True, MUTEX_NAME)
        last_error = kernel32.GetLastError()
        
        if last_error == ERROR_ALREADY_EXISTS:
            # Another instance is already running
            if mutex:
                kernel32.CloseHandle(mutex)
            print("NeXroll backend is already running. Exiting.")
            sys.exit(0)
        # Keep mutex handle alive (don't close it) so the mutex persists
    except Exception as e:
        # If mutex fails, continue anyway (fallback behavior)
        print(f"Single-instance check failed: {e}")

# Check for single instance before loading the heavy backend
_check_single_instance()

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