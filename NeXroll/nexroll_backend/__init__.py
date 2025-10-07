"""
NeXroll backend package initializer.

This file ensures Python treats the 'backend' directory as a proper package
so absolute imports like 'from backend.database import SessionLocal' resolve
correctly in both source and PyInstaller-frozen environments.
"""
__all__ = [
    "database",
    "models",
    "scheduler",
    "plex_connector",
]