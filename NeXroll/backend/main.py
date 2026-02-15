from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form, Request, Query, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, select, func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from pydantic import BaseModel
from typing import List, Optional
import datetime
import pytz
import os
import json
import random
import zipfile
import io
import shutil
import subprocess
from pathlib import Path
from urllib.parse import unquote
import uuid
import time
import re
import asyncio

class DashboardSection(BaseModel):
    id: str
    title: str
    visible: bool
import plexapi
from plexapi.myplex import MyPlexPinLogin, MyPlexAccount

import requests
import sys
import os
import hmac
import hashlib
import base64

# Add the current directory and parent directory to Python path (dev only; avoid in frozen builds)
if not getattr(sys, "frozen", False):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, current_dir)
    sys.path.insert(0, parent_dir)

from backend.database import SessionLocal, engine
import backend.models as models
from backend.plex_connector import PlexConnector
from backend.scheduler import scheduler
from backend import secure_store

models.Base.metadata.create_all(bind=engine)

# Lightweight runtime schema upgrades for older SQLite databases
def _sqlite_has_column(table: str, column: str) -> bool:
    try:
        with engine.connect() as conn:
            res = conn.exec_driver_sql(f'PRAGMA table_info({table})')
            cols = [row[1] for row in res.fetchall()]
            return column in cols
    except Exception as e:
        print(f"Schema check failed for {table}.{column}: {e}")
        return False

def _sqlite_add_column(table: str, ddl: str) -> None:
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql(f'ALTER TABLE {table} ADD COLUMN {ddl}')
            print(f"Schema upgrade: added column {table}.{ddl}")
    except Exception as e:
        # Ignore if already exists or not applicable
        print(f"Schema upgrade skip for {table}.{ddl}: {e}")

def ensure_schema() -> None:
    try:
        if engine.url.drivername.startswith("sqlite"):
            # Categories: ensure apply_to_plex
            if not _sqlite_has_column("categories", "apply_to_plex"):
                _sqlite_add_column("categories", "apply_to_plex BOOLEAN DEFAULT 0")
            # Categories: ensure plex_mode
            if not _sqlite_has_column("categories", "plex_mode"):
                _sqlite_add_column("categories", "plex_mode TEXT DEFAULT 'shuffle'")
            # Categories: ensure is_system (for NeX-Up Trailers, etc.)
            if not _sqlite_has_column("categories", "is_system"):
                _sqlite_add_column("categories", "is_system BOOLEAN DEFAULT 0")

            # Schedules: ensure fallback_category_id
            if not _sqlite_has_column("schedules", "fallback_category_id"):
                _sqlite_add_column("schedules", "fallback_category_id INTEGER")
            # Schedules: ensure sequence JSON field
            if not _sqlite_has_column("schedules", "sequence"):
                _sqlite_add_column("schedules", "sequence TEXT")
            # Schedules: ensure holiday metadata fields for auto-updating variable date holidays
            if not _sqlite_has_column("schedules", "holiday_name"):
                _sqlite_add_column("schedules", "holiday_name TEXT")
            if not _sqlite_has_column("schedules", "holiday_country"):
                _sqlite_add_column("schedules", "holiday_country TEXT")

            # Holiday presets: ensure date range fields and is_recurring
            for col, ddl in [
                ("start_month", "start_month INTEGER"),
                ("start_day", "start_day INTEGER"),
                ("end_month", "end_month INTEGER"),
                ("end_day", "end_day INTEGER"),
                ("is_recurring", "is_recurring BOOLEAN DEFAULT 1"),
            ]:
                if not _sqlite_has_column("holiday_presets", col):
                    _sqlite_add_column("holiday_presets", ddl)

            # Settings: ensure new Plex and app-state columns exist on legacy DBs
            for col, ddl in [
                ("plex_client_id", "plex_client_id TEXT"),
                ("plex_server_base_url", "plex_server_base_url TEXT"),
                ("plex_server_machine_id", "plex_server_machine_id TEXT"),
                ("plex_server_name", "plex_server_name TEXT"),
                ("active_category", "active_category INTEGER"),
                ("updated_at", "updated_at DATETIME"),
                ("path_mappings", "path_mappings TEXT"),
                ("override_expires_at", "override_expires_at DATETIME"),
                ("jellyfin_url", "jellyfin_url TEXT"),
                ("last_seen_version", "last_seen_version TEXT"),
                ("last_schedule_fallback", "last_schedule_fallback INTEGER"),
            ]:
                if not _sqlite_has_column("settings", col):
                    _sqlite_add_column("settings", ddl)

            # Prerolls: ensure display_name column for UI-friendly naming separate from disk file
            if not _sqlite_has_column("prerolls", "display_name"):
                _sqlite_add_column("prerolls", "display_name TEXT")
            # Prerolls: ensure managed flag to indicate external/mapped files (no moves/deletes)
            if not _sqlite_has_column("prerolls", "managed"):
                _sqlite_add_column("prerolls", "managed BOOLEAN DEFAULT 1")
            # Prerolls: ensure community_preroll_id for tracking downloaded community prerolls
            if not _sqlite_has_column("prerolls", "community_preroll_id"):
                _sqlite_add_column("prerolls", "community_preroll_id TEXT")
            # Prerolls: ensure exclude_from_matching flag to prevent auto-matching
            if not _sqlite_has_column("prerolls", "exclude_from_matching"):
                _sqlite_add_column("prerolls", "exclude_from_matching BOOLEAN DEFAULT 0")
            # Prerolls: ensure file_hash for duplicate detection
            if not _sqlite_has_column("prerolls", "file_hash"):
                _sqlite_add_column("prerolls", "file_hash TEXT")

            # Genre maps: ensure canonical normalized key for robust matching/synonyms
            if not _sqlite_has_column("genre_maps", "genre_norm"):
                _sqlite_add_column("genre_maps", "genre_norm TEXT")

            # Settings: ensure genre-based preroll settings
            if not _sqlite_has_column("settings", "genre_auto_apply"):
                _sqlite_add_column("settings", "genre_auto_apply BOOLEAN DEFAULT 1")
            if not _sqlite_has_column("settings", "genre_priority_mode"):
                _sqlite_add_column("settings", "genre_priority_mode TEXT DEFAULT 'schedules_override'")
            if not _sqlite_has_column("settings", "genre_override_ttl_seconds"):
                _sqlite_add_column("settings", "genre_override_ttl_seconds INTEGER DEFAULT 10")
            if not _sqlite_has_column("settings", "genre_override_ttl_seconds"):
                _sqlite_add_column("settings", "genre_override_ttl_seconds INTEGER DEFAULT 10")
            # Settings: ensure aggressive intercept setting
            if not _sqlite_has_column("settings", "genre_aggressive_intercept_enabled"):
                _sqlite_add_column("settings", "genre_aggressive_intercept_enabled BOOLEAN DEFAULT 0")

            # Settings: ensure dashboard tile order
            if not _sqlite_has_column("settings", "dashboard_tile_order"):
                _sqlite_add_column("settings", "dashboard_tile_order TEXT")
            
            # Settings: ensure dashboard layout column
            if not _sqlite_has_column("settings", "dashboard_layout"):
                _sqlite_add_column("settings", "dashboard_layout TEXT")
            
            # Settings: ensure timezone column
            if not _sqlite_has_column("settings", "timezone"):
                _sqlite_add_column("settings", "timezone TEXT DEFAULT 'UTC'")
            
            # Settings: ensure verbose_logging column
            if not _sqlite_has_column("settings", "verbose_logging"):
                _sqlite_add_column("settings", "verbose_logging BOOLEAN DEFAULT 0")
            
            # Settings: ensure passive_mode column (coexistence mode)
            if not _sqlite_has_column("settings", "passive_mode"):
                _sqlite_add_column("settings", "passive_mode BOOLEAN DEFAULT 0")
            
            # Settings: ensure clear_when_inactive column (clear prerolls when no schedule active)
            if not _sqlite_has_column("settings", "clear_when_inactive"):
                _sqlite_add_column("settings", "clear_when_inactive BOOLEAN DEFAULT 0")
            
            # NeX-Up Settings (Radarr integration for upcoming movie trailers)
            nexup_columns = [
                ("nexup_enabled", "nexup_enabled BOOLEAN DEFAULT 0"),
                ("nexup_radarr_url", "nexup_radarr_url TEXT"),
                ("nexup_radarr_api_key", "nexup_radarr_api_key TEXT"),
                ("nexup_storage_path", "nexup_storage_path TEXT"),
                ("nexup_quality", "nexup_quality TEXT DEFAULT '1080'"),
                ("nexup_days_ahead", "nexup_days_ahead INTEGER DEFAULT 90"),
                ("nexup_max_trailers", "nexup_max_trailers INTEGER DEFAULT 10"),
                ("nexup_max_storage_gb", "nexup_max_storage_gb REAL DEFAULT 5.0"),
                ("nexup_trailers_per_playback", "nexup_trailers_per_playback INTEGER DEFAULT 2"),
                ("nexup_playback_order", "nexup_playback_order TEXT DEFAULT 'release_date'"),
                ("nexup_auto_refresh_hours", "nexup_auto_refresh_hours INTEGER DEFAULT 24"),
                ("nexup_last_sync", "nexup_last_sync DATETIME"),
                ("nexup_category_id", "nexup_category_id INTEGER"),
                # YouTube Rate Limiting
                ("nexup_download_delay", "nexup_download_delay INTEGER DEFAULT 5"),
                ("nexup_max_concurrent", "nexup_max_concurrent INTEGER DEFAULT 1"),
                ("nexup_bulk_warning_threshold", "nexup_bulk_warning_threshold INTEGER DEFAULT 5"),
                # TMDB API Key (user-provided)
                ("nexup_tmdb_api_key", "nexup_tmdb_api_key TEXT"),
                # Sonarr Settings
                ("nexup_sonarr_enabled", "nexup_sonarr_enabled BOOLEAN DEFAULT 0"),
                ("nexup_sonarr_url", "nexup_sonarr_url TEXT"),
                ("nexup_sonarr_api_key", "nexup_sonarr_api_key TEXT"),
                ("nexup_tv_category_id", "nexup_tv_category_id INTEGER"),
                ("nexup_last_sonarr_sync", "nexup_last_sonarr_sync DATETIME"),
                # Max trailer duration filter
                ("nexup_max_trailer_duration", "nexup_max_trailer_duration INTEGER DEFAULT 180"),
            ]
            for col, ddl in nexup_columns:
                if not _sqlite_has_column("settings", col):
                    _sqlite_add_column("settings", ddl)
            
            # Create coming_soon_tv_trailers table for Sonarr
            with engine.connect() as conn:
                conn.exec_driver_sql("""
                    CREATE TABLE IF NOT EXISTS coming_soon_tv_trailers (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sonarr_series_id INTEGER,
                        tvdb_id INTEGER,
                        tmdb_id INTEGER,
                        imdb_id TEXT,
                        title TEXT,
                        year INTEGER,
                        season_number INTEGER,
                        overview TEXT,
                        network TEXT,
                        release_date DATETIME,
                        release_type TEXT,
                        trailer_url TEXT,
                        local_path TEXT,
                        file_size_mb REAL,
                        duration_seconds INTEGER,
                        resolution TEXT,
                        poster_url TEXT,
                        fanart_url TEXT,
                        downloaded_at DATETIME,
                        status TEXT DEFAULT 'pending',
                        error_message TEXT,
                        is_enabled BOOLEAN DEFAULT 1,
                        play_count INTEGER DEFAULT 0,
                        last_played DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tv_trailers_sonarr ON coming_soon_tv_trailers(sonarr_series_id)")
                conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tv_trailers_tvdb ON coming_soon_tv_trailers(tvdb_id)")
                conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_tv_trailers_title ON coming_soon_tv_trailers(title)")
                conn.commit()
            
            # Dynamic Preroll Generation Settings
            dynamic_preroll_columns = [
                ("nexup_dynamic_preroll_template", "nexup_dynamic_preroll_template TEXT"),
                ("nexup_dynamic_preroll_server_name", "nexup_dynamic_preroll_server_name TEXT"),
                ("nexup_dynamic_preroll_duration", "nexup_dynamic_preroll_duration INTEGER"),
                ("nexup_dynamic_preroll_theme", "nexup_dynamic_preroll_theme TEXT"),
            ]
            for col, ddl in dynamic_preroll_columns:
                if not _sqlite_has_column("settings", col):
                    _sqlite_add_column("settings", ddl)
            
            # Schedules: ensure color column for custom calendar colors
            if not _sqlite_has_column("schedules", "color"):
                _sqlite_add_column("schedules", "color TEXT")
            
            # Schedules: ensure blend_enabled column for mix mode
            if not _sqlite_has_column("schedules", "blend_enabled"):
                _sqlite_add_column("schedules", "blend_enabled BOOLEAN DEFAULT 0")
            
            # Schedules: ensure priority column for schedule priority (1-10, default 5)
            if not _sqlite_has_column("schedules", "priority"):
                _sqlite_add_column("schedules", "priority INTEGER DEFAULT 5")
            
            # Schedules: ensure exclusive column for exclusive override mode
            if not _sqlite_has_column("schedules", "exclusive"):
                _sqlite_add_column("schedules", "exclusive BOOLEAN DEFAULT 0")
    except Exception as e:
        print(f"Schema ensure error: {e}")

def migrate_legacy_community_prerolls() -> None:
    """
    One-time migration to match legacy community prerolls (downloaded before ID tracking)
    with their community library IDs by searching the community API by title.
    """
    try:
        db = SessionLocal()

        # Check if column exists before querying (handles old DB schemas)
        if not _sqlite_has_column("prerolls", "community_preroll_id"):
            return

        # Find prerolls that were downloaded from community but don't have an ID yet
        legacy_prerolls = db.query(models.Preroll).filter(
            models.Preroll.description.like("%Downloaded from Community Prerolls%"),
            models.Preroll.community_preroll_id.is_(None)
        ).all()

        if not legacy_prerolls:
            return

        import requests
        matched_count = 0
        
        for preroll in legacy_prerolls:
            try:
                # Try to find this preroll in the community library by searching its display name or filename
                search_title = preroll.display_name or preroll.filename.replace('.mp4', '').replace('.mkv', '')
                
                # Search community API
                response = requests.get(
                    'https://prerolls.uk/api/search',
                    params={'query': search_title, 'limit': 5},
                    timeout=5
                )
                
                if response.ok:
                    results = response.json().get('results', [])
                    
                    # Look for exact or very close title match
                    for result in results:
                        import re
                        result_title = re.sub(r'^\d+\s*-\s*', '', result.get('title', '')).strip().lower()
                        search_lower = search_title.lower().strip()
                        
                        # Match if titles are very similar
                        if result_title == search_lower or search_lower in result_title or result_title in search_lower:
                            preroll.community_preroll_id = str(result.get('id'))
                            matched_count += 1
                            print(f"Matched legacy preroll '{preroll.display_name}' to community ID {result.get('id')}")
                            break
                
            except Exception as e:
                print(f"Failed to match preroll {preroll.id}: {e}")
                continue
        
        if matched_count > 0:
            db.commit()
            print(f"Legacy community preroll migration: matched {matched_count} prerolls")
        
        db.close()
    except Exception as e:
        print(f"Legacy community preroll migration error: {e}")

def ensure_settings_schema_now() -> None:
    """
    Best-effort migration to add newer Setting columns on legacy SQLite DBs.
    Safe to call multiple times. Logs any errors to file logger.
    """
    try:
        if not engine.url.drivername.startswith("sqlite"):
            return
        
        added_columns = []
        skipped_columns = []
        
        with engine.connect() as conn:
            cols = []
            try:
                res = conn.exec_driver_sql("PRAGMA table_info(settings)")
                cols = [row[1] for row in res.fetchall()]
            except Exception:
                cols = []

            need = {
                "plex_client_id": "TEXT",
                "plex_server_base_url": "TEXT",
                "plex_server_machine_id": "TEXT",
                "plex_server_name": "TEXT",
                "active_category": "INTEGER",
                "updated_at": "DATETIME",
                "path_mappings": "TEXT",
                "override_expires_at": "DATETIME",
                "jellyfin_url": "TEXT",
                "jellyfin_api_key": "TEXT",
                "community_fair_use_accepted": "BOOLEAN",
                "community_fair_use_accepted_at": "DATETIME",
                "genre_auto_apply": "BOOLEAN",
                "genre_priority_mode": "TEXT",
                "genre_override_ttl_seconds": "INTEGER",
                "dashboard_tile_order": "TEXT",
                "dashboard_layout": "TEXT",
            }
            for col, ddl in need.items():
                if col not in cols:
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE settings ADD COLUMN {col} {ddl}")
                        added_columns.append(col)
                        try:
                            _file_log(f">>> SCHEMA MIGRATION: Added settings.{col} ({ddl})")
                        except Exception:
                            pass
                    except Exception as e:
                        skipped_columns.append((col, str(e)))
                        try:
                            _file_log(f">>> SCHEMA MIGRATION: Skipped settings.{col}: {e}")
                        except Exception:
                            pass
        
        try:
            if added_columns:
                _file_log(f">>> SCHEMA MIGRATION COMPLETE: Added {len(added_columns)} column(s): {', '.join(added_columns)}")
            elif skipped_columns:
                _file_log(f">>> SCHEMA MIGRATION: No new columns added ({len(skipped_columns)} skipped)")
            else:
                _file_log(">>> SCHEMA MIGRATION: Database already up-to-date")
        except Exception:
            pass
    except Exception as e:
        try:
            _file_log(f">>> SCHEMA MIGRATION ERROR: {e}", level="ERROR")
        except Exception:
            pass

# Run schema upgrades early so requests won't hit missing columns
ensure_schema()

def migrate_preroll_hashes() -> None:
    """
    Calculate and store file hashes for existing prerolls that don't have one.
    This enables duplicate detection for prerolls uploaded before hash tracking.
    """
    try:
        db = SessionLocal()
        
        # Find all prerolls without a hash
        prerolls_without_hash = db.query(models.Preroll).filter(
            (models.Preroll.file_hash == None) | (models.Preroll.file_hash == "")
        ).all()
        
        if not prerolls_without_hash:
            _file_log("Hash migration: All prerolls already have hashes")
            db.close()
            return
        
        _file_log(f"Hash migration: Found {len(prerolls_without_hash)} prerolls without hashes, calculating...")
        
        updated_count = 0
        failed_count = 0
        
        for preroll in prerolls_without_hash:
            try:
                # Check if file exists
                if not preroll.path or not os.path.exists(preroll.path):
                    _file_log(f"Hash migration: Skipping preroll {preroll.id} - file not found: {preroll.path}")
                    failed_count += 1
                    continue
                
                # Calculate hash
                file_hash = calculate_file_hash(preroll.path)
                preroll.file_hash = file_hash
                updated_count += 1
                
                if updated_count % 10 == 0:
                    _file_log(f"Hash migration: Processed {updated_count}/{len(prerolls_without_hash)} prerolls...")
                    
            except Exception as e:
                _file_log(f"Hash migration: Error processing preroll {preroll.id}: {e}", level="WARNING")
                failed_count += 1
                continue
        
        # Commit all changes
        try:
            db.commit()
            _file_log(f"Hash migration: Complete! Updated {updated_count} prerolls, {failed_count} failed")
        except Exception as e:
            db.rollback()
            _file_log(f"Hash migration: Failed to commit changes: {e}", level="ERROR")
        finally:
            db.close()
            
    except Exception as e:
        _file_log(f"Hash migration: Fatal error: {e}", level="ERROR")
        import traceback
        _file_log(f"Hash migration traceback: {traceback.format_exc()}", level="ERROR")

# Run legacy community preroll migration in background (one-time, safe to call multiple times)
import threading
threading.Thread(target=migrate_legacy_community_prerolls, daemon=True).start()

# Run hash migration in background for existing prerolls
threading.Thread(target=migrate_preroll_hashes, daemon=True).start()

# Simple file logger to ProgramData\NeXroll\logs for frozen builds
def _ensure_log_dir():
    r"""
    Resolve a writable log directory with fallback:
      1) %ProgramData%\NeXroll\logs (if writable)
      2) %LOCALAPPDATA% or %APPDATA%\NeXroll\logs (if writable)
      3) .\logs under current working directory (if writable)
      4) cwd (as last resort)
    """
    candidates = []
    try:
        if sys.platform.startswith("win"):
            base = os.environ.get("ProgramData")
            if base:
                candidates.append(os.path.join(base, "NeXroll", "logs"))
            la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
            if la:
                candidates.append(os.path.join(la, "NeXroll", "logs"))
    except Exception:
        pass
    candidates.append(os.path.join(os.getcwd(), "logs"))

    for d in candidates:
        try:
            os.makedirs(d, exist_ok=True)
            test = os.path.join(d, f".nexroll_write_test_{os.getpid()}.tmp")
            with open(test, "a", encoding="utf-8") as f:
                f.write("ok")
            try:
                os.remove(test)
            except Exception:
                pass
            return d
        except Exception:
            continue
    # Last resort
    return os.getcwd()

def _log_file_path():
    try:
        return os.path.join(_ensure_log_dir(), "app.log")
    except Exception:
        return os.path.join(os.getcwd(), "app.log")

# Cached verbose logging state to avoid DB hits
_verbose_logging_cache = {"enabled": False, "last_check": 0}
_verbose_cache_ttl = 5  # seconds

# Track last log rotation check to avoid checking on every write
_log_rotation_cache = {"last_check": 0}
_log_rotation_check_interval = 60  # Check every 60 seconds

def _check_log_rotation():
    """Check and rotate log if needed (cached to avoid checking too often)"""
    try:
        import time
        now = time.time()
        
        # Only check periodically
        if now - _log_rotation_cache["last_check"] < _log_rotation_check_interval:
            return
        
        _log_rotation_cache["last_check"] = now
        
        log_path = _log_file_path()
        if not os.path.exists(log_path):
            return
        
        size_mb = os.path.getsize(log_path) / (1024 * 1024)
        if size_mb > 10:  # 10MB limit
            backup_path = log_path + ".1"
            # Remove old backup if exists
            if os.path.exists(backup_path):
                os.remove(backup_path)
            # Rename current log to backup
            os.rename(log_path, backup_path)
    except Exception:
        pass

def _file_log(msg: str, level: str = "INFO"):
    """
    Log message to file with timestamp and level.
    Levels: DEBUG, INFO, WARNING, ERROR
    """
    try:
        # Check rotation before writing
        _check_log_rotation()
        
        with open(_log_file_path(), "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] [{level}] {msg}\n")
    except Exception:
        pass

def _is_verbose_logging_enabled() -> bool:
    """Check if verbose logging is enabled in settings (cached)"""
    try:
        import time
        now = time.time()
        
        # Use cached value if recent
        if now - _verbose_logging_cache["last_check"] < _verbose_cache_ttl:
            return _verbose_logging_cache["enabled"]
        
        # Refresh cache from DB
        from backend.database import SessionLocal
        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            enabled = setting.verbose_logging if setting and hasattr(setting, 'verbose_logging') else False
            _verbose_logging_cache["enabled"] = enabled
            _verbose_logging_cache["last_check"] = now
            return enabled
        finally:
            db.close()
    except Exception:
        return False

def _verbose_log(msg: str):
    """Log message only if verbose logging is enabled"""
    if _is_verbose_logging_enabled():
        print(f"[DEBUG] {msg}")
        _file_log(msg, level="DEBUG")

def _rotate_log_if_needed(max_size_mb=10):
    """
    Rotate the log file if it exceeds max_size_mb.
    Keeps one backup (app.log.1) and starts fresh.
    """
    try:
        log_path = _log_file_path()
        if not os.path.exists(log_path):
            return
        
        size_mb = os.path.getsize(log_path) / (1024 * 1024)
        if size_mb > max_size_mb:
            backup_path = log_path + ".1"
            # Remove old backup if exists
            if os.path.exists(backup_path):
                os.remove(backup_path)
            # Rename current log to backup
            os.rename(log_path, backup_path)
            _file_log(f"Log rotated: previous log saved to {backup_path} ({size_mb:.1f} MB)")
    except Exception as e:
        try:
            _file_log(f"Log rotation error: {e}", level="ERROR")
        except Exception:
            pass

def _log_startup_banner():
    """Log startup information banner for troubleshooting"""
    try:
        from backend.version import __version__
        import datetime
        _file_log("=" * 80)
        _file_log(f"NeXroll v{__version__} - Starting Up")
        _file_log(f"Build Date: {datetime.datetime.now().strftime('%Y-%m-%d')}")
        _file_log("=" * 80)
        _file_log(f"Python: {sys.version.split()[0]}")
        _file_log(f"Platform: {sys.platform}")
        _file_log(f"Frozen: {getattr(sys, 'frozen', False)}")
        _file_log(f"Working Directory: {os.getcwd()}")
        _file_log(f"Log Directory: {_ensure_log_dir()}")
        _file_log(f"Database: {os.path.abspath('nexroll.db')}")
        
        # Check verbose logging status
        verbose = _is_verbose_logging_enabled()
        _file_log(f"Verbose Logging: {'ENABLED' if verbose else 'DISABLED'}")
        
        # Environment info
        _file_log("-" * 80)
        _file_log("Environment:")
        env_vars = ['PLEX_URL', 'JELLYFIN_URL', 'TZ']
        for var in env_vars:
            val = os.environ.get(var)
            if val:
                # Mask sensitive values
                if 'TOKEN' in var or 'KEY' in var or 'PASSWORD' in var:
                    val = '***' + val[-4:] if len(val) > 4 else '***'
                _file_log(f"  {var}: {val}")
        
        _file_log("=" * 80)
    except Exception as e:
        try:
            _file_log(f"Error logging startup banner: {e}", level="ERROR")
        except Exception:
            pass

# Global logging helpers: write unhandled exceptions and stdout/stderr to ProgramData\NeXroll\logs\app.log
def _install_global_excepthook():
    try:
        import traceback
        def _hook(exc_type, exc, tb):
            try:
                lines = "".join(traceback.format_exception(exc_type, exc, tb))
                _file_log(f"Unhandled exception: {lines}", level="ERROR")
            except Exception:
                pass
        sys.excepthook = _hook
    except Exception:
        pass

def _redirect_std_streams():
    """
    When running as a packaged EXE, tee stdout/stderr to app.log so print() and uvicorn traces
    are persisted under ProgramData. Keeps original console streams in dev runs.
    """
    try:
        if not getattr(sys, "frozen", False):
            return
        log_path = _log_file_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        # Open a single append handle for both streams
        lf = open(log_path, "a", encoding="utf-8", buffering=1)
        class _Tee:
            def __init__(self, original, fileh):
                self._orig = original
                self._fh = fileh
            def write(self, s):
                try:
                    if self._orig:
                        self._orig.write(s)
                except Exception:
                    pass
                try:
                    if self._fh:
                        self._fh.write(s)
                except Exception:
                    pass
            def flush(self):
                try:
                    if self._orig:
                        self._orig.flush()
                except Exception:
                    pass
                try:
                    if self._fh:
                        self._fh.flush()
                except Exception:
                    pass
        try:
            sys.stdout = _Tee(getattr(sys, "stdout", None), lf)
            sys.stderr = _Tee(getattr(sys, "stderr", None), lf)
        except Exception:
            pass
        _file_log("Stdout/stderr redirection active")
    except Exception:
        pass

def _setup_python_logging():
    """Configure Python's logging module to write to the same log file"""
    try:
        import logging
        log_path = _log_file_path()
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        
        # Create a file handler for all backend modules
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # Use a format similar to _file_log
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', 
                                      datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        
        # Add handler to root logger and specific backend loggers
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        
        # Also configure specific backend module loggers
        for module_name in ['backend.radarr_connector', 'backend.scheduler', 
                           'backend.sonarr_connector', 'backend.main']:
            module_logger = logging.getLogger(module_name)
            module_logger.setLevel(logging.INFO)
            module_logger.addHandler(file_handler)
            
    except Exception as e:
        _file_log(f"Failed to setup Python logging: {e}", level="ERROR")

def _init_global_logging():
    try:
        _install_global_excepthook()
        _redirect_std_streams()
        _setup_python_logging()  # Add Python logging handler
        _file_log("Global logging initialized")
    except Exception:
        pass

# Initialize logging as early as possible in module import
_init_global_logging()

# Resolve ffmpeg/ffprobe in a PATH-agnostic way (service/tray safe)
import shutil

# Windows-safe subprocess runner to prevent flashing console windows for tools like ffmpeg/ffprobe
def _run_subprocess(cmd, **kwargs):
    try:
        if sys.platform.startswith("win"):
            import subprocess as _sp
            si = _sp.STARTUPINFO()
            try:
                si.dwFlags |= _sp.STARTF_USESHOWWINDOW
            except Exception:
                pass
            cf = kwargs.pop("creationflags", 0)
            return _sp.run(cmd, startupinfo=si, creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0) | cf, **kwargs)
        else:
            import subprocess as _sp
            return _sp.run(cmd, **kwargs)
    except Exception:
        # Fallback if anything above fails
        import subprocess as _sp
        return _sp.run(cmd, **kwargs)
def _resolve_tool(tool_name: str) -> str:
    """
    Return an absolute path or the bare tool name that can be executed.
    Checks:
      - NEXROLL_&lt;TOOL&gt; env var
      - shutil.which on PATH
      - Common Windows install locations
      - Fallback to bare tool name
    """
    try:
        # Environment override
        env_key = f"NEXROLL_{tool_name.upper()}"
        env_val = os.environ.get(env_key)
        if env_val and os.path.exists(env_val):
            return env_val

        # Windows registry hint (installer may store explicit paths)
        if sys.platform.startswith("win"):
            try:
                import winreg
                # Try both 64-bit and 32-bit registry views (NSIS may write to Wow6432Node)
                views = [
                    getattr(winreg, "KEY_WOW64_64KEY", 0),
                    getattr(winreg, "KEY_WOW64_32KEY", 0),
                ]
                reg_name = "FFmpegPath" if tool_name.lower() == "ffmpeg" else ("FFprobePath" if tool_name.lower() == "ffprobe" else None)
                if reg_name:
                    for view in views:
                        try:
                            k = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, r"Software\NeXroll", 0, winreg.KEY_READ | view)
                            try:
                                val, _ = winreg.QueryValueEx(k, reg_name)
                                if val and os.path.exists(val):
                                    return val
                            finally:
                                winreg.CloseKey(k)
                        except Exception:
                            continue
            except Exception:
                pass

        # PATH
        p = shutil.which(tool_name)
        if p:
            return p

        # Common Windows locations
        if sys.platform.startswith("win"):
            candidates = []
            prog_dirs = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramW6432"), os.environ.get("ProgramData")]
            prog_dirs = [d for d in prog_dirs if d]
            for base in prog_dirs:
                candidates += [
                    os.path.join(base, "ffmpeg", "bin", f"{tool_name}.exe"),
                    os.path.join(base, "FFmpeg", "bin", f"{tool_name}.exe"),
                    os.path.join(base, "Gyan", "ffmpeg", "bin", f"{tool_name}.exe"),
                    os.path.join(base, "chocolatey", "bin", f"{tool_name}.exe"),
                ]
            # Common standalone root
            candidates += [
                os.path.join("C:\\", "ffmpeg", "bin", f"{tool_name}.exe"),
            ]
            for c in candidates:
                try:
                    if c and os.path.exists(c):
                        return c
                except Exception:
                    continue

        # Common POSIX
        for c in [f"/usr/bin/{tool_name}", f"/usr/local/bin/{tool_name}"]:
            try:
                if os.path.exists(c):
                    return c
            except Exception:
                pass
    except Exception:
        pass
    # Fallback
    return tool_name

def get_ffmpeg_cmd() -> str:
    return _resolve_tool("ffmpeg")

def get_ffprobe_cmd() -> str:
    return _resolve_tool("ffprobe")

def _generate_placeholder(out_path: str, width: int = 426, height: int = 240):
    """
    Generate a placeholder JPEG thumbnail at out_path.
    Prefer ffmpeg color source; fallback to an embedded 1x1 JPEG.
    """
    try:
        # Attempt using ffmpeg to generate a neutral gray frame
        res = _run_subprocess(
            [get_ffmpeg_cmd(), "-f", "lavfi", "-i", f"color=c=gray:s={width}x{height}", "-vframes", "1", "-y", out_path],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path):
            return
    except Exception:
        pass
    # Fallback: embedded tiny white JPEG (base64)
    try:
        import base64
        _SMALL_JPEG = (
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
            "//////////////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
            "//////////////////////////////////////////////////////////////////////////////////////////////wAARCAAQABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAgP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwC4A//Z"
        )
        data = base64.b64decode(_SMALL_JPEG)
        # Ensure output directory exists
        try:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        except Exception:
            pass
        with open(out_path, "wb") as f:
            f.write(data)
    except Exception:
        # Last resort: create an empty file to avoid repeated attempts
        try:
            with open(out_path, "wb") as f:
                f.write(b"")
        except Exception:
            pass

def _generate_thumbnail_for_preroll(preroll, video_path: str, category_name: str = None) -> Optional[str]:
    """
    Generate a thumbnail for a preroll and update its thumbnail field.
    Returns the relative thumbnail path on success, None on failure.
    
    Args:
        preroll: The Preroll model instance (must have an id)
        video_path: Absolute path to the video file
        category_name: Category name for thumbnail folder organization (optional)
    """
    try:
        if not preroll or not preroll.id or not video_path:
            return None
        
        # Determine thumbnail directory
        if category_name:
            thumbnail_dir = os.path.join(THUMBNAILS_DIR, category_name)
        else:
            thumbnail_dir = THUMBNAILS_DIR
        os.makedirs(thumbnail_dir, exist_ok=True)
        
        # Generate thumbnail filename with preroll ID prefix
        video_filename = os.path.basename(video_path)
        thumb_filename = f"{preroll.id}_{video_filename}.jpg"
        thumb_abs = os.path.join(thumbnail_dir, thumb_filename)
        tmp_thumb = thumb_abs + ".tmp.jpg"
        
        # Try ffmpeg to extract a frame at 5 seconds
        res = _run_subprocess(
            [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", video_path, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp_thumb],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp_thumb):
            _file_log(f"FFmpeg thumbnail generation failed for {video_path}: {getattr(res, 'stderr', '')}")
            _generate_placeholder(tmp_thumb)
        
        # Replace any existing thumbnail
        try:
            if os.path.exists(thumb_abs):
                os.remove(thumb_abs)
        except Exception:
            pass
        
        os.replace(tmp_thumb, thumb_abs)
        
        # Return relative path
        thumbnail_rel = os.path.relpath(thumb_abs, data_dir).replace("\\", "/")
        _file_log(f"Generated thumbnail for preroll {preroll.id}: {thumbnail_rel}")
        return thumbnail_rel
        
    except Exception as e:
        _file_log(f"Thumbnail generation error for preroll {preroll.id if preroll else 'unknown'}: {e}")
        return None

def _placeholder_bytes_jpeg() -> bytes:
    """
    Return a tiny valid JPEG as bytes for inline responses when file I/O fails.
    """
    import base64
    _SMALL_JPEG = (
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
        "//////////////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
        "//////////////////////////////////////////////////////////////////////////////////////////////wAARCAAQABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAgP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwC4A//Z"
    )
    try:
        return base64.b64decode(_SMALL_JPEG)
    except Exception:
        # Minimal SOI/EOI as a last resort (may not render everywhere, but prevents crashes)
        return b"\xff\xd8\xff\xd9"
# Pydantic models for API
class ScheduleCreate(BaseModel):
    name: str
    type: str
    start_date: str  # Accept as string from frontend
    end_date: Optional[str] = None  # Accept as string from frontend
    category_id: Optional[int] = None  # Optional for sequence-based schedules
    shuffle: bool = False
    playlist: bool = False
    recurrence_pattern: Optional[str] = None
    preroll_ids: Optional[str] = None
    sequence: Optional[str] = None
    fallback_category_id: Optional[int] = None
    color: Optional[str] = None  # Custom color for calendar display
    is_active: bool = True  # Whether the schedule is enabled
    blend_enabled: bool = False  # Allow blending with other overlapping schedules
    priority: int = 5  # Priority level 1-10 (higher wins during overlap)
    exclusive: bool = False  # When active, this schedule wins exclusively (no blending)

class ScheduleResponse(BaseModel):
    id: int
    name: str
    type: str
    start_date: datetime.datetime
    end_date: Optional[datetime.datetime] = None
    category_id: int
    shuffle: bool
    playlist: bool
    is_active: bool
    last_run: Optional[datetime.datetime] = None
    next_run: Optional[datetime.datetime] = None
    recurrence_pattern: Optional[str] = None
    preroll_ids: Optional[str] = None
    sequence: Optional[str] = None
    color: Optional[str] = None
    blend_enabled: bool = False  # Allow blending with other overlapping schedules
    priority: int = 5  # Priority level 1-10 (higher wins during overlap)
    exclusive: bool = False  # When active, this schedule wins exclusively (no blending)
    
    class Config:
        json_encoders = {
            datetime.datetime: lambda v: v.isoformat() if v else None
        }

class CategoryCreate(BaseModel):
    name: str
    description: str = None
    apply_to_plex: bool = False
    plex_mode: str = "shuffle"

class PrerollUpdate(BaseModel):
    tags: Optional[str | list[str]] = None
    category_id: Optional[int] = None                 # primary category (affects storage path and thumbnail folder)
    category_ids: Optional[list[int]] = None          # additional categories (many-to-many)
    description: Optional[str] = None
    display_name: Optional[str] = None                # UI display label
    new_filename: Optional[str] = None                # optional on-disk rename (basename; extension optional)
    exclude_from_matching: Optional[bool] = None      # prevent automatic community matching

class PathMapping(BaseModel):
    local: str
    plex: str

class PathMappingsPayload(BaseModel):
    mappings: list[PathMapping]

class TestTranslationRequest(BaseModel):
    paths: list[str]

class MapRootRequest(BaseModel):
    root_path: str
    category_id: Optional[int] = None
    recursive: bool = True
    extensions: Optional[list[str]] = None
    dry_run: bool = True
    generate_thumbnails: bool = True
    tags: Optional[list[str]] = None

class PlexConnectRequest(BaseModel):
    url: str
    token: str

class PlexStableConnectRequest(BaseModel):
    url: Optional[str] = None
    token: Optional[str] = None  # accepted but ignored for stable-token flow
    stableToken: Optional[str] = None  # alias some UIs might send

class PlexTvConnectRequest(BaseModel):
    id: Optional[str] = None
    token: Optional[str] = None
    prefer_local: bool = True
    save_token: bool = True

class PlexAutoConnectRequest(BaseModel):
    token: Optional[str] = None
    urls: Optional[list[str]] = None
    prefer_local: bool = True

class GenreMapCreate(BaseModel):
    genre: str
    category_id: int

class GenreMapUpdate(BaseModel):
    genre: str | None = None
    category_id: int | None = None

class ResolveGenresRequest(BaseModel):
    genres: list[str]

class CommunityPrerollDownloadRequest(BaseModel):
    preroll_id: str = ""
    title: str = ""
    url: str = ""
    category_id: int | None = None
    add_to_category: bool = False
    tags: str = ""

class HolidayScheduleRequest(BaseModel):
    holiday_name: str
    holiday_date: str = None
    country_code: str
    category_id: int
    multi_year: bool = False
    year_count: int = 5

def _normalize_url(url: str) -> str:
    try:
        if not url:
            return ""
        u = str(url).strip()
        if not u.startswith(("http://", "https://")):
            u = "http://" + u
        return u.rstrip("/")
    except Exception:
        return ""


def _probe_plex_url(url: str, token: str, timeout: int = 5) -> tuple[bool, int | None]:
    """
    Probe a Plex base URL, tolerant of local/private HTTPS with self-signed certs.
    Env override: NEXROLL_PLEX_TLS_VERIFY=0|1 to force behavior.
    """
    try:
        # Normalize URL and decide TLS verification
        nu = _normalize_url(url)

        def _bool_env(name: str):
            try:
                v = os.environ.get(name)
                if v is None:
                    return None
                s = str(v).strip().lower()
                if s in ("1","true","yes","on"):
                    return True
                if s in ("0","false","no","off"):
                    return False
            except Exception:
                pass
            return None

        verify = True
        env = _bool_env("NEXROLL_PLEX_TLS_VERIFY")
        if env is not None:
            verify = bool(env)
        else:
            # Heuristic: disable verify for https to private/local hosts
            if nu.startswith("https://"):
                host = ""
                try:
                    from urllib.parse import urlparse
                    host = (urlparse(nu).hostname or "").lower()
                except Exception:
                    host = ""
                private = False
                if host in ("localhost", "127.0.0.1", "host.docker.internal", "gateway.docker.internal"):
                    private = True
                elif host.startswith("192.168.") or host.startswith("10."):
                    private = True
                elif host.startswith("172."):
                    # check 172.16.0.0 – 172.31.255.255
                    parts = host.split(".")
                    if len(parts) >= 2:
                        try:
                            second = int(parts[1])
                            if 16 <= second <= 31:
                                private = True
                        except Exception:
                            pass
                if private:
                    verify = False

        headers = {"X-Plex-Token": token} if token else {}
        r = requests.get(f"{nu}/", headers=headers, timeout=timeout, verify=verify)
        return (r.status_code == 200, r.status_code)
    except Exception:
        return (False, None)


def _default_gateway_candidates() -> list[str]:
    cands: list[str] = []
    try:
        # Linux containers: parse default gateway from /proc/net/route
        if os.name != "nt" and os.path.exists("/proc/net/route"):
            with open("/proc/net/route", "r", encoding="utf-8") as f:
                rows = f.read().strip().splitlines()
            for ln in rows[1:]:
                parts = ln.strip().split()
                # Destination hex 00000000 means default
                if len(parts) >= 3 and parts[1] == "00000000":
                    gw_hex = parts[2]
                    try:
                        gw_ip = ".".join(str(int(gw_hex[i:i+2], 16)) for i in (6, 4, 2, 0))
                        if gw_ip:
                            cands.append(f"http://{gw_ip}:32400")
                            cands.append(f"https://{gw_ip}:32400")
                    except Exception:
                        pass
                    break
    except Exception:
        pass
    # Common docker bridge host
    cands.append("http://172.17.0.1:32400")
    cands.append("https://172.17.0.1:32400")
    return cands


def _docker_candidate_urls() -> list[str]:
    cands: list[str] = []
    # Env-provided first
    try:
        for k in ("NEXROLL_PLEX_URL", "PLEX_URL"):
            v = os.environ.get(k)
            if v and str(v).strip():
                cands.append(_normalize_url(v))
    except Exception:
        pass
    # Typical host aliases when running in Docker
    cands += [
        "http://host.docker.internal:32400", "https://host.docker.internal:32400",
        "http://gateway.docker.internal:32400", "https://gateway.docker.internal:32400",
    ]
    # Default gateway and docker bridge
    cands += _default_gateway_candidates()
    # Local machine fallbacks (when not actually inside docker)
    cands += [
        "http://127.0.0.1:32400",
        "http://localhost:32400",
    ]
    # Dedupe preserving order
    out: list[str] = []
    seen: set[str] = set()
    for u in cands:
        u2 = _normalize_url(u)
        if u2 and u2 not in seen:
            seen.add(u2)
            out.append(u2)
    return out


def _bootstrap_plex_from_env() -> None:
    """
    Best-effort auto-connect for container/CI:
    - Reads NEXROLL_PLEX_TOKEN/PLEX_TOKEN and NEXROLL_PLEX_URL/PLEX_URL
    - If URL not provided, probes common Docker host addresses with token
    - Persists to settings and secure store when successful
    """
    try:
        url_env = (os.environ.get("NEXROLL_PLEX_URL") or os.environ.get("PLEX_URL") or "").strip() or None
        tok_env = (os.environ.get("NEXROLL_PLEX_TOKEN") or os.environ.get("PLEX_TOKEN") or "").strip() or None
        if not url_env and not tok_env:
            return

        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=None, plex_token=None)
                db.add(setting)
                db.commit()
                db.refresh(setting)

            # Prefer existing working configuration
            cur_url = getattr(setting, "plex_url", None)
            cur_tok = getattr(setting, "plex_token", None) or secure_store.get_plex_token()
            if cur_url and cur_tok:
                try:
                    if PlexConnector(cur_url, cur_tok).test_connection():
                        return
                except Exception:
                    pass

            # Persist token from env to secure store
            token = tok_env or cur_tok
            if tok_env:
                try:
                    secure_store.set_plex_token(tok_env)
                    token = tok_env
                except Exception:
                    pass

            if not token:
                return

            # If URL provided, test it first
            if url_env:
                ok, _ = _probe_plex_url(url_env, token, timeout=5)
                if ok:
                    setting.plex_url = _normalize_url(url_env)
                    setting.plex_token = token
                    try:
                        setting.updated_at = datetime.datetime.utcnow()
                    except Exception:
                        pass
                    db.commit()
                    return

            # Probe docker candidates
            for u in _docker_candidate_urls():
                ok, _ = _probe_plex_url(u, token, timeout=4)
                if ok:
                    setting.plex_url = _normalize_url(u)
                    setting.plex_token = token
                    try:
                        setting.updated_at = datetime.datetime.utcnow()
                    except Exception:
                        pass
                    db.commit()
                    return
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        pass


# Import version management
import sys
import os

# Try multiple paths to find version.py (for both dev and PyInstaller builds)
app_version = "1.7.7"  # Default fallback
try:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from version import get_version
    app_version = get_version()
except ImportError:
    try:
        # PyInstaller bundles version.py at the root level
        import version
        app_version = version.get_version()
    except (ImportError, AttributeError):
        pass  # Use fallback version

app = FastAPI(title="NeXroll Backend", version=app_version)

# Rate limiter for community prerolls to avoid triggering Cloudflare DDoS protection
# Typical Nerds requested this to keep their site accessible
community_search_rate_limit = {}  # {ip: last_search_time}
COMMUNITY_SEARCH_COOLDOWN = 5  # seconds between searches per IP

# Local index for Typical Nerds prerolls (faster than remote scraping)
PREROLLS_INDEX_PATH = Path(os.environ.get("PROGRAMDATA", os.path.expanduser("~"))) / "NeXroll" / "prerolls_index.json"
PREROLLS_INDEX_MAX_AGE = 7 * 24 * 3600  # 7 days in seconds (refresh weekly recommended)

# Smart search synonym mapping - helps find related content
SEARCH_SYNONYMS = {
    "halloween": ["pumpkin", "scary", "ghost", "spooky", "witch", "haunted", "october", "trick", "treat", "monster", "zombie", "skeleton"],
    "christmas": ["santa", "xmas", "holiday", "winter", "snow", "reindeer", "elf", "sleigh", "december", "festive", "merry"],
    "thanksgiving": ["turkey", "autumn", "fall", "november", "harvest", "pilgrim", "feast"],
    "turkey": ["thanksgiving", "november", "autumn", "fall", "harvest"],
    "4th july": ["independence", "july", "fireworks", "patriotic", "america"],
    "independence": ["4th july", "july", "fireworks", "patriotic", "america"],
    "valentines": ["love", "heart", "romance", "cupid", "february"],
    "easter": ["bunny", "egg", "spring", "april"],
    "new year": ["nye", "celebration", "january", "countdown", "resolution"],
    "summer": ["beach", "sun", "vacation", "june", "july", "august"],
    "spring": ["flower", "bloom", "april", "may", "easter"],
    "fall": ["autumn", "thanksgiving", "october", "november", "harvest", "leaves"],
    "winter": ["snow", "christmas", "cold", "december", "january", "february"],
    "birthday": ["party", "celebration", "cake", "celebrate"],
    "scary": ["halloween", "horror", "spooky", "ghost", "monster", "zombie"],
    "spooky": ["halloween", "scary", "ghost", "haunted"],
    "pumpkin": ["halloween", "october", "autumn", "fall"],
}

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handler for Pydantic validation errors
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_details = exc.errors()
    _file_log(f"VALIDATION ERROR {request.method} {request.url.path}: {error_details}", level="ERROR")
    print(f"VALIDATION ERROR {request.method} {request.url.path}: {error_details}")
    return JSONResponse(
        status_code=422,
        content={"detail": error_details}
    )

# Ensure app.version attribute is set for runtime inspection (used by /system/version and headers)
try:
    # FastAPI stores version internally, but we also add a direct attribute for any code reading it
    setattr(app, 'version', app_version)
except Exception:
    pass

# TEST ENDPOINT - verify build includes endpoints after app declaration
@app.get("/test-build-verification")
def test_build_verification():
    return {"status": "ok", "message": "Build verification successful - endpoints after app declaration are working", "version": app_version}

# In-memory store for Plex.tv OAuth sessions
OAUTH_SESSIONS: dict[str, dict] = {}

# Recent genre applications for UI feedback (last 10, in-memory)
RECENT_GENRE_APPLICATIONS: list[dict] = []

# Stable client identifier for Plex integrations (persisted in settings when possible)
CLIENT_ID_CACHE: str | None = None
def _get_or_create_plex_client_id() -> str:
    global CLIENT_ID_CACHE
    if CLIENT_ID_CACHE:
        return CLIENT_ID_CACHE

    # 1) Environment override for containerized deployments
    env_id = os.environ.get("NEXROLL_CLIENT_ID")
    if env_id and str(env_id).strip():
        CLIENT_ID_CACHE = str(env_id).strip()
        return CLIENT_ID_CACHE

    # 2) Persist and reuse a client id in the settings table
    cid = None
    db = None
    try:
        db = SessionLocal()
        setting = db.query(models.Setting).first()
        if not setting:
            setting = models.Setting(plex_url=None, plex_token=None)
            db.add(setting)
            db.commit()
            db.refresh(setting)

        existing = getattr(setting, "plex_client_id", None)
        if not existing or not str(existing).strip():
            new_id = str(uuid.uuid4())
            try:
                setting.plex_client_id = new_id
                # best-effort updated_at
                try:
                    setting.updated_at = datetime.datetime.utcnow()
                except Exception:
                    pass
                db.commit()
                existing = new_id
            except Exception:
                db.rollback()
                existing = new_id  # still return a stable id this process
        cid = str(existing).strip()
    except Exception:
        # 3) Fallback: ephemeral in-memory id
        cid = str(uuid.uuid4())
    finally:
        try:
            if db is not None:
                db.close()
        except Exception:
            pass

    CLIENT_ID_CACHE = cid
    return CLIENT_ID_CACHE

def _build_plex_headers() -> dict:
    """Build X-Plex-* headers for OAuth device auth."""
    try:
        headers = dict(getattr(plexapi, "BASE_HEADERS", {}))
    except Exception:
        headers = {}
    headers["X-Plex-Product"] = "NeXroll"
    headers["X-Plex-Device"] = "NeXroll"
    headers["X-Plex-Version"] = getattr(app, "version", None) or "1.0.0"
    try:
        headers["X-Plex-Client-Identifier"] = _get_or_create_plex_client_id()
    except Exception:
        headers.setdefault("X-Plex-Client-Identifier", str(uuid.uuid4()))
    return headers

# CORS middleware for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:9393",
        "http://127.0.0.1:9393",
    ],  # React dev server and production port (localhost and 127.0.0.1)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Log unhandled exceptions and 4xx/5xx responses to writable logs (with fallback)
@app.middleware("http")
async def _log_errors_mw(request, call_next):
    try:
        response = await call_next(request)
    except Exception as e:
        try:
            _file_log(f"Unhandled error {request.method} {request.url.path}: {e}", level="ERROR")
        except Exception:
            pass
        raise

    try:
        status = getattr(response, "status_code", 200)
        if status >= 400:
            _file_log(f"HTTP {status} {request.method} {request.url.path}")
    except Exception:
        pass
    return response
# Cache-busting middleware: prevent stale cached HTML/manifest causing "React App" title
@app.middleware("http")
async def _no_cache_index_mw(request, call_next):
    response = await call_next(request)
    try:
        path = (request.url.path or "").lower()
        # Prevent cache for entry and manifest/service worker to avoid stale hashed bundles
        if path in ("/", "/index.html", "/manifest.json", "/asset-manifest.json", "/sw.js", "/service-worker.js", "/dashboard"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
    except Exception:
        pass
    return response

# API routes are defined here (they need to be before static mounts)

# Start scheduler on app startup
@app.on_event("startup")
def startup_event():
    # First: Ensure database schema is up-to-date (adds missing columns to legacy DBs)
    try:
        ensure_schema()
    except Exception as e:
        try:
            _file_log(f"Schema migration error: {e}", level="ERROR")
        except Exception:
            print(f"Schema migration error: {e}")
    
    # Normalize thumbnail paths in DB on startup (idempotent migration for legacy paths)
    try:
        db = SessionLocal()
        prerolls = db.query(models.Preroll).filter(models.Preroll.thumbnail.isnot(None)).all()
        updated = 0
        for p in prerolls:
            if not p.thumbnail:
                continue
            path = str(p.thumbnail).lstrip("/")
            changed = False
            if path.startswith("data/"):
                path = path.replace("data/", "", 1)
                changed = True
            if path.startswith("thumbnails/"):
                path = "prerolls/" + path
                changed = True
            if changed and p.thumbnail != path:
                p.thumbnail = path
                updated += 1
        if updated:
            try:
                db.commit()
                _file_log(f"Startup normalization updated {updated} thumbnail paths")
            except Exception as e:
                db.rollback()
                _file_log(f"Startup normalization commit failed: {e}", level="ERROR")
    except Exception as e:
        try:
            _file_log(f"Startup normalization error: {e}", level="ERROR")
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    # Rotate log if it's getting too large (before scheduler starts logging)
    _rotate_log_if_needed(max_size_mb=10)
    
    # Log startup banner
    _log_startup_banner()
    
    scheduler.start()

@app.on_event("startup")
def startup_env_bootstrap():
    # Independent startup hook to allow env-driven Docker quick-connect
    # Bootstraps Plex and Jellyfin from environment variables when present.
    # Also ensures a Setting record exists in the database
    try:
        db = SessionLocal()
        setting = db.query(models.Setting).first()
        if not setting:
            # Create an empty Setting record if one doesn't exist
            setting = models.Setting()
            db.add(setting)
            db.commit()
            _file_log("Created default Setting record on startup")
        
        # Auto-detect timezone from TZ environment variable (Docker support)
        if setting and not setting.timezone or setting.timezone == 'UTC':
            tz_env = os.environ.get('TZ')
            if tz_env:
                try:
                    # Validate timezone using pytz
                    pytz.timezone(tz_env)
                    setting.timezone = tz_env
                    db.commit()
                    _file_log(f"Auto-detected timezone from TZ environment variable: {tz_env}")
                except Exception as tz_err:
                    _file_log(f"Invalid TZ environment variable '{tz_env}': {tz_err}")
        
        db.close()
    except Exception as e:
        try:
            _file_log(f"Startup Setting initialization error: {e}", level="ERROR")
        except Exception:
            pass
    
    try:
        _bootstrap_plex_from_env()
    except Exception:
        # keep server healthy regardless of failures here
        pass
    try:
        _bootstrap_jellyfin_from_env()
    except Exception:
        # keep server healthy regardless of failures here
        pass
    
    # Auto-refresh variable-date holiday schedules on startup (once per day)
    try:
        _auto_refresh_holiday_dates()
    except Exception as e:
        try:
            _file_log(f"Holiday date refresh error on startup: {e}", level="WARNING")
        except Exception:
            pass

def _auto_refresh_holiday_dates():
    """
    Automatically refresh variable-date holiday schedules (Thanksgiving, Easter, etc.)
    This runs on startup and updates any schedules linked to holidays that have
    different dates for the current year.
    """
    from datetime import datetime
    
    db = SessionLocal()
    try:
        current_year = datetime.now().year
        
        # Find all schedules with holiday_name set
        holiday_schedules = db.query(models.Schedule).filter(
            models.Schedule.holiday_name.isnot(None),
            models.Schedule.holiday_country.isnot(None)
        ).all()
        
        if not holiday_schedules:
            return
        
        _file_log(f"Auto-checking {len(holiday_schedules)} holiday-linked schedules for {current_year}...")
        
        from backend.holiday_api import HolidayAPI
        updated_count = 0
        
        for schedule in holiday_schedules:
            try:
                # Skip if schedule is for future year already
                if schedule.start_date and schedule.start_date.year > current_year:
                    continue
                
                # Get the holiday for current year
                holidays = HolidayAPI.get_holidays(schedule.holiday_country, current_year)
                
                # Find matching holiday
                matching = None
                for h in holidays:
                    if h.get("name", "").lower() == schedule.holiday_name.lower():
                        matching = h
                        break
                    if h.get("localName", "").lower() == schedule.holiday_name.lower():
                        matching = h
                        break
                
                if matching:
                    new_date = datetime.strptime(matching["date"], "%Y-%m-%d")
                    old_date = schedule.start_date
                    
                    # Update if year changed or date changed
                    if old_date.year != current_year or old_date.month != new_date.month or old_date.day != new_date.day:
                        schedule.start_date = new_date
                        schedule.end_date = new_date.replace(hour=23, minute=59, second=59)
                        updated_count += 1
                        _file_log(f"  Updated '{schedule.name}': {old_date.strftime('%Y-%m-%d')} -> {new_date.strftime('%Y-%m-%d')}")
                        
            except Exception as e:
                _file_log(f"  Error updating schedule '{schedule.name}': {e}", level="WARNING")
                continue
        
        if updated_count > 0:
            db.commit()
            _file_log(f"Auto-updated {updated_count} holiday schedule(s) for {current_year}")
        else:
            _file_log(f"All {len(holiday_schedules)} holiday schedule(s) already up-to-date for {current_year}")
            
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()

@app.on_event("shutdown")
def shutdown_event():
    scheduler.stop()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/system/dependencies")
def system_dependencies():
    """Return comprehensive system dependency information for the System Information page."""
    import shutil
    import platform
    
    def probe_version(cmd: str, version_flag: str = "-version"):
        """Run a command with version flag and return (available, version_string)."""
        try:
            r = _run_subprocess([cmd, version_flag], capture_output=True, text=True)
            if r.returncode == 0:
                first = r.stdout.splitlines()[0] if r.stdout else ""
                return True, first.strip()
        except Exception:
            pass
        return False, None
    
    def probe_which(cmd: str):
        """Check if a command exists in PATH."""
        return shutil.which(cmd) is not None
    
    dependencies = {
        "python": {
            "available": True,
            "version": platform.python_version(),
            "description": "Python runtime for NeXroll backend",
            "path": sys.executable
        },
        "ffmpeg": {
            "available": False,
            "version": None,
            "description": "Video processing & preroll generation",
            "path": None
        },
        "ffprobe": {
            "available": False,
            "version": None,
            "description": "Video analysis & metadata extraction",
            "path": None
        },
        "yt_dlp": {
            "available": False,
            "version": None,
            "description": "YouTube & trailer downloads (NeX-Up)",
            "path": None
        },
        "deno": {
            "available": False,
            "version": None,
            "description": "JavaScript runtime for YouTube extraction",
            "path": None
        }
    }
    
    # Check FFmpeg
    ffmpeg_cmd = get_ffmpeg_cmd()
    ffmpeg_ok, ffmpeg_ver = probe_version(ffmpeg_cmd)
    dependencies["ffmpeg"]["available"] = ffmpeg_ok
    dependencies["ffmpeg"]["version"] = ffmpeg_ver
    dependencies["ffmpeg"]["path"] = ffmpeg_cmd if ffmpeg_ok else None
    
    # Check FFprobe
    ffprobe_cmd = get_ffprobe_cmd()
    ffprobe_ok, ffprobe_ver = probe_version(ffprobe_cmd)
    dependencies["ffprobe"]["available"] = ffprobe_ok
    dependencies["ffprobe"]["version"] = ffprobe_ver
    dependencies["ffprobe"]["path"] = ffprobe_cmd if ffprobe_ok else None
    
    # Check yt-dlp (Python module first, then CLI)
    try:
        import yt_dlp
        dependencies["yt_dlp"]["available"] = True
        dependencies["yt_dlp"]["version"] = f"yt-dlp {yt_dlp.version.__version__}"
        dependencies["yt_dlp"]["path"] = "Python module (bundled)"
    except ImportError:
        yt_dlp_path = shutil.which('yt-dlp')
        if yt_dlp_path:
            dependencies["yt_dlp"]["available"] = True
            yt_ok, yt_ver = probe_version('yt-dlp', '--version')
            dependencies["yt_dlp"]["version"] = f"yt-dlp {yt_ver}" if yt_ver else "yt-dlp (version unknown)"
            dependencies["yt_dlp"]["path"] = yt_dlp_path
    
    # Check Deno (required for yt-dlp YouTube extraction)
    deno_path = shutil.which('deno')
    if deno_path:
        dependencies["deno"]["available"] = True
        deno_ok, deno_ver = probe_version('deno', '--version')
        if deno_ver:
            # deno --version returns multiple lines, first line is "deno X.X.X"
            dependencies["deno"]["version"] = deno_ver
        dependencies["deno"]["path"] = deno_path
    
    # Add system info
    system_info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node()
    }
    
    return {
        "dependencies": dependencies,
        "system": system_info
    }


@app.get("/system/ffmpeg-info")
def system_ffmpeg_info():
    """Return presence and versions for ffmpeg and ffprobe (for diagnostics UI)."""
    def probe(cmd: str):
        try:
            r = _run_subprocess([cmd, "-version"], capture_output=True, text=True)
            if r.returncode == 0:
                first = r.stdout.splitlines()[0] if r.stdout else ""
                return True, first
        except Exception:
            pass
        return False, None

    ffmpeg_cmd = get_ffmpeg_cmd()
    ffprobe_cmd = get_ffprobe_cmd()
    ffmpeg_ok, ffmpeg_ver = probe(ffmpeg_cmd)
    ffprobe_ok, ffprobe_ver = probe(ffprobe_cmd)
    return {
        "ffmpeg_present": ffmpeg_ok,
        "ffmpeg_version": ffmpeg_ver,
        "ffprobe_present": ffprobe_ok,
        "ffprobe_version": ffprobe_ver,
        "ffmpeg_cmd": ffmpeg_cmd,
        "ffprobe_cmd": ffprobe_cmd,
    }


@app.get("/settings/dashboard-layout")
def get_dashboard_layout(db: Session = Depends(get_db)):
    """Get the dashboard layout configuration"""
    setting = db.query(models.Setting).first()
    if not setting:
        # Return default layout
        return {
            "grid": {"cols": 4, "rows": 2},
            "order": ["servers", "prerolls", "storage", "schedules", "scheduler", "current_category", "upcoming", "recent_genres"],
            "hidden": [],
            "locked": False
        }
    
    layout = setting.get_json_value("dashboard_layout")
    if not layout:
        # Return default layout
        return {
            "grid": {"cols": 4, "rows": 2},
            "order": ["servers", "prerolls", "storage", "schedules", "scheduler", "current_category", "upcoming", "recent_genres"],
            "hidden": [],
            "locked": False
        }
    return layout

@app.put("/settings/dashboard-layout")
async def update_dashboard_layout(request: Request, db: Session = Depends(get_db)):
    """Update the dashboard layout configuration"""
    try:
        # Get JSON body
        layout_data = await request.json()
        
        # Validate the layout data structure
        if not isinstance(layout_data, dict):
            raise ValueError("Layout data must be a dictionary")
        
        # Save to database
        setting = db.query(models.Setting).first()
        if not setting:
            setting = models.Setting()
            db.add(setting)
        
        setting.set_json_value("dashboard_layout", layout_data)
        db.commit()
        return {"status": "success", "data": layout_data}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/system/version")
def system_version():
    """Expose backend version and installed version (from Windows registry if present)."""
    reg_version = None
    install_dir = None
    try:
        if sys.platform.startswith("win"):
            import winreg
            # Read both 64-bit and 32-bit registry views (NSIS x86 writes to Wow6432Node)
            for access in (
                getattr(winreg, "KEY_READ", 0) | getattr(winreg, "KEY_WOW64_64KEY", 0),
                getattr(winreg, "KEY_READ", 0) | getattr(winreg, "KEY_WOW64_32KEY", 0),
            ):
                try:
                    k = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, r"Software\NeXroll", 0, access)
                    try:
                        v, _ = winreg.QueryValueEx(k, "Version")
                        if v and str(v).strip():
                            reg_version = str(v).strip()
                    except Exception:
                        pass
                    try:
                        d, _ = winreg.QueryValueEx(k, "InstallDir")
                        if d and str(d).strip():
                            install_dir = str(d).strip()
                    except Exception:
                        pass
                    try:
                        winreg.CloseKey(k)
                    except Exception:
                        pass
                except Exception:
                    continue
    except Exception:
        reg_version = None
        install_dir = None

    return {
        "api_version": getattr(app, "version", None),
        "registry_version": reg_version,
        "install_dir": install_dir,
    }


@app.get("/system/changelog")
def get_changelog(db: Session = Depends(get_db)):
    """
    Returns the changelog content and whether it should be displayed.
    Also returns the current version and last seen version.
    """
    current_version = getattr(app, "version", "unknown")
    
    # Get last seen version from settings
    settings = db.query(models.Setting).first()
    last_seen_version = settings.last_seen_version if settings else None
    
    # Determine if changelog should be shown (version changed)
    show_changelog = (last_seen_version is None or last_seen_version != current_version)
    
    # Read changelog content
    changelog_content = ""
    try:
        # Try multiple possible locations for CHANGELOG.md
        possible_paths = []
        
        # Check if running from PyInstaller bundle
        if getattr(sys, '_MEIPASS', None):
            # Running from PyInstaller - check extracted temp directory
            possible_paths.append(os.path.join(sys._MEIPASS, 'CHANGELOG.md'))
        
        # Docker: Check /app directory (typical Docker working directory)
        possible_paths.append('/app/CHANGELOG.md')
        possible_paths.append('/app/NeXroll/CHANGELOG.md')
        
        # Add source directory paths (for development)
        possible_paths.extend([
            os.path.join(os.path.dirname(__file__), "..", "CHANGELOG.md"),
            os.path.join(os.path.dirname(__file__), "..", "..", "CHANGELOG.md"),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "CHANGELOG.md"),
            "CHANGELOG.md",
            "./CHANGELOG.md"
        ])
        
        _file_log(f"Searching for CHANGELOG.md in {len(possible_paths)} locations...")
        for path in possible_paths:
            abs_path = os.path.abspath(path)
            if os.path.exists(abs_path):
                with open(abs_path, 'r', encoding='utf-8') as f:
                    changelog_content = f.read()
                _file_log(f"✓ Found CHANGELOG.md at: {abs_path}")
                break
            else:
                _file_log(f"  ✗ Not found: {abs_path}")
        
        if not changelog_content:
            _file_log("⚠ CHANGELOG.md not found in any location", level="WARNING")
    except Exception as e:
        _file_log(f"Failed to read CHANGELOG.md: {e}", level="ERROR")
        _file_log(f"Changelog read error: {e}", level="ERROR")
        changelog_content = "Changelog not available."
    
    return {
        "current_version": current_version,
        "last_seen_version": last_seen_version,
        "show_changelog": show_changelog,
        "changelog": changelog_content
    }


@app.post("/system/changelog/mark-seen")
def mark_changelog_seen(db: Session = Depends(get_db)):
    """
    Mark the current version as seen by the user.
    Called when user dismisses the changelog modal.
    """
    current_version = getattr(app, "version", "unknown")
    
    settings = db.query(models.Setting).first()
    if not settings:
        settings = models.Setting()
        db.add(settings)
    
    settings.last_seen_version = current_version
    db.commit()
    
    return {"success": True, "version": current_version}


@app.get("/system/db-introspect")
def system_db_introspect():
    """
    Diagnostics: report DB URL/path and presence of key columns in SQLite.
    Helps diagnose legacy DBs missing new columns (e.g., apply_to_plex).
    """
    info = {}
    try:
        # Engine string and resolved database path (for sqlite)
        info["db_url"] = str(engine.url)
        db_path = None
        try:
            db_path = engine.url.database
            if db_path:
                db_path = os.path.abspath(db_path)
        except Exception:
            db_path = None
        info["db_path"] = db_path

        # Introspect categories table
        categories_columns = []
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(categories)")
                categories_columns = [row[1] for row in res.fetchall()]
        except Exception as e:
            info["categories_error"] = str(e)
        info["categories_columns"] = categories_columns
        info["has_apply_to_plex"] = "apply_to_plex" in categories_columns

        # Introspect schedules table
        schedules_columns = []
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(schedules)")
                schedules_columns = [row[1] for row in res.fetchall()]
        except Exception as e:
            info["schedules_error"] = str(e)
        info["schedules_columns"] = schedules_columns
        info["has_fallback_category_id"] = "fallback_category_id" in schedules_columns

        # Introspect settings table
        settings_columns = []
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(settings)")
                settings_columns = [row[1] for row in res.fetchall()]
        except Exception as e:
            info["settings_error"] = str(e)
        info["settings_columns"] = settings_columns
        info["has_plex_client_id"] = "plex_client_id" in settings_columns
        info["has_updated_at"] = "updated_at" in settings_columns

    except Exception as e:
        info["error"] = str(e)

    return info

@app.post("/system/migrate-hashes")
def trigger_hash_migration(db: Session = Depends(get_db)):
    """
    Manually trigger file hash migration for existing prerolls.
    Calculates and stores SHA256 hashes for all prerolls that don't have one.
    """
    try:
        # Count prerolls without hash
        count = db.query(models.Preroll).filter(
            (models.Preroll.file_hash == None) | (models.Preroll.file_hash == "")
        ).count()
        
        if count == 0:
            return {"message": "All prerolls already have hashes", "processed": 0}
        
        # Run migration in background thread
        def run_migration():
            migrate_preroll_hashes()
        
        threading.Thread(target=run_migration, daemon=True).start()
        
        return {
            "message": f"Hash migration started for {count} prerolls. Check logs for progress.",
            "prerolls_to_process": count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start migration: {str(e)}")

@app.get("/system/hash-migration-status")
def hash_migration_status(db: Session = Depends(get_db)):
    """
    Check the status of file hash migration.
    Returns count of prerolls with and without hashes.
    """
    try:
        total = db.query(models.Preroll).count()
        with_hash = db.query(models.Preroll).filter(
            (models.Preroll.file_hash != None) & (models.Preroll.file_hash != "")
        ).count()
        without_hash = total - with_hash
        
        return {
            "total_prerolls": total,
            "with_hash": with_hash,
            "without_hash": without_hash,
            "percentage_complete": round((with_hash / total * 100), 2) if total > 0 else 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")

@app.get("/system/paths")
def system_paths():
    """
    Diagnostics: show resolved important paths and writability hints.
    Helps identify permission-related issues when running as standard user,
    service, or via the tray application.
    """
    info = {}
    try:
        info["cwd"] = os.getcwd()
        # These globals are assigned later in the module; safe to reference at call time
        info["install_root"] = "install_root" in globals() and install_root or None
        info["resource_root"] = "resource_root" in globals() and resource_root or None
        info["frontend_dir"] = "frontend_dir" in globals() and frontend_dir or None
        info["data_dir"] = "data_dir" in globals() and data_dir or None
        info["prerolls_dir"] = "PREROLLS_DIR" in globals() and PREROLLS_DIR or None
        info["thumbnails_dir"] = "THUMBNAILS_DIR" in globals() and THUMBNAILS_DIR or None

        try:
            log_dir = _ensure_log_dir()
            info["log_dir"] = log_dir
            info["log_path"] = os.path.join(log_dir, "app.log") if log_dir else None
        except Exception as e:
            info["log_error"] = str(e)

        info["db_url"] = str(engine.url)
        try:
            db_path = engine.url.database
            info["db_path"] = os.path.abspath(db_path) if db_path else None
        except Exception as e:
            info["db_path_error"] = str(e)
    except Exception as e:
        info["error"] = str(e)

    return info

@app.post("/system/apply-env-vars")
def apply_env_vars():
    """
    Apply Windows environment variables required for genre-based preroll intercept functionality.
    Requires administrator privileges to set machine-level environment variables.
    """
    try:
        commands = [
            "[System.Environment]::SetEnvironmentVariable('NEXROLL_INTERCEPT_ALWAYS','1','Machine')",
            "[System.Environment]::SetEnvironmentVariable('NEXROLL_INTERCEPT_THRESHOLD_MS','15000','Machine')",
            "[System.Environment]::SetEnvironmentVariable('NEXROLL_INTERCEPT_DELAY_MS','1000','Machine')",
            "[System.Environment]::SetEnvironmentVariable('NEXROLL_FORCE_INTERCEPT','1','Machine')"
        ]

        for cmd in commands:
            result = _run_subprocess(["powershell", "-Command", cmd], capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Failed to set environment variable: {cmd}, error: {result.stderr}")

        return {"success": True, "message": "Environment variables applied successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply environment variables: {str(e)}")

# Minimal built-in Dashboard with a Reinitialize Thumbnails button
@app.get("/dashboard")
def dashboard():
    html = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>NeXroll Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root{--bg:#fafafa;--card:#fff;--text:#222;--muted:#666;--border:#e5e7eb;--brand:#0b1020;--brandText:#d1f7c4}
  body{font-family:Segoe UI, Arial, sans-serif; margin:24px; color:var(--text); background:var(--bg)}
  h1{margin:0 0 12px 0}
  small{color:var(--muted)}
  button{padding:8px 12px; margin:8px 8px 8px 0; cursor:pointer}
  pre{background:var(--brand);color:var(--brandText);padding:12px;border-radius:6px;white-space:pre-wrap;max-width:100%;overflow:auto}
  .card{background:var(--card);padding:16px;border:1px solid var(--border);border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.04);margin-bottom:16px}
  .row{display:flex; gap:12px; flex-wrap:wrap; align-items:center}
  .field{display:flex; flex-direction:column; margin:6px 12px 6px 0}
  .field label{font-size:12px; color:#444; margin-bottom:4px}
  input[type="text"], input[type="number"], textarea, select{
    padding:8px; border:1px solid var(--border); border-radius:6px; min-width:220px; font-family:inherit
  }
  input[type="checkbox"]{transform:translateY(2px)}
  table{border-collapse:collapse; width:100%; margin-top:8px}
  th, td{border:1px solid var(--border); padding:8px; text-align:left}
  th{background:#f3f4f6; font-weight:600}
  .muted{color:#666; font-size:12px}
</style>
</head>
<body>
  <h1>NeXroll Dashboard</h1>

  <!-- Quick actions -->
  <div class="card">
    <div class="row">
      <button onclick="reinit()">Reinitialize Thumbnails</button>
      <button onclick="ffmpeg()">FFmpeg Info</button>
      <button onclick="plex()">Plex Status</button>
      <button onclick="jellyfin()">Jellyfin Status</button>
      <button onclick="version()">Version</button>
      <small id="status"></small>
    </div>
  </div>

  <!-- Path Mappings -->
  <div class="card">
    <h2 style="margin:0 0 8px 0;">Path Mappings</h2>
    <div class="muted">Define how local/UNC paths translate to the path Plex sees. Longest-prefix wins; Windows is case-insensitive.</div>

    <div class="row" style="margin-top:8px;">
      <button onclick="loadMappings()">Load Mappings</button>
      <button onclick="addMappingRow()">Add Row</button>
      <button onclick="saveMappings(false)">Save (Replace)</button>
      <button onclick="saveMappings(true)">Save (Merge)</button>
    </div>

    <table id="mapTable">
      <thead>
        <tr><th style="width:45%;">Local Prefix (e.g. \\\\NAS\\PreRolls or D:\\Media\\Prerolls)</th><th style="width:45%;">Plex Prefix (e.g. Z:\\PreRolls or /mnt/prerolls)</th><th style="width:10%;">Actions</th></tr>
      </thead>
      <tbody id="mapTableBody">
      </tbody>
    </table>

    <div class="row" style="margin-top:12px;">
      <div class="field" style="flex:1 1 420px;">
        <label for="testPaths">Test translation (one path per line)</label>
        <textarea id="testPaths" rows="4" placeholder="\\\\NAS\\PreRolls\\Holiday\\intro.mp4"></textarea>
      </div>
    </div>
    <div class="row">
      <button onclick="testMappings()">Run Test</button>
    </div>
    <pre id="mapOut">Mappings ready.</pre>
  </div>

  <!-- Map External Folder -->
  <div class="card">
    <h2 style="margin:0 0 8px 0;">Map External Folder (No Copy/Move)</h2>
    <div class="muted">Indexes an existing folder (local or UNC) into NeXroll. Files are marked managed=false so NeXroll will not move/delete them.</div>

    <div class="row" style="margin-top:8px;">
      <div class="field" style="flex:1 1 420px;">
        <label for="rootPath">Root Path</label>
        <input type="text" id="rootPath" placeholder="\\\\NAS\\PreRolls\\Holiday or D:\\Media\\Prerolls\\Holiday" />
      </div>
      <div class="field">
        <label for="categoryId">Category ID (optional)</label>
        <input type="number" id="categoryId" placeholder="e.g. 5" />
      </div>
      <div class="field">
        <label for="extensions">Extensions (comma)</label>
        <input type="text" id="extensions" value="mp4,mkv,mov,avi,m4v,webm" />
      </div>
    </div>

    <div class="row">
      <div class="field">
        <label>
          <input type="checkbox" id="recursive" checked />
          Recursive
        </label>
      </div>
      <div class="field">
        <label>
          <input type="checkbox" id="generateThumbnails" checked />
          Generate Thumbnails
        </label>
      </div>
      <div class="field" style="flex:1 1 420px;">
        <label for="tags">Tags (comma, optional)</label>
        <input type="text" id="tags" placeholder="mapped,external" />
      </div>
    </div>

    <div class="row" style="margin-top:8px;">
      <button onclick="mapRoot(true)">Dry Run</button>
      <button onclick="mapRoot(false)">Map Now</button>
    </div>
    <pre id="mapRootOut">Ready.</pre>
  </div>

  <!-- Output -->
  <div class="card">
    <pre id="out">Ready.</pre>
  </div>

<script>
function setOut(t){document.getElementById('out').textContent=t;}
function setStatus(t){document.getElementById('status').textContent=t;}
function setMapOut(t){document.getElementById('mapOut').textContent=t;}
function setMapRootOut(t){document.getElementById('mapRootOut').textContent=t;}

function addMappingRow(local='', plex=''){
  const tb = document.getElementById('mapTableBody');
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td><input type="text" class="mapLocal" placeholder="\\\\\\NAS\\PreRolls or D:\\\\Media\\\\Prerolls" style="width:100%;"/></td>
    <td><input type="text" class="mapPlex" placeholder="Z:\\\\PreRolls or /mnt/prerolls" style="width:100%;"/></td>
    <td><button type="button" onclick="this.closest('tr').remove()">Remove</button></td>
  `;
  tb.appendChild(tr);
  // Set values after insertion to avoid JS parsing issues with backslashes in HTML attributes
  try{
    const loc = tr.querySelector('.mapLocal');
    const plx = tr.querySelector('.mapPlex');
    if(loc) loc.value = local || '';
    if(plx) plx.value = plex || '';
  }catch(e){}
}

async function loadMappings(){
  setMapOut('GET /settings/path-mappings ...');
  try{
    const res = await fetch('/settings/path-mappings');
    const j = await res.json();
    const tb = document.getElementById('mapTableBody');
    tb.innerHTML = '';
    const maps = (j && j.mappings) ? j.mappings : [];
    for(const m of maps){
      addMappingRow(m.local || '', m.plex || '');
    }
    if(maps.length === 0){ addMappingRow(); }
    setMapOut(JSON.stringify(j,null,2));
  }catch(e){
    setMapOut('Error: '+e);
  }
}

function collectMappings(){
  const rows = Array.from(document.querySelectorAll('#mapTableBody tr'));
  const out = [];
  for(const r of rows){
    const local = (r.querySelector('.mapLocal')?.value || '').trim();
    const plex = (r.querySelector('.mapPlex')?.value || '').trim();
    if(local && plex){ out.push({local, plex}); }
  }
  return out;
}

async function saveMappings(merge){
  const mappings = collectMappings();
  const payload = { mappings };
  setMapOut((merge? 'PUT /settings/path-mappings?merge=true' : 'PUT /settings/path-mappings') + ' ...');
  try{
    const res = await fetch('/settings/path-mappings' + (merge ? '?merge=true' : ''), {
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const j = await res.json();
    setMapOut(JSON.stringify(j,null,2));
  }catch(e){
    setMapOut('Error: '+e);
  }
}

async function testMappings(){
  const raw = (document.getElementById('testPaths').value || '').split(/\\r?\\n/).map(s=>s.trim()).filter(Boolean);
  const payload = { paths: raw };
  setMapOut('POST /settings/path-mappings/test ...');
  try{
    const res = await fetch('/settings/path-mappings/test', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const j = await res.json();
    setMapOut(JSON.stringify(j,null,2));
  }catch(e){
    setMapOut('Error: '+e);
  }
}

function parseExtensions(str){
  if(!str) return [];
  return str.split(',').map(s=>s.trim()).filter(Boolean).map(s => s.startsWith('.') ? s : ('.'+s));
}

function parseTags(str){
  if(!str) return null;
  const t = str.split(',').map(s=>s.trim()).filter(Boolean);
  return t.length ? t : null;
}

async function mapRoot(isDry){
  const root_path = (document.getElementById('rootPath').value || '').trim();
  const categoryRaw = (document.getElementById('categoryId').value || '').trim();
  const category_id = categoryRaw ? parseInt(categoryRaw, 10) : null;
  const recursive = document.getElementById('recursive').checked;
  const exts = parseExtensions((document.getElementById('extensions').value || ''));
  const generate_thumbnails = document.getElementById('generateThumbnails').checked;
  const tags = parseTags((document.getElementById('tags').value || ''));

  const payload = {
    root_path,
    category_id,
    recursive,
    extensions: exts,
    dry_run: !!isDry,
    generate_thumbnails,
    tags
  };

  setMapRootOut('POST /prerolls/map-root ...');
  try{
    const res = await fetch('/prerolls/map-root', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const j = await res.json();
    setMapRootOut(JSON.stringify(j,null,2));
  }catch(e){
    setMapRootOut('Error: '+e);
  }
}

/* Existing quick actions */
async function reinit(){
  setStatus('Rebuilding thumbnails...');
  setOut('POST /thumbnails/rebuild?force=true ...');
  try{
    const res = await fetch('/thumbnails/rebuild?force=true', { method:'POST' });
    const j = await res.json();
    setOut(JSON.stringify(j,null,2));
    setStatus('Done.');
  }catch(e){
    setOut('Error: '+e);
    setStatus('Failed.');
  }
}

async function ffmpeg(){
  setStatus('Probing ffmpeg...');
  try{
    const res = await fetch('/system/ffmpeg-info');
    const j = await res.json();
    setOut(JSON.stringify(j,null,2));
    setStatus('OK.');
  }catch(e){
    setOut('Error: '+e);
    setStatus('Failed.');
  }
}

async function plex(){
  setStatus('Checking Plex status...');
  try{
    const res = await fetch('/plex/status');
    const j = await res.json();
    setOut(JSON.stringify(j,null,2));
    setStatus('OK.');
  }catch(e){
    setOut('Error: '+e);
    setStatus('Failed.');
  }
}

async function jellyfin(){
  setStatus('Checking Jellyfin status...');
  try{
    const res = await fetch('/jellyfin/status');
    const j = await res.json();
    setOut(JSON.stringify(j,null,2));
    setStatus('OK.');
  }catch(e){
    setOut('Error: '+e);
    setStatus('Failed.');
  }
}

async function version(){
  setStatus('Getting version...');
  try{
    const res = await fetch('/system/version');
    const j = await res.json();
    setOut(JSON.stringify(j,null,2));
    setStatus('OK.');
  }catch(e){
    setOut('Error: '+e);
    setStatus('Failed.');
  }
}

/* Initialize UI */
window.addEventListener('DOMContentLoaded', () => {
  loadMappings().catch(()=>{});
});
</script>
</body>
</html>"""
    return Response(content=html, media_type="text/html")
@app.post("/plex/connect")
def connect_plex(request: PlexConnectRequest, db: Session = Depends(get_db)):
    url = (request.url or "").strip()
    token = (request.token or "").strip()

    # Validate input
    if not url:
        raise HTTPException(status_code=422, detail="Plex server URL is required")
    if not token:
        raise HTTPException(status_code=422, detail="Plex authentication token is required")

    # Normalize URL format (default to http:// when scheme missing)
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"

    try:
        _file_log(f"/plex/connect: Testing connection to {url}")
        connector = PlexConnector(url, token)
        if connector.test_connection():
            # Save to settings (do not persist plaintext token)
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=url, plex_token=None)
                db.add(setting)
                _file_log(f"/plex/connect: Created new settings record")
            else:
                setting.plex_url = url
                setting.plex_token = None
                setting.updated_at = datetime.datetime.utcnow()
                _file_log(f"/plex/connect: Updated existing settings")

            # Persist token in secure store
            provider_name = "unknown"
            try:
                if secure_store.set_plex_token(token):
                    provider_name = secure_store.provider_info()[1]
                    _file_log(f"/plex/connect: ✓ Token saved to secure store ({provider_name})")
                else:
                    _file_log(f"/plex/connect: ⚠ Failed to save token to secure store", level="ERROR")
                    raise HTTPException(status_code=500, detail="Failed to save token to secure storage. Please ensure Windows Credential Manager is available.")
            except HTTPException:
                raise
            except Exception as e:
                _file_log(f"/plex/connect: ⚠ Exception saving token: {e}", level="ERROR")
                raise HTTPException(status_code=500, detail=f"Failed to save token securely: {str(e)}")

            db.commit()
            _file_log(f"/plex/connect: ✓ Connection successful - URL: {url}, Token storage: {provider_name}")
            return {
                "connected": True,
                "message": "Successfully connected to Plex server",
                "token_storage": provider_name
            }
        else:
            _file_log(f"/plex/connect: ✗ Connection test failed for {url}", level="ERROR")
            raise HTTPException(status_code=422, detail="Failed to connect to Plex server. Please check your URL and token.")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Connection error: {str(e)}")

@app.get("/plex/status")
def get_plex_status(db: Session = Depends(get_db)):
    """
    Return Plex connection status without throwing 500s.
    Always returns 200 with a JSON object. Logs internal errors.
    Triggers a best-effort settings schema migration if a legacy DB is detected.

    Enhancement: fall back to secure_store token when Setting.plex_token is None
    (e.g., after manual X-Plex-Token connect that avoids persisting plaintext).
    """
    def _do_fetch():
        setting = db.query(models.Setting).first()

        # Resolve URL and token with secure-store fallback
        plex_url = getattr(setting, "plex_url", None) if setting else None
        token = None
        token_source = None
        try:
            token = getattr(setting, "plex_token", None) if setting else None
            if token:
                token_source = "database"
        except Exception:
            token = None
        if not token:
            try:
                token = secure_store.get_plex_token()
                if token:
                    token_source = "secure_store"
                    _file_log(f"/plex/status: Using token from secure store (DB token was empty)")
            except Exception as e:
                _file_log(f"/plex/status: Could not access secure store: {e}")
                token = None

        # If either piece is missing, report disconnected with detailed diagnostics
        if not plex_url or not token:
            out = {"connected": False}
            try:
                out["url"] = plex_url
                out["has_token"] = bool(token)
                out["provider"] = secure_store.provider_info()[1]
                
                # Add detailed error messages for troubleshooting
                if not plex_url and not token:
                    out["error"] = "not_configured"
                    out["message"] = "Plex server not configured. Please connect to your Plex server."
                elif not plex_url:
                    out["error"] = "missing_url"
                    out["message"] = "Plex server URL not set. Please reconnect to your Plex server."
                else:
                    out["error"] = "missing_token"
                    out["message"] = "Plex authentication token not found. Please reconnect to your Plex server."
                
                _file_log(f"/plex/status: Disconnected - URL: {bool(plex_url)}, Token: {bool(token)}")
            except Exception as e:
                _file_log(f"/plex/status: Error building disconnected response: {e}", level="ERROR")
                pass
            return out

        connector = PlexConnector(plex_url, token)
        try:
            info = connector.get_server_info() or {}
        except Exception as e:
            _file_log(f"/plex/status: Connection test failed for {plex_url}: {e}", level="WARNING")
            return {
                "connected": False,
                "url": plex_url,
                "has_token": True,
                "error": "connection_failed",
                "message": f"Could not connect to Plex server at {plex_url}. Please verify the URL and that the server is running."
            }
        
        if not isinstance(info, dict):
            info = {}
        
        is_connected = info.get("connected", False)
        info.setdefault("connected", False)
        
        # Surface resolved URL and token source for diagnostics
        try:
            info.setdefault("url", plex_url)
            if token_source:
                info["token_source"] = token_source
            # Commented out to reduce log verbosity (called every 30 seconds by frontend polling)
            # if is_connected:
            #     _file_log(f"/plex/status: Connected successfully (token from {token_source})")
        except Exception:
            pass
        return info

    try:
        return _do_fetch()
    except OperationalError as oe:
        # Auto-migrate settings schema then retry once
        try:
            _file_log(f"/plex/status OperationalError: {oe} (attempting schema migration)")
            _file_log(">>> UPGRADE DETECTED: Migrating database schema for Plex settings...")
        except Exception:
            pass
        try:
            ensure_settings_schema_now()
            _file_log(">>> UPGRADE SUCCESS: Database schema migration completed")
            result = _do_fetch()
            _file_log(f">>> UPGRADE STATUS: Plex connection status after migration - connected: {result.get('connected', False)}")
            return result
        except Exception as e2:
            try:
                _file_log(f">>> UPGRADE FAILED: Post-migration fetch failed: {e2}")
            except Exception:
                pass
            return {
                "connected": False,
                "error": "migration_failed",
                "message": "Database migration failed. Please check logs or try reconnecting to Plex."
            }
    except Exception as e:
        try:
            _file_log(f"/plex/status error: {e}")
        except Exception:
            pass
        # Never propagate error to the UI; keep the dashboard stable
        return {
            "connected": False,
            "error": "unknown",
            "message": "An unexpected error occurred checking Plex status. Please try reconnecting."
        }

@app.post("/plex/disconnect")
def disconnect_plex(db: Session = Depends(get_db)):
    """Disconnect from Plex server by clearing stored credentials"""
    setting = db.query(models.Setting).first()

    # Clear secure token (best-effort)
    try:
        secure_store.delete_plex_token()
    except Exception:
        pass

    if setting:
        setting.plex_url = None
        setting.plex_token = None
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()

    return {"disconnected": True, "message": "Successfully disconnected from Plex server"}

@app.post("/plex/connect/stable-token")
def connect_plex_stable_token(request: PlexStableConnectRequest, db: Session = Depends(get_db)):
    """Connect to Plex server using stable token from config file"""
    url = (getattr(request, "url", None) or "").strip()

    # Normalize URL format (default to http:// when scheme missing)
    if not url:
        raise HTTPException(status_code=422, detail="Plex server URL is required")
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"

    try:
        # Create connector without explicit token - it will try to load stable token
        connector = PlexConnector(url)
        if connector.token:
            if connector.test_connection():
                # Save to settings
                setting = db.query(models.Setting).first()
                if not setting:
                    setting = models.Setting(plex_url=url, plex_token=connector.token)
                    db.add(setting)
                else:
                    setting.plex_url = url
                    setting.plex_token = connector.token
                    setting.updated_at = datetime.datetime.utcnow()
                db.commit()
                return {
                    "connected": True,
                    "message": "Successfully connected to Plex server using stable token",
                    "method": "stable_token"
                }
            else:
                # Keep UI stable with structured response
                return {
                    "connected": False,
                    "message": "Failed to connect to Plex server with stable token. Please verify URL and token.",
                    "method": "stable_token"
                }
        else:
            # No stable token available
            return {
                "connected": False,
                "message": "No stable token found. Run setup_plex_token.exe or save token via UI.",
                "method": "stable_token"
            }
    except Exception as e:
        # Keep contract stable with 200 where possible
        return {
            "connected": False,
            "message": f"Connection error: {str(e)}",
            "method": "stable_token"
        }

@app.post("/plex/auto-connect")
def plex_auto_connect(req: PlexAutoConnectRequest, db: Session = Depends(get_db)):
    """
    Docker-friendly quick connect:
    - Accepts a server X-Plex-Token (optional; falls back to secure store)
    - Probes common Docker host URLs and any user-provided candidate URLs
    - Persists the first reachable URL+token pair
    """
    # Resolve token
    token = (getattr(req, "token", None) or "").strip() or None
    if not token:
        try:
            token = secure_store.get_plex_token()
        except Exception:
            token = None
    if not token:
        raise HTTPException(status_code=422, detail="Missing Plex token. Paste your X-Plex-Token or save it via /plex/stable-token/save")

    # Build candidate URL list: user-specified first, then Docker heuristics
    candidates: list[str] = []
    try:
        if isinstance(getattr(req, "urls", None), list):
            for u in req.urls or []:
                if u and str(u).strip():
                    candidates.append(_normalize_url(str(u)))
    except Exception:
        pass
    for u in _docker_candidate_urls():
        if u not in candidates:
            candidates.append(u)

    tried = []
    chosen = None
    invalid_token_seen = False

    def _bool_env_local(name: str):
        try:
            v = os.environ.get(name)
            if v is None:
                return None
            s = str(v).strip().lower()
            if s in ("1","true","yes","on"):
                return True
            if s in ("0","false","no","off"):
                return False
        except Exception:
            pass
        return None

    for u in candidates:
        nu = _normalize_url(u)

        # Decide TLS verification (mirror _probe_plex_url with Docker host allowances)
        verify = True
        env = _bool_env_local("NEXROLL_PLEX_TLS_VERIFY")
        if env is not None:
            verify = bool(env)
        else:
            if nu.startswith("https://"):
                try:
                    from urllib.parse import urlparse
                    host = (urlparse(nu).hostname or "").lower()
                except Exception:
                    host = ""
                private = False
                if host in ("localhost", "127.0.0.1", "host.docker.internal", "gateway.docker.internal"):
                    private = True
                elif host.startswith("192.168.") or host.startswith("10."):
                    private = True
                elif host.startswith("172."):
                    parts = host.split(".")
                    if len(parts) >= 2:
                        try:
                            second = int(parts[1])
                            if 16 <= second <= 31:
                                private = True
                        except Exception:
                            pass
                if private:
                    verify = False

        det = {"url": nu, "ok": False, "status": None, "verify": verify, "error": None, "reachable": False}

        headers = {"X-Plex-Token": token}
        # First, verify token works against an authenticated endpoint
        try:
            r = requests.get(f"{nu}/status/sessions", headers=headers, timeout=5, verify=verify)
            det["status"] = r.status_code
            if r.status_code == 200:
                det["ok"] = True
                tried.append(det)
                chosen = nu
                break
            else:
                if r.status_code in (401, 403):
                    det["error"] = "invalid_token"
                    invalid_token_seen = True
                else:
                    det["error"] = f"http_{r.status_code}"
        except requests.exceptions.SSLError:
            det["error"] = "ssl_verify_failed"
        except requests.exceptions.ConnectTimeout:
            det["error"] = "timeout"
        except requests.exceptions.ReadTimeout:
            det["error"] = "timeout"
        except requests.exceptions.ConnectionError as ce:
            emsg = str(getattr(ce, "__cause__", None) or getattr(ce, "__context__", None) or ce)
            if ("Name or service not known" in emsg) or ("getaddrinfo" in emsg) or ("No such host" in emsg) or ("nodename nor servname provided" in emsg):
                det["error"] = "dns"
            elif ("Connection refused" in emsg) or ("ECONNREFUSED" in emsg):
                det["error"] = "conn_refused"
            elif ("Network is unreachable" in emsg) or ("EHOSTUNREACH" in emsg):
                det["error"] = "host_unreachable"
            elif "timed out" in emsg:
                det["error"] = "timeout"
            else:
                det["error"] = "conn_error"
        except Exception:
            det["error"] = "error"

        # Second, check basic reachability without token for diagnostics
        try:
            r2 = requests.get(f"{nu}/identity", timeout=5, verify=verify)
            if r2.status_code == 200:
                det["reachable"] = True
        except Exception:
            pass

        tried.append(det)

    if not chosen:
        return {
            "connected": False,
            "invalid_token": invalid_token_seen,
            "message": "No reachable Plex server found" + (" (token invalid)" if invalid_token_seen else " with the provided/saved token"),
            "tried": tried,
        }

    # Persist settings
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=chosen, plex_token=token)
        db.add(setting)
    else:
        setting.plex_url = chosen
        setting.plex_token = token
        try:
            setting.updated_at = datetime.datetime.utcnow()
        except Exception:
            pass
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to persist Plex settings: {e}")

    return {"connected": True, "url": chosen, "tried": tried, "method": "auto_connect"}


# Diagnostics: probe a Plex URL with optional token and TLS verify control
@app.get("/plex/probe")
def plex_probe(url: str, token: str | None = None, verify: bool | None = None):
    """
    Probe a Plex base URL for reachability and token validity.

    Query params:
      - url: Plex base URL (http/https)
      - token: optional X-Plex-Token; if omitted, uses secure store if present
      - verify: optional true/false to override TLS verification

    Returns detailed diagnostics without exposing the token value.
    """
    import time as _time
    from urllib.parse import urlparse as _urlparse
    import socket as _socket
    import requests as _rq

    def _bool_env(name: str):
        try:
            v = os.environ.get(name)
            if v is None:
                return None
            s = str(v).strip().lower()
            if s in ("1","true","yes","on"):
                return True
            if s in ("0","false","no","off"):
                return False
        except Exception:
            pass
        return None

    nu = _normalize_url(url or "")
    if not nu:
        raise HTTPException(status_code=422, detail="Missing or invalid url")

    # Resolve token
    tok = (token or "").strip() or None
    if not tok:
        try:
            tok = secure_store.get_plex_token()
        except Exception:
            tok = None

    # TLS verification heuristic (same as _probe_plex_url), overridable by query param
    verify_eff = True
    env = _bool_env("NEXROLL_PLEX_TLS_VERIFY")
    if env is not None:
        verify_eff = bool(env)
    else:
        if nu.startswith("https://"):
            try:
                host = (_urlparse(nu).hostname or "").lower()
            except Exception:
                host = ""
            private = False
            if host in ("localhost", "127.0.0.1", "host.docker.internal", "gateway.docker.internal"):
                private = True
            elif host.startswith("192.168.") or host.startswith("10."):
                private = True
            elif host.startswith("172."):
                parts = host.split(".")
                if len(parts) >= 2:
                    try:
                        second = int(parts[1])
                        if 16 <= second <= 31:
                            private = True
                    except Exception:
                        pass
            if private:
                verify_eff = False
    if verify is not None:
        verify_eff = bool(verify)

    # DNS resolution diagnostics
    host = ""
    dns_ok = None
    ips: list[str] = []
    try:
        host = (_urlparse(nu).hostname or "").lower()
        fams = [getattr(_socket, "AF_INET", None)]
        for fam in [f for f in fams if f is not None]:
            try:
                infos = _socket.getaddrinfo(host, None, family=fam)
                for inf in infos:
                    try:
                        ip = inf[4][0]
                        if ip and ip not in ips:
                            ips.append(ip)
                    except Exception:
                        pass
                dns_ok = True if ips else False
            except Exception:
                pass
        if dns_ok is None:
            # gethostbyname fallback
            try:
                ip = _socket.gethostbyname(host)
                if ip:
                    ips.append(ip)
                    dns_ok = True
            except Exception:
                dns_ok = False
    except Exception:
        dns_ok = False

    def _classify_error(exc: Exception) -> str:
        if isinstance(exc, _rq.exceptions.SSLError):
            return "ssl_verify_failed"
        if isinstance(exc, _rq.exceptions.ConnectTimeout) or isinstance(exc, _rq.exceptions.ReadTimeout):
            return "timeout"
        if isinstance(exc, _rq.exceptions.ConnectionError):
            emsg = str(getattr(exc, "__cause__", None) or getattr(exc, "__context__", None) or exc)
            if ("Name or service not known" in emsg) or ("getaddrinfo" in emsg) or ("No such host" in emsg) or ("nodename nor servname provided" in emsg):
                return "dns"
            if ("Connection refused" in emsg) or ("ECONNREFUSED" in emsg):
                return "conn_refused"
            if ("Network is unreachable" in emsg) or ("EHOSTUNREACH" in emsg):
                return "host_unreachable"
            if "timed out" in emsg:
                return "timeout"
            return "conn_error"
        return "error"

    # Probe /identity (no token)
    ident = {"status": None, "latency_ms": None, "error": None}
    try:
        t0 = _time.time()
        r = requests.get(f"{nu}/identity", timeout=5, verify=verify_eff)
        ident["status"] = r.status_code
        ident["latency_ms"] = int((_time.time() - t0) * 1000)
    except Exception as e:
        ident["error"] = _classify_error(e)

    # Probe /status/sessions (with token if available)
    sessions = {"status": None, "latency_ms": None, "error": None, "invalid_token": None}
    if tok:
        try:
            t0 = _time.time()
            r = requests.get(f"{nu}/status/sessions", headers={"X-Plex-Token": tok}, timeout=5, verify=verify_eff)
            sessions["status"] = r.status_code
            sessions["latency_ms"] = int((_time.time() - t0) * 1000)
            if r.status_code in (401, 403):
                sessions["invalid_token"] = True
            else:
                sessions["invalid_token"] = False
        except Exception as e:
            sessions["error"] = _classify_error(e)
    else:
        sessions["error"] = "no_token"

    # Summarize
    reachable = bool((ident.get("status") == 200) or (sessions.get("status") == 200))
    invalid_token = bool(sessions.get("invalid_token")) if tok else False

    host_type = "unknown"
    try:
        if host in ("localhost", "127.0.0.1"):
            host_type = "localhost"
        elif ".plex.direct" in host:
            host_type = "plex.direct"
        elif host.startswith(("192.168.", "10.")) or (host.startswith("172.") and len(host.split(".")) > 1 and 16 <= int(host.split(".")[1]) <= 31):
            host_type = "lan"
        else:
            host_type = "public"
    except Exception:
        pass

    advice = []
    if invalid_token:
        advice.append("Token rejected by server (401/403). Ensure you used a server token, not a Plex.tv account token.")
    if not reachable:
        if ident.get("error") == "ssl_verify_failed" or sessions.get("error") == "ssl_verify_failed":
            advice.append("HTTPS TLS verification failed. Set NEXROLL_PLEX_TLS_VERIFY=0 or trust the certificate.")
        if ident.get("error") == "dns" or sessions.get("error") == "dns" or dns_ok is False:
            advice.append("DNS failed. Verify that this hostname resolves from the NeXroll host/container.")
        if ident.get("error") == "conn_refused":
            advice.append("Connection refused. Verify Plex is running and listening on the provided host:port.")
        if ident.get("error") == "host_unreachable":
            advice.append("Network unreachable from NeXroll to Plex. Check Docker networking or firewall.")
        if not advice:
            advice.append("If using Docker, try http://host.docker.internal:32400 or the host LAN IP.")

    return {
        "input": {"url": nu, "token_present": bool(tok), "verify_override": verify, "verify_effective": verify_eff},
        "dns": {"host": host, "ok": dns_ok, "ips": ips},
        "identity": ident,
        "sessions": sessions,
        "reachable": reachable,
        "invalid_token": invalid_token,
        "host_type": host_type,
        "advice": advice,
    }
@app.post("/plex/tv/start")
def plex_tv_start(forward_url: str | None = None):
    """
    Start Plex.tv OAuth device login and return the URL to open.
    The session id can be polled via /plex/tv/status/{id} and finalized via /plex/tv/connect.
    """
    try:
        # Periodically purge expired sessions
        try:
            now = datetime.datetime.utcnow()
            expired = [k for k, v in OAUTH_SESSIONS.items() if v.get("expires") and v["expires"] < now]
            for k in expired:
                OAUTH_SESSIONS.pop(k, None)
        except Exception:
            pass

        headers = _build_plex_headers()
        pinlogin = MyPlexPinLogin(headers=headers, oauth=True)
        url = pinlogin.oauthUrl(forward_url)
        # Spawn background thread and return immediately
        pinlogin.run(timeout=600)  # 10 minutes window

        sid = str(uuid.uuid4())
        OAUTH_SESSIONS[sid] = {
            "pin": pinlogin,
            "headers": headers,
            "created": datetime.datetime.utcnow(),
            "expires": datetime.datetime.utcnow() + datetime.timedelta(minutes=10),
        }
        return {"id": sid, "url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Plex OAuth: {str(e)}")


@app.get("/plex/tv/status/{sid}")
def plex_tv_status(sid: str):
    """
    Poll the status of a Plex.tv OAuth device login.
    Returns: { status: pending|success|expired|not_found|error, token_preview? }
    """
    s = OAUTH_SESSIONS.get(sid)
    if not s:
        return {"status": "not_found"}
    pin = s.get("pin")
    try:
        if getattr(pin, "expired", False):
            return {"status": "expired"}
        token = getattr(pin, "token", None)
        if token:
            preview = (token[:8] + "...") if len(token) > 8 else token
            return {"status": "success", "token_preview": preview}
        return {"status": "pending"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/plex/tv/connect")
def plex_tv_connect(req: PlexTvConnectRequest, db: Session = Depends(get_db)):
    """
    Complete Plex.tv OAuth by resolving a reachable server URL and saving credentials.
    Body: { id?: string, token?: string, prefer_local?: bool, save_token?: bool }
    """
    # Resolve token from request or session
    token = (getattr(req, "token", None) or "").strip() or None
    if not token and getattr(req, "id", None):
        st = OAUTH_SESSIONS.get(req.id)
        if st and getattr(st.get("pin"), "token", None):
            token = st["pin"].token

    if not token:
        raise HTTPException(status_code=422, detail="Missing token or session id")

    try:
        # Discover servers from Plex account
        account = MyPlexAccount(token=token)
        resources = account.resources()
        # Build a robust list of server-capable resources (handles string or list provides)
        servers = []
        for r in resources:
            prov = getattr(r, "provides", None)
            provs = []
            try:
                if isinstance(prov, str):
                    provs = [p.strip().lower() for p in prov.split(",")]
                elif isinstance(prov, (list, set, tuple)):
                    provs = [str(p).strip().lower() for p in prov]
            except Exception:
                provs = []
            # Also consider product/name hints
            product = (getattr(r, "product", None) or "")
            name = (getattr(r, "name", None) or "")
            if ("server" in provs) or ("server" in str(product).lower()) or ("plex media server" in str(name).lower()):
                servers.append(r)
        candidates = servers if servers else list(resources)

        # Prefer owned resources and try to connect
        baseurl = None
        server_name = None
        machine_id = None
        ordered = sorted(candidates, key=lambda r: (not getattr(r, "owned", True)))
        for res in ordered:
            try:
                srv = res.connect(timeout=5)
                baseurl = getattr(srv, "_baseurl", None) or getattr(srv, "url", None)
                server_name = getattr(srv, "friendlyName", None) or getattr(srv, "name", None) or getattr(res, "name", None)
                machine_id = getattr(srv, "machineIdentifier", None) or getattr(res, "clientIdentifier", None)
                if baseurl:
                    break
            except Exception:
                continue

        # Fallback: try first declared connection URI across all resources
        if not baseurl:
            for res in ordered:
                try:
                    conns = getattr(res, "connections", []) or []
                    # Prefer local connections when available
                    if conns:
                        try:
                            conns = sorted(conns, key=lambda c: (not getattr(c, "local", False)))
                        except Exception:
                            pass
                        baseurl = getattr(conns[0], "uri", None)
                        server_name = getattr(res, "name", None)
                        machine_id = getattr(res, "clientIdentifier", None)
                        if baseurl:
                            break
                except Exception:
                    continue

        if not baseurl:
            raise HTTPException(status_code=502, detail="Unable to resolve a reachable Plex server URL. Ensure your Plex server is claimed on this account and Remote Access is enabled if not on the same LAN.")

        # Persist settings
        setting = db.query(models.Setting).first()
        if not setting:
            setting = models.Setting(plex_url=baseurl, plex_token=token)
            db.add(setting)
        else:
            setting.plex_url = baseurl
            setting.plex_token = token
            setting.updated_at = datetime.datetime.utcnow()

        # Save to secure store (best effort)
        try:
            if getattr(req, "save_token", True):
                secure_store.set_plex_token(token)
        except Exception:
            pass

        db.commit()
        return {
            "connected": True,
            "message": "Connected via Plex.tv authentication",
            "method": "plex_oauth",
            "url": baseurl,
            "server_name": server_name,
            "machine_identifier": machine_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to complete Plex.tv auth: {str(e)}")

def calculate_file_hash(file_path: str) -> str:
    """Calculate SHA256 hash of a file for duplicate detection"""
    import hashlib
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def calculate_content_hash(content: bytes) -> str:
    """Calculate SHA256 hash of file content for duplicate detection"""
    import hashlib
    return hashlib.sha256(content).hexdigest()

@app.post("/prerolls/check-duplicate")
def check_duplicate(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Check if an uploaded file is a duplicate based on hash"""
    try:
        # Read file content
        content = file.file.read()
        file_hash = calculate_content_hash(content)
        
        # Check if a preroll with this hash already exists
        existing = db.query(models.Preroll).filter(models.Preroll.file_hash == file_hash).first()
        
        if existing:
            # Return duplicate info
            return {
                "is_duplicate": True,
                "existing_preroll": {
                    "id": existing.id,
                    "filename": existing.filename,
                    "display_name": existing.display_name,
                    "category_id": existing.category_id,
                    "category_name": existing.category.name if existing.category else None,
                    "file_size": existing.file_size,
                    "upload_date": existing.upload_date.isoformat() if existing.upload_date else None
                },
                "file_hash": file_hash
            }
        else:
            return {
                "is_duplicate": False,
                "file_hash": file_hash
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking duplicate: {str(e)}")

@app.post("/prerolls/upload")
def upload_preroll(
    file: UploadFile = File(...),
    tags: str = Form(""),
    category_id: str = Form(""),
    category_ids: str = Form(""),
    description: str = Form(""),
    duplicate_action: str = Form(""),  # skip, replace, rename, or empty to allow duplicate
    file_hash: str = Form(""),  # Hash from check-duplicate endpoint
    db: Session = Depends(get_db)
):
    # Ensure directories exist
    os.makedirs(PREROLLS_DIR, exist_ok=True)
    os.makedirs(THUMBNAILS_DIR, exist_ok=True)

    def _parse_id_list(s: str) -> list[int]:
        ids: list[int] = []
        if s and s.strip():
            try:
                data = json.loads(s)
                if isinstance(data, list):
                    ids = [int(x) for x in data if str(x).strip().isdigit()]
            except Exception:
                ids = [int(x) for x in [p.strip() for p in s.split(",")] if str(x).isdigit()]
        # unique preserve order
        seen = set()
        uniq = []
        for x in ids:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq

    all_ids = _parse_id_list(category_ids)
    # Determine primary category (explicit category_id first, otherwise first from category_ids)
    primary_category_id = None
    if category_id and category_id.strip():
        try:
            primary_category_id = int(category_id)
        except Exception:
            primary_category_id = None
    if primary_category_id is None and all_ids:
        primary_category_id = all_ids[0]

    # Determine category directory name for storage
    category_dir = "Default"
    if primary_category_id:
        category = db.query(models.Category).filter(models.Category.id == primary_category_id).first()
        if category:
            category_dir = category.name

    # Create category directories if they don't exist
    category_path = os.path.join(PREROLLS_DIR, category_dir)
    thumbnail_category_path = os.path.join(THUMBNAILS_DIR, category_dir)
    os.makedirs(category_path, exist_ok=True)
    os.makedirs(thumbnail_category_path, exist_ok=True)

    # Read file content once
    content = file.file.read()
    file_size = len(content)
    
    # Calculate hash if not provided
    if not file_hash or not file_hash.strip():
        file_hash = calculate_content_hash(content)
    
    # Check for duplicates and handle according to duplicate_action
    existing_duplicate = db.query(models.Preroll).filter(models.Preroll.file_hash == file_hash).first()
    
    if existing_duplicate and duplicate_action:
        if duplicate_action == "skip":
            # Return the existing preroll info without creating a new one
            return {
                "message": "Duplicate skipped",
                "skipped": True,
                "existing_preroll": {
                    "id": existing_duplicate.id,
                    "filename": existing_duplicate.filename,
                    "display_name": existing_duplicate.display_name
                }
            }
        elif duplicate_action == "replace":
            # Delete the existing preroll (will also delete the file)
            try:
                if existing_duplicate.path and os.path.exists(existing_duplicate.path):
                    os.remove(existing_duplicate.path)
                if existing_duplicate.thumbnail and os.path.exists(existing_duplicate.thumbnail):
                    os.remove(existing_duplicate.thumbnail)
                db.delete(existing_duplicate)
                db.commit()
            except Exception as e:
                db.rollback()
                raise HTTPException(status_code=500, detail=f"Failed to replace duplicate: {str(e)}")
        elif duplicate_action == "rename":
            # Auto-rename the new file to avoid conflict
            base, ext = os.path.splitext(file.filename)
            counter = 1
            new_filename = file.filename
            while db.query(models.Preroll).filter(
                models.Preroll.filename == new_filename,
                models.Preroll.category_id == primary_category_id
            ).first():
                new_filename = f"{base}_{counter}{ext}"
                counter += 1
            file.filename = new_filename
    
    # Save file to disk (single physical copy regardless of multi-category assignment)
    file_path = os.path.join(category_path, file.filename)
    with open(file_path, "wb") as f:
        f.write(content)

    # Probe duration (best-effort)
    duration = None
    try:
        result = _run_subprocess(
            [get_ffprobe_cmd(), "-v", "quiet", "-print_format", "json", "-show_format", file_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            probe_data = json.loads(result.stdout) if result.stdout else {}
            duration = float(probe_data.get("format", {}).get("duration"))
    except Exception:
        pass

    # Normalize tags -> JSON string array
    processed_tags = None
    if tags and tags.strip():
        try:
            processed_tags = json.dumps(json.loads(tags))
        except Exception:
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
            processed_tags = json.dumps(tag_list)

    # Persist initial row (to get ID for thumbnail naming)
    preroll = models.Preroll(
        filename=file.filename,
        display_name=None,
        path=file_path,
        thumbnail=None,
        tags=processed_tags,
        category_id=primary_category_id,
        description=description or None,
        duration=duration,
        file_size=file_size,
        file_hash=file_hash,
    )
    db.add(preroll)
    db.commit()
    db.refresh(preroll)

    # If file is named 'loading.*', place it into a unique subfolder to avoid name collisions
    try:
        stem = os.path.splitext(file.filename)[0].lower()
        if stem == "loading":
            subdir = os.path.join(category_path, f"Preroll_{preroll.id}")
            os.makedirs(subdir, exist_ok=True)
            new_abs = os.path.join(subdir, file.filename)
            if os.path.abspath(new_abs) != os.path.abspath(file_path):
                try:
                    os.replace(file_path, new_abs)
                except Exception:
                    shutil.copy2(file_path, new_abs)
                    try:
                        os.remove(file_path)
                    except Exception:
                        pass
            file_path = new_abs
            preroll.path = new_abs
    except Exception as e:
        _file_log(f"upload_preroll: move to subfolder failed: {e}")

    # Generate id-prefixed thumbnail under primary category
    thumbnail_path = None
    try:
        thumbnail_abs = os.path.join(thumbnail_category_path, f"{preroll.id}_{file.filename}.jpg")
        tmp_thumb = thumbnail_abs + ".tmp.jpg"
        res = _run_subprocess(
            [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", file_path, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp_thumb],
            capture_output=True,
            text=True,
        )
        if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp_thumb):
            _file_log(f"FFmpeg thumbnail generation failed: {getattr(res, 'stderr', '')}")
            _generate_placeholder(tmp_thumb)
        try:
            if os.path.exists(thumbnail_abs):
                os.remove(thumbnail_abs)
        except Exception:
            pass
        os.replace(tmp_thumb, thumbnail_abs)
        thumbnail_path = os.path.relpath(thumbnail_abs, data_dir).replace("\\", "/")
        preroll.thumbnail = thumbnail_path
    except Exception as e:
        _file_log(f"upload_preroll: thumbnail generation error: {e}")
        preroll.thumbnail = None

    # Assign many-to-many categories (store a single file; categories are tags)
    try:
        assoc_ids = list(all_ids)
        if primary_category_id and primary_category_id not in assoc_ids:
            assoc_ids.insert(0, primary_category_id)
        if assoc_ids:
            cats = db.query(models.Category).filter(models.Category.id.in_(assoc_ids)).all()
            preroll.categories = cats
    except Exception as e:
        _file_log(f"upload_preroll: category association failed: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        _file_log(f"upload_preroll: final commit failed: {e}")

    # Auto-apply to Plex/Jellyfin if primary category is already applied or currently active
    auto_applied = False
    if primary_category_id:
        try:
            category = db.query(models.Category).filter(models.Category.id == primary_category_id).first()
            if category:
                should_apply = getattr(category, "apply_to_plex", False)
                
                # Also check if this category is currently active via scheduler
                if not should_apply:
                    setting = db.query(models.Setting).first()
                    if setting and getattr(setting, "active_category", None) == category.id:
                        should_apply = True
                        _file_log(f"upload_preroll: Category '{category.name}' (ID {category.id}) is currently active via schedule")
                
                if should_apply:
                    _file_log(f"upload_preroll: Auto-applying category '{category.name}' (ID {category.id}) to Plex after upload")
                    ok = _apply_category_to_plex_and_track(db, category.id, ttl=15)
                    if ok:
                        auto_applied = True
                        _file_log(f"upload_preroll: Successfully auto-applied category '{category.name}' to Plex")
                    else:
                        _file_log(f"upload_preroll: Failed to auto-apply category '{category.name}' to Plex")
        except Exception as e:
            _file_log(f"upload_preroll: Error auto-applying to Plex: {e}")

    return {
        "uploaded": True,
        "id": preroll.id,
        "filename": preroll.filename,
        "display_name": preroll.display_name,
        "thumbnail": thumbnail_path,
        "duration": duration,
        "file_size": file_size,
        "category_id": preroll.category_id,
        "categories": [{"id": c.id, "name": c.name} for c in (preroll.categories or [])],
        "auto_applied": auto_applied,
    }

@app.post("/prerolls/upload-multiple")
def upload_multiple_prerolls(
    files: list[UploadFile] = File(...),
    tags: str = Form(""),
    category_id: str = Form(""),
    category_ids: str = Form(""),
    description: str = Form(""),
    db: Session = Depends(get_db)
):
    """Upload multiple preroll files at once with optional multi-category assignment"""
    if not files or len(files) == 0:
        raise HTTPException(status_code=422, detail="No files provided")

    def _parse_id_list(s: str) -> list[int]:
        ids: list[int] = []
        if s and s.strip():
            try:
                data = json.loads(s)
                if isinstance(data, list):
                    ids = [int(x) for x in data if str(x).strip().isdigit()]
            except Exception:
                ids = [int(x) for x in [p.strip() for p in s.split(",")] if str(x).isdigit()]
        # unique keep order
        seen = set()
        out = []
        for i in ids:
            if i not in seen:
                seen.add(i)
                out.append(i)
        return out

    all_ids = _parse_id_list(category_ids)

    results = []
    successful_uploads = 0

    for file in files:
        try:
            # Ensure directories exist
            os.makedirs(PREROLLS_DIR, exist_ok=True)
            os.makedirs(THUMBNAILS_DIR, exist_ok=True)

            # Resolve primary category
            primary_category_id = None
            if category_id and category_id.strip():
                try:
                    primary_category_id = int(category_id)
                except Exception:
                    primary_category_id = None
            if primary_category_id is None and all_ids:
                primary_category_id = all_ids[0]

            # Determine primary category directory name
            category_dir = "Default"
            if primary_category_id:
                category = db.query(models.Category).filter(models.Category.id == primary_category_id).first()
                if category:
                    category_dir = category.name

            # Ensure category folders
            category_path = os.path.join(PREROLLS_DIR, category_dir)
            thumb_cat_path = os.path.join(THUMBNAILS_DIR, category_dir)
            os.makedirs(category_path, exist_ok=True)
            os.makedirs(thumb_cat_path, exist_ok=True)

            # Save file to disk
            file_path = os.path.join(category_path, file.filename)
            file_size = 0
            with open(file_path, "wb") as f:
                content = file.file.read()
                file_size = len(content)
                f.write(content)

            # Probe duration (best-effort)
            duration = None
            try:
                result = _run_subprocess(
                    [get_ffprobe_cmd(), "-v", "quiet", "-print_format", "json", "-show_format", file_path],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    probe_data = json.loads(result.stdout) if result.stdout else {}
                    duration = float(probe_data.get("format", {}).get("duration"))
            except Exception:
                pass

            # Normalize tags -> JSON string array
            processed_tags = None
            if tags and tags.strip():
                try:
                    processed_tags = json.dumps(json.loads(tags))
                except Exception:
                    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
                    processed_tags = json.dumps(tag_list)

            # Persist preroll row (to get ID)
            preroll = models.Preroll(
                filename=file.filename,
                display_name=None,
                path=file_path,
                thumbnail=None,
                tags=processed_tags,
                category_id=primary_category_id,
                description=description or None,
                duration=duration,
                file_size=file_size,
            )
            db.add(preroll)
            db.commit()
            db.refresh(preroll)

            # If filename is 'loading.*', place into unique subfolder
            try:
                stem = os.path.splitext(file.filename)[0].lower()
                if stem == "loading":
                    subdir = os.path.join(category_path, f"Preroll_{preroll.id}")
                    os.makedirs(subdir, exist_ok=True)
                    new_abs = os.path.join(subdir, file.filename)
                    if os.path.abspath(new_abs) != os.path.abspath(file_path):
                        try:
                            os.replace(file_path, new_abs)
                        except Exception:
                            shutil.copy2(file_path, new_abs)
                            try:
                                os.remove(file_path)
                            except Exception:
                                pass
                    file_path = new_abs
                    preroll.path = new_abs
            except Exception as e:
                _file_log(f"upload_multiple: move to subfolder failed: {e}")

            # Generate id-prefixed thumbnail under primary category
            thumbnail_rel = None
            try:
                thumb_abs = os.path.join(thumb_cat_path, f"{preroll.id}_{file.filename}.jpg")
                tmp = thumb_abs + ".tmp.jpg"
                res = _run_subprocess(
                    [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", file_path, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp],
                    capture_output=True,
                    text=True,
                )
                if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp):
                    _file_log(f"FFmpeg thumbnail generation failed: {getattr(res, 'stderr', '')}")
                    _generate_placeholder(tmp)
                try:
                    if os.path.exists(thumb_abs):
                        os.remove(thumb_abs)
                except Exception:
                    pass
                os.replace(tmp, thumb_abs)
                thumbnail_rel = os.path.relpath(thumb_abs, data_dir).replace("\\", "/")
                preroll.thumbnail = thumbnail_rel
            except Exception as e:
                _file_log(f"upload_multiple: thumbnail generation error: {e}")
                preroll.thumbnail = None

            # Assign many-to-many categories
            try:
                assoc_ids = list(all_ids)
                if primary_category_id and primary_category_id not in assoc_ids:
                    assoc_ids.insert(0, primary_category_id)
                if assoc_ids:
                    cats = db.query(models.Category).filter(models.Category.id.in_(assoc_ids)).all()
                    preroll.categories = cats
            except Exception as e:
                _file_log(f"upload_multiple: category association failed: {e}")

            try:
                db.commit()
                db.refresh(preroll)
            except Exception as e:
                db.rollback()
                _file_log(f"upload_multiple: final commit failed: {e}")

            results.append({
                "filename": file.filename,
                "uploaded": True,
                "id": preroll.id,
                "thumbnail": thumbnail_rel,
                "duration": duration,
                "file_size": file_size,
                "category_id": preroll.category_id,
                "categories": [{"id": c.id, "name": c.name} for c in (preroll.categories or [])],
            })
            successful_uploads += 1

        except Exception as e:
            results.append({
                "filename": file.filename if hasattr(file, "filename") else "unknown",
                "uploaded": False,
                "error": str(e)
            })

    # Auto-apply to Plex/Jellyfin if primary category is already applied or currently active (after all uploads complete)
    auto_applied = False
    if successful_uploads > 0:
        primary_category_id = None
        if category_id and category_id.strip():
            try:
                primary_category_id = int(category_id)
            except Exception:
                pass
        if primary_category_id is None and all_ids:
            primary_category_id = all_ids[0]
        
        if primary_category_id:
            try:
                category = db.query(models.Category).filter(models.Category.id == primary_category_id).first()
                if category:
                    should_apply = getattr(category, "apply_to_plex", False)
                    
                    # Also check if this category is currently active via scheduler
                    if not should_apply:
                        setting = db.query(models.Setting).first()
                        if setting and getattr(setting, "active_category", None) == category.id:
                            should_apply = True
                            _file_log(f"upload_multiple: Category '{category.name}' (ID {category.id}) is currently active via schedule")
                    
                    if should_apply:
                        _file_log(f"upload_multiple: Auto-applying category '{category.name}' (ID {category.id}) to Plex after {successful_uploads} uploads")
                        ok = _apply_category_to_plex_and_track(db, category.id, ttl=15)
                        if ok:
                            auto_applied = True
                            _file_log(f"upload_multiple: Successfully auto-applied category '{category.name}' to Plex")
                        else:
                            _file_log(f"upload_multiple: Failed to auto-apply category '{category.name}' to Plex")
            except Exception as e:
                _file_log(f"upload_multiple: Error auto-applying to Plex: {e}")

    return {
        "total_files": len(files),
        "successful_uploads": successful_uploads,
        "failed_uploads": len(files) - successful_uploads,
        "results": results,
        "auto_applied": auto_applied,
    }

# ─────────────────────────────────────────────────────────────────────────────
# Video Scaling/Transcoding Endpoint
# ─────────────────────────────────────────────────────────────────────────────

class TranscodeRequest(BaseModel):
    resolution: str = "720p"  # 1080p, 720p, 480p
    replace_original: bool = True  # If false, creates a new file with suffix

@app.post("/prerolls/{preroll_id}/transcode")
def transcode_preroll(preroll_id: int, request: TranscodeRequest, db: Session = Depends(get_db)):
    """
    Transcode a preroll video to a different resolution.
    
    Useful for remote streaming where lower resolution prerolls 
    avoid live transcoding on the media server.
    
    Supported resolutions:
    - 1080p: 1920x1080 (Full HD)
    - 720p: 1280x720 (HD - recommended for remote streaming)
    - 480p: 854x480 (SD - low bandwidth)
    """
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")
    
    if not preroll.path or not os.path.exists(preroll.path):
        raise HTTPException(status_code=404, detail="Video file not found on disk")
    
    # Validate resolution
    resolution_map = {
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "480p": (854, 480),
    }
    if request.resolution not in resolution_map:
        raise HTTPException(status_code=400, detail=f"Invalid resolution. Supported: {', '.join(resolution_map.keys())}")
    
    target_width, target_height = resolution_map[request.resolution]
    
    # Check ffmpeg availability
    ffmpeg_cmd = get_ffmpeg_cmd()
    ffprobe_cmd = get_ffprobe_cmd()
    
    # Get current video resolution using ffprobe
    try:
        probe_result = _run_subprocess(
            [ffprobe_cmd, "-v", "error", "-select_streams", "v:0", 
             "-show_entries", "stream=width,height", "-of", "json", preroll.path],
            capture_output=True, text=True
        )
        if probe_result.returncode == 0:
            probe_data = json.loads(probe_result.stdout) if probe_result.stdout else {}
            streams = probe_data.get("streams", [])
            if streams:
                current_width = streams[0].get("width", 0)
                current_height = streams[0].get("height", 0)
                _file_log(f"[TRANSCODE] Current resolution: {current_width}x{current_height}")
                
                # Check if already at target resolution
                if current_width == target_width and current_height == target_height:
                    return {
                        "success": True,
                        "message": f"Video is already at {request.resolution} ({target_width}x{target_height})",
                        "skipped": True,
                        "current_resolution": f"{current_width}x{current_height}"
                    }
    except Exception as e:
        _file_log(f"[TRANSCODE] Warning: Could not probe video resolution: {e}")
    
    # Prepare output path
    original_path = Path(preroll.path)
    original_stem = original_path.stem
    original_suffix = original_path.suffix
    
    if request.replace_original:
        # Create temp file, then replace original
        temp_output = original_path.parent / f"{original_stem}_transcoding{original_suffix}"
        final_output = original_path
    else:
        # Create new file with resolution suffix
        final_output = original_path.parent / f"{original_stem}_{request.resolution}{original_suffix}"
        temp_output = final_output
    
    _file_log(f"[TRANSCODE] Starting transcode of '{preroll.filename}' to {request.resolution}")
    _file_log(f"[TRANSCODE] Input: {preroll.path}")
    _file_log(f"[TRANSCODE] Output: {temp_output}")
    
    try:
        # FFmpeg command for transcoding
        # Using scale with force_original_aspect_ratio to maintain aspect ratio
        # and pad to exact dimensions if needed
        # Note: -pix_fmt yuv420p ensures compatibility with H.264 high profile
        # (required for 4:2:2 sources like ProRes which use yuv422p)
        ffmpeg_args = [
            ffmpeg_cmd,
            "-y",  # Overwrite output
            "-i", str(preroll.path),
            "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",  # Convert to 4:2:0 for H.264 high profile compatibility
            "-preset", "slow",  # Good quality/speed balance
            "-crf", "18",  # High quality (lower = better, 18 is visually lossless)
            "-profile:v", "high",
            "-level", "4.1",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",  # Web optimization
            str(temp_output)
        ]
        
        result = _run_subprocess(ffmpeg_args, capture_output=True, text=True)
        
        if result.returncode != 0:
            _file_log(f"[TRANSCODE] FFmpeg error: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"FFmpeg transcoding failed: {result.stderr[:500]}")
        
        # Verify output file exists
        if not temp_output.exists():
            raise HTTPException(status_code=500, detail="Transcoding failed - output file not created")
        
        # If replacing original, swap files
        if request.replace_original and temp_output != final_output:
            # Remove original and rename temp to original
            original_path.unlink()
            temp_output.rename(final_output)
            _file_log(f"[TRANSCODE] Replaced original file")
        
        # Get new file size
        new_size = final_output.stat().st_size
        
        # Update database record
        if request.replace_original:
            preroll.file_size = new_size
            # Regenerate thumbnail after transcode
            thumb_path = _generate_thumbnail_for_preroll(preroll, str(final_output), 
                                                         preroll.category.name if preroll.category else None)
            if thumb_path:
                preroll.thumbnail = thumb_path
            db.commit()
        else:
            # Create new preroll record for the scaled version
            new_preroll = models.Preroll(
                filename=final_output.name,
                display_name=f"{preroll.display_name or original_stem} ({request.resolution})" if preroll.display_name or original_stem else final_output.name,
                path=str(final_output),
                thumbnail=None,
                tags=preroll.tags,
                category_id=preroll.category_id,
                description=f"Scaled to {request.resolution} from {preroll.filename}",
                duration=preroll.duration,
                file_size=new_size,
            )
            db.add(new_preroll)
            db.commit()
            db.refresh(new_preroll)
            
            # Generate thumbnail for new preroll
            thumb_path = _generate_thumbnail_for_preroll(new_preroll, str(final_output),
                                                         preroll.category.name if preroll.category else None)
            if thumb_path:
                new_preroll.thumbnail = thumb_path
                db.commit()
        
        _file_log(f"[TRANSCODE] Successfully transcoded to {request.resolution}: {final_output}")
        
        return {
            "success": True,
            "message": f"Successfully transcoded to {request.resolution}",
            "resolution": request.resolution,
            "dimensions": f"{target_width}x{target_height}",
            "new_size_bytes": new_size,
            "new_size_mb": round(new_size / (1024 * 1024), 2),
            "replaced_original": request.replace_original,
            "output_path": str(final_output)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        _file_log(f"[TRANSCODE] Error: {e}")
        # Cleanup temp file if it exists
        if temp_output.exists() and temp_output != original_path:
            try:
                temp_output.unlink()
            except:
                pass
        raise HTTPException(status_code=500, detail=f"Transcoding failed: {str(e)}")

@app.get("/prerolls/{preroll_id}/video-info")
def get_preroll_video_info(preroll_id: int, db: Session = Depends(get_db)):
    """Get detailed video information including current resolution."""
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")
    
    if not preroll.path or not os.path.exists(preroll.path):
        raise HTTPException(status_code=404, detail="Video file not found")
    
    ffprobe_cmd = get_ffprobe_cmd()
    
    try:
        probe_result = _run_subprocess(
            [ffprobe_cmd, "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height,codec_name,bit_rate,r_frame_rate",
             "-show_entries", "format=duration,size,bit_rate",
             "-of", "json", preroll.path],
            capture_output=True, text=True, timeout=30
        )
        
        if probe_result.returncode == 0:
            probe_data = json.loads(probe_result.stdout) if probe_result.stdout else {}
            streams = probe_data.get("streams", [{}])
            format_info = probe_data.get("format", {})
            
            video_stream = streams[0] if streams else {}
            width = video_stream.get("width", 0)
            height = video_stream.get("height", 0)
            
            # Determine resolution label
            resolution_label = "Unknown"
            if height >= 1080:
                resolution_label = "1080p (Full HD)"
            elif height >= 720:
                resolution_label = "720p (HD)"
            elif height >= 480:
                resolution_label = "480p (SD)"
            elif height > 0:
                resolution_label = f"{height}p"
            
            return {
                "success": True,
                "width": width,
                "height": height,
                "resolution_label": resolution_label,
                "codec": video_stream.get("codec_name", "unknown"),
                "duration": format_info.get("duration"),
                "file_size": format_info.get("size"),
                "bitrate": format_info.get("bit_rate"),
                "frame_rate": video_stream.get("r_frame_rate")
            }
    except Exception as e:
        _file_log(f"[VIDEO-INFO] Error probing video: {e}")
    
    return {
        "success": False,
        "error": "Could not retrieve video information"
    }

@app.get("/prerolls")
def get_prerolls(db: Session = Depends(get_db), category_id: str = "", tags: str = "", search: str = ""):
    # Base query
    query = db.query(models.Preroll)

    # Handle category filtering (include primary and many-to-many associations)
    if category_id and category_id.strip():
        try:
            cat_id = int(category_id)
            query = query.outerjoin(
                models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id
            ).filter(
                or_(
                    models.Preroll.category_id == cat_id,
                    models.preroll_categories.c.category_id == cat_id,
                )
            )
        except ValueError:
            pass  # Invalid category_id, ignore filter

    # Handle search (searches tags, filename, and display_name)
    search_term = (search or tags).strip()
    if search_term:
        search_terms = [term.strip() for term in search_term.split(',') if term.strip()]
        for term in search_terms:
            search_pattern = f"%{term}%"
            query = query.filter(
                or_(
                    models.Preroll.tags.ilike(search_pattern),
                    models.Preroll.filename.ilike(search_pattern),
                    models.Preroll.display_name.ilike(search_pattern)
                )
            )

    prerolls = query.options(joinedload(models.Preroll.category)).distinct().all()
    result = []
    for p in prerolls:
        cats = [{"id": c.id, "name": c.name} for c in (p.categories or [])]
        result.append({
            "id": p.id,
            "filename": p.filename,
            "display_name": getattr(p, "display_name", None),
            "path": p.path,
            "thumbnail": (p.thumbnail if not (p.thumbnail and str(p.thumbnail).startswith("thumbnails/")) else f"prerolls/{p.thumbnail}"),
            "tags": p.tags,
            "category_id": p.category_id,
            "category": {"id": p.category.id, "name": p.category.name} if p.category else None,
            "categories": cats,
            "description": p.description,
            "duration": p.duration,
            "file_size": p.file_size,
            "managed": getattr(p, "managed", True),
            "upload_date": p.upload_date,
            "community_preroll_id": getattr(p, "community_preroll_id", None),
            "exclude_from_matching": getattr(p, "exclude_from_matching", False)
        })
    return result

@app.put("/prerolls/{preroll_id}")
def update_preroll(preroll_id: int, payload: PrerollUpdate, db: Session = Depends(get_db)):
    p = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Preroll not found")

    changed_thumbnail = False
    old_primary_cat_name = getattr(getattr(p, "category", None), "name", None)

    # Tags: accept JSON array or comma-separated string; persist as JSON string array
    if payload.tags is not None:
        try:
            if isinstance(payload.tags, list):
                p.tags = json.dumps(payload.tags)
            elif isinstance(payload.tags, str):
                try:
                    p.tags = json.dumps(json.loads(payload.tags))
                except Exception:
                    tag_list = [t.strip() for t in payload.tags.split(",") if t.strip()]
                    p.tags = json.dumps(tag_list)
        except Exception:
            # Keep original if conversion fails
            pass

    # Display name (UI label)
    if payload.display_name is not None:
        p.display_name = (payload.display_name or "").strip() or None

    # Description
    if payload.description is not None:
        p.description = (payload.description or "").strip() or None

    # Physical rename on disk (optional)
    if payload.new_filename and str(payload.new_filename).strip() and getattr(p, "managed", True):
        new_name = str(payload.new_filename).strip()
        # resolve current absolute path
        old_abs = p.path if os.path.isabs(p.path) else os.path.join(data_dir, p.path)
        base_dir = os.path.dirname(old_abs)
        old_ext = os.path.splitext(old_abs)[1]
        # Append old extension if none provided
        if not os.path.splitext(new_name)[1]:
            new_name = f"{new_name}{old_ext}"
        new_abs = os.path.join(base_dir, new_name)
        try:
            if os.path.abspath(old_abs) != os.path.abspath(new_abs):
                os.makedirs(os.path.dirname(new_abs), exist_ok=True)
                try:
                    os.replace(old_abs, new_abs)
                except Exception:
                    shutil.copy2(old_abs, new_abs)
                    try:
                        os.remove(old_abs)
                    except Exception:
                        pass
                p.path = new_abs
                p.filename = new_name
                changed_thumbnail = True
        except Exception as e:
            _file_log(f"update_preroll: rename failed for id={p.id}: {e}")

    # Primary category change: move file under new primary category folder
    new_primary = None
    if payload.category_id is not None and payload.category_id != p.category_id:
        new_primary = db.query(models.Category).filter(models.Category.id == payload.category_id).first()
        if new_primary:
            if getattr(p, "managed", True):
                # Resolve current absolute path
                cur_abs = p.path if os.path.isabs(p.path) else os.path.join(data_dir, p.path)
                try:
                    # Derive suffix relative to <oldCat>/ (preserve subfolders like Preroll_<id>)
                    rel_from_root = os.path.relpath(cur_abs, PREROLLS_DIR)
                    parts = rel_from_root.split(os.sep)
                    suffix = os.path.join(*parts[1:]) if len(parts) > 1 else os.path.basename(cur_abs)
                except Exception:
                    # Fallback: just use filename
                    suffix = os.path.basename(p.path)

                new_cat_dir = os.path.join(PREROLLS_DIR, new_primary.name)
                os.makedirs(new_cat_dir, exist_ok=True)
                new_abs = os.path.join(new_cat_dir, suffix)
                try:
                    if os.path.abspath(new_abs) != os.path.abspath(cur_abs):
                        os.makedirs(os.path.dirname(new_abs), exist_ok=True)
                        try:
                            os.replace(cur_abs, new_abs)
                        except Exception:
                            shutil.copy2(cur_abs, new_abs)
                            try:
                                os.remove(cur_abs)
                            except Exception:
                                pass
                        p.path = new_abs
                    p.category_id = new_primary.id
                    changed_thumbnail = True
                except Exception as e:
                    _file_log(f"update_preroll: move to new category failed id={p.id}: {e}")
            else:
                # External/mapped file: do not move on disk; only change primary category
                p.category_id = new_primary.id
                changed_thumbnail = True

    # Many-to-many categories update
    if payload.category_ids is not None:
        try:
            ids = [int(x) for x in payload.category_ids if str(x).isdigit()]
            # Ensure primary is included when provided
            if p.category_id and p.category_id not in ids:
                ids.insert(0, p.category_id)
            cats = db.query(models.Category).filter(models.Category.id.in_(ids)).all() if ids else []
            p.categories = cats
        except Exception as e:
            _file_log(f"update_preroll: updating categories failed id={p.id}: {e}")

    # Update thumbnail if filename or primary category changed
    try:
        primary_name = getattr(getattr(p, "category", None), "name", None) or old_primary_cat_name or "Default"
        tgt_dir = os.path.join(THUMBNAILS_DIR, primary_name)
        os.makedirs(tgt_dir, exist_ok=True)
        new_thumb_abs = os.path.join(tgt_dir, f"{p.id}_{p.filename}.jpg")

        # Determine current thumbnail absolute path (if exists)
        old_thumb_abs = None
        if p.thumbnail:
            old_thumb_abs = p.thumbnail if os.path.isabs(p.thumbnail) else os.path.join(data_dir, p.thumbnail)

        if changed_thumbnail or not old_thumb_abs or not os.path.exists(old_thumb_abs):
            # Regenerate from video file
            video_abs = p.path if os.path.isabs(p.path) else os.path.join(data_dir, p.path)
            tmp = new_thumb_abs + ".tmp.jpg"
            res = _run_subprocess(
                [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", video_abs, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp],
                capture_output=True,
                text=True,
            )
            if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp):
                _generate_placeholder(tmp)
            try:
                if os.path.exists(new_thumb_abs):
                    os.remove(new_thumb_abs)
            except Exception:
                pass
            os.replace(tmp, new_thumb_abs)
        else:
            # Try to rename/move existing thumbnail if only path/name changed
            try:
                if os.path.abspath(old_thumb_abs) != os.path.abspath(new_thumb_abs):
                    os.makedirs(os.path.dirname(new_thumb_abs), exist_ok=True)
                    try:
                        os.replace(old_thumb_abs, new_thumb_abs)
                    except Exception:
                        shutil.copy2(old_thumb_abs, new_thumb_abs)
                        try:
                            os.remove(old_thumb_abs)
                        except Exception:
                            pass
            except Exception:
                pass

        # Store relative path
        rel = os.path.relpath(new_thumb_abs, data_dir).replace("\\", "/")
        p.thumbnail = rel
    except Exception as e:
        _file_log(f"update_preroll: thumbnail update failed id={p.id}: {e}")

    # Update exclude_from_matching flag
    if payload.exclude_from_matching is not None:
        p.exclude_from_matching = payload.exclude_from_matching

    try:
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update preroll: {str(e)}")

    return {
        "message": "Preroll updated",
        "id": p.id,
        "filename": p.filename,
        "display_name": getattr(p, "display_name", None),
        "category_id": p.category_id,
        "categories": [{"id": c.id, "name": c.name} for c in (p.categories or [])],
        "thumbnail": p.thumbnail,
        "description": p.description,
        "tags": p.tags,
    }

@app.delete("/prerolls/{preroll_id}")
def delete_preroll(preroll_id: int, db: Session = Depends(get_db)):
    try:
        preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
        if not preroll:
            raise HTTPException(status_code=404, detail="Preroll not found")

        # Delete the actual files (do not delete external mapped files)
        try:
            # Handle new path structure
            if getattr(preroll, "managed", True):
                full_path = preroll.path
                if not os.path.isabs(full_path):
                    full_path = os.path.join(data_dir, full_path)

                if os.path.exists(full_path):
                    os.remove(full_path)

            if preroll.thumbnail:
                thumbnail_path = preroll.thumbnail
                if not os.path.isabs(thumbnail_path):
                    thumbnail_path = os.path.join(data_dir, thumbnail_path)

                if os.path.exists(thumbnail_path):
                    os.remove(thumbnail_path)
        except Exception as e:
            print(f"Warning: Could not delete files for preroll {preroll_id}: {e}")

        # Remove preroll_id from all schedules' preroll_ids JSON field
        schedules = db.query(models.Schedule).all()
        for schedule in schedules:
            if schedule.preroll_ids:
                try:
                    preroll_list = json.loads(schedule.preroll_ids)
                    if isinstance(preroll_list, list) and preroll_id in preroll_list:
                        preroll_list.remove(preroll_id)
                        schedule.preroll_ids = json.dumps(preroll_list) if preroll_list else None
                except Exception as e:
                    print(f"Warning: Could not update schedule {schedule.id}: {e}")
        db.commit()

        # Use SQLAlchemy connection to access raw DB connection
        sqlalchemy_conn = db.connection()
        dbapi_conn = sqlalchemy_conn.connection  # Get the raw DBAPI connection
        try:
            cursor = dbapi_conn.cursor()
            
            # Check foreign key status
            cursor.execute("PRAGMA foreign_keys")
            fk_status = cursor.fetchone()[0]
            print(f"FK status before: {fk_status}")
            
            # Disable foreign keys
            cursor.execute("PRAGMA foreign_keys=OFF;")
            cursor.execute("PRAGMA foreign_keys")
            fk_status_off = cursor.fetchone()[0]
            print(f"FK status after OFF: {fk_status_off}")
            
            # Delete many-to-many
            print(f"Deleting from preroll_categories WHERE preroll_id={preroll_id}")
            cursor.execute("DELETE FROM preroll_categories WHERE preroll_id = ?;", (preroll_id,))
            print(f"  Deleted {cursor.rowcount} rows from preroll_categories")
            
            # Delete preroll
            print(f"Deleting from prerolls WHERE id={preroll_id}")
            cursor.execute("DELETE FROM prerolls WHERE id = ?;", (preroll_id,))
            print(f"  Deleted {cursor.rowcount} rows from prerolls")
            
            # Re-enable foreign keys
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA foreign_keys")
            fk_status_on = cursor.fetchone()[0]
            print(f"FK status after ON: {fk_status_on}")
            
            # Commit
            dbapi_conn.commit()
            cursor.close()
            print(f"[OK] Successfully deleted preroll {preroll_id} using raw SQL with FK disabled")
        except Exception as e:
            print(f"[ERR] Raw SQL deletion failed: {type(e).__name__}: {e}")
            dbapi_conn.rollback()
            raise e

        return {"message": "Preroll deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting preroll {preroll_id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error deleting preroll: {str(e)}")

@app.post("/prerolls/{preroll_id}/auto-match")
def auto_match_single_preroll(preroll_id: int, db: Session = Depends(get_db)):
    """
    Automatically match a preroll to the Community Prerolls library using fuzzy matching.
    Returns matched community preroll or similar matches with confidence scores.
    """
    try:
        preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
        if not preroll:
            raise HTTPException(status_code=404, detail="Preroll not found")
        
        # Check if preroll is excluded from auto-matching
        if getattr(preroll, 'exclude_from_matching', False):
            return {
                "success": False,
                "matched": False,
                "excluded": True,
                "message": "This preroll is excluded from community matching"
            }
        
        # Check if already matched
        if getattr(preroll, 'community_preroll_id', None):
            return {
                "matched": True,
                "already_matched": True,
                "community_preroll_id": preroll.community_preroll_id
            }
        
        # Load community index
        if not PREROLLS_INDEX_PATH.exists():
            return {
                "matched": False,
                "message": "Community prerolls index not available. Please build the index first."
            }
        
        try:
            with open(PREROLLS_INDEX_PATH, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            # Extract prerolls array from wrapper dict
            community_data = index_data.get("prerolls", [])
            _file_log(f"Loaded community index: {len(community_data)} prerolls for auto-match")
        except Exception as e:
            _file_log(f"Failed to load community index: {e}")
            return {"matched": False, "message": f"Failed to load community index: {str(e)}"}
        
        # Get preroll title for matching
        title = preroll.display_name or preroll.filename
        title_clean = os.path.splitext(title)[0]
        
        # Normalize title for matching
        def normalize(s):
            s = s.lower()
            # Replace underscores with spaces first
            s = s.replace('_', ' ')
            # Remove all non-alphanumeric characters except spaces
            s = re.sub(r'[^a-z0-9\s]', '', s)
            # Collapse multiple spaces into one
            s = re.sub(r'\s+', ' ', s)
            return s.strip()
        
        # Check if title has hash-like prefix (e.g., "1740Bdd395C04C5Ea7843Da12858C2B4.Title")
        def has_hash_prefix(title):
            # Match pattern: starts with 20+ alphanumeric chars followed by dot or space
            # This catches hash prefixes like "1740Bdd395C04C5Ea7843Da12858C2B4."
            match = re.match(r'^[a-zA-Z0-9]{20,}[\.\s]', title)
            return match is not None
        
        title_norm = normalize(title_clean)
        
        # Try to find exact match
        for cp in community_data:
            cp_title_norm = normalize(cp.get('title', ''))
            if title_norm == cp_title_norm:
                # Exact match found
                preroll.community_preroll_id = cp.get('id')
                db.commit()
                _file_log(f"Auto-matched preroll '{title}' to community preroll '{cp.get('title')}' (exact match)")
                return {
                    "matched": True,
                    "community_preroll_id": cp.get('id'),
                    "matched_title": cp.get('title'),
                    "match_type": "exact",
                    "match_score": 1.0
                }
        
        # No exact match - find similar matches using fuzzy matching
        similar_matches = []
        title_words = set(title_norm.split())
        _file_log(f"Fuzzy matching for '{title_norm}' with {len(title_words)} words: {title_words}")
        
        matches_checked = 0
        for cp in community_data:
            cp_title = cp.get('title', '')
            
            # Skip prerolls with hash-like prefixes (e.g., "1740Bdd395C04C5Ea7843Da12858C2B4.Title")
            if has_hash_prefix(cp_title):
                continue
            
            cp_title_norm = normalize(cp_title)
            cp_words = set(cp_title_norm.split())
            
            # Calculate similarity score
            score = 0.0
            reason = ""
            
            # Check if one title is substring of another
            if title_norm in cp_title_norm or cp_title_norm in title_norm:
                score = 0.85
                reason = "substring"
            else:
                # Word overlap scoring - ANY matching word counts
                if title_words and cp_words:
                    common_words = title_words & cp_words
                    if common_words:
                        # Score based on how many words match relative to the shorter title
                        # This gives higher scores when ANY word matches
                        min_words = min(len(title_words), len(cp_words))
                        score = len(common_words) / min_words
                        reason = f"word_match ({len(common_words)}/{min_words})"
            
            # Threshold at 50% to show matches where at least half the words match
            if score >= 0.50:
                similar_matches.append({
                    "id": cp.get('id'),
                    "title": cp_title,
                    "confidence": int(score * 100),
                    "score": score,
                    "reason": reason,
                    "video_url": cp.get('url')  # Include video URL for preview
                })
            
            matches_checked += 1
            # Log first few high-scoring matches for debugging
            if score >= 0.50 and len(similar_matches) <= 5:
                _file_log(f"  Match: '{cp_title}' (score: {int(score*100)}%, common: {common_words if score > 0 else 'none'})")
        
        _file_log(f"Checked {matches_checked} community prerolls, found {len(similar_matches)} matches >= 50%")
        
        # Sort by score descending
        similar_matches.sort(key=lambda x: x['score'], reverse=True)
        
        # Auto-link only if we have a very confident match (>= 80%)
        # Lower confidence matches (20-79%) are shown to user for manual selection
        if similar_matches and similar_matches[0]['score'] >= 0.8:
            best_match = similar_matches[0]
            preroll.community_preroll_id = best_match['id']
            db.commit()
            _file_log(f"Auto-matched preroll '{title}' to community preroll '{best_match['title']}' (fuzzy match: {best_match['confidence']}%)")
            return {
                "matched": True,
                "community_preroll_id": best_match['id'],
                "matched_title": best_match['title'],
                "match_type": "fuzzy",
                "match_score": best_match['score']
            }
        
        # Return similar matches for user to choose (limit to top 10)
        if similar_matches:
            _file_log(f"Returning {len(similar_matches[:10])} similar matches for preroll '{title}'. Top match: {similar_matches[0]['title']} ({similar_matches[0]['confidence']}%)")
            response = {
                "matched": False,
                "similar_matches": similar_matches[:10]
            }
            _file_log(f"Response JSON: {json.dumps(response, indent=2)[:500]}...")
            return response
        
        _file_log(f"No matches found for preroll '{title}' (searched {len(community_data)} community prerolls)")
        return {
            "matched": False,
            "message": "No matching community prerolls found"
        }
    
    except Exception as e:
        _file_log(f"Auto-match error for preroll {preroll_id}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Auto-match failed: {str(e)}")

@app.post("/prerolls/{preroll_id}/link-community/{community_id}")
def link_preroll_to_community(preroll_id: int, community_id: str, db: Session = Depends(get_db)):
    """
    Manually link a preroll to a community preroll ID.
    """
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")
    
    # Validate community ID exists in index
    if PREROLLS_INDEX_PATH.exists():
        try:
            with open(PREROLLS_INDEX_PATH, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            # Extract prerolls array from wrapper dict
            community_data = index_data.get("prerolls", [])
            
            community_exists = any(cp.get('id') == community_id for cp in community_data)
            if not community_exists:
                return {
                    "success": False,
                    "message": f"Community preroll ID '{community_id}' not found in index"
                }
        except Exception as e:
            _file_log(f"Failed to validate community ID: {e}")
    
    preroll.community_preroll_id = community_id
    db.commit()
    
    _file_log(f"Manually linked preroll '{preroll.display_name or preroll.filename}' (ID {preroll_id}) to community ID '{community_id}'")
    
    return {
        "success": True,
        "message": "Successfully linked to community preroll",
        "community_preroll_id": community_id
    }

@app.post("/prerolls/{preroll_id}/unmatch-community")
def unmatch_preroll_from_community(preroll_id: int, db: Session = Depends(get_db)):
    """
    Remove community preroll link from a preroll.
    """
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")
    
    if not getattr(preroll, 'community_preroll_id', None):
        return {
            "success": False,
            "message": "Preroll is not linked to any community preroll"
        }
    
    old_id = preroll.community_preroll_id
    preroll.community_preroll_id = None
    db.commit()
    
    _file_log(f"Unmatched preroll '{preroll.display_name or preroll.filename}' (ID {preroll_id}) from community ID '{old_id}'")
    
    return {
        "success": True,
        "message": "Successfully removed community preroll link"
    }

class BulkUpdateTagsRequest(BaseModel):
    preroll_ids: List[int]
    tags_to_add: List[str] = []
    tags_to_remove: List[str] = []

@app.post("/prerolls/bulk-update-tags")
def bulk_update_tags(request: BulkUpdateTagsRequest, db: Session = Depends(get_db)):
    """
    Bulk update tags for multiple prerolls.
    Add and/or remove tags from selected prerolls.
    """
    if not request.preroll_ids:
        raise HTTPException(status_code=400, detail="No preroll IDs provided")
    
    updated_count = 0
    errors = []
    
    for preroll_id in request.preroll_ids:
        try:
            preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
            if not preroll:
                errors.append(f"Preroll ID {preroll_id} not found")
                continue
            
            # Parse existing tags
            existing_tags = set()
            if preroll.tags:
                try:
                    existing_tags = set(json.loads(preroll.tags))
                except:
                    # Handle comma-separated tags
                    existing_tags = {tag.strip() for tag in preroll.tags.split(',') if tag.strip()}
            
            # Add new tags
            for tag in request.tags_to_add:
                if tag and tag.strip():
                    existing_tags.add(tag.strip())
            
            # Remove tags
            for tag in request.tags_to_remove:
                existing_tags.discard(tag.strip())
            
            # Update preroll
            preroll.tags = json.dumps(sorted(list(existing_tags)))
            updated_count += 1
            
        except Exception as e:
            errors.append(f"Error updating preroll ID {preroll_id}: {str(e)}")
    
    db.commit()
    
    _file_log(f"Bulk updated tags for {updated_count} prerolls (added: {request.tags_to_add}, removed: {request.tags_to_remove})")
    
    return {
        "success": True,
        "updated_count": updated_count,
        "total_requested": len(request.preroll_ids),
        "errors": errors if errors else None
    }

@app.get("/tags")
def get_all_tags(db: Session = Depends(get_db)):
    """Get all unique tags from prerolls"""
    prerolls = db.query(models.Preroll).filter(models.Preroll.tags.isnot(None)).all()
    all_tags = set()

    for preroll in prerolls:
        if preroll.tags:
            try:
                tags = json.loads(preroll.tags)
                all_tags.update(tags)
            except:
                # Handle comma-separated tags
                tags = [tag.strip() for tag in preroll.tags.split(',')]
                all_tags.update(tags)

    return {"tags": sorted(list(all_tags))}

@app.delete("/categories/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db)):
    """
    Delete a category if it is not referenced by prerolls (primary or many-to-many)
    or by schedules. Any HolidayPreset rows that reference this category will be
    removed automatically to prevent foreign-key errors on legacy databases.
    """
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Prevent deletion of system categories (e.g., NeX-Up Trailers)
    if getattr(category, 'is_system', False):
        raise HTTPException(status_code=403, detail="Cannot delete system category")

    # Check if category is used by prerolls (primary) or via many-to-many, or by schedules
    preroll_primary_count = db.query(models.Preroll).filter(models.Preroll.category_id == category_id).count()
    m2m_count = db.query(models.Preroll).join(
        models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id
    ).filter(models.preroll_categories.c.category_id == category_id).count()
    schedule_count = db.query(models.Schedule).filter(models.Schedule.category_id == category_id).count()

    if (preroll_primary_count + m2m_count) > 0 or schedule_count > 0:
        raise HTTPException(status_code=400, detail="Category must be empty before deleting. Remove or reassign prerolls first.")

    # Remove any holiday presets pointing at this category to avoid FK integrity errors
    try:
        db.query(models.HolidayPreset).filter(models.HolidayPreset.category_id == category_id).delete(synchronize_session=False)
    except Exception:
        # Best-effort; continue with deletion attempt
        pass

    db.delete(category)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete category due to integrity constraints: {e}")
    return {"message": "Category deleted"}

# Category endpoints
@app.post("/categories")
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    # Validate input
    name = (category.name or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Category name is required")

    # Check duplicates by name
    existing = db.query(models.Category).filter(models.Category.name == name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category with this name already exists")

    # Normalize plex_mode
    mode = (getattr(category, "plex_mode", "shuffle") or "shuffle").strip().lower()
    if mode not in ("shuffle", "playlist"):
        mode = "shuffle"

    db_category = models.Category(
        name=name,
        description=(category.description or "").strip() or None,
        plex_mode=mode,
        # keep compatibility; apply_to_plex is controlled via separate endpoints
        apply_to_plex=getattr(category, "apply_to_plex", False)
    )

    try:
        db.add(db_category)
        db.commit()
        db.refresh(db_category)
    except IntegrityError:
        db.rollback()
        # In case of race conditions or existing unique index
        raise HTTPException(status_code=409, detail="Category with this name already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create category: {str(e)}")

    return {
        "id": db_category.id,
        "name": db_category.name,
        "description": db_category.description,
        "apply_to_plex": getattr(db_category, "apply_to_plex", False),
        "plex_mode": getattr(db_category, "plex_mode", "shuffle"),
    }

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(models.Category).all()
    return [{
        "id": c.id,
        "name": c.name,
        "description": c.description,
        "apply_to_plex": getattr(c, "apply_to_plex", False),
        "plex_mode": getattr(c, "plex_mode", "shuffle"),
        "is_system": getattr(c, "is_system", False),
    } for c in categories]

@app.put("/categories/{category_id}")
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Prevent editing of system categories (e.g., NeX-Up Trailers)
    if getattr(db_category, 'is_system', False):
        raise HTTPException(status_code=403, detail="Cannot edit system category")

    new_name = (category.name or "").strip()
    if not new_name:
        raise HTTPException(status_code=422, detail="Category name is required")

    # Ensure name is unique among other categories
    existing = db.query(models.Category).filter(
        models.Category.name == new_name,
        models.Category.id != category_id
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Category with this name already exists")

    db_category.name = new_name
    db_category.description = (category.description or "").strip() or None
    # Normalize and update plex_mode
    mode = (getattr(category, "plex_mode", "shuffle") or "shuffle").strip().lower()
    if mode not in ("shuffle", "playlist"):
        mode = "shuffle"
    try:
        db_category.plex_mode = mode
    except Exception:
        pass
    # Do not toggle apply_to_plex here; dedicated endpoints manage it

    try:
        db.commit()
        db.refresh(db_category)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Category with this name already exists")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update category: {str(e)}")

    return {
        "id": db_category.id,
        "name": db_category.name,
        "description": db_category.description,
        "apply_to_plex": getattr(db_category, "apply_to_plex", False),
        "plex_mode": getattr(db_category, "plex_mode", "shuffle"),
        "message": "Category updated",
    }

@app.get("/categories/{category_id}/prerolls")
def get_category_prerolls(category_id: int, db: Session = Depends(get_db)):
    """
    List prerolls assigned to a category (includes primary and many-to-many associations).
    Response mirrors /prerolls fields.
    """
    # Validate category
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    query = db.query(models.Preroll)\
        .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id)\
        .filter(or_(models.Preroll.category_id == category_id, models.preroll_categories.c.category_id == category_id))\
        .distinct()

    prerolls = query.all()
    result = []
    for p in prerolls:
        cats = [{"id": c.id, "name": c.name} for c in (p.categories or [])]
        result.append({
            "id": p.id,
            "filename": p.filename,
            "display_name": getattr(p, "display_name", None),
            "path": p.path,
            "thumbnail": (p.thumbnail if not (p.thumbnail and str(p.thumbnail).startswith("thumbnails/")) else f"prerolls/{p.thumbnail}"),
            "tags": p.tags,
            "category_id": p.category_id,
            "category": {"id": p.category.id, "name": p.category.name} if p.category else None,
            "categories": cats,
            "description": p.description,
            "duration": p.duration,
            "file_size": p.file_size,
            "managed": getattr(p, "managed", True),
            "upload_date": p.upload_date
        })
    return result

@app.post("/categories/{category_id}/prerolls/{preroll_id}")
def add_preroll_to_category(category_id: int, preroll_id: int, set_primary: bool = False, db: Session = Depends(get_db)):
    """
    Add a preroll to a category (many-to-many). If set_primary=true, make this category
    the primary category and move the file under the new primary category folder.
    """
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    p = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Preroll not found")

    # Add association (if not already present)
    try:
        assigned_ids = {c.id for c in (p.categories or [])}
        if category_id not in assigned_ids:
            # attach (load actual row to ensure identity matches)
            p.categories = (p.categories or []) + [cat]
    except Exception as e:
        _file_log(f"add_preroll_to_category: association add failed p={p.id}, c={category_id}: {e}")

    moved_primary = False
    # Optionally set as primary category (move file path)
    if set_primary and p.category_id != category_id:
        if getattr(p, "managed", True):
            # Resolve current absolute path
            cur_abs = p.path if os.path.isabs(p.path) else os.path.join(data_dir, p.path)
            try:
                # Derive suffix relative to <oldCat>/ (preserve subfolders like Preroll_<id>)
                rel_from_root = os.path.relpath(cur_abs, PREROLLS_DIR)
                parts = rel_from_root.split(os.sep)
                suffix = os.path.join(*parts[1:]) if len(parts) > 1 else os.path.basename(cur_abs)
            except Exception:
                suffix = os.path.basename(p.path)

            new_cat_dir = os.path.join(PREROLLS_DIR, cat.name)
            os.makedirs(new_cat_dir, exist_ok=True)
            new_abs = os.path.join(new_cat_dir, suffix)
            try:
                if os.path.abspath(new_abs) != os.path.abspath(cur_abs):
                    os.makedirs(os.path.dirname(new_abs), exist_ok=True)
                    try:
                        os.replace(cur_abs, new_abs)
                    except Exception:
                        shutil.copy2(cur_abs, new_abs)
                        try:
                            os.remove(cur_abs)
                        except Exception:
                            pass
                    p.path = new_abs
                p.category_id = cat.id
                moved_primary = True
                # Update thumbnail for new primary location/name (id-prefixed)
                try:
                    tgt_dir = os.path.join(THUMBNAILS_DIR, cat.name)
                    os.makedirs(tgt_dir, exist_ok=True)
                    new_thumb_abs = os.path.join(tgt_dir, f"{p.id}_{p.filename}.jpg")
                    video_abs = p.path if os.path.isabs(p.path) else os.path.join(data_dir, p.path)
                    tmp = new_thumb_abs + ".tmp.jpg"
                    res = _run_subprocess(
                        [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", video_abs, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp],
                        capture_output=True,
                        text=True,
                    )
                    if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp):
                        _generate_placeholder(tmp)
                    try:
                        if os.path.exists(new_thumb_abs):
                            os.remove(new_thumb_abs)
                    except Exception:
                        pass
                    os.replace(tmp, new_thumb_abs)
                    rel = os.path.relpath(new_thumb_abs, data_dir).replace("\\", "/")
                    p.thumbnail = rel
                except Exception as e:
                    _file_log(f"add_preroll_to_category: primary move thumb update failed p={p.id}: {e}")
            except Exception as e:
                _file_log(f"add_preroll_to_category: primary move failed p={p.id} to category={cat.name}: {e}")
                raise HTTPException(status_code=500, detail="Failed to set primary category (move operation)")
        else:
            # External/mapped file: do not move on disk; only change primary category and update thumbnail
            p.category_id = cat.id
            moved_primary = True
            try:
                tgt_dir = os.path.join(THUMBNAILS_DIR, cat.name)
                os.makedirs(tgt_dir, exist_ok=True)
                new_thumb_abs = os.path.join(tgt_dir, f"{p.id}_{p.filename}.jpg")
                video_abs = p.path if os.path.isabs(p.path) else os.path.join(data_dir, p.path)
                tmp = new_thumb_abs + ".tmp.jpg"
                res = _run_subprocess(
                    [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", video_abs, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp],
                    capture_output=True,
                    text=True,
                )
                if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp):
                    _generate_placeholder(tmp)
                try:
                    if os.path.exists(new_thumb_abs):
                        os.remove(new_thumb_abs)
                except Exception:
                    pass
                os.replace(tmp, new_thumb_abs)
                rel = os.path.relpath(new_thumb_abs, data_dir).replace("\\", "/")
                p.thumbnail = rel
            except Exception as e:
                _file_log(f"add_preroll_to_category: external primary thumb update failed p={p.id}: {e}")

    try:
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add preroll to category: {str(e)}")

    # Auto-apply to Plex/Jellyfin if category is already applied or currently active
    auto_applied = False
    should_apply = getattr(cat, "apply_to_plex", False)
    
    # Also check if this category is currently active via scheduler
    if not should_apply:
        try:
            setting = db.query(models.Setting).first()
            if setting and getattr(setting, "active_category", None) == cat.id:
                should_apply = True
                _file_log(f"add_preroll_to_category: Category '{cat.name}' (ID {cat.id}) is currently active via schedule")
        except Exception as e:
            _file_log(f"add_preroll_to_category: Error checking active category: {e}")
    
    if should_apply:
        try:
            # Expire all cached objects to ensure fresh query results include the new association
            db.expire_all()
            _file_log(f"add_preroll_to_category: Auto-applying category '{cat.name}' (ID {cat.id}) to Plex after adding preroll {p.id}")
            ok = _apply_category_to_plex_and_track(db, cat.id, ttl=15)
            if ok:
                auto_applied = True
                _file_log(f"add_preroll_to_category: Successfully auto-applied category '{cat.name}' to Plex")
            else:
                _file_log(f"add_preroll_to_category: Failed to auto-apply category '{cat.name}' to Plex")
        except Exception as e:
            _file_log(f"add_preroll_to_category: Error auto-applying to Plex: {e}")

    return {
        "message": "Preroll added to category" + (" and set as primary" if set_primary else "") + (" and auto-applied to server" if auto_applied else ""),
        "category_id": category_id,
        "preroll_id": p.id,
        "primary_category_id": p.category_id,
        "categories": [{"id": c.id, "name": c.name} for c in (p.categories or [])],
        "moved_primary": moved_primary,
    }

@app.delete("/categories/{category_id}/prerolls/{preroll_id}")
def remove_preroll_from_category(category_id: int, preroll_id: int, db: Session = Depends(get_db)):
    """
    Remove a preroll's membership from a category (many-to-many).
    Primary category cannot be removed here; change primary on the preroll edit instead.
    """
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")

    p = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="Preroll not found")

    if p.category_id == category_id:
        raise HTTPException(status_code=400, detail="Cannot remove primary category here. Edit the preroll to change its primary category.")

    try:
        p.categories = [c for c in (p.categories or []) if c.id != category_id]
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove preroll from category: {str(e)}")

    return {
        "message": "Preroll removed from category",
        "category_id": category_id,
        "preroll_id": p.id,
        "primary_category_id": p.category_id,
        "categories": [{"id": c.id, "name": c.name} for c in (p.categories or [])],
    }

@app.post("/categories/{category_id}/apply-to-plex")
def apply_category_to_plex(category_id: int, rotation_hours: int = 24, db: Session = Depends(get_db)):
    """Apply a category's videos to Plex as the active preroll with optional rotation"""
    # Get the category
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Get all prerolls in this category (include primary and many-to-many)
    prerolls = db.query(models.Preroll)\
        .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id)\
        .filter(or_(models.Preroll.category_id == category_id, models.preroll_categories.c.category_id == category_id))\
        .distinct().all()
    if not prerolls:
        raise HTTPException(status_code=404, detail="No prerolls found in this category")

    # Collect local absolute paths
    preroll_paths_local = []
    for preroll in prerolls:
        full_local_path = os.path.abspath(preroll.path)
        preroll_paths_local.append(full_local_path)

    # Choose delimiter based on category.plex_mode:
    # - ';' for shuffle (random rotation)
    # - ',' for playlist (ordered playback)
    delimiter = ";"
    try:
        mode = getattr(category, "plex_mode", "shuffle")
        if isinstance(mode, str) and mode.lower() == "playlist":
            delimiter = ","
    except Exception:
        pass

    # Get Plex settings
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Plex not configured")

    # Translate local paths to Plex-accessible paths using configured mappings
    mappings = []
    try:
        raw = getattr(setting, "path_mappings", None)
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
    except Exception:
        mappings = []

    def _translate_for_plex(local_path: str) -> str:
        try:
            lp = os.path.normpath(local_path)
            best = None
            best_src = None
            best_len = -1
            for m in mappings:
                src = os.path.normpath(str(m.get("local")))
                # Case-insensitive on Windows
                if sys.platform.startswith("win"):
                    if lp.lower().startswith(src.lower()) and len(src) > best_len:
                        best = m
                        best_src = src
                        best_len = len(src)
                else:
                    if lp.startswith(src) and len(src) > best_len:
                        best = m
                        best_src = src
                        best_len = len(src)
            if best:
                dst_prefix = str(best.get("plex"))
                rest = lp[len(best_src):].lstrip("\\/")
                # Join using the separator implied by the mapping's plex prefix
                try:
                    if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                        # Likely Plex path on POSIX
                        out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                    elif "\\" in dst_prefix:
                        # Likely Windows path
                        out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                    else:
                        # Fallback: safest to use forward slashes for Plex
                        out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                except Exception:
                    out = dst_prefix + (("/" if not dst_prefix.endswith(("/", "\\")) else "") + rest)
                return out
        except Exception:
            pass
        return local_path

    preroll_paths_plex = [_translate_for_plex(p) for p in preroll_paths_local]
    multi_preroll_path = delimiter.join(preroll_paths_plex)
 
    # Apply to Plex
    connector = PlexConnector(setting.plex_url, setting.plex_token)
 
    # Preflight: ensure the translated path style matches the Plex host platform.
    # Prevents sending container-only paths (e.g., /data/...) to a Windows Plex or Windows paths (Z:\, \\NAS\share) to a POSIX Plex.
    try:
        info = connector.get_server_info() or {}
    except Exception:
        info = {}
    platform_str = str(info.get("platform") or info.get("Platform") or "").lower()
 
    def _looks_windows_path(s: str) -> bool:
        try:
            if not s:
                return False
            # UNC
            if s.startswith("\\\\"):
                return True
            # Drive-letter
            if len(s) >= 3 and s[1] == ":" and (s[2] == "\\" or s[2] == "/"):
                return True
        except Exception:
            pass
        return False
 
    def _looks_posix_path(s: str) -> bool:
        try:
            if not s:
                return False
            # Exclude Windows patterns first
            if _looks_windows_path(s):
                return False
            return s.startswith("/")
        except Exception:
            return False
 
    target_windows = ("win" in platform_str) or ("windows" in platform_str)
    mismatches: list[str] = []
    try:
        for out in preroll_paths_plex:
            if target_windows and _looks_posix_path(out):
                mismatches.append(out)
            elif (not target_windows) and _looks_windows_path(out):
                mismatches.append(out)
    except Exception:
        mismatches = []
 
    if mismatches:
        # Compose actionable guidance and refuse to send an unusable path to Plex
        try:
            changed = sum(1 for a, b in zip(preroll_paths_local, preroll_paths_plex) if a != b)
        except Exception:
            changed = 0
        try:
            common_local = os.path.commonpath(preroll_paths_local) if preroll_paths_local else None
        except Exception:
            common_local = None
        ex_local = common_local or PREROLLS_DIR
        if target_windows:
            # Prefer UNC for Plex service accounts; drive letters shown as an alternative
            example_hint = f"local='{ex_local}' → plex='Z:\\\\Prerolls' or plex='\\\\\\\\NAS\\\\Prerolls'"
        else:
            example_hint = f"local='{ex_local}' → plex='/mnt/prerolls'"
        detail = (
            f"Plex platform appears {'Windows' if target_windows else 'POSIX'}, but translated preroll paths look "
            f"{'POSIX' if target_windows else 'Windows'} (e.g., '{mismatches[0]}'). "
            "Add a path mapping under Settings → 'UNC/Local → Plex Path Mappings' so NeXroll can translate local/container paths "
            "to the exact path Plex can see on its host. Example mapping: " + example_hint +
            ". Use 'Test Translation' in Settings to validate, then retry Apply."
        )
        raise HTTPException(status_code=422, detail=detail)

    print(f"Setting {len(prerolls)} prerolls for category '{category.name}':")
    for i, preroll in enumerate(prerolls, 1):
        print(f"  {i}. {preroll.filename}")
    print(f"Combined path: {multi_preroll_path}")

    # Attempt to set the multi-preroll in Plex
    success = False

    if connector.set_preroll(multi_preroll_path):
        success = True
        print("Successfully set multi-preroll using combined file paths")
    else:
        print("Failed to set multi-preroll")

    if success:
        # Mark this category as applied and remove from others
        db.query(models.Category).update({"apply_to_plex": False})
        category.apply_to_plex = True
        
        # Also save it as the active category in the Setting
        setting = db.query(models.Setting).first()
        if setting:
            setting.active_category = category_id
        db.commit()

        return {
            "message": f"Category '{category.name}' applied to Plex successfully",
            "preroll_count": len(prerolls),
            "prerolls": [p.filename for p in prerolls],
            "rotation_info": ("Plex will play all prerolls in order (Sequential ,)" if getattr(category, "plex_mode", "shuffle") == "playlist" else "Plex will pick one preroll at random each time (Random ;)"),
            "plex_updated": True
        }
    else:
        # Don't update the database if Plex update failed
        raise HTTPException(
            status_code=500,
            detail="Failed to update Plex preroll settings. The CinemaTrailersPrerollID could not be set. Please check your Plex server connection and ensure you have the necessary permissions."
        )

@app.post("/categories/{category_id}/remove-from-plex")
def remove_category_from_plex(category_id: int, db: Session = Depends(get_db)):
    """Remove a category from Plex application"""
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.apply_to_plex = False
    db.commit()

    return {"message": f"Category '{category.name}' removed from Plex"}


@app.post("/categories/default")
def create_default_category(db: Session = Depends(get_db)):
    """Create a default category for fallback preroll selection"""
    existing = db.query(models.Category).filter(models.Category.name == "Default").first()
    if existing:
        return {"message": "Default category already exists", "category": existing}

    default_category = models.Category(
        name="Default",
        description="Default category for fallback preroll selection when no schedule is active"
    )
    db.add(default_category)
    db.commit()
    db.refresh(default_category)
    return {"message": "Default category created", "category": default_category}

@app.get("/categories/default")
def get_default_category(db: Session = Depends(get_db)):
    """Get the default category for fallback"""
    default_category = db.query(models.Category).filter(models.Category.name == "Default").first()
    return default_category

# Schedule endpoints
@app.post("/schedules")
def create_schedule(schedule: ScheduleCreate, db: Session = Depends(get_db)):
    # Validate: must have either category_id or sequence
    if not schedule.category_id and not schedule.sequence:
        raise HTTPException(status_code=400, detail="Schedule must have either a category or a sequence")
    
    # Validate category exists if provided
    category = None
    if schedule.category_id:
        category = db.query(models.Category).filter(models.Category.id == schedule.category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    # Parse dates from strings - store as naive local datetime (no timezone conversion)
    # The user enters their local time, we store it as-is, and the scheduler compares against local time
    start_date = None
    end_date = None

    try:
        if schedule.start_date:
            sd = schedule.start_date
            # Remove any timezone info and store as naive datetime
            # This avoids timezone conversion bugs where browser TZ != configured TZ
            if 'Z' in sd:
                sd = sd.replace('Z', '')
            if '+' in sd and 'T' in sd:
                sd = sd.split('+')[0]
            if sd.count('-') > 2 and 'T' in sd:  # Has negative offset like -07:00
                parts = sd.rsplit('-', 1)
                if ':' in parts[-1]:  # It's a timezone offset, not part of the date
                    sd = parts[0]
            start_date = datetime.datetime.fromisoformat(sd)
                
        if schedule.end_date:
            ed = schedule.end_date
            # Remove any timezone info and store as naive datetime
            if 'Z' in ed:
                ed = ed.replace('Z', '')
            if '+' in ed and 'T' in ed:
                ed = ed.split('+')[0]
            if ed.count('-') > 2 and 'T' in ed:  # Has negative offset like -07:00
                parts = ed.rsplit('-', 1)
                if ':' in parts[-1]:  # It's a timezone offset, not part of the date
                    ed = parts[0]
            end_date = datetime.datetime.fromisoformat(ed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    db_schedule = models.Schedule(
        name=schedule.name,
        type=schedule.type,
        start_date=start_date,
        end_date=end_date,
        category_id=schedule.category_id,
        fallback_category_id=schedule.fallback_category_id,
        shuffle=schedule.shuffle,
        playlist=schedule.playlist,
        recurrence_pattern=schedule.recurrence_pattern,
        preroll_ids=schedule.preroll_ids,
        sequence=schedule.sequence,
        color=schedule.color,
        blend_enabled=schedule.blend_enabled,
        priority=schedule.priority,
        exclusive=schedule.exclusive
    )
    db.add(db_schedule)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        _file_log(f"Schedule create failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")
    db.refresh(db_schedule)

    # Load the category relationship for the response
    created_schedule = db.query(models.Schedule).options(joinedload(models.Schedule.category)).filter(models.Schedule.id == db_schedule.id).first()

    # Return dates as naive datetime strings (no 'Z' suffix - they're local times)
    return {
        "id": created_schedule.id,
        "name": created_schedule.name,
        "type": created_schedule.type,
        "start_date": created_schedule.start_date.isoformat() if created_schedule.start_date else None,
        "end_date": created_schedule.end_date.isoformat() if created_schedule.end_date else None,
        "category_id": created_schedule.category_id,
        "category": {"id": created_schedule.category.id, "name": created_schedule.category.name} if created_schedule.category else None,
        "shuffle": created_schedule.shuffle,
        "playlist": created_schedule.playlist,
        "is_active": created_schedule.is_active,
        "last_run": created_schedule.last_run.isoformat() if created_schedule.last_run else None,
        "next_run": created_schedule.next_run.isoformat() if created_schedule.next_run else None,
        "recurrence_pattern": created_schedule.recurrence_pattern,
        "preroll_ids": created_schedule.preroll_ids,
        "fallback_category_id": getattr(created_schedule, "fallback_category_id", None),
        "sequence": getattr(created_schedule, "sequence", None),
        "color": getattr(created_schedule, "color", None),
        "blend_enabled": getattr(created_schedule, "blend_enabled", False),
        "priority": getattr(created_schedule, "priority", 5),
        "exclusive": getattr(created_schedule, "exclusive", False)
    }

@app.get("/schedules")
def get_schedules(db: Session = Depends(get_db)):
    schedules = db.query(models.Schedule).options(joinedload(models.Schedule.category)).all()
    result = []
    for s in schedules:
        # Return dates as naive datetime strings (no timezone conversion)
        # The frontend will display them as local times in the user's browser
        start_iso = s.start_date.isoformat() if s.start_date else None
        end_iso = s.end_date.isoformat() if s.end_date else None
        
        result.append({
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "start_date": start_iso,
            "end_date": end_iso,
            "category_id": s.category_id,
            "category": {"id": s.category.id, "name": s.category.name} if s.category else None,
            "shuffle": s.shuffle,
            "playlist": s.playlist,
            "is_active": s.is_active,
            "last_run": s.last_run.isoformat() if s.last_run else None,
            "next_run": s.next_run.isoformat() if s.next_run else None,
            "recurrence_pattern": s.recurrence_pattern,
            "preroll_ids": s.preroll_ids,
            "fallback_category_id": getattr(s, "fallback_category_id", None),
            "sequence": getattr(s, "sequence", None),
            "color": getattr(s, "color", None),
            "blend_enabled": getattr(s, "blend_enabled", False),
            "priority": getattr(s, "priority", 5),
            "exclusive": getattr(s, "exclusive", False)
        })
    
    return result

def _apply_schedule_win_lose_logic(db: Session, is_being_enabled: bool, is_being_disabled: bool, updated_schedule: models.Schedule):
    """
    Apply win/lose logic when a schedule is enabled or disabled.
    Immediately updates Plex prerolls based on which schedule should win.
    """
    # Use local time for comparisons since schedules are stored as naive local datetimes
    now = datetime.datetime.now()
    
    # Helper function to check if a schedule is currently active (within its time window AND time range)
    def _is_schedule_active(sched: models.Schedule) -> bool:
        if not sched.start_date:
            return False
        
        # First check date window
        date_active = False
        if sched.end_date:
            # Windowed schedules: active between start and end (inclusive)
            date_active = sched.start_date <= now <= sched.end_date
        else:
            # Indefinite schedule: active from start onward
            date_active = now >= sched.start_date
        
        if not date_active:
            return False
        
        # Now check time range for daily schedules with timeRange in recurrence_pattern
        if sched.recurrence_pattern:
            try:
                pattern = json.loads(sched.recurrence_pattern)
                time_range = pattern.get("timeRange")
                if time_range and time_range.get("start"):
                    # This schedule has a time-of-day constraint
                    start_time_str = time_range.get("start", "")  # e.g., "22:00"
                    end_time_str = time_range.get("end", "")  # e.g., "03:00"
                    
                    if start_time_str:
                        # Parse time strings (HH:MM format)
                        try:
                            start_parts = start_time_str.split(":")
                            start_hour = int(start_parts[0])
                            start_minute = int(start_parts[1]) if len(start_parts) > 1 else 0
                            
                            end_hour = 23
                            end_minute = 59
                            if end_time_str:
                                end_parts = end_time_str.split(":")
                                end_hour = int(end_parts[0])
                                end_minute = int(end_parts[1]) if len(end_parts) > 1 else 59
                            
                            # Use local time for comparison (timeRange is stored in local time)
                            current_hour = now.hour
                            current_minute = now.minute
                            current_time_val = current_hour * 60 + current_minute
                            start_time_val = start_hour * 60 + start_minute
                            end_time_val = end_hour * 60 + end_minute
                            
                            # Handle overnight ranges (e.g., 22:00 to 03:00)
                            if start_time_val <= end_time_val:
                                # Normal range (e.g., 09:00 to 17:00)
                                time_active = start_time_val <= current_time_val <= end_time_val
                            else:
                                # Overnight range (e.g., 22:00 to 03:00)
                                # Active if current time is >= start OR <= end
                                time_active = current_time_val >= start_time_val or current_time_val <= end_time_val
                            
                            if not time_active:
                                print(f"TOGGLE: Schedule '{sched.name}' outside time range {start_time_str}-{end_time_str} (local: {current_hour:02d}:{current_minute:02d})")
                                return False
                            
                        except (ValueError, IndexError) as e:
                            print(f"TOGGLE: Error parsing time range for schedule '{sched.name}': {e}")
                            # If we can't parse the time, fall through to date-only logic
            except json.JSONDecodeError:
                pass  # Invalid JSON, ignore time range
        
        return True
    
    # Helper function to apply a schedule's prerolls to Plex
    def _apply_schedule_to_plex(sched: models.Schedule) -> bool:
        """Apply a schedule's prerolls to Plex. Returns True if successful."""
        try:
            setting = db.query(models.Setting).first()
            if not setting or not setting.plex_url or not setting.plex_token:
                print(f"TOGGLE: No Plex settings configured, cannot apply schedule")
                return False
            
            plex_connector = PlexConnector(setting.plex_url, setting.plex_token)
            
            # If schedule has a sequence, apply it
            if sched.sequence:
                try:
                    seq = sched.sequence
                    if isinstance(seq, str):
                        seq = json.loads(seq)
                    
                    preroll_paths = []
                    for block in seq:
                        block_type = block.get("type")
                        if block_type == "fixed":
                            preroll_ids = block.get("prerolls", [])
                            for pid in preroll_ids:
                                preroll = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                                if preroll:
                                    preroll_paths.append(os.path.abspath(preroll.path))
                        elif block_type == "random":
                            preroll_ids = block.get("prerolls", [])
                            count = block.get("count", 1)
                            available = []
                            for pid in preroll_ids:
                                preroll = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                                if preroll:
                                    available.append(os.path.abspath(preroll.path))
                            if available:
                                selected = random.sample(available, min(count, len(available)))
                                preroll_paths.extend(selected)
                    
                    if preroll_paths:
                        preroll_string = ';'.join(preroll_paths)
                        plex_connector.set_preroll(preroll_string)
                        print(f"TOGGLE: Applied sequence for schedule '{sched.name}' (ID {sched.id}) with {len(preroll_paths)} prerolls")
                        return True
                except Exception as seq_error:
                    print(f"TOGGLE: Error applying sequence for schedule {sched.id}: {seq_error}")
                    return False
            
            # Otherwise, apply the category's prerolls
            elif sched.category_id:
                prerolls = db.query(models.Preroll) \
                    .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
                    .filter(or_(models.Preroll.category_id == sched.category_id,
                                models.preroll_categories.c.category_id == sched.category_id)) \
                    .distinct().all()
                
                if prerolls:
                    preroll_paths = [os.path.abspath(p.path) for p in prerolls]
                    preroll_string = ';'.join(preroll_paths)
                    plex_connector.set_preroll(preroll_string)
                    print(f"TOGGLE: Applied category {sched.category_id} for schedule '{sched.name}' (ID {sched.id}) with {len(prerolls)} prerolls")
                    return True
                else:
                    print(f"TOGGLE: No prerolls found for category {sched.category_id}")
                    return False
            
            return False
        except Exception as e:
            print(f"TOGGLE: Error applying schedule to Plex: {e}")
            return False
    
    # Get all active schedules (is_active=True)
    active_schedules = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()
    
    # Filter to schedules that are currently in their time window
    current_schedules = [s for s in active_schedules if _is_schedule_active(s)]
    
    if is_being_enabled:
        # Schedule was just enabled - check if it should win
        if _is_schedule_active(updated_schedule):
            # This schedule is in its active window
            if current_schedules:
                # Win/lose logic: Prefer the schedule that ends soonest, then earliest start, then lowest id
                def _sort_key(s):
                    end = s.end_date if s.end_date else datetime.datetime.max
                    start = s.start_date or datetime.datetime.min
                    return (end, start, s.id)
                
                current_schedules.sort(key=_sort_key)
                winner = current_schedules[0]
                
                if winner.id == updated_schedule.id:
                    # The newly enabled schedule wins - apply it
                    print(f"TOGGLE: Newly enabled schedule '{updated_schedule.name}' (ID {updated_schedule.id}) wins, applying to Plex")
                    if _apply_schedule_to_plex(updated_schedule):
                        setting = db.query(models.Setting).first()
                        if setting:
                            setting.active_category = updated_schedule.category_id
                            db.commit()
                else:
                    # Another schedule wins
                    print(f"TOGGLE: Newly enabled schedule '{updated_schedule.name}' (ID {updated_schedule.id}) loses to schedule '{winner.name}' (ID {winner.id})")
            else:
                # No other active schedules, this one wins by default
                print(f"TOGGLE: Newly enabled schedule '{updated_schedule.name}' (ID {updated_schedule.id}) is the only active schedule, applying to Plex")
                if _apply_schedule_to_plex(updated_schedule):
                    setting = db.query(models.Setting).first()
                    if setting:
                        setting.active_category = updated_schedule.category_id
                        db.commit()
        else:
            print(f"TOGGLE: Newly enabled schedule '{updated_schedule.name}' (ID {updated_schedule.id}) is not yet in its active time window")
    
    elif is_being_disabled:
        # Schedule was just disabled - check if another schedule should take over
        if current_schedules:
            # Win/lose logic: Pick the winning schedule
            def _sort_key(s):
                end = s.end_date if s.end_date else datetime.datetime.max
                start = s.start_date or datetime.datetime.min
                return (end, start, s.id)
            
            current_schedules.sort(key=_sort_key)
            winner = current_schedules[0]
            
            # Apply the winning schedule
            print(f"TOGGLE: Schedule disabled, applying winning schedule '{winner.name}' (ID {winner.id}) to Plex")
            if _apply_schedule_to_plex(winner):
                setting = db.query(models.Setting).first()
                if setting:
                    setting.active_category = winner.category_id
                    db.commit()
        else:
            # No active schedules remaining - clear Plex prerolls
            print(f"TOGGLE: Schedule '{updated_schedule.name}' (ID {updated_schedule.id}) disabled and no other active schedules found, clearing Plex prerolls")
            try:
                setting = db.query(models.Setting).first()
                if setting and setting.plex_url and setting.plex_token:
                    plex_connector = PlexConnector(setting.plex_url, setting.plex_token)
                    plex_connector.set_preroll('')
                    setting.active_category = None
                    db.commit()
                    print(f"TOGGLE: Cleared Plex prerolls")
            except Exception as clear_error:
                print(f"TOGGLE: Error clearing Plex prerolls: {clear_error}")

@app.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, schedule: ScheduleCreate, db: Session = Depends(get_db)):
    db_schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Parse dates from strings - store as naive local datetime (no timezone conversion)
    # The user enters their local time, we store it as-is, and the scheduler compares against local time
    start_date = None
    end_date = None

    try:
        if schedule.start_date:
            sd = schedule.start_date
            # Remove any timezone info and store as naive datetime
            # This avoids timezone conversion bugs where browser TZ != configured TZ
            if 'Z' in sd:
                sd = sd.replace('Z', '')
            if '+' in sd and 'T' in sd:
                sd = sd.split('+')[0]
            if sd.count('-') > 2 and 'T' in sd:  # Has negative offset like -07:00
                parts = sd.rsplit('-', 1)
                if ':' in parts[-1]:  # It's a timezone offset, not part of the date
                    sd = parts[0]
            start_date = datetime.datetime.fromisoformat(sd)
                
        if schedule.end_date:
            ed = schedule.end_date
            # Remove any timezone info and store as naive datetime
            if 'Z' in ed:
                ed = ed.replace('Z', '')
            if '+' in ed and 'T' in ed:
                ed = ed.split('+')[0]
            if ed.count('-') > 2 and 'T' in ed:  # Has negative offset like -07:00
                parts = ed.rsplit('-', 1)
                if ':' in parts[-1]:  # It's a timezone offset, not part of the date
                    ed = parts[0]
            end_date = datetime.datetime.fromisoformat(ed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

    # Check if schedule is being enabled or disabled
    was_active = db_schedule.is_active
    is_being_disabled = was_active and not schedule.is_active
    is_being_enabled = not was_active and schedule.is_active
    
    # Update fields
    db_schedule.name = schedule.name
    db_schedule.type = schedule.type
    db_schedule.start_date = start_date
    db_schedule.end_date = end_date
    db_schedule.category_id = schedule.category_id
    db_schedule.shuffle = schedule.shuffle
    db_schedule.playlist = schedule.playlist
    db_schedule.recurrence_pattern = schedule.recurrence_pattern
    db_schedule.preroll_ids = schedule.preroll_ids
    db_schedule.fallback_category_id = schedule.fallback_category_id
    db_schedule.sequence = schedule.sequence
    db_schedule.color = schedule.color
    db_schedule.is_active = schedule.is_active
    db_schedule.blend_enabled = schedule.blend_enabled
    db_schedule.priority = schedule.priority
    db_schedule.exclusive = schedule.exclusive

    try:
        db.commit()
        db.refresh(db_schedule)
    except Exception as e:
        db.rollback()
        _file_log(f"Schedule update failed for id={schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")
    
    # Apply changes to Plex immediately using win/lose logic
    try:
        _apply_schedule_win_lose_logic(db, is_being_enabled, is_being_disabled, db_schedule)
    except Exception as apply_error:
        print(f"SCHEDULER: Warning - Failed to apply schedule changes to Plex: {apply_error}")
    
    return {"message": "Schedule updated"}

@app.delete("/schedules/{schedule_id}")
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    db_schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    db.delete(db_schedule)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        _file_log(f"Schedule delete failed for id={schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete schedule: {str(e)}")
    return {"message": "Schedule deleted"}

# ============================================================================
# SAVED SEQUENCES API
# ============================================================================

class SavedSequenceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    blocks: List[dict]

class SavedSequenceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    blocks: Optional[List[dict]] = None

@app.get("/sequences")
def get_saved_sequences(db: Session = Depends(get_db)):
    """Get all saved sequences"""
    try:
        sequences = db.query(models.SavedSequence).order_by(models.SavedSequence.updated_at.desc()).all()
        return [{
            "id": seq.id,
            "name": seq.name,
            "description": seq.description,
            "blocks": seq.get_blocks(),
            "created_at": seq.created_at.isoformat() if seq.created_at else None,
            "updated_at": seq.updated_at.isoformat() if seq.updated_at else None
        } for seq in sequences]
    except Exception as e:
        _file_log(f"Failed to fetch saved sequences: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch sequences: {str(e)}")

@app.post("/sequences")
def create_saved_sequence(sequence: SavedSequenceCreate, db: Session = Depends(get_db)):
    """Create a new saved sequence"""
    try:
        new_sequence = models.SavedSequence(
            name=sequence.name,
            description=sequence.description,
            blocks=json.dumps(sequence.blocks)
        )
        db.add(new_sequence)
        db.commit()
        db.refresh(new_sequence)
        
        _file_log(f"Saved new sequence: {sequence.name} with {len(sequence.blocks)} blocks")
        
        return {
            "id": new_sequence.id,
            "name": new_sequence.name,
            "description": new_sequence.description,
            "blocks": new_sequence.get_blocks(),
            "created_at": new_sequence.created_at.isoformat() if new_sequence.created_at else None,
            "updated_at": new_sequence.updated_at.isoformat() if new_sequence.updated_at else None
        }
    except Exception as e:
        db.rollback()
        _file_log(f"Failed to create saved sequence: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create sequence: {str(e)}")

@app.get("/sequences/{sequence_id}")
def get_saved_sequence(sequence_id: int, db: Session = Depends(get_db)):
    """Get a specific saved sequence by ID"""
    sequence = db.query(models.SavedSequence).filter(models.SavedSequence.id == sequence_id).first()
    if not sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    return {
        "id": sequence.id,
        "name": sequence.name,
        "description": sequence.description,
        "blocks": sequence.get_blocks(),
        "created_at": sequence.created_at.isoformat() if sequence.created_at else None,
        "updated_at": sequence.updated_at.isoformat() if sequence.updated_at else None
    }

@app.put("/sequences/{sequence_id}")
def update_saved_sequence(sequence_id: int, sequence: SavedSequenceUpdate, db: Session = Depends(get_db)):
    """Update an existing saved sequence"""
    db_sequence = db.query(models.SavedSequence).filter(models.SavedSequence.id == sequence_id).first()
    if not db_sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    try:
        if sequence.name is not None:
            db_sequence.name = sequence.name
        if sequence.description is not None:
            db_sequence.description = sequence.description
        if sequence.blocks is not None:
            db_sequence.blocks = json.dumps(sequence.blocks)
        
        db_sequence.updated_at = datetime.datetime.utcnow()
        db.commit()
        db.refresh(db_sequence)
        
        _file_log(f"Updated sequence: {db_sequence.name} (ID: {sequence_id})")
        
        return {
            "id": db_sequence.id,
            "name": db_sequence.name,
            "description": db_sequence.description,
            "blocks": db_sequence.get_blocks(),
            "created_at": db_sequence.created_at.isoformat() if db_sequence.created_at else None,
            "updated_at": db_sequence.updated_at.isoformat() if db_sequence.updated_at else None
        }
    except Exception as e:
        db.rollback()
        _file_log(f"Failed to update sequence {sequence_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update sequence: {str(e)}")

@app.delete("/sequences/{sequence_id}")
def delete_saved_sequence(sequence_id: int, db: Session = Depends(get_db)):
    """Delete a saved sequence"""
    db_sequence = db.query(models.SavedSequence).filter(models.SavedSequence.id == sequence_id).first()
    if not db_sequence:
        raise HTTPException(status_code=404, detail="Sequence not found")
    
    try:
        sequence_name = db_sequence.name
        db.delete(db_sequence)
        db.commit()
        
        _file_log(f"Deleted sequence: {sequence_name} (ID: {sequence_id})")
        
        return {"message": "Sequence deleted successfully"}
    except Exception as e:
        db.rollback()
        _file_log(f"Failed to delete sequence {sequence_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete sequence: {str(e)}")

@app.get("/sequences/preview-video/{preview_id}/{video_path:path}")
async def get_preview_video(preview_id: str, video_path: str):
    """
    Serve a video file from a bundle preview for playback.
    The preview_id is a unique identifier for the extracted bundle.
    The video_path is the relative path within the bundle (e.g., "fixed/file.mp4" or "categories/Christmas/file.mp4")
    """
    import re
    import tempfile
    from fastapi.responses import FileResponse
    
    # Validate preview_id format (alphanumeric, max 8 chars)
    if not re.match(r'^[a-zA-Z0-9]{1,8}$', preview_id):
        raise HTTPException(status_code=400, detail="Invalid preview ID")
    
    # Sanitize video_path to prevent directory traversal
    video_path = video_path.replace('..', '').replace('//', '/')
    
    # Build the full path
    preview_dir = os.path.join(tempfile.gettempdir(), f"nexroll_preview_{preview_id}")
    full_path = os.path.join(preview_dir, video_path)
    
    # Security check - ensure the path is within the preview directory
    if not os.path.abspath(full_path).startswith(os.path.abspath(preview_dir)):
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not os.path.exists(full_path):
        _file_log(f"[PREVIEW] Video not found: {full_path}")
        raise HTTPException(status_code=404, detail="Preview video not found")
    
    # Get file extension for media type
    ext = os.path.splitext(full_path)[1].lower()
    media_types = {
        '.mp4': 'video/mp4',
        '.mkv': 'video/x-matroska',
        '.mov': 'video/quicktime',
        '.avi': 'video/x-msvideo',
        '.webm': 'video/webm',
        '.m4v': 'video/mp4'
    }
    media_type = media_types.get(ext, 'video/mp4')
    
    _file_log(f"[PREVIEW] Serving video: {video_path}")
    return FileResponse(full_path, media_type=media_type)

@app.delete("/sequences/preview/{preview_id}")
def cleanup_preview(preview_id: str):
    """
    Clean up preview files when the import is cancelled or completed.
    """
    import re
    import tempfile
    import shutil
    
    # Validate preview_id format
    if not re.match(r'^[a-zA-Z0-9]{1,8}$', preview_id):
        raise HTTPException(status_code=400, detail="Invalid preview ID")
    
    preview_dir = os.path.join(tempfile.gettempdir(), f"nexroll_preview_{preview_id}")
    
    if os.path.exists(preview_dir):
        try:
            shutil.rmtree(preview_dir)
            _file_log(f"[PREVIEW] Cleaned up preview directory: {preview_dir}")
            return {"message": "Preview cleaned up successfully"}
        except Exception as e:
            _file_log(f"[PREVIEW] Failed to clean up: {e}")
            return {"message": f"Cleanup failed: {str(e)}"}
    
    return {"message": "Preview directory not found"}

@app.post("/sequences/import")
async def import_sequence_pattern(
    file: UploadFile = File(...), 
    auto_download: bool = Query(False, description="Automatically download missing prerolls from community"),
    folder_mappings: Optional[str] = Form(None, description="JSON string of folder mappings for ZIP bundles"),
    db: Session = Depends(get_db)
):
    """
    Import a .nexseq pattern file or .zip bundle with prerolls.
    
    Supports:
    - .nexseq JSON files (pattern only)
    - .zip bundles (pattern + video files organized by category/fixed folders)
    
    Matching priority:
    1. Community preroll ID (most reliable)
    2. Exact name match in local library
    3. If auto_download=true, download from community prerolls
    4. Import video files from ZIP bundle (avoids duplicates)
    
    For ZIP bundles:
    - First call without folder_mappings returns bundle_preview with contents
    - Second call with folder_mappings performs actual import with user-selected destinations
    
    Returns preview data with match statistics and import results
    """
    try:
        # Parse folder mappings if provided
        mappings = {}
        if folder_mappings:
            try:
                mappings = json.loads(folder_mappings)
                _file_log(f"[IMPORT] Folder mappings provided: {mappings}")
            except json.JSONDecodeError:
                _file_log(f"[IMPORT] Failed to parse folder_mappings: {folder_mappings}")
        
        # Read the uploaded file
        contents = await file.read()
        pattern_data = None
        imported_prerolls = []
        imported_categories = []
        bundle_mode = False
        bundle_preview = None
        
        # Check if it's a ZIP bundle or JSON file
        if file.filename.endswith('.zip'):
            bundle_mode = True
            # Handle ZIP bundle
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp_file:
                tmp_file.write(contents)
                tmp_path = tmp_file.name
            
            try:
                with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
                    # Extract to temporary directory
                    extract_dir = tempfile.mkdtemp()
                    zip_ref.extractall(extract_dir)
                    
                    # Find the .nexseq file
                    nexseq_file = None
                    for root, dirs, files in os.walk(extract_dir):
                        for file_name in files:
                            if file_name.endswith('.nexseq'):
                                nexseq_file = os.path.join(root, file_name)
                                break
                        if nexseq_file:
                            break
                    
                    if not nexseq_file:
                        raise HTTPException(status_code=400, detail="No .nexseq file found in ZIP bundle")
                    
                    # Read pattern data
                    with open(nexseq_file, 'r') as f:
                        pattern_data = json.load(f)
                    
                    # Paths for video content
                    categories_path = os.path.join(extract_dir, 'categories')
                    fixed_path = os.path.join(extract_dir, 'fixed')
                    
                    # If no folder_mappings provided, just return a preview of bundle contents
                    if not mappings:
                        _file_log(f"[IMPORT] ZIP bundle preview mode - scanning contents")
                        bundle_preview = {
                            'categories': [],
                            'fixed': [],
                            'sequence': [],  # Ordered list of prerolls as they appear in the sequence
                            'preview_id': None  # ID for accessing preview videos
                        }
                        
                        # Generate a unique preview ID and keep extracted files
                        import uuid as uuid_module
                        preview_id = str(uuid_module.uuid4())[:8]
                        preview_dir = os.path.join(tempfile.gettempdir(), f"nexroll_preview_{preview_id}")
                        
                        # Move extracted files to preview directory
                        import shutil
                        shutil.move(extract_dir, preview_dir)
                        extract_dir = preview_dir  # Update reference
                        categories_path = os.path.join(extract_dir, 'categories')
                        fixed_path = os.path.join(extract_dir, 'fixed')
                        
                        bundle_preview['preview_id'] = preview_id
                        _file_log(f"[IMPORT] Created preview directory: {preview_dir}")
                        
                        # Build category info with file list
                        category_files = {}  # { category_name: [files] }
                        if os.path.exists(categories_path):
                            for category_folder in os.listdir(categories_path):
                                category_folder_path = os.path.join(categories_path, category_folder)
                                if os.path.isdir(category_folder_path):
                                    files = [f for f in os.listdir(category_folder_path) 
                                            if f.lower().endswith(('.mp4', '.mkv', '.avi', '.mov'))]
                                    category_files[category_folder] = files
                                    bundle_preview['categories'].append({
                                        'name': category_folder,
                                        'preroll_count': len(files),
                                        'files': [os.path.splitext(f)[0] for f in files]
                                    })
                        
                        # Build fixed prerolls info
                        fixed_files = {}  # { name: filename }
                        if os.path.exists(fixed_path):
                            for video_file in os.listdir(fixed_path):
                                if video_file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                                    name = os.path.splitext(video_file)[0]
                                    fixed_files[name] = video_file
                                    bundle_preview['fixed'].append({
                                        'name': name,
                                        'filename': video_file
                                    })
                        
                        # Build sequence order from pattern blocks
                        for block in pattern_data.get('blocks', []):
                            block_type = block.get('type', '')
                            if block_type == 'fixed':
                                preroll_name = block.get('preroll_name', '')
                                if preroll_name:
                                    # Find the file path
                                    if preroll_name in fixed_files:
                                        bundle_preview['sequence'].append({
                                            'type': 'fixed',
                                            'name': preroll_name,
                                            'path': f"fixed/{fixed_files[preroll_name]}"
                                        })
                                    else:
                                        # Check in categories
                                        for cat_name, cat_files in category_files.items():
                                            for f in cat_files:
                                                if os.path.splitext(f)[0] == preroll_name:
                                                    bundle_preview['sequence'].append({
                                                        'type': 'fixed',
                                                        'name': preroll_name,
                                                        'path': f"categories/{cat_name}/{f}",
                                                        'category': cat_name
                                                    })
                                                    break
                            elif block_type == 'random':
                                category_name = block.get('category_name', '')
                                count = block.get('count', 1)
                                # Find matching category with normalized comparison (handle apostrophes, case)
                                def normalize_name(name):
                                    return name.lower().replace("'", "").replace("'", "").replace("`", "")
                                matched_cat = None
                                for cat_key in category_files.keys():
                                    if normalize_name(cat_key) == normalize_name(category_name):
                                        matched_cat = cat_key
                                        break
                                if matched_cat:
                                    _file_log(f"[IMPORT] Matched category '{category_name}' to folder '{matched_cat}'")
                                    # Add placeholder for random block
                                    bundle_preview['sequence'].append({
                                        'type': 'random',
                                        'category': category_name,
                                        'count': count,
                                        'available_files': [
                                            f"categories/{matched_cat}/{f}" 
                                            for f in category_files[matched_cat]
                                        ]
                                    })
                                else:
                                    _file_log(f"[IMPORT] WARNING: No matching category folder for '{category_name}'")
                        
                        _file_log(f"[IMPORT] Bundle preview: {len(bundle_preview['categories'])} categories, {len(bundle_preview['fixed'])} fixed prerolls, {len(bundle_preview['sequence'])} sequence blocks")
                        
                        # DON'T cleanup temp files - keep them for preview
                        # They will be cleaned up when the import is confirmed or cancelled
                        try:
                            os.unlink(tmp_path)
                        except Exception:
                            pass
                        
                        # Return early with just the bundle preview for folder mapping UI
                        return {
                            'pattern_name': pattern_data.get('pattern_name', 'Imported Pattern'),
                            'pattern_description': pattern_data.get('pattern_description', ''),
                            'bundle_preview': bundle_preview,
                            'blocks': [],
                            'match_results': {
                                'matched': 0,
                                'unmatched': 0,
                                'downloadable': 0,
                                'total_blocks': len(pattern_data.get('blocks', [])),
                                'missing_prerolls': [],
                                'missing_categories': []
                            }
                        }
                    else:
                        # Folder mappings provided - do the actual import
                        _file_log(f"[IMPORT] ZIP bundle import mode with mappings")
                        plex_library_path = PREROLLS_DIR
                        
                        # Build a lookup map of preroll names to community IDs from pattern data
                        # This allows us to set community_preroll_id when importing from bundle
                        community_id_map = {}  # { preroll_name: community_id }
                        for block in pattern_data.get('blocks', []):
                            block_type = block.get('type', '')
                            if block_type == 'random':
                                # Random blocks may have available_prerolls list with community IDs
                                for preroll_info in block.get('available_prerolls', []):
                                    name = preroll_info.get('name', '')
                                    cid = preroll_info.get('community_id')
                                    if name and cid:
                                        community_id_map[name] = cid
                                        _file_log(f"[IMPORT] Mapped community ID for '{name}': {cid}")
                            elif block_type == 'fixed':
                                # Fixed blocks have preroll_name and community_id directly
                                name = block.get('preroll_name', '')
                                cid = block.get('community_id')
                                if name and cid:
                                    community_id_map[name] = cid
                                    _file_log(f"[IMPORT] Mapped community ID for '{name}': {cid}")
                                # Also check preroll_data if present
                                preroll_data = block.get('preroll_data', {})
                                if preroll_data:
                                    name = preroll_data.get('name', '')
                                    cid = preroll_data.get('community_id')
                                    if name and cid:
                                        community_id_map[name] = cid
                        
                        _file_log(f"[IMPORT] Built community ID map with {len(community_id_map)} entries")
                        
                        # Import category folders with user-specified destinations
                        if os.path.exists(categories_path):
                            for category_folder in os.listdir(categories_path):
                                category_folder_path = os.path.join(categories_path, category_folder)
                                if os.path.isdir(category_folder_path):
                                    # Get user-specified target category
                                    mapping_key = f"category:{category_folder}"
                                    target = str(mappings.get(mapping_key, f"new:{category_folder}"))
                                    
                                    if target.startswith('new:'):
                                        # Create new category with specified name
                                        new_cat_name = target[4:]  # Remove 'new:' prefix
                                        category = db.query(models.Category).filter(
                                            models.Category.name.ilike(new_cat_name)
                                        ).first()
                                        if not category:
                                            category = models.Category(name=new_cat_name)
                                            db.add(category)
                                            db.commit()
                                            db.refresh(category)
                                            imported_categories.append(new_cat_name)
                                    else:
                                        # Use existing category by ID
                                        try:
                                            category = db.query(models.Category).filter(
                                                models.Category.id == int(target)
                                            ).first()
                                        except (ValueError, TypeError):
                                            category = None
                                        
                                        if not category:
                                            # Fallback to creating new category
                                            category = models.Category(name=category_folder)
                                            db.add(category)
                                            db.commit()
                                            db.refresh(category)
                                            imported_categories.append(category_folder)
                                    
                                    _file_log(f"[IMPORT] Importing category '{category_folder}' -> '{category.name}' (ID: {category.id})")
                                    
                                    # Import prerolls from this category
                                    for video_file in os.listdir(category_folder_path):
                                        video_path = os.path.join(category_folder_path, video_file)
                                        if os.path.isfile(video_path) and video_file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                                            preroll_display_name = os.path.splitext(video_file)[0]
                                            _file_log(f"[IMPORT] Processing category preroll: {preroll_display_name}")
                                            
                                            # Check if preroll already exists (by name in target category)
                                            # Check both with and without extension, case-insensitive
                                            existing = db.query(models.Preroll).filter(
                                                models.Preroll.category_id == category.id,
                                                (
                                                    models.Preroll.display_name.ilike(preroll_display_name) |
                                                    models.Preroll.display_name.ilike(video_file) |
                                                    models.Preroll.filename.ilike(video_file)
                                                )
                                            ).first()
                                            
                                            if existing:
                                                _file_log(f"[IMPORT] Skipping '{preroll_display_name}' - already exists in category '{category.name}' as '{existing.display_name}'")
                                                continue
                                            
                                            # Copy file to Plex library under category folder
                                            dest_category_path = os.path.join(plex_library_path, category.name)
                                            os.makedirs(dest_category_path, exist_ok=True)
                                            dest_file = os.path.join(dest_category_path, video_file)
                                            
                                            # Copy file if it doesn't exist on disk
                                            if not os.path.exists(dest_file):
                                                import shutil
                                                shutil.copy2(video_path, dest_file)
                                                _file_log(f"[IMPORT] Copied file to: {dest_file}")
                                            else:
                                                _file_log(f"[IMPORT] File already exists on disk: {dest_file}")
                                            
                                            # Look up community ID from pattern data
                                            community_id = community_id_map.get(preroll_display_name)
                                            
                                            # Create preroll record with community_preroll_id if available
                                            preroll_kwargs = {
                                                'filename': video_file,
                                                'display_name': preroll_display_name,
                                                'path': dest_file,
                                                'category_id': category.id,
                                                'file_size': os.path.getsize(dest_file),
                                                'tags': json.dumps([])
                                            }
                                            if community_id:
                                                preroll_kwargs['community_preroll_id'] = community_id
                                                _file_log(f"[IMPORT] Setting community_preroll_id for '{preroll_display_name}': {community_id}")
                                            
                                            new_preroll = models.Preroll(**preroll_kwargs)
                                            db.add(new_preroll)
                                            db.commit()
                                            db.refresh(new_preroll)
                                            _file_log(f"[IMPORT] Created preroll record: {new_preroll.display_name} (ID: {new_preroll.id})")
                                            
                                            # Generate thumbnail
                                            thumb_path = _generate_thumbnail_for_preroll(new_preroll, dest_file, category.name)
                                            if thumb_path:
                                                new_preroll.thumbnail = thumb_path
                                                db.commit()
                                            
                                            imported_prerolls.append({
                                                'name': new_preroll.display_name,
                                                'category': category.name,
                                                'type': 'category',
                                                'community_id': community_id
                                            })
                    
                        # Import fixed prerolls with user-specified destinations
                        if os.path.exists(fixed_path):
                            for video_file in os.listdir(fixed_path):
                                video_path = os.path.join(fixed_path, video_file)
                                if os.path.isfile(video_path) and video_file.lower().endswith(('.mp4', '.mkv', '.avi', '.mov')):
                                    preroll_name = os.path.splitext(video_file)[0]
                                    
                                    # Check if preroll already exists (by name in any category)
                                    existing = db.query(models.Preroll).filter(
                                        models.Preroll.display_name == preroll_name
                                    ).first()
                                    
                                    if not existing:
                                        # Get user-specified target category
                                        mapping_key = f"fixed:{preroll_name}"
                                        target = str(mappings.get(mapping_key, 'new:Imported'))
                                        
                                        if target.startswith('new:'):
                                            # Create new category with specified name
                                            new_cat_name = target[4:]  # Remove 'new:' prefix
                                            target_category = db.query(models.Category).filter(
                                                models.Category.name.ilike(new_cat_name)
                                            ).first()
                                            if not target_category:
                                                target_category = models.Category(name=new_cat_name)
                                                db.add(target_category)
                                                db.commit()
                                                db.refresh(target_category)
                                        else:
                                            # Use existing category by ID
                                            try:
                                                target_category = db.query(models.Category).filter(
                                                    models.Category.id == int(target)
                                                ).first()
                                            except (ValueError, TypeError):
                                                target_category = None
                                            
                                            if not target_category:
                                                # Fallback to creating 'Imported' category
                                                target_category = db.query(models.Category).filter(
                                                    models.Category.name == 'Imported'
                                                ).first()
                                                if not target_category:
                                                    target_category = models.Category(name='Imported')
                                                    db.add(target_category)
                                                    db.commit()
                                                    db.refresh(target_category)
                                        
                                        _file_log(f"[IMPORT] Importing fixed preroll '{preroll_name}' -> '{target_category.name}' (ID: {target_category.id})")
                                        
                                        # Copy file to target category folder
                                        dest_folder = os.path.join(plex_library_path, target_category.name)
                                        os.makedirs(dest_folder, exist_ok=True)
                                        dest_file = os.path.join(dest_folder, video_file)
                                        
                                        if not os.path.exists(dest_file):
                                            import shutil
                                            shutil.copy2(video_path, dest_file)
                                            
                                            # Look up community ID from pattern data
                                            community_id = community_id_map.get(preroll_name)
                                            
                                            # Create preroll record with community_preroll_id if available
                                            preroll_kwargs = {
                                                'filename': video_file,
                                                'display_name': preroll_name,
                                                'path': dest_file,
                                                'category_id': target_category.id,
                                                'file_size': os.path.getsize(dest_file),
                                                'tags': json.dumps([])
                                            }
                                            if community_id:
                                                preroll_kwargs['community_preroll_id'] = community_id
                                                _file_log(f"[IMPORT] Setting community_preroll_id for '{preroll_name}': {community_id}")
                                            
                                            new_preroll = models.Preroll(**preroll_kwargs)
                                            db.add(new_preroll)
                                            db.commit()
                                            db.refresh(new_preroll)
                                            
                                            # Generate thumbnail
                                            thumb_path = _generate_thumbnail_for_preroll(new_preroll, dest_file, target_category.name)
                                            if thumb_path:
                                                new_preroll.thumbnail = thumb_path
                                                db.commit()
                                            
                                            imported_prerolls.append({
                                                'name': new_preroll.display_name,
                                                'category': target_category.name,
                                                'type': 'fixed',
                                                'community_id': community_id
                                            })
                    
                    db.commit()
                
                # Cleanup (outside the zipfile context manager)
                import shutil
                try:
                    shutil.rmtree(extract_dir)
                except Exception as cleanup_error:
                    _file_log(f"Cleanup warning (extract_dir): {cleanup_error}")
                
            except Exception as e:
                _file_log(f"Failed to process ZIP bundle: {e}")
                import traceback
                _file_log(f"Traceback: {traceback.format_exc()}")
                raise HTTPException(status_code=400, detail=f"Failed to process ZIP bundle: {str(e)}")
            finally:
                # Always cleanup temp file
                try:
                    if os.path.exists(tmp_path):
                        os.unlink(tmp_path)
                except Exception as cleanup_error:
                    _file_log(f"Cleanup warning (tmp_path): {cleanup_error}")
        else:
            # Handle regular .nexseq or .nexbundle JSON file
            pattern_data = json.loads(contents.decode('utf-8'))
        
        # Check if this is a .nexbundle file (multiple sequences)
        if pattern_data.get('type') == 'nexbundle' and 'sequences' in pattern_data:
            _file_log(f"[IMPORT] Processing .nexbundle with {len(pattern_data.get('sequences', []))} sequences")
            
            # Get all categories and prerolls for matching
            all_categories = {cat.name.lower(): cat for cat in db.query(models.Category).all()}
            all_prerolls = db.query(models.Preroll).all()
            
            # Create lookup dictionaries for prerolls
            prerolls_by_community_id = {p.community_preroll_id: p for p in all_prerolls if p.community_preroll_id}
            prerolls_by_name = {}
            for p in all_prerolls:
                display_name = (p.display_name or p.filename).strip().lower()
                prerolls_by_name[display_name] = p
                filename_no_ext = os.path.splitext(p.filename)[0].strip().lower()
                if filename_no_ext != display_name:
                    prerolls_by_name[filename_no_ext] = p
            
            # Track all missing prerolls across all sequences
            all_missing_prerolls = []
            all_missing_categories = []
            sequences_preview = []
            total_matched = 0
            total_unmatched = 0
            total_downloadable = 0
            
            # Process each sequence for matching
            for seq_data in pattern_data.get('sequences', []):
                seq_name = seq_data.get('name', 'Imported Sequence')
                seq_description = seq_data.get('description', '')
                seq_blocks = seq_data.get('blocks', [])
                
                matched_blocks = []
                seq_matched = 0
                seq_unmatched = 0
                seq_downloadable = 0
                seq_missing_prerolls = []
                
                for block_data in seq_blocks:
                    block_type = block_data.get('type', '')
                    matched_block = {
                        'type': block_type,
                        'id': block_data.get('id', str(uuid.uuid4()))
                    }
                    block_matched = False
                    
                    if block_type == 'random':
                        category_name = block_data.get('category_name', '').strip().lower()
                        if category_name and category_name in all_categories:
                            matched_block['category_id'] = all_categories[category_name].id
                            matched_block['category_name'] = all_categories[category_name].name
                            matched_block['count'] = block_data.get('count', 1)
                            block_matched = True
                            seq_matched += 1
                        else:
                            seq_unmatched += 1
                            original_category_name = block_data.get('category_name', 'Unknown')
                            matched_block['category_name'] = original_category_name
                            matched_block['count'] = block_data.get('count', 1)
                            matched_block['_unmatched'] = True
                            matched_block['_missing_category'] = original_category_name
                            if original_category_name not in all_missing_categories:
                                all_missing_categories.append(original_category_name)
                    
                    elif block_type == 'fixed':
                        preroll_ids_in_block = block_data.get('preroll_ids', [])
                        preroll_name = block_data.get('preroll_name')
                        community_id = block_data.get('community_id')
                        preroll_data = block_data.get('preroll_data', {})
                        # New format: preroll_info array with detailed info per preroll
                        preroll_info = block_data.get('preroll_info', [])
                        
                        matched_preroll_ids = []
                        unmatched_preroll_info = []  # Track info for prerolls we can't find locally
                        
                        # If we have preroll_info (new format), use it for matching
                        if preroll_info:
                            for pinfo in preroll_info:
                                pid = pinfo.get('id')
                                pname = pinfo.get('name')
                                pcommunity_id = pinfo.get('community_id')
                                
                                # Try to find local preroll by ID first
                                local_preroll = None
                                if pid:
                                    local_preroll = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                                
                                if local_preroll:
                                    matched_preroll_ids.append(pid)
                                else:
                                    # Try to find by community_id
                                    if pcommunity_id and pcommunity_id in prerolls_by_community_id:
                                        matched_preroll_ids.append(prerolls_by_community_id[pcommunity_id].id)
                                    elif pname:
                                        # Try to find by name
                                        name_lower = pname.strip().lower()
                                        if name_lower in prerolls_by_name:
                                            matched_preroll_ids.append(prerolls_by_name[name_lower].id)
                                        else:
                                            name_no_ext = os.path.splitext(name_lower)[0]
                                            if name_no_ext in prerolls_by_name:
                                                matched_preroll_ids.append(prerolls_by_name[name_no_ext].id)
                                            else:
                                                # Couldn't match - track for missing prerolls
                                                unmatched_preroll_info.append({
                                                    'name': pname,
                                                    'community_id': pcommunity_id,
                                                    'original_id': pid
                                                })
                                    else:
                                        # No name, no community_id, can't match
                                        unmatched_preroll_info.append({
                                            'name': f'Preroll ID {pid}' if pid else 'Unknown preroll',
                                            'community_id': pcommunity_id,
                                            'original_id': pid
                                        })
                        
                        # Fallback: If we have preroll_ids but no preroll_info (old format), validate each one
                        elif preroll_ids_in_block:
                            for pid in preroll_ids_in_block:
                                local_preroll = db.query(models.Preroll).filter(models.Preroll.id == pid).first()
                                if local_preroll:
                                    matched_preroll_ids.append(pid)
                                else:
                                    # Preroll ID not found - check if we have community_id info
                                    if community_id and community_id in prerolls_by_community_id:
                                        matched_preroll_ids.append(prerolls_by_community_id[community_id].id)
                                    elif preroll_name:
                                        name_lower = preroll_name.strip().lower()
                                        if name_lower in prerolls_by_name:
                                            matched_preroll_ids.append(prerolls_by_name[name_lower].id)
                                        else:
                                            # Try without extension
                                            name_no_ext = os.path.splitext(name_lower)[0]
                                            if name_no_ext in prerolls_by_name:
                                                matched_preroll_ids.append(prerolls_by_name[name_no_ext].id)
                        
                        # Also try matching by community_id or name if no preroll_ids
                        if not matched_preroll_ids:
                            if community_id and community_id in prerolls_by_community_id:
                                matched_preroll_ids.append(prerolls_by_community_id[community_id].id)
                            elif preroll_name:
                                name_lower = preroll_name.strip().lower()
                                if name_lower in prerolls_by_name:
                                    matched_preroll_ids.append(prerolls_by_name[name_lower].id)
                                else:
                                    name_no_ext = os.path.splitext(name_lower)[0]
                                    if name_no_ext in prerolls_by_name:
                                        matched_preroll_ids.append(prerolls_by_name[name_no_ext].id)
                        
                        if matched_preroll_ids:
                            matched_block['preroll_ids'] = matched_preroll_ids
                            block_matched = True
                            seq_matched += 1
                        else:
                            # Track as missing
                            seq_unmatched += 1
                            matched_block['_unmatched'] = True
                            matched_block['_original_preroll_ids'] = preroll_ids_in_block
                            
                            # Use unmatched_preroll_info if available (new format), otherwise use legacy data
                            if unmatched_preroll_info:
                                for upi in unmatched_preroll_info:
                                    upi_community_id = upi.get('community_id')
                                    can_download = upi_community_id and not str(upi_community_id).startswith('_') and '\\' not in str(upi_community_id)
                                    missing_info = {
                                        'name': upi.get('name', 'Unknown preroll'),
                                        'community_id': upi_community_id,
                                        'downloadable': can_download,
                                        'sequence_name': seq_name,
                                        'block_id': matched_block['id']
                                    }
                                    
                                    if can_download:
                                        seq_downloadable += 1
                                        missing_info['status'] = 'needs_download'
                                    else:
                                        missing_info['status'] = 'unavailable'
                                        missing_info['reason'] = 'No community ID available' if not upi_community_id else 'Invalid community ID format'
                                    
                                    seq_missing_prerolls.append(missing_info)
                                    # Add to global missing list if not already there
                                    existing = next((m for m in all_missing_prerolls if m.get('community_id') == upi_community_id and m.get('name') == missing_info['name']), None)
                                    if not existing:
                                        all_missing_prerolls.append(missing_info)
                            else:
                                # Legacy format - single preroll info
                                can_download = community_id and not community_id.startswith('_') and '\\' not in community_id
                                missing_info = {
                                    'name': preroll_name or preroll_data.get('display_name') or f'Preroll ID {preroll_ids_in_block[0] if preroll_ids_in_block else "unknown"}',
                                    'community_id': community_id,
                                    'downloadable': can_download,
                                    'sequence_name': seq_name,
                                    'block_id': matched_block['id']
                                }
                                
                                if can_download:
                                    seq_downloadable += 1
                                    missing_info['status'] = 'needs_download'
                                else:
                                    missing_info['status'] = 'unavailable'
                                    missing_info['reason'] = 'No community ID available' if not community_id else 'Invalid community ID format'
                                
                                seq_missing_prerolls.append(missing_info)
                                # Add to global missing list if not already there
                                existing = next((m for m in all_missing_prerolls if m.get('community_id') == community_id and m.get('name') == missing_info['name']), None)
                                if not existing:
                                    all_missing_prerolls.append(missing_info)
                    
                    elif block_type == 'sequential':
                        category_name = block_data.get('category_name', '').strip().lower()
                        if category_name and category_name in all_categories:
                            matched_block['category_id'] = all_categories[category_name].id
                            matched_block['category_name'] = all_categories[category_name].name
                            block_matched = True
                            seq_matched += 1
                        else:
                            seq_unmatched += 1
                            original_category_name = block_data.get('category_name', 'Unknown')
                            matched_block['category_name'] = original_category_name
                            matched_block['_unmatched'] = True
                            matched_block['_missing_category'] = original_category_name
                            if original_category_name not in all_missing_categories:
                                all_missing_categories.append(original_category_name)
                    
                    elif block_type == 'separator':
                        # Separators don't need matching
                        block_matched = True
                        seq_matched += 1
                    
                    matched_blocks.append(matched_block)
                
                total_matched += seq_matched
                total_unmatched += seq_unmatched
                total_downloadable += seq_downloadable
                
                sequences_preview.append({
                    'name': seq_name,
                    'description': seq_description,
                    'blocks': matched_blocks,
                    'original_blocks': seq_blocks,
                    'stats': {
                        'matched': seq_matched,
                        'unmatched': seq_unmatched,
                        'downloadable': seq_downloadable,
                        'total': len(seq_blocks)
                    },
                    'missing_prerolls': seq_missing_prerolls
                })
            
            # Return preview data instead of immediately importing
            return {
                'success': True,
                'bundle_preview': True,
                'type': 'nexbundle',
                'version': pattern_data.get('version', '1.0'),
                'exported': pattern_data.get('exported'),
                'sequences': sequences_preview,
                'match_results': {
                    'matched': total_matched,
                    'unmatched': total_unmatched,
                    'downloadable': total_downloadable,
                    'total_sequences': len(sequences_preview),
                    'total_blocks': sum(len(s['original_blocks']) for s in sequences_preview),
                    'missing_categories': all_missing_categories,
                    'missing_prerolls': all_missing_prerolls
                },
                'message': f"Preview: {len(sequences_preview)} sequences with {total_matched} matched blocks, {total_unmatched} unmatched"
            }
        
        # Normalize pattern data format (handle both old and new .nexseq formats)
        # Old format: { pattern_name, blocks }
        # New format: { type, version, metadata: { name, description }, blocks }
        if 'metadata' in pattern_data and 'name' in pattern_data.get('metadata', {}):
            # New format - convert to normalized format
            pattern_data['pattern_name'] = pattern_data['metadata']['name']
            pattern_data['pattern_description'] = pattern_data.get('metadata', {}).get('description', '')
        
        # Validate required fields
        if not pattern_data or 'blocks' not in pattern_data:
            raise HTTPException(status_code=400, detail="Invalid pattern file: missing 'blocks' field")
        
        # Ensure pattern_name exists (fallback to filename if not present)
        if 'pattern_name' not in pattern_data:
            # Try to extract name from the filename
            base_name = os.path.splitext(file.filename)[0] if file.filename else 'Imported Sequence'
            pattern_data['pattern_name'] = base_name
        
        # Initialize match tracking
        matched_count = 0
        unmatched_count = 0
        downloadable_count = 0
        missing_categories = []
        missing_prerolls = []
        matched_blocks = []
        
        # Get all categories and prerolls for matching
        all_categories = {cat.name.lower(): cat for cat in db.query(models.Category).all()}
        all_prerolls = db.query(models.Preroll).all()
        
        # Create lookup dictionaries for prerolls
        prerolls_by_community_id = {p.community_preroll_id: p for p in all_prerolls if p.community_preroll_id}
        prerolls_by_name = {}
        for p in all_prerolls:
            # Try multiple name variations for better matching
            display_name = (p.display_name or p.filename).strip().lower()
            prerolls_by_name[display_name] = p
            # Also try filename without extension
            filename_no_ext = os.path.splitext(p.filename)[0].strip().lower()
            if filename_no_ext != display_name:
                prerolls_by_name[filename_no_ext] = p
        
        # Process each block in the pattern
        for block_data in pattern_data.get('blocks', []):
            block_type = block_data.get('type', '')
            matched_block = {
                'type': block_type,
                'id': block_data.get('id', str(uuid.uuid4()))
            }
            block_matched = False
            
            if block_type == 'random':
                # Match random block by category name (case-insensitive, trim whitespace)
                category_name = block_data.get('category_name', '').strip().lower()
                if category_name and category_name in all_categories:
                    matched_block['category_id'] = all_categories[category_name].id
                    matched_block['category_name'] = all_categories[category_name].name
                    matched_block['count'] = block_data.get('count', 1)
                    
                    # Check for available prerolls in exported data
                    if 'available_prerolls' in block_data:
                        matched_block['available_prerolls'] = block_data['available_prerolls']
                    
                    block_matched = True
                    matched_count += 1
                else:
                    # Preserve the original category name for debugging
                    unmatched_count += 1
                    original_category_name = block_data.get('category_name', 'Unknown')
                    matched_block['category_name'] = original_category_name
                    matched_block['count'] = block_data.get('count', 1)
                    matched_block['_unmatched'] = True
                    matched_block['_missing_category'] = original_category_name
                    if original_category_name not in missing_categories:
                        missing_categories.append(original_category_name)
            
            elif block_type == 'fixed':
                # Handle single preroll or array of prerolls
                preroll_refs = []
                
                # Check different field names for compatibility
                if 'prerolls' in block_data:
                    # Array format (future-proofing for multi-preroll fixed blocks)
                    preroll_refs = block_data['prerolls']
                elif 'preroll_name' in block_data or 'community_id' in block_data or 'preroll_data' in block_data:
                    # Single preroll format (current standard)
                    preroll_refs = [{
                        'name': block_data.get('preroll_name'),  # Export uses 'preroll_name'
                        'community_id': block_data.get('community_id'),
                        'preroll_data': block_data.get('preroll_data')
                    }]
                elif 'preroll_ids' in block_data:
                    # Legacy format using local database IDs - look up the prerolls
                    for preroll_id in block_data['preroll_ids']:
                        try:
                            preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
                            if preroll:
                                preroll_refs.append({
                                    'name': preroll.display_name or preroll.filename,
                                    'community_id': preroll.community_preroll_id,
                                    'local_id': preroll_id  # Keep reference for direct matching
                                })
                            else:
                                # Preroll not found in local DB - add placeholder
                                preroll_refs.append({
                                    'name': f'Unknown Preroll (ID: {preroll_id})',
                                    'local_id': preroll_id
                                })
                        except Exception as e:
                            _file_log(f"[IMPORT] Error looking up preroll ID {preroll_id}: {e}")
                            preroll_refs.append({
                                'name': f'Unknown Preroll (ID: {preroll_id})',
                                'local_id': preroll_id
                            })
                else:
                    # No preroll data to import
                    pass
                matched_preroll_ids = []
                
                for preroll_ref in preroll_refs:
                    matched_preroll = None
                    can_download = False
                    
                    # Validate community_id format first
                    # Community IDs can be URL paths (e.g., "/Holidays/Christmas/file.mp4")
                    community_id = preroll_ref.get('community_id')
                    is_valid_community_id = False
                    if community_id:
                        community_id_str = str(community_id)
                        # Only reject obviously invalid patterns (starts with underscore from old mangled IDs, or Windows paths)
                        if community_id_str.startswith('_') or '\\' in community_id_str:
                            _file_log(f"[IMPORT] Rejecting invalid community_id (mangled ID): {community_id_str}")
                        else:
                            is_valid_community_id = True
                    
                    # Try matching by local_id first (for imports on the same system)
                    local_id = preroll_ref.get('local_id')
                    if local_id:
                        local_preroll = db.query(models.Preroll).filter(models.Preroll.id == local_id).first()
                        if local_preroll:
                            matched_preroll = local_preroll
                    
                    # Try matching by community_id (most reliable for cross-system imports)
                    if not matched_preroll and is_valid_community_id and community_id in prerolls_by_community_id:
                        matched_preroll = prerolls_by_community_id[community_id]
                    
                    # Fall back to name matching (try multiple variations)
                    if not matched_preroll and preroll_ref.get('name'):
                        name_lower = preroll_ref['name'].strip().lower()
                        # Skip placeholder names
                        if not name_lower.startswith('unknown preroll'):
                            if name_lower in prerolls_by_name:
                                matched_preroll = prerolls_by_name[name_lower]
                            else:
                                # Try without file extension
                                name_no_ext = os.path.splitext(name_lower)[0]
                                if name_no_ext in prerolls_by_name:
                                    matched_preroll = prerolls_by_name[name_no_ext]
                    
                    # If still not matched, check if we can download from community (only if valid community_id)
                    if not matched_preroll and is_valid_community_id:
                        can_download = True
                        # downloadable_count will be incremented below when added to missing_prerolls
                        
                        # If auto_download is enabled, attempt to download it
                        if auto_download:
                            try:
                                _file_log(f"Auto-download enabled for community ID: {preroll_ref['community_id']}")
                                
                                # Determine the category_id to use
                                category_id = None
                                category_names = preroll_ref.get('category_names', [])
                                if category_names and len(category_names) > 0:
                                    # Try to find the category by name
                                    category = db.query(models.Category).filter(models.Category.name == category_names[0]).first()
                                    if category:
                                        category_id = category.id
                                
                                # Create the download request object
                                download_request = CommunityPrerollDownloadRequest(
                                    preroll_id=preroll_ref['community_id'],
                                    title=preroll_ref.get('name', 'Unknown'),
                                    category_id=category_id,
                                    add_to_category=True if category_id else False
                                )
                                
                                # Call the download function with the request and db session
                                download_result = download_community_preroll(download_request, db)
                                
                                # Refresh the matched_preroll after download
                                matched_preroll = db.query(models.Preroll).filter(
                                    models.Preroll.community_preroll_id == preroll_ref['community_id']
                                ).first()
                                if matched_preroll:
                                    _file_log(f"Successfully downloaded preroll: {matched_preroll.name} (ID {matched_preroll.id})")
                                else:
                                    _file_log(f"Download completed but preroll not found in database")
                            except Exception as e:
                                _file_log(f"Failed to auto-download community preroll: {e}")
                    
                    if matched_preroll:
                        matched_preroll_ids.append(matched_preroll.id)
                        # Log successful match
                        _file_log(f"Matched preroll: {preroll_ref.get('name')} -> ID {matched_preroll.id} " +
                                 f"(community_id: {matched_preroll.community_preroll_id})")
                    elif can_download:
                        # Track as downloadable missing preroll with actionable info
                        # Only include if community_id is valid (already validated above)
                        missing_preroll = {
                            'name': preroll_ref.get('name', 'Unknown'),
                            'community_id': community_id,  # Use validated community_id variable
                            'downloadable': True,
                            'download_url': f'https://prerolls.video/api/prerolls/{community_id}',
                            'status': 'needs_download',
                            'category': preroll_ref.get('preroll_data', {}).get('category_name') if preroll_ref.get('preroll_data') else None,
                            'category_names': preroll_ref.get('category_names'),  # Categories from export
                            'data': preroll_ref.get('preroll_data')
                        }
                        if missing_preroll not in missing_prerolls:
                            missing_prerolls.append(missing_preroll)
                            downloadable_count += 1  # Increment counter for downloadable prerolls
                        _file_log(f"Preroll needs download: {preroll_ref.get('name')} (community_id: {community_id})")
                    else:
                        # Track as truly missing preroll (no community ID or download option)
                        missing_preroll = {
                            'name': preroll_ref.get('name', 'Unknown'),
                            'community_id': preroll_ref.get('community_id'),
                            'downloadable': False,
                            'status': 'unavailable',
                            'reason': 'No community ID available' if not preroll_ref.get('community_id') else 'Not found in community library',
                            'category': preroll_ref.get('preroll_data', {}).get('category_name') if preroll_ref.get('preroll_data') else None,
                            'data': preroll_ref.get('preroll_data')
                        }
                        if missing_preroll not in missing_prerolls:
                            missing_prerolls.append(missing_preroll)
                        _file_log(f"Preroll unavailable: {preroll_ref.get('name')} - {missing_preroll['reason']}")
                
                if matched_preroll_ids:
                    matched_block['preroll_ids'] = matched_preroll_ids
                    block_matched = True
                    matched_count += 1
                else:
                    # Preserve preroll names for debugging even if not matched
                    unmatched_count += 1
                    matched_block['_unmatched'] = True
                    matched_block['_missing_prerolls'] = [ref.get('name', 'Unknown') for ref in preroll_refs]
                    if preroll_refs and len(preroll_refs) > 0:
                        matched_block['_community_ids'] = [ref.get('community_id') for ref in preroll_refs if ref.get('community_id')]
            
            # Add block to result if it has any matches (or if it's a valid type)
            if block_matched or block_type in ['random', 'fixed']:
                matched_blocks.append(matched_block)
        
        # Prepare detailed response with match statistics and actionable items
        response_data = {
            'pattern_name': pattern_data.get('pattern_name', 'Imported Pattern') if pattern_data else 'Bundle Preview',
            'pattern_description': pattern_data.get('pattern_description', '') if pattern_data else '',
            'created_by': pattern_data.get('created_by', 'Unknown') if pattern_data else 'Unknown',
            'export_mode': pattern_data.get('export_mode', 'unknown') if pattern_data else 'bundle',
            'exported_at': pattern_data.get('exported_at') if pattern_data else None,
            'nexroll_version': pattern_data.get('nexroll_version') if pattern_data else None,
            'blocks': matched_blocks,
            'sequence_json': pattern_data,
            'match_results': {
                'matched': matched_count,
                'unmatched': unmatched_count,
                'downloadable': downloadable_count,
                'total_blocks': len(pattern_data.get('blocks', [])) if pattern_data else 0,
                'missing_categories': missing_categories,
                'missing_prerolls': missing_prerolls,
                'auto_download_enabled': auto_download,
                # Detailed breakdown for UI
                'status_summary': {
                    'fully_matched': matched_count,
                    'partially_matched': 0,  # TODO: track partial matches
                    'needs_download': downloadable_count,
                    'completely_missing': unmatched_count - downloadable_count
                }
            },
            'import_results': {
                'bundle_mode': bundle_mode,
                'imported_prerolls': imported_prerolls,
                'imported_categories': imported_categories,
                'prerolls_imported_count': len(imported_prerolls),
                'categories_imported_count': len(imported_categories)
            }
        }
        
        # Add bundle_preview if available (for ZIP file preview mode)
        if bundle_preview:
            response_data['bundle_preview'] = bundle_preview
        
        log_msg = f"Pattern import: {pattern_data.get('pattern_name', 'Bundle') if pattern_data else 'Bundle Preview'}"
        if pattern_data:
            log_msg += f" - {matched_count} matched, {unmatched_count} unmatched, {downloadable_count} downloadable"
        if bundle_mode:
            if bundle_preview:
                log_msg += f" (preview mode: {len(bundle_preview.get('categories', []))} categories, {len(bundle_preview.get('fixed', []))} fixed)"
            else:
                log_msg += f", {len(imported_prerolls)} prerolls imported, {len(imported_categories)} new categories"
        _file_log(log_msg)
        
        return response_data
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format in pattern file")
    except Exception as e:
        _file_log(f"Failed to import sequence pattern: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

class BundleConfirmRequest(BaseModel):
    """Request body for confirming a bundle import after preview"""
    sequences: List[dict]  # Array of sequences with their matched blocks

@app.post("/sequences/import-bundle-confirm")
async def confirm_bundle_import(
    request: BundleConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Confirm and save sequences from a .nexbundle after preview/matching.
    
    This endpoint is called after the user has reviewed the bundle preview,
    optionally downloaded missing prerolls, and is ready to import.
    """
    try:
        imported_sequences = []
        
        for seq_data in request.sequences:
            seq_name = seq_data.get('name', 'Imported Sequence')
            seq_description = seq_data.get('description', '')
            # Use the matched blocks (which have resolved preroll_ids)
            seq_blocks = seq_data.get('blocks', [])
            
            # Check if sequence with same name already exists
            existing = db.query(models.SavedSequence).filter(models.SavedSequence.name == seq_name).first()
            if existing:
                counter = 1
                new_name = f"{seq_name} ({counter})"
                while db.query(models.SavedSequence).filter(models.SavedSequence.name == new_name).first():
                    counter += 1
                    new_name = f"{seq_name} ({counter})"
                seq_name = new_name
            
            # Clean blocks - remove internal matching metadata
            cleaned_blocks = []
            for block in seq_blocks:
                cleaned_block = {k: v for k, v in block.items() if not k.startswith('_')}
                cleaned_blocks.append(cleaned_block)
            
            # Create new sequence with matched/cleaned blocks
            new_sequence = models.SavedSequence(
                name=seq_name,
                description=seq_description,
                blocks=json.dumps(cleaned_blocks)
            )
            db.add(new_sequence)
            imported_sequences.append({
                'name': seq_name,
                'blocks_count': len(cleaned_blocks)
            })
        
        db.commit()
        
        _file_log(f"[BUNDLE IMPORT] Confirmed import of {len(imported_sequences)} sequences")
        
        return {
            'success': True,
            'bundle_import': True,
            'imported_count': len(imported_sequences),
            'sequences': imported_sequences,
            'message': f"Successfully imported {len(imported_sequences)} sequences from bundle"
        }
        
    except Exception as e:
        db.rollback()
        _file_log(f"Failed to confirm bundle import: {e}")
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

def _find_community_id_by_name(preroll_name: str) -> Optional[str]:
    """
    Try to find a community preroll ID by matching the preroll name against the community index.
    This is useful when the stored community_preroll_id is mangled or missing.
    
    Returns the community ID if a match is found, or None otherwise.
    """
    import re
    
    if not preroll_name:
        return None
    
    try:
        if not PREROLLS_INDEX_PATH.exists():
            return None
        
        with open(PREROLLS_INDEX_PATH, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        community_prerolls = index_data.get('prerolls', [])
        
        if not community_prerolls:
            return None
        
        def normalize(s):
            """Normalize a string for comparison"""
            s = s.lower()
            # Remove extension
            s = re.sub(r'\.(mp4|mkv|mov|avi|m4v|webm)$', '', s)
            # Replace underscores and dashes with spaces
            s = s.replace('_', ' ').replace('-', ' ')
            # Remove non-alphanumeric except spaces
            s = re.sub(r'[^a-z0-9\s]', '', s)
            # Collapse multiple spaces
            s = re.sub(r'\s+', ' ', s).strip()
            return s
        
        name_normalized = normalize(preroll_name)
        
        # Try exact match first
        for cp in community_prerolls:
            cp_title = cp.get('title', '')
            if normalize(cp_title) == name_normalized:
                _file_log(f"[FIND_ID_BY_NAME] Exact match: '{preroll_name}' -> '{cp.get('id')}'")
                return cp.get('id')
        
        # Try substring match
        for cp in community_prerolls:
            cp_title = cp.get('title', '')
            cp_norm = normalize(cp_title)
            if name_normalized in cp_norm or cp_norm in name_normalized:
                _file_log(f"[FIND_ID_BY_NAME] Substring match: '{preroll_name}' -> '{cp.get('id')}'")
                return cp.get('id')
        
        # Try word overlap match
        name_words = set(name_normalized.split())
        best_match = None
        best_score = 0
        
        for cp in community_prerolls:
            cp_title = cp.get('title', '')
            cp_norm = normalize(cp_title)
            cp_words = set(cp_norm.split())
            
            if name_words and cp_words:
                common = name_words & cp_words
                if len(common) >= 2:
                    score = len(common) / max(len(name_words), len(cp_words))
                    if score > best_score:
                        best_score = score
                        best_match = cp.get('id')
        
        if best_match and best_score >= 0.5:
            _file_log(f"[FIND_ID_BY_NAME] Word match ({int(best_score*100)}%): '{preroll_name}' -> '{best_match}'")
            return best_match
        
        _file_log(f"[FIND_ID_BY_NAME] No match found for '{preroll_name}'")
        return None
        
    except Exception as e:
        _file_log(f"[FIND_ID_BY_NAME] Error: {e}")
        return None

def _unmangle_community_id(mangled_id: str) -> Optional[str]:
    """
    Attempt to convert a mangled community preroll ID back to proper URL path format.
    Also tries to validate/find the correct ID by looking up the community index.
    
    Old versions stored IDs like "_Holidays_Christmas__Plex_file%20name_mp4"
    which should be converted back to "/Holidays/Christmas/_Plex/file name.mp4"
    
    Returns the unmangled ID if successful, or None if the format is unrecognizable.
    """
    import urllib.parse
    
    if not mangled_id:
        return None
    
    # Already in correct format (starts with /)
    if mangled_id.startswith('/'):
        return mangled_id
    
    # Check if this looks like a mangled ID (starts with underscore, has encoded chars)
    if not mangled_id.startswith('_'):
        return None
    
    # First try to find a match in the community index by comparing normalized versions
    try:
        if PREROLLS_INDEX_PATH.exists():
            with open(PREROLLS_INDEX_PATH, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            community_prerolls = index_data.get('prerolls', [])
            
            # URL decode the mangled ID for comparison
            decoded_mangled = urllib.parse.unquote(mangled_id)
            
            # Try to match by comparing normalized versions of the ID
            for cp in community_prerolls:
                proper_id = cp.get('id', '')
                if not proper_id:
                    continue
                
                # Create a mangled version of the proper ID for comparison
                # Replace / with _ and URL encode
                test_mangled = proper_id.replace('/', '_')
                test_decoded = urllib.parse.unquote(test_mangled)
                
                # Compare decoded versions
                if decoded_mangled.lower() == test_decoded.lower():
                    _file_log(f"[UNMANGLE] Found exact match in index: '{mangled_id[:40]}...' -> '{proper_id}'")
                    return proper_id
                
                # Also try comparing with URL-encoded mangled version
                test_encoded = urllib.parse.quote(proper_id.replace('/', '_'), safe='')
                if mangled_id == test_encoded:
                    _file_log(f"[UNMANGLE] Found encoded match in index: '{mangled_id[:40]}...' -> '{proper_id}'")
                    return proper_id
                    
            _file_log(f"[UNMANGLE] No exact match in index, trying heuristic unmangle")
    except Exception as e:
        _file_log(f"[UNMANGLE] Error checking community index: {e}")
    
    # Fall back to heuristic unmangling
    try:
        # URL decode first
        decoded = urllib.parse.unquote(mangled_id)
        
        # The mangling replaced / with _ but we need to be careful
        # because underscores can be legitimate parts of filenames.
        # Common pattern: _Category_Subcategory_Creator_filename_ext
        # Should become: /Category/Subcategory/Creator/filename.ext
        
        # Strategy: Convert first underscore to /, then use heuristics
        # for subsequent underscores
        if decoded.startswith('_'):
            decoded = '/' + decoded[1:]
        
        # Split by underscore
        parts = decoded.split('_')
        
        # If the last part looks like an extension (mp4, mkv, etc), 
        # join it with a dot to the previous part
        if len(parts) >= 2:
            last = parts[-1].lower()
            if last in ['mp4', 'mkv', 'mov', 'avi', 'm4v', 'webm']:
                # Join extension with dot
                parts[-2] = parts[-2] + '.' + parts[-1]
                parts = parts[:-1]
        
        # Now we need to figure out which underscores were slashes
        # Typical structure: /Category/Subcategory/Creator/filename.ext
        # This is tricky because we don't know how many levels there are
        
        # Simple heuristic: The first 2-3 parts are likely path components,
        # everything after might be part of the filename
        # Let's use the community library structure as guidance
        
        # Count how many parts we have
        if len(parts) <= 4:
            # Short path - all underscores were likely slashes
            result = '/'.join(parts)
        else:
            # Longer path - first 3 parts are likely path, rest is filename
            # Try to find where the filename starts by looking for common creator names
            # or fall back to using the first 3 parts as path
            path_parts = parts[:3]
            filename_parts = parts[3:]
            result = '/'.join(path_parts) + '/' + ' '.join(filename_parts)
        
        # Ensure it starts with /
        if not result.startswith('/'):
            result = '/' + result
        
        _file_log(f"[UNMANGLE] Heuristic result: '{mangled_id[:50]}...' -> '{result}'")
        return result
        
    except Exception as e:
        _file_log(f"[UNMANGLE] Failed to unmangle '{mangled_id}': {e}")
        return None


@app.post("/sequences/{sequence_id}/export")
def export_sequence_pattern(
    sequence_id: int, 
    export_mode: str = Query("pattern_only", regex="^(pattern_only|with_community_ids|with_preroll_data|full_bundle)$"),
    db: Session = Depends(get_db)
):
    """
    Export a saved sequence as a .nexseq pattern file with various levels of detail.
    
    Export modes:
    - pattern_only: Structure only (category names, no preroll details)
    - with_community_ids: Include community preroll IDs for easy re-downloading
    - with_preroll_data: Include full preroll metadata (name, tags, duration, etc.)
    - full_bundle: ZIP file with pattern + all preroll video files (large!)
    
    Returns JSON pattern or ZIP file depending on mode
    """
    try:
        # Get the sequence
        sequence = db.query(models.SavedSequence).filter(models.SavedSequence.id == sequence_id).first()
        if not sequence:
            raise HTTPException(status_code=404, detail="Sequence not found")
        
        # Parse the sequence blocks
        blocks = sequence.get_blocks()
        
        # Convert blocks to pattern format
        pattern_blocks = []
        all_preroll_ids = []  # Collect for full bundle mode
        
        for block in blocks:
            block_type = block.get('type', '')
            pattern_block = {
                'type': block_type,
                'id': block.get('id', str(uuid.uuid4()))
            }
            
            if block_type == 'random':
                # Include category information
                category_id = block.get('category_id') or block.get('categoryId')
                if category_id:
                    category = db.query(models.Category).filter(models.Category.id == category_id).first()
                    if category:
                        pattern_block['category_name'] = category.name
                        
                        # For preroll_data mode, include category's prerolls metadata
                        if export_mode in ['with_preroll_data', 'full_bundle']:
                            category_prerolls = db.query(models.Preroll).filter(
                                models.Preroll.category_id == category_id
                            ).all()
                            pattern_block['available_prerolls'] = [
                                {
                                    'name': p.display_name or p.filename,
                                    'community_id': p.community_preroll_id,
                                    'tags': json.loads(p.tags) if p.tags else [],
                                    'duration': p.duration,
                                    'file_size': p.file_size
                                } for p in category_prerolls
                            ]
                            all_preroll_ids.extend([p.id for p in category_prerolls])
                            
                pattern_block['count'] = block.get('count', 1)
            
            elif block_type == 'fixed':
                # Include preroll information
                preroll_id = block.get('preroll_id') or block.get('prerollId')
                preroll_ids = block.get('preroll_ids') or block.get('prerollIds')
                
                # Handle both single preroll_id and array preroll_ids
                if not preroll_id and preroll_ids and len(preroll_ids) > 0:
                    preroll_id = preroll_ids[0]  # Use first preroll for now
                
                if preroll_id:
                    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
                    if preroll:
                        # Always include preroll name for matching
                        preroll_name = preroll.display_name or preroll.filename
                        pattern_block['preroll_name'] = preroll_name
                        
                        # Include community ID for all modes (helps with matching even in pattern_only)
                        # Community IDs can be URL paths (e.g., "/Holidays/Christmas/file.mp4")
                        _file_log(f"[EXPORT] Checking preroll '{preroll_name}' - community_preroll_id: '{getattr(preroll, 'community_preroll_id', 'ATTRIBUTE_MISSING')}'")
                        
                        resolved_community_id = None
                        
                        if preroll.community_preroll_id:
                            community_id = str(preroll.community_preroll_id)
                            # Check if this is a mangled ID - prioritize name lookup since heuristic unmangling is unreliable
                            if community_id.startswith('_') or '\\' in community_id:
                                _file_log(f"[EXPORT] Detected mangled community_preroll_id: {community_id}")
                                # First try name lookup - more reliable than heuristic unmangling
                                resolved_community_id = _find_community_id_by_name(preroll_name)
                                if resolved_community_id:
                                    _file_log(f"[EXPORT] Found correct ID by name lookup: {resolved_community_id}")
                                else:
                                    # Only try unmangle as last resort
                                    unmangled = _unmangle_community_id(community_id)
                                    if unmangled:
                                        resolved_community_id = unmangled
                                        _file_log(f"[EXPORT] Using heuristically unmangled ID (may be incorrect): {unmangled}")
                                    else:
                                        _file_log(f"[EXPORT] Could not resolve mangled ID")
                            else:
                                resolved_community_id = community_id
                        else:
                            # No community_preroll_id stored - try to find by name
                            _file_log(f"[EXPORT] No community_preroll_id - trying name lookup for '{preroll_name}'")
                            resolved_community_id = _find_community_id_by_name(preroll_name)
                        
                        if resolved_community_id:
                            pattern_block['community_id'] = resolved_community_id
                            _file_log(f"[EXPORT] Including community_id in export: {resolved_community_id}")
                        else:
                            _file_log(f"[EXPORT] No community_id found - preroll will not be re-downloadable after import")
                        
                        # Include category names so imports can match/download into the same categories
                        if preroll.categories:
                            category_names = [cat.name for cat in preroll.categories]
                            if category_names:
                                pattern_block['category_names'] = category_names
                                _file_log(f"[EXPORT] Including categories for '{preroll.display_name or preroll.filename}': {category_names}")
                        
                        # Include full metadata only for detailed modes
                        if export_mode in ['with_preroll_data', 'full_bundle']:
                            pattern_block['preroll_data'] = {
                                'name': preroll.display_name or preroll.filename,
                                'community_id': preroll.community_preroll_id,
                                'tags': json.loads(preroll.tags) if preroll.tags else [],
                                'duration': preroll.duration,
                                'file_size': preroll.file_size,
                                'description': preroll.description,
                                'category_name': preroll.category.name if preroll.category else None
                            }
                        
                        all_preroll_ids.append(preroll.id)
            
            pattern_blocks.append(pattern_block)
        
        # Create pattern data
        pattern_data = {
            'pattern_name': sequence.name,
            'pattern_description': sequence.description,
            'created_by': 'NeXroll',
            'export_mode': export_mode,
            'nexroll_version': app_version,
            'exported_at': datetime.datetime.utcnow().isoformat() + 'Z',
            'blocks': pattern_blocks
        }
        
        # For full_bundle mode, create a ZIP with pattern + video files organized by category
        if export_mode == 'full_bundle':
            try:
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Add pattern JSON
                    zip_file.writestr(
                        f"{sequence.name.replace(' ', '_')}.nexseq",
                        json.dumps(pattern_data, indent=2)
                    )
                    
                    # Track what we're adding to avoid duplicates
                    added_files = set()
                    categories_exported = {}
                    fixed_prerolls_exported = []
                    
                    # Process blocks to organize files by type
                    for block in blocks:
                        block_type = block.get('type', '')
                        
                        if block_type == 'random':
                            # For random blocks, export entire category folder
                            category_id = block.get('category_id') or block.get('categoryId')
                            if category_id and category_id not in categories_exported:
                                category = db.query(models.Category).filter(models.Category.id == category_id).first()
                                if category:
                                    category_prerolls = db.query(models.Preroll).filter(
                                        models.Preroll.category_id == category_id
                                    ).all()
                                    
                                    # Create category folder in ZIP
                                    category_folder = "".join(c for c in category.name if c.isalnum() or c in (' ', '_', '-'))
                                    
                                    for preroll in category_prerolls:
                                        if preroll.path and os.path.exists(preroll.path):
                                            file_name = preroll.display_name or preroll.filename
                                            # Ensure filename has extension
                                            if not any(file_name.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.mov', '.avi', '.m4v', '.webm']):
                                                # Get extension from original path
                                                _, ext = os.path.splitext(preroll.path)
                                                file_name = file_name + ext
                                            # Sanitize filename
                                            file_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '.', '_', '-'))
                                            zip_path = f"categories/{category_folder}/{file_name}"
                                            
                                            if zip_path not in added_files:
                                                zip_file.write(preroll.path, zip_path)
                                                added_files.add(zip_path)
                                    
                                    categories_exported[category_id] = {
                                        'name': category.name,
                                        'preroll_count': len(category_prerolls)
                                    }
                        
                        elif block_type == 'fixed':
                            # For fixed blocks, export individual preroll to "fixed" folder
                            # Handle both single preroll_id and array preroll_ids formats
                            preroll_id = block.get('preroll_id') or block.get('prerollId')
                            preroll_ids = block.get('preroll_ids') or block.get('prerollIds') or []
                            
                            # If no single preroll_id but we have an array, use the first one
                            if not preroll_id and preroll_ids:
                                preroll_id = preroll_ids[0] if len(preroll_ids) > 0 else None
                            
                            _file_log(f"[FULL_BUNDLE] Fixed block - preroll_id: {preroll_id}, preroll_ids: {preroll_ids}")
                            
                            if preroll_id:
                                preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
                                _file_log(f"[FULL_BUNDLE] Found preroll: {preroll.display_name if preroll else 'None'}, path: {preroll.path if preroll else 'N/A'}, exists: {os.path.exists(preroll.path) if preroll and preroll.path else False}")
                                if preroll and preroll.path and os.path.exists(preroll.path):
                                    file_name = preroll.display_name or preroll.filename
                                    # Ensure filename has extension
                                    if not any(file_name.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.mov', '.avi', '.m4v', '.webm']):
                                        # Get extension from original path
                                        _, ext = os.path.splitext(preroll.path)
                                        file_name = file_name + ext
                                    # Sanitize filename
                                    file_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '.', '_', '-'))
                                    zip_path = f"fixed/{file_name}"
                                    
                                    if zip_path not in added_files:
                                        _file_log(f"[FULL_BUNDLE] Adding to ZIP: {preroll.path} -> {zip_path}")
                                        zip_file.write(preroll.path, zip_path)
                                        added_files.add(zip_path)
                                        fixed_prerolls_exported.append({
                                            'name': preroll.display_name or preroll.filename,
                                            'category': preroll.category.name if preroll.category else 'Uncategorized'
                                        })
                                else:
                                    _file_log(f"[FULL_BUNDLE] Skipping preroll - not found or path doesn't exist")
                    
                    _file_log(f"[FULL_BUNDLE] Export complete - {len(added_files)} files added to ZIP")
                    
                    # Add a manifest file with export details
                    manifest = {
                        'sequence_name': sequence.name,
                        'exported_at': datetime.datetime.utcnow().isoformat() + 'Z',
                        'nexroll_version': app_version,
                        'total_files': len(added_files),
                        'categories_exported': categories_exported,
                        'fixed_prerolls_exported': fixed_prerolls_exported,
                        'instructions': {
                            'import': 'Use NeXroll\'s Import feature to restore this sequence',
                            'structure': {
                                'categories/': 'Entire category folders for random blocks',
                                'fixed/': 'Individual prerolls for fixed blocks',
                                '*.nexseq': 'Sequence pattern file'
                            }
                        }
                    }
                    zip_file.writestr('MANIFEST.json', json.dumps(manifest, indent=2))
                
                zip_buffer.seek(0)
                _file_log(f"Exported full bundle: {sequence.name} - {len(categories_exported)} categories, {len(fixed_prerolls_exported)} fixed prerolls, {len(added_files)} total files")
                
                return StreamingResponse(
                    zip_buffer,
                    media_type="application/zip",
                    headers={
                        "Content-Disposition": f"attachment; filename={sequence.name.replace(' ', '_')}_bundle.zip"
                    }
                )
            except Exception as e:
                _file_log(f"Failed to create full bundle: {e}")
                raise HTTPException(status_code=500, detail=f"Bundle creation failed: {str(e)}")
        
        _file_log(f"Exported sequence pattern ({export_mode}): {sequence.name} with {len(pattern_blocks)} blocks")
        return pattern_data
        
    except Exception as e:
        _file_log(f"Failed to export sequence pattern: {e}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")

# Holiday presets
@app.post("/holiday-presets/init")
def initialize_holiday_presets(db: Session = Depends(get_db)):
    categories_created = 0
    presets_created = 0
    
    # Create default category for holidays if it doesn't exist
    holiday_category = db.query(models.Category).filter(models.Category.name == "Holidays").first()
    if not holiday_category:
        holiday_category = models.Category(name="Holidays", description="Holiday-themed prerolls")
        db.add(holiday_category)
        db.commit()
        db.refresh(holiday_category)
        categories_created += 1

    # Add common holiday presets with month-long date ranges
    holidays = [
        {
            "name": "Christmas",
            "description": "Christmas season (December 1-31)",
            "start_month": 12, "start_day": 1,
            "end_month": 12, "end_day": 31
        },
        {
            "name": "New Year",
            "description": "New Year season (January 1-31)",
            "start_month": 1, "start_day": 1,
            "end_month": 1, "end_day": 31
        },
        {
            "name": "Halloween",
            "description": "Halloween season (October 1-31)",
            "start_month": 10, "start_day": 1,
            "end_month": 10, "end_day": 31
        },
        {
            "name": "Thanksgiving",
            "description": "Thanksgiving season (November 1-30)",
            "start_month": 11, "start_day": 1,
            "end_month": 11, "end_day": 30
        },
        {
            "name": "Valentine's Day",
            "description": "Valentine's season (February 1-28/29)",
            "start_month": 2, "start_day": 1,
            "end_month": 2, "end_day": 29  # Will handle leap year in scheduler
        },
        {
            "name": "Easter",
            "description": "Easter season (April 1-30)",
            "start_month": 4, "start_day": 1,
            "end_month": 4, "end_day": 30
        }
    ]

    for holiday in holidays:
        # Ensure a per-holiday category exists
        cat = db.query(models.Category).filter(models.Category.name == holiday["name"]).first()
        if not cat:
            cat = models.Category(name=holiday["name"], description=holiday["description"])
            db.add(cat)
            db.commit()
            db.refresh(cat)
            categories_created += 1

        # Upsert holiday preset bound to that category
        existing = db.query(models.HolidayPreset).filter(models.HolidayPreset.name == holiday["name"]).first()
        if not existing:
            presets_created += 1
            preset = models.HolidayPreset(
                name=holiday["name"],
                description=holiday["description"],
                # Legacy single-day fields (keep for compatibility)
                month=holiday["start_month"],
                day=holiday["start_day"],
                # Range fields
                start_month=holiday["start_month"],
                start_day=holiday["start_day"],
                end_month=holiday["end_month"],
                end_day=holiday["end_day"],
                category_id=cat.id,
            )
            db.add(preset)
        else:
            # Keep preset synchronized and attach to per-holiday category
            existing.description = holiday["description"]
            existing.month = holiday["start_month"]
            existing.day = holiday["start_day"]
            existing.start_month = holiday["start_month"]
            existing.start_day = holiday["start_day"]
            existing.end_month = holiday["end_month"]
            existing.end_day = holiday["end_day"]
            existing.category_id = cat.id

    db.commit()
    return {
        "message": "Holiday presets initialized",
        "categories_created": categories_created,
        "presets_created": presets_created,
        "total_categories": len(holidays) + 1  # Including the "Holidays" category
    }

@app.get("/holiday-presets")
def get_holiday_presets(db: Session = Depends(get_db)):
    presets = db.query(models.HolidayPreset).all()
    return presets

# Holiday API integration endpoints
@app.get("/holiday-api/countries")
def get_holiday_countries():
    """Get list of countries supported by holiday API"""
    try:
        from backend.holiday_api import HolidayAPI
        countries = HolidayAPI.get_available_countries()
        return {
            "countries": countries,
            "total": len(countries),
            "api_available": HolidayAPI.is_api_available()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch countries: {str(e)}")

@app.get("/holiday-api/holidays/{country_code}/{year}")
def get_holidays_for_country(country_code: str, year: int):
    """
    Get all holidays for a specific country and year
    Example: /holiday-api/holidays/US/2024
    """
    try:
        from backend.holiday_api import HolidayAPI
        holidays = HolidayAPI.get_holidays(country_code.upper(), year)
        multi_day = HolidayAPI.get_multi_day_holidays(country_code.upper(), year)
        
        return {
            "country_code": country_code.upper(),
            "year": year,
            "holidays": holidays,
            "multi_day_holidays": multi_day,
            "total": len(holidays),
            "api_available": HolidayAPI.is_api_available()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch holidays: {str(e)}")

@app.get("/holiday-api/search")
def search_holiday(name: str, country_code: str = "US", year: int = None):
    """
    Search for a specific holiday by name
    Example: /holiday-api/search?name=Christmas&country_code=US&year=2024
    """
    try:
        from backend.holiday_api import HolidayAPI
        from datetime import datetime
        
        if year is None:
            year = datetime.now().year
        
        holiday = HolidayAPI.search_holiday_by_name(name, country_code.upper(), year)
        
        if holiday:
            return {
                "found": True,
                "holiday": holiday,
                "country_code": country_code.upper(),
                "year": year
            }
        else:
            return {
                "found": False,
                "message": f"Holiday '{name}' not found for {country_code} in {year}",
                "country_code": country_code.upper(),
                "year": year
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to search holiday: {str(e)}")

@app.get("/holiday-api/next/{holiday_name}")
def get_next_holiday_occurrence(holiday_name: str, country_code: str = "US"):
    """
    Get the next occurrence of a holiday
    Example: /holiday-api/next/Christmas?country_code=CA
    """
    try:
        from backend.holiday_api import HolidayAPI
        
        result = HolidayAPI.get_next_occurrence(holiday_name, country_code.upper())
        
        if result:
            holiday_date, description = result
            return {
                "found": True,
                "name": description,
                "date": holiday_date.strftime("%Y-%m-%d"),
                "month": holiday_date.month,
                "day": holiday_date.day,
                "year": holiday_date.year,
                "country_code": country_code.upper()
            }
        else:
            return {
                "found": False,
                "message": f"Could not find next occurrence of '{holiday_name}'",
                "country_code": country_code.upper()
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to find next occurrence: {str(e)}")

@app.post("/holiday-api/create-schedule")
def create_schedule_from_holiday(
    request: HolidayScheduleRequest,
    db: Session = Depends(get_db)
):
    """
    Create a recurring schedule from a holiday using the API
    Will automatically fetch the correct dates for the holiday
    """
    try:
        from backend.holiday_api import HolidayAPI
        from datetime import datetime
        
        # Extract values from request
        holiday_name = request.holiday_name
        country_code = request.country_code
        category_id = request.category_id
        
        # Generate years list based on multi_year setting
        if request.multi_year and request.year_count:
            current_year = datetime.now().year
            years = [current_year + i for i in range(request.year_count)]
        else:
            current_year = datetime.now().year
            years = [current_year]
        
        # Verify category exists
        category = db.query(models.Category).filter(models.Category.id == category_id).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Category {category_id} not found")
        
        # Get holiday dates for all requested years
        suggestions = HolidayAPI.suggest_schedule_dates(holiday_name, country_code.upper(), years)
        
        if not suggestions:
            raise HTTPException(
                status_code=404,
                detail=f"Holiday '{holiday_name}' not found for {country_code} in years {years}"
            )
        
        # Use the first year's date to create the schedule
        first_occurrence = suggestions[0]
        
        # Check for multi-day holiday
        multi_day = HolidayAPI.get_multi_day_holidays(country_code.upper(), first_occurrence["year"])
        matching_multi = next(
            (h for h in multi_day if holiday_name.lower() in h["name"].lower()),
            None
        )
        
        if matching_multi:
            # Multi-day holiday
            start_month = matching_multi["start_month"]
            start_day = matching_multi["start_day"]
            end_month = matching_multi["end_month"]
            end_day = matching_multi["end_day"]
        else:
            # Single day holiday
            start_month = first_occurrence["month"]
            start_day = first_occurrence["day"]
            end_month = start_month
            end_day = start_day
        
        # Create the schedule with proper datetime objects
        start_date_obj = datetime(2024, start_month, start_day)  # Use a reference year
        end_date_obj = datetime(2024, end_month, end_day)
        
        schedule = models.Schedule(
            name=first_occurrence["name"],
            category_id=category_id,
            type="yearly",
            is_active=True,
            start_date=start_date_obj,
            end_date=end_date_obj,
            shuffle=False,
            playlist=False
        )
        
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        
        return {
            "message": f"Schedule created for {first_occurrence['name']}",
            "schedule_id": schedule.id,
            "schedule": {
                "id": schedule.id,
                "name": schedule.name,
                "start_date": schedule.start_date,
                "end_date": schedule.end_date,
                "type": schedule.type
            },
            "holiday_dates": suggestions,
            "years_created": years
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        error_details = traceback.format_exc()
        _file_log(f"[ERROR] Error creating holiday schedule: {str(e)}\n{error_details}")
        raise HTTPException(status_code=500, detail=f"Failed to create schedule: {str(e)}")

@app.get("/holiday-api/status")
def get_holiday_api_status():
    """Check if holiday API is available and working"""
    try:
        from backend.holiday_api import HolidayAPI
        
        is_available = HolidayAPI.is_api_available()
        
        # Test with a simple query
        test_result = None
        if is_available:
            try:
                from datetime import datetime
                test_holidays = HolidayAPI.get_holidays("US", datetime.now().year)
                test_result = {
                    "test_country": "US",
                    "test_year": datetime.now().year,
                    "holidays_found": len(test_holidays)
                }
            except Exception as e:
                test_result = {"error": str(e)}
        
        return {
            "available": is_available,
            "api_available": is_available,  # Keep for backward compatibility
            "api_url": HolidayAPI.BASE_URL,
            "supported_countries": len(HolidayAPI.SUPPORTED_COUNTRIES),
            "test_result": test_result,
            "features": {
                "multi_day_holidays": True,
                "holiday_search": True,
                "next_occurrence": True,
                "auto_schedule_creation": True
            }
        }
    except Exception as e:
        return {
            "available": False,
            "api_available": False,  # Keep for backward compatibility
            "error": str(e)
        }

@app.post("/holiday-api/refresh-dates")
def refresh_holiday_dates(db: Session = Depends(get_db)):
    """
    Refresh dates for all schedules linked to holidays.
    This updates variable-date holidays (Thanksgiving, Easter, etc.) to their correct dates
    for the current/upcoming year.
    """
    try:
        from backend.holiday_api import HolidayAPI
        from datetime import datetime
        
        current_year = datetime.now().year
        updated_count = 0
        errors = []
        updated_schedules = []
        
        # Find all schedules with holiday_name set
        holiday_schedules = db.query(models.Schedule).filter(
            models.Schedule.holiday_name.isnot(None),
            models.Schedule.holiday_country.isnot(None)
        ).all()
        
        for schedule in holiday_schedules:
            try:
                # Get the holiday for current year
                holidays = HolidayAPI.get_holidays(schedule.holiday_country, current_year)
                
                # Find matching holiday
                matching = None
                for h in holidays:
                    if h.get("name", "").lower() == schedule.holiday_name.lower():
                        matching = h
                        break
                    # Also check localName
                    if h.get("localName", "").lower() == schedule.holiday_name.lower():
                        matching = h
                        break
                
                if matching:
                    # Parse the date
                    new_date = datetime.strptime(matching["date"], "%Y-%m-%d")
                    old_date = schedule.start_date
                    
                    # Update if date changed or year is different
                    if old_date.year != current_year or old_date.month != new_date.month or old_date.day != new_date.day:
                        schedule.start_date = new_date
                        schedule.end_date = new_date.replace(hour=23, minute=59, second=59)
                        updated_count += 1
                        updated_schedules.append({
                            "id": schedule.id,
                            "name": schedule.name,
                            "holiday": schedule.holiday_name,
                            "old_date": old_date.strftime("%Y-%m-%d"),
                            "new_date": new_date.strftime("%Y-%m-%d")
                        })
                else:
                    errors.append({
                        "schedule_id": schedule.id,
                        "holiday": schedule.holiday_name,
                        "error": f"Holiday not found for {schedule.holiday_country} in {current_year}"
                    })
                    
            except Exception as e:
                errors.append({
                    "schedule_id": schedule.id,
                    "holiday": schedule.holiday_name,
                    "error": str(e)
                })
        
        db.commit()
        
        return {
            "success": True,
            "total_holiday_schedules": len(holiday_schedules),
            "updated_count": updated_count,
            "updated_schedules": updated_schedules,
            "errors": errors,
            "year": current_year
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to refresh holiday dates: {str(e)}")

@app.get("/holiday-api/linked-schedules")
def get_holiday_linked_schedules(db: Session = Depends(get_db)):
    """Get all schedules that are linked to holidays (have holiday_name set)"""
    try:
        schedules = db.query(models.Schedule).filter(
            models.Schedule.holiday_name.isnot(None)
        ).all()
        
        return [{
            "id": s.id,
            "name": s.name,
            "holiday_name": s.holiday_name,
            "holiday_country": s.holiday_country,
            "start_date": s.start_date.isoformat() if s.start_date else None,
            "type": s.type,
            "is_active": s.is_active
        } for s in schedules]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Community templates endpoints
@app.get("/community-templates")
def get_community_templates(db: Session = Depends(get_db), category: str = None):
    query = db.query(models.CommunityTemplate)
    if category:
        query = query.filter(models.CommunityTemplate.category == category)
    templates = query.filter(models.CommunityTemplate.is_public == True).all()
    return [{
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "author": t.author,
        "category": t.category,
        "tags": t.tags,
        "downloads": t.downloads,
        "rating": t.rating,
        "created_at": t.created_at
    } for t in templates]

@app.post("/community-templates")
def create_community_template(
    name: str,
    description: str,
    author: str,
    category: str,
    schedule_ids: str,  # JSON array of schedule IDs
    tags: str = None,
    db: Session = Depends(get_db)
):
    """Create a community template from existing schedules"""
    try:
        schedule_id_list = json.loads(schedule_ids)
        schedules = db.query(models.Schedule).filter(models.Schedule.id.in_(schedule_id_list)).all()

        if not schedules:
            raise HTTPException(status_code=404, detail="No schedules found")

        # Create template data
        template_data = {
            "schedules": [{
                "name": s.name,
                "type": s.type,
                "start_date": s.start_date.isoformat() if s.start_date else None,
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "category_id": s.category_id,
                "shuffle": s.shuffle,
                "playlist": s.playlist,
                "recurrence_pattern": s.recurrence_pattern,
                "preroll_ids": s.preroll_ids
            } for s in schedules]
        }

        template = models.CommunityTemplate(
            name=name,
            description=description,
            author=author,
            category=category,
            template_data=json.dumps(template_data),
            tags=tags or json.dumps([]),
            is_public=True
        )

        db.add(template)
        db.commit()
        db.refresh(template)

        return {"message": "Template created successfully", "id": template.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Template creation failed: {str(e)}")

@app.post("/community-templates/{template_id}/import")
def import_community_template(template_id: int, db: Session = Depends(get_db)):
    """Import a community template into the user's schedules"""
    template = db.query(models.CommunityTemplate).filter(models.CommunityTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        template_data = json.loads(template.template_data)

        # Import schedules
        imported_schedules = []
        for schedule_data in template_data.get("schedules", []):
            # Check if category exists, create if not
            category = None
            if schedule_data.get("category_id"):
                category = db.query(models.Category).filter(models.Category.id == schedule_data["category_id"]).first()

            if not category and schedule_data.get("category_id"):
                # Try to find by name if ID doesn't match
                pass  # For now, skip category linking

            new_schedule = models.Schedule(
                name=f"{schedule_data['name']} (Imported)",
                type=schedule_data["type"],
                start_date=datetime.datetime.fromisoformat(schedule_data["start_date"]) if schedule_data.get("start_date") else None,
                end_date=datetime.datetime.fromisoformat(schedule_data["end_date"]) if schedule_data.get("end_date") else None,
                category_id=schedule_data.get("category_id"),
                shuffle=schedule_data.get("shuffle", False),
                playlist=schedule_data.get("playlist", False),
                recurrence_pattern=schedule_data.get("recurrence_pattern"),
                preroll_ids=schedule_data.get("preroll_ids")
            )

            db.add(new_schedule)
            imported_schedules.append(new_schedule)

        # Increment download count
        template.downloads += 1
        db.commit()

        return {
            "message": "Template imported successfully",
            "imported_schedules": len(imported_schedules)
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")

@app.post("/community-templates/init")
def initialize_community_templates(db: Session = Depends(get_db)):
    """Initialize with some default community templates"""
    templates = [
        {
            "name": "Christmas Celebration",
            "description": "Festive holiday schedule with Christmas-themed prerolls",
            "author": "NeXroll Team",
            "category": "Holiday",
            "tags": json.dumps(["christmas", "holiday", "festive"]),
            "template_data": json.dumps({
                "schedules": [{
                    "name": "Christmas Morning",
                    "type": "holiday",
                    "start_date": "2024-12-25T08:00:00",
                    "shuffle": True,
                    "playlist": False
                }]
            })
        },
        {
            "name": "Halloween Spooky",
            "description": "Spooky Halloween schedule for trick-or-treaters",
            "author": "NeXroll Team",
            "category": "Holiday",
            "tags": json.dumps(["halloween", "spooky", "fun"]),
            "template_data": json.dumps({
                "schedules": [{
                    "name": "Halloween Night",
                    "type": "holiday",
                    "start_date": "2024-10-31T18:00:00",
                    "shuffle": True,
                    "playlist": False
                }]
            })
        },
        {
            "name": "Monthly Rotation",
            "description": "Basic monthly preroll rotation schedule",
            "author": "NeXroll Team",
            "category": "General",
            "tags": json.dumps(["monthly", "rotation", "basic"]),
            "template_data": json.dumps({
                "schedules": [{
                    "name": "Monthly Update",
                    "type": "monthly",
                    "start_date": "2024-01-01T12:00:00",
                    "shuffle": True,
                    "playlist": False
                }]
            })
        }
    ]

    for template_data in templates:
        existing = db.query(models.CommunityTemplate).filter(
            models.CommunityTemplate.name == template_data["name"]
        ).first()

        if not existing:
            template = models.CommunityTemplate(**template_data)
            db.add(template)

    db.commit()
    return {"message": "Community templates initialized"}

# Scheduler control endpoints
@app.post("/scheduler/start")
def start_scheduler():
    scheduler.start()
    return {"message": "Scheduler started"}

@app.post("/scheduler/stop")
def stop_scheduler():
    scheduler.stop()
    return {"message": "Scheduler stopped"}

@app.get("/scheduler/status")
def get_scheduler_status():
    return {
        "running": scheduler.running,
        "active_schedules": len(scheduler._get_active_schedules()) if hasattr(scheduler, '_get_active_schedules') else 0
    }

@app.get("/scheduler/active-schedule-ids")
def get_active_schedule_ids():
    """Return list of currently active schedule IDs"""
    try:
        active_schedules = scheduler._get_active_schedules() if hasattr(scheduler, '_get_active_schedules') else []
        return {"active_schedule_ids": [s.id for s in active_schedules]}
    except Exception as e:
        return {"active_schedule_ids": [], "error": str(e)}

@app.post("/scheduler/run-now")
def run_scheduler_now(db: Session = Depends(get_db)):
    """Manually trigger scheduler execution"""
    try:
        scheduler._check_and_execute_schedules()
        return {"message": "Scheduler executed successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scheduler execution failed: {str(e)}")


@app.post("/schedules/validate-cron")
def validate_cron(pattern: str):
    """
    Placeholder cron-like pattern validation for v1.1.0 scaffolding.
    Accepts 5-field patterns (minute hour day month weekday). Basic syntax-only checks.
    """
    try:
        parts = pattern.strip().split()
    except Exception:
        parts = []

    valid = False
    message = ""
    if len(parts) == 5:
        allowed = set("0123456789*/,-")
        if all(len(p) > 0 and set(p) <= allowed for p in parts):
            valid = True
            message = "Pattern looks valid (basic checks only)."
        else:
            message = "Invalid characters in one or more fields."
    else:
        message = "Pattern must have 5 fields separated by spaces."

    return {"valid": valid, "message": message, "pattern": pattern}

# Stable token workflow endpoints
@app.get("/plex/stable-token/status")
def get_stable_token_status():
    """Check if stable token is configured"""
    # Prefer secure store
    try:
        tok = secure_store.get_plex_token()
    except Exception:
        tok = None
    return {
        "has_stable_token": bool(tok),
        "config_file_exists": os.path.exists("plex_config.json"),
        "token_length": len(tok) if tok else 0,
        "provider": secure_store.provider_info()[1],
    }

@app.post("/plex/stable-token/save")
def save_stable_token(token: str):
    """Save a stable token manually"""
    connector = PlexConnector(None)
    if connector.save_stable_token(token):
        return {"message": "Stable token saved successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to save stable token")

@app.get("/plex/stable-token/config")
def get_stable_token_config():
    """Get current stable token configuration (sanitized; token never returned)."""
    try:
        tok = None
        try:
            tok = secure_store.get_plex_token()
        except Exception:
            tok = None

        cfg = {}
        try:
            if os.path.exists("plex_config.json"):
                with open("plex_config.json", "r", encoding="utf-8") as f:
                    cfg = json.load(f) or {}
        except Exception:
            cfg = {}

        # Prefer secure store length if present; otherwise fall back to legacy hints
        length = len(tok) if tok else (cfg.get("token_length") if isinstance(cfg.get("token_length"), int) else 0)

        return {
            "configured": bool(tok),
            "setup_date": cfg.get("setup_date"),
            "note": "Token stored in secure store" if tok else (cfg.get("note") or "No token configured"),
            "token_length": length,
            "provider": secure_store.provider_info()[1],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading config: {str(e)}")

@app.get("/plex/current-preroll")
def get_current_preroll(db: Session = Depends(get_db)):
    """Get the current preroll setting from Plex"""
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Plex not configured")

    connector = PlexConnector(setting.plex_url, setting.plex_token)
    current_preroll = connector.get_current_preroll()

    return {
        "current_preroll": current_preroll,
        "has_preroll": current_preroll is not None and current_preroll != ""
    }

@app.delete("/plex/stable-token")
def delete_stable_token():
    """Delete the stable token configuration"""
    try:
        if os.path.exists("plex_config.json"):
            os.remove("plex_config.json")
            return {"message": "Stable token configuration deleted"}
        else:
            return {"message": "No stable token configuration found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting config: {str(e)}")

# Path mapping management endpoints
@app.get("/settings/path-mappings")
def get_path_mappings(db: Session = Depends(get_db)):
    """
    Return the configured local->plex path prefix mappings used to translate local/UNC paths
    to Plex-acceptable paths when setting prerolls.
    """
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)

    mappings = []
    try:
        raw = getattr(setting, "path_mappings", None)
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                for m in data:
                    if isinstance(m, dict) and m.get("local") and m.get("plex"):
                        mappings.append({"local": str(m["local"]), "plex": str(m["plex"])})
    except Exception:
        mappings = []
    return {"mappings": mappings}

@app.put("/settings/path-mappings")
def put_path_mappings(payload: PathMappingsPayload, merge: bool = False, db: Session = Depends(get_db)):
    """
    Set or merge local->plex path mappings.
    - payload.mappings: list of {local, plex}
    - merge=false (default): replace existing
    - merge=true: merge with existing by 'local' key (case-insensitive on Windows)
    """
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)

    # Normalize incoming mappings (normalize ONLY local side)
    def _norm_local(p: str) -> str:
        try:
            return os.path.normpath(p)
        except Exception:
            return p

    incoming = []
    for m in payload.mappings or []:
        try:
            loc = _norm_local(str(m.local).strip())
            plex = str(m.plex).strip()
            if loc and plex:
                incoming.append({"local": loc, "plex": plex})
        except Exception:
            continue

    if merge:
        existing = []
        try:
            raw = getattr(setting, "path_mappings", None)
            if raw:
                data = json.loads(raw)
                if isinstance(data, list):
                    for m in data:
                        if isinstance(m, dict) and m.get("local") and m.get("plex"):
                            existing.append({"local": _norm_local(str(m["local"])), "plex": str(m["plex"])})
        except Exception:
            existing = []
        # Merge by local prefix key
        merged: dict[str, dict] = {}
        if sys.platform.startswith("win"):
            for m in existing:
                merged[m["local"].lower()] = m
            for m in incoming:
                merged[m["local"].lower()] = m
            out = list(merged.values())
        else:
            for m in existing:
                merged[m["local"]] = m
            for m in incoming:
                merged[m["local"]] = m
            out = list(merged.values())
    else:
        out = incoming

    try:
        setting.path_mappings = json.dumps(out)
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save path mappings: {e}")

    return {"saved": len(out), "mappings": out, "merge": merge}

@app.post("/settings/path-mappings/test")
def test_path_mappings(req: TestTranslationRequest, db: Session = Depends(get_db)):
    """
    Test-translate one or more local paths using the configured mappings.
    Returns per-path translation result and matched mapping (if any).
    """
    setting = db.query(models.Setting).first()
    if not setting:
        return {"results": []}

    mappings = []
    try:
        raw = getattr(setting, "path_mappings", None)
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
    except Exception:
        mappings = []

    def _translate(local_path: str):
        lp = os.path.normpath(local_path)
        best = None
        best_src = None
        best_len = -1
        for m in mappings:
            src = os.path.normpath(str(m.get("local")))
            if sys.platform.startswith("win"):
                if lp.lower().startswith(src.lower()) and len(src) > best_len:
                    best = m
                    best_src = src
                    best_len = len(src)
            else:
                if lp.startswith(src) and len(src) > best_len:
                    best = m
                    best_src = src
                    best_len = len(src)
        if best:
            dst_prefix = str(best.get("plex"))
            rest = lp[len(best_src):].lstrip("\\/")
            try:
                if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                    out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                elif "\\" in dst_prefix:
                    out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                else:
                    out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
            except Exception:
                out = dst_prefix + (("/" if not dst_prefix.endswith(("/", "\\")) else "") + rest)
            return {
                "input": local_path,
                "output": out,
                "matched_local_prefix": best_src,
                "mapping": best,
                "matched": True,
            }
        return {"input": local_path, "output": local_path, "matched": False}

    paths = list(req.paths or [])
    results = [_translate(p) for p in paths]
    return {"results": results}


# Folder browser endpoint for Import feature
class BrowseFolderRequest(BaseModel):
    path: str = ""  # Empty string or path to browse

@app.post("/browse-folders")
def browse_folders(req: BrowseFolderRequest):
    """
    Browse filesystem folders for the Import feature.
    Returns list of subfolders in the given path.
    If path is empty, returns available drives (Windows) or root directories.
    """
    import string
    
    path = (req.path or "").strip()
    
    try:
        # If no path provided, return drive list (Windows) or root (Unix)
        if not path:
            if sys.platform.startswith("win"):
                # List available Windows drives
                drives = []
                for letter in string.ascii_uppercase:
                    drive = f"{letter}:\\"
                    if os.path.exists(drive):
                        try:
                            # Get drive label if possible
                            drives.append({
                                "name": f"{letter}:",
                                "path": drive,
                                "type": "drive"
                            })
                        except Exception:
                            pass
                return {"path": "", "folders": drives, "parent": None}
            else:
                # Unix - return root subfolders
                folders = []
                try:
                    for item in os.listdir("/"):
                        item_path = f"/{item}"
                        if os.path.isdir(item_path):
                            folders.append({
                                "name": item,
                                "path": item_path,
                                "type": "folder"
                            })
                    folders.sort(key=lambda x: x["name"].lower())
                except Exception:
                    pass
                return {"path": "/", "folders": folders, "parent": None}
        
        # Normalize and validate path
        try:
            abs_path = os.path.abspath(path)
        except Exception:
            abs_path = path
        
        if not os.path.isdir(abs_path):
            raise HTTPException(status_code=404, detail=f"Path not found or not a directory: {path}")
        
        # Get parent path
        parent = os.path.dirname(abs_path)
        if parent == abs_path:  # Root
            parent = None
        
        # List subfolders
        folders = []
        try:
            for item in os.listdir(abs_path):
                item_path = os.path.join(abs_path, item)
                try:
                    if os.path.isdir(item_path):
                        folders.append({
                            "name": item,
                            "path": item_path,
                            "type": "folder"
                        })
                except PermissionError:
                    pass  # Skip inaccessible folders
        except PermissionError:
            raise HTTPException(status_code=403, detail=f"Permission denied accessing: {path}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error listing directory: {str(e)}")
        
        # Sort folders alphabetically
        folders.sort(key=lambda x: x["name"].lower())
        
        # Count video files in this folder for preview
        video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.webm', '.m4v', '.flv'}
        video_count = 0
        try:
            for item in os.listdir(abs_path):
                if os.path.isfile(os.path.join(abs_path, item)):
                    _, ext = os.path.splitext(item)
                    if ext.lower() in video_extensions:
                        video_count += 1
        except Exception:
            pass
        
        return {
            "path": abs_path,
            "folders": folders,
            "parent": parent,
            "video_count": video_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error browsing folders: {str(e)}")


# Preroll external directory mapping endpoint
@app.post("/prerolls/map-root")
def map_preroll_root(req: MapRootRequest, db: Session = Depends(get_db)):
    """
    Map an existing directory of preroll files (local or UNC) into NeXroll without copying/moving files.
    Creates Preroll rows with managed=False and optionally generates thumbnails.
    """
    root = (req.root_path or "").strip()
    if not root:
        raise HTTPException(status_code=422, detail="root_path is required")
    try:
        root_abs = os.path.abspath(root)
    except Exception:
        root_abs = root

    if not os.path.isdir(root_abs):
        hint = "If running in Docker, mount your NAS/host folder into the container and use the container path (e.g., /mnt/prerolls or /data/prerolls). UNC paths like \\\\NAS\\share are not visible inside Linux containers."
        raise HTTPException(status_code=404, detail=f"Root path not found or not a directory: {root_abs}. {hint}")

    # Resolve target category
    category = None
    if req.category_id:
        category = db.query(models.Category).filter(models.Category.id == int(req.category_id)).first()
        if not category:
            raise HTTPException(status_code=404, detail=f"Category id {req.category_id} not found")
    else:
        category = db.query(models.Category).filter(models.Category.name == "Default").first()
        if not category:
            category = models.Category(name="Default", description="Default category for mapped prerolls")
            db.add(category)
            db.commit()
            db.refresh(category)

    # Extensions to include
    default_exts = [".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm"]
    exts = req.extensions if isinstance(req.extensions, list) else default_exts
    try:
        exts = [(e if e.startswith(".") else f".{e}").lower() for e in exts]
    except Exception:
        exts = default_exts

    # Walk and collect files
    candidate_files: list[str] = []
    if req.recursive:
        for r, _dirs, files in os.walk(root_abs):
            for f in files:
                if os.path.splitext(f)[1].lower() in exts:
                    candidate_files.append(os.path.join(r, f))
    else:
        try:
            for f in os.listdir(root_abs):
                fp = os.path.join(root_abs, f)
                if os.path.isfile(fp) and os.path.splitext(fp)[1].lower() in exts:
                    candidate_files.append(fp)
        except Exception:
            pass

    total_found = len(candidate_files)

    # Helper: check existing by case-insensitive path on Windows OR by filename within the same category
    def _exists_in_db(abs_path: str, filename: str, category_id: int) -> bool:
        try:
            # Check by exact path
            row = db.query(models.Preroll).filter(models.Preroll.path == abs_path).first()
            if row:
                return True
            # Check by path case-insensitive on Windows
            if sys.platform.startswith("win"):
                lp = abs_path.lower()
                row = db.query(models.Preroll).filter(func.lower(models.Preroll.path) == lp).first()
                if row:
                    return True
            # Check by filename within the same category (case-insensitive)
            fname_lower = filename.lower()
            row = db.query(models.Preroll).filter(
                models.Preroll.category_id == category_id,
                func.lower(models.Preroll.filename) == fname_lower
            ).first()
            if row:
                return True
        except Exception:
            pass
        return False

    existing = 0
    for pth in candidate_files:
        try:
            ap = os.path.abspath(pth)
        except Exception:
            ap = pth
        fname = os.path.basename(ap)
        if _exists_in_db(ap, fname, category.id):
            existing += 1

    to_add = total_found - existing
    if req.dry_run:
        return {
            "dry_run": True,
            "root": root_abs,
            "category": {"id": category.id, "name": category.name},
            "total_found": total_found,
            "already_present": existing,
            "to_add": to_add,
        }

    # Normalize tags
    tags_json = None
    if req.tags:
        try:
            tags_json = json.dumps([str(t).strip() for t in req.tags if str(t).strip()])
        except Exception:
            tags_json = None

    added_details = []
    added_count = 0
    skipped_count = existing

    # Ensure thumbnail category folder
    thumb_cat_dir = os.path.join(THUMBNAILS_DIR, category.name)
    try:
        os.makedirs(thumb_cat_dir, exist_ok=True)
    except Exception:
        pass

    for src in candidate_files:
        try:
            abs_src = os.path.abspath(src)
        except Exception:
            abs_src = src

        filename = os.path.basename(abs_src)
        if _exists_in_db(abs_src, filename, category.id):
            continue

        file_size = None
        try:
            file_size = os.path.getsize(abs_src)
        except Exception:
            file_size = None

        duration = None
        try:
            result = _run_subprocess(
                [get_ffprobe_cmd(), "-v", "quiet", "-print_format", "json", "-show_format", abs_src],
                capture_output=True,
                text=True,
            )
            if getattr(result, "returncode", 1) == 0 and result.stdout:
                probe_data = json.loads(result.stdout)
                duration = float(probe_data.get("format", {}).get("duration")) if probe_data else None
        except Exception:
            duration = None

        # Create DB row (managed=False)
        p = models.Preroll(
            filename=filename,
            display_name=None,
            path=abs_src,
            thumbnail=None,
            tags=tags_json,
            category_id=category.id,
            description=None,
            duration=duration,
            file_size=file_size,
            managed=False,
        )
        db.add(p)
        db.commit()
        db.refresh(p)

        # Generate thumbnail if requested
        thumb_rel = None
        if req.generate_thumbnails:
            try:
                thumb_abs = os.path.join(thumb_cat_dir, f"{p.id}_{filename}.jpg")
                tmp = thumb_abs + ".tmp.jpg"
                res = _run_subprocess(
                    [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", abs_src, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp],
                    capture_output=True,
                    text=True,
                )
                if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp):
                    _generate_placeholder(tmp)
                try:
                    if os.path.exists(thumb_abs):
                        os.remove(thumb_abs)
                except Exception:
                    pass
                os.replace(tmp, thumb_abs)
                thumb_rel = os.path.relpath(thumb_abs, data_dir).replace("\\", "/")
                p.thumbnail = thumb_rel
            except Exception as e:
                try:
                    _file_log(f"map_preroll_root: thumbnail generation failed for '{abs_src}': {e}")
                except Exception:
                    pass
            finally:
                try:
                    db.commit()
                except Exception:
                    db.rollback()

        added_details.append({
            "id": p.id,
            "filename": p.filename,
            "path": p.path,
            "thumbnail": thumb_rel,
        })
        added_count += 1

    return {
        "dry_run": False,
        "root": root_abs,
        "category": {"id": category.id, "name": category.name},
        "total_found": total_found,
        "already_present": skipped_count,
        "added": added_count,
        "added_details": added_details[:50],  # limit detail size
    }

# Backup and Restore endpoints
@app.get("/backup/database")
def backup_database(db: Session = Depends(get_db)):
    """Export database to JSON"""
    try:
        # Export all data
        data = {
            "prerolls": [
                {
                    "filename": p.filename,
                    "display_name": getattr(p, "display_name", None),
                    "path": p.path,
                    "thumbnail": p.thumbnail,
                    "tags": p.tags,
                    "category_id": p.category_id,
                    "categories": [{"id": c.id, "name": c.name} for c in (p.categories or [])],
                    "description": p.description,
                    "managed": getattr(p, "managed", True),
                    "upload_date": p.upload_date.isoformat() if p.upload_date else None
                } for p in db.query(models.Preroll).all()
            ],
            "categories": [
                {
                    "name": c.name,
                    "description": c.description
                } for c in db.query(models.Category).all()
            ],
            "schedules": [
                {
                    "name": s.name,
                    "type": s.type,
                    "start_date": s.start_date.isoformat() if s.start_date else None,
                    "end_date": s.end_date.isoformat() if s.end_date else None,
                    "category_id": s.category_id,
                    "shuffle": s.shuffle,
                    "playlist": s.playlist,
                    "is_active": s.is_active,
                    "recurrence_pattern": s.recurrence_pattern,
                    "preroll_ids": s.preroll_ids
                } for s in db.query(models.Schedule).all()
            ],
            "holiday_presets": [
                {
                    "name": h.name,
                    "description": h.description,
                    "month": h.month,
                    "day": h.day,
                    "category_id": h.category_id
                } for h in db.query(models.HolidayPreset).all()
            ],
            "saved_sequences": [
                {
                    "name": seq.name,
                    "description": seq.description,
                    "blocks": seq.get_blocks(),
                    "created_at": seq.created_at.isoformat() if seq.created_at else None,
                    "updated_at": seq.updated_at.isoformat() if seq.updated_at else None
                } for seq in db.query(models.SavedSequence).all()
            ],
            "exported_at": datetime.datetime.utcnow().isoformat()
        }

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

@app.post("/backup/files")
def backup_files():
    """Create comprehensive ZIP archive of all system files including database, prerolls, and thumbnails"""
    try:
        from backend.database import DB_PATH
        
        # Create temp file for ZIP (streaming large files)
        import tempfile
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"nexroll_system_backup_{timestamp}.zip"
        zip_path = os.path.join(temp_dir, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # 1. Add database file
            if os.path.exists(DB_PATH):
                zip_file.write(DB_PATH, "database/nexroll.db")
            
            # 2. Add database JSON export (for cross-version compatibility)
            try:
                db = SessionLocal()
                try:
                    db_export = {
                        "prerolls": [
                            {
                                "filename": p.filename,
                                "display_name": getattr(p, "display_name", None),
                                "path": p.path,
                                "thumbnail": p.thumbnail,
                                "tags": p.tags,
                                "category_id": p.category_id,
                                "categories": [{"id": c.id, "name": c.name} for c in (p.categories or [])],
                                "description": p.description,
                                "managed": getattr(p, "managed", True),
                                "upload_date": p.upload_date.isoformat() if p.upload_date else None
                            } for p in db.query(models.Preroll).all()
                        ],
                        "categories": [
                            {
                                "id": c.id,
                                "name": c.name,
                                "description": c.description
                            } for c in db.query(models.Category).all()
                        ],
                        "schedules": [
                            {
                                "name": s.name,
                                "type": s.type,
                                "start_date": s.start_date.isoformat() if s.start_date else None,
                                "end_date": s.end_date.isoformat() if s.end_date else None,
                                "category_id": s.category_id,
                                "fallback_category_id": getattr(s, "fallback_category_id", None),
                                "shuffle": s.shuffle,
                                "playlist": s.playlist,
                                "is_active": s.is_active,
                                "recurrence_pattern": s.recurrence_pattern,
                                "preroll_ids": s.preroll_ids
                            } for s in db.query(models.Schedule).all()
                        ],
                        "holiday_presets": [
                            {
                                "name": h.name,
                                "description": h.description,
                                "month": h.month,
                                "day": h.day,
                                "category_id": h.category_id
                            } for h in db.query(models.HolidayPreset).all()
                        ],
                        "saved_sequences": [
                            {
                                "name": seq.name,
                                "description": seq.description,
                                "blocks": seq.get_blocks(),
                                "created_at": seq.created_at.isoformat() if seq.created_at else None,
                                "updated_at": seq.updated_at.isoformat() if seq.updated_at else None
                            } for seq in db.query(models.SavedSequence).all()
                        ],
                        "exported_at": datetime.datetime.utcnow().isoformat(),
                        "version": "1.10.14"
                    }
                    zip_file.writestr("database/nexroll_data.json", json.dumps(db_export, indent=2))
                finally:
                    db.close()
            except Exception as db_err:
                print(f"Warning: Could not export database JSON: {db_err}")
            
            # 3. Add all preroll video files
            if os.path.exists(PREROLLS_DIR):
                for file_path in Path(PREROLLS_DIR).rglob("*"):
                    if file_path.is_file():
                        # Skip thumbnails folder - we'll add it separately
                        rel_path = file_path.relative_to(Path(PREROLLS_DIR))
                        if not str(rel_path).startswith("thumbnails"):
                            zip_file.write(file_path, f"prerolls/{rel_path}")
            
            # 4. Add thumbnails
            if os.path.exists(THUMBNAILS_DIR):
                for file_path in Path(THUMBNAILS_DIR).rglob("*"):
                    if file_path.is_file():
                        rel_path = file_path.relative_to(Path(THUMBNAILS_DIR))
                        zip_file.write(file_path, f"thumbnails/{rel_path}")
            
            # 5. Add settings.json if exists
            settings_path = os.path.join(data_dir, "settings.json")
            if os.path.exists(settings_path):
                zip_file.write(settings_path, "settings/settings.json")
        
        # Return as streaming response
        return FileResponse(
            path=zip_path,
            filename=zip_filename,
            media_type="application/zip",
            background=BackgroundTask(lambda: os.unlink(zip_path) if os.path.exists(zip_path) else None)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"System backup failed: {str(e)}")

@app.post("/restore/database")
def restore_database(backup_data: dict, db: Session = Depends(get_db)):
    """Import database from JSON backup (restores categories, prerolls with multi-category links, schedules, and holidays)"""
    try:
        print("RESTORE: Starting deletion sequence...")
        # Clear existing data in correct order to avoid foreign key constraint errors
        # 1. Delete junction table entries first (many-to-many relationships)
        print("RESTORE: Deleting preroll_categories junction table...")
        result = db.execute(text("DELETE FROM preroll_categories"))
        print(f"RESTORE: Deleted {result.rowcount} rows from preroll_categories")
        db.flush()
        
        # 2. Delete genre maps (has FK to categories)
        print("RESTORE: Deleting genre maps...")
        db.query(models.GenreMap).delete(synchronize_session=False)
        
        # 3. Clear active_category from settings (has FK to categories)
        print("RESTORE: Clearing active_category from settings...")
        db.execute(text("UPDATE settings SET active_category = NULL"))
        db.flush()
        
        # 4. Delete schedules (has FK to categories via category_id and fallback_category_id)
        print("RESTORE: Deleting schedules...")
        db.query(models.Schedule).delete(synchronize_session=False)
        
        # 5. Delete holiday presets (has FK to categories)
        print("RESTORE: Deleting holiday presets...")
        db.query(models.HolidayPreset).delete(synchronize_session=False)
        
        # 6. Delete saved sequences (no FKs, but should be restored fresh)
        print("RESTORE: Deleting saved sequences...")
        db.query(models.SavedSequence).delete(synchronize_session=False)
        
        # 7. Delete prerolls (has FK to categories via category_id)
        print("RESTORE: Deleting prerolls...")
        db.query(models.Preroll).delete(synchronize_session=False)
        
        # 8. Finally delete categories (all FKs cleared)
        print("RESTORE: Deleting categories...")
        db.query(models.Category).delete(synchronize_session=False)
        
        db.commit()
        print("RESTORE: All deletions committed successfully")

        # Restore categories first (needed for foreign keys)
        print("RESTORE: Restoring categories...")
        old_id_to_new_id = {}  # Map old category IDs to new IDs
        for cat_data in backup_data.get("categories", []):
            try:
                old_id = cat_data.get("id")
                category = models.Category(
                    name=cat_data.get("name"),
                    description=cat_data.get("description")
                )
                db.add(category)
                db.flush()  # Get the new ID
                if old_id:
                    old_id_to_new_id[old_id] = category.id
                print(f"RESTORE: Category '{category.name}' - old ID {old_id} -> new ID {category.id}")
            except Exception as cat_err:
                print(f"Error adding category: {cat_err}")
                db.rollback()
                continue
        db.commit()

        # Build quick lookup by name
        name_to_category = {c.name: c for c in db.query(models.Category).all()}

        # Restore prerolls (including display_name and many-to-many categories if present)
        for preroll_data in backup_data.get("prerolls", []):
            try:
                # Safe datetime parsing
                upload_date = None
                if preroll_data.get("upload_date"):
                    try:
                        upload_date = datetime.datetime.fromisoformat(str(preroll_data["upload_date"]).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        upload_date = None
                
                # Map old category_id to new category_id
                old_cat_id = preroll_data.get("category_id")
                new_cat_id = old_id_to_new_id.get(old_cat_id) if old_cat_id else None
                
                p = models.Preroll(
                    filename=preroll_data.get("filename"),
                    display_name=preroll_data.get("display_name"),
                    path=preroll_data.get("path"),
                    thumbnail=preroll_data.get("thumbnail"),
                    tags=preroll_data.get("tags"),
                    category_id=new_cat_id,
                    description=preroll_data.get("description"),
                    upload_date=upload_date,
                    managed=preroll_data.get("managed", True)
                )
                db.add(p)
                db.flush()  # get p.id without full commit

                # Restore associated categories by name (IDs in backup may not match new DB)
                assoc = []
                try:
                    for c in preroll_data.get("categories", []):
                        nm = c.get("name") if isinstance(c, dict) else c
                        if nm and nm in name_to_category:
                            assoc.append(name_to_category[nm])
                except Exception as cat_assoc_err:
                    print(f"Error associating categories to preroll: {cat_assoc_err}")
                    assoc = []
                if assoc:
                    p.categories = assoc
            except Exception as preroll_err:
                print(f"Error adding preroll {preroll_data.get('filename')}: {preroll_err}")
                db.rollback()
                continue

        db.commit()

        # Restore schedules
        for schedule_data in backup_data.get("schedules", []):
            try:
                # Safe datetime parsing for schedules
                start_date = None
                end_date = None
                if schedule_data.get("start_date"):
                    try:
                        start_date = datetime.datetime.fromisoformat(str(schedule_data["start_date"]).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        start_date = None
                if schedule_data.get("end_date"):
                    try:
                        end_date = datetime.datetime.fromisoformat(str(schedule_data["end_date"]).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        end_date = None
                
                # Map old category IDs to new category IDs
                old_cat_id = schedule_data.get("category_id")
                new_cat_id = old_id_to_new_id.get(old_cat_id) if old_cat_id else None
                old_fallback_id = schedule_data.get("fallback_category_id")
                new_fallback_id = old_id_to_new_id.get(old_fallback_id) if old_fallback_id else None
                
                schedule = models.Schedule(
                    name=schedule_data.get("name"),
                    type=schedule_data.get("type"),
                    start_date=start_date,
                    end_date=end_date,
                    category_id=new_cat_id,
                    fallback_category_id=new_fallback_id,
                    shuffle=schedule_data.get("shuffle", False),
                    playlist=schedule_data.get("playlist", False),
                    is_active=schedule_data.get("is_active", True),
                    recurrence_pattern=schedule_data.get("recurrence_pattern"),
                    preroll_ids=schedule_data.get("preroll_ids")
                )
                db.add(schedule)
            except Exception as schedule_err:
                print(f"Error adding schedule {schedule_data.get('name')}: {schedule_err}")
                db.rollback()
                continue

        # Restore holiday presets
        for holiday_data in backup_data.get("holiday_presets", []):
            try:
                # Map old category_id to new category_id
                old_cat_id = holiday_data.get("category_id")
                new_cat_id = old_id_to_new_id.get(old_cat_id) if old_cat_id else None
                
                holiday = models.HolidayPreset(
                    name=holiday_data.get("name"),
                    description=holiday_data.get("description"),
                    month=holiday_data.get("month"),
                    day=holiday_data.get("day"),
                    category_id=new_cat_id
                )
                db.add(holiday)
            except Exception as holiday_err:
                print(f"Error adding holiday preset {holiday_data.get('name')}: {holiday_err}")
                db.rollback()
                continue

        # Restore saved sequences
        print("RESTORE: Restoring saved sequences...")
        for seq_data in backup_data.get("saved_sequences", []):
            try:
                # Safe datetime parsing
                created_at = None
                updated_at = None
                if seq_data.get("created_at"):
                    try:
                        created_at = datetime.datetime.fromisoformat(str(seq_data["created_at"]).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        created_at = None
                if seq_data.get("updated_at"):
                    try:
                        updated_at = datetime.datetime.fromisoformat(str(seq_data["updated_at"]).replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        updated_at = None
                
                sequence = models.SavedSequence(
                    name=seq_data.get("name"),
                    description=seq_data.get("description"),
                    blocks=json.dumps(seq_data.get("blocks", [])),
                    created_at=created_at or datetime.datetime.utcnow(),
                    updated_at=updated_at or datetime.datetime.utcnow()
                )
                db.add(sequence)
                print(f"RESTORE: Added sequence '{seq_data.get('name')}'")
            except Exception as seq_err:
                print(f"Error adding saved sequence {seq_data.get('name')}: {seq_err}")
                db.rollback()
                continue

        db.commit()
        return {"message": "Database restored successfully (v1.9.0)", "version": "1.9.0"}
    except Exception as e:
        print(f"Critical restore error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

@app.post("/restore/files")
def restore_files(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import system backup from ZIP archive (handles new comprehensive format and legacy format)"""
    try:
        from backend.database import DB_PATH
        import tempfile
        import shutil
        
        # Save uploaded ZIP file temporarily
        temp_dir = tempfile.gettempdir()
        zip_path = os.path.join(temp_dir, "nexroll_restore_temp.zip")
        with open(zip_path, "wb") as f:
            content = file.file.read()
            f.write(content)
        
        restored_items = []
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            namelist = zip_ref.namelist()
            
            # Detect backup format
            is_new_format = any(n.startswith("database/") or n.startswith("prerolls/") for n in namelist)
            
            if is_new_format:
                # New comprehensive format
                print("RESTORE: Detected new comprehensive backup format")
                
                # 1. Restore database file if present
                if "database/nexroll.db" in namelist:
                    print("RESTORE: Restoring database file...")
                    # Extract to temp location first
                    db_temp = os.path.join(temp_dir, "nexroll_restore.db")
                    with zip_ref.open("database/nexroll.db") as src:
                        with open(db_temp, "wb") as dst:
                            dst.write(src.read())
                    # Copy to actual location (backup existing first)
                    if os.path.exists(DB_PATH):
                        backup_db = DB_PATH + ".backup"
                        try:
                            shutil.copy2(DB_PATH, backup_db)
                        except Exception:
                            pass
                    shutil.copy2(db_temp, DB_PATH)
                    os.unlink(db_temp)
                    restored_items.append("database")
                
                # 2. Restore preroll files
                preroll_files = [n for n in namelist if n.startswith("prerolls/") and not n.endswith("/")]
                if preroll_files:
                    print(f"RESTORE: Restoring {len(preroll_files)} preroll files...")
                    for name in preroll_files:
                        # Extract relative path after "prerolls/"
                        rel_path = name[len("prerolls/"):]
                        target_path = os.path.join(PREROLLS_DIR, rel_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zip_ref.open(name) as src:
                            with open(target_path, "wb") as dst:
                                dst.write(src.read())
                    restored_items.append(f"{len(preroll_files)} preroll files")
                
                # 3. Restore thumbnails
                thumb_files = [n for n in namelist if n.startswith("thumbnails/") and not n.endswith("/")]
                if thumb_files:
                    print(f"RESTORE: Restoring {len(thumb_files)} thumbnail files...")
                    for name in thumb_files:
                        rel_path = name[len("thumbnails/"):]
                        target_path = os.path.join(THUMBNAILS_DIR, rel_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zip_ref.open(name) as src:
                            with open(target_path, "wb") as dst:
                                dst.write(src.read())
                    restored_items.append(f"{len(thumb_files)} thumbnails")
                
                # 4. Restore settings if present
                if "settings/settings.json" in namelist:
                    print("RESTORE: Restoring settings...")
                    settings_path = os.path.join(data_dir, "settings.json")
                    with zip_ref.open("settings/settings.json") as src:
                        with open(settings_path, "wb") as dst:
                            dst.write(src.read())
                    restored_items.append("settings")
                
            else:
                # Legacy format - just prerolls folder directly
                print("RESTORE: Detected legacy backup format")
                zip_ref.extractall(PREROLLS_DIR)
                restored_items.append("preroll files (legacy format)")
        
        # Clean up temp file
        os.unlink(zip_path)
        
        return {
            "message": "System restore completed successfully",
            "restored": restored_items,
            "format": "comprehensive" if is_new_format else "legacy"
        }
    except Exception as e:
        print(f"RESTORE ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"System restore failed: {str(e)}")

@app.post("/maintenance/fix-thumbnail-paths")
def fix_thumbnail_paths(db: Session = Depends(get_db)):
    """Normalize thumbnail paths in DB for static serving compatibility."""
    try:
        prerolls = db.query(models.Preroll).filter(models.Preroll.thumbnail.isnot(None)).all()
        updated_count = 0

        for preroll in prerolls:
            if not preroll.thumbnail:
                continue
            # Normalize leading slash and fix known prefixes
            path = str(preroll.thumbnail).lstrip("/")
            changed = False

            # Remove legacy 'data/' prefix
            if path.startswith("data/"):
                path = path.replace("data/", "", 1)
                changed = True

            # If stored as 'thumbnails/...', ensure 'prerolls/' prefix for compatibility with /static/prerolls/thumbnails
            if path.startswith("thumbnails/"):
                path = "prerolls/" + path
                changed = True

            if changed:
                preroll.thumbnail = path
                updated_count += 1

        db.commit()
        return {"message": f"Fixed {updated_count} thumbnail paths"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error fixing thumbnail paths: {str(e)}")

@app.post("/thumbnails/rebuild")
def thumbnails_rebuild(category: str = None, force: bool = False, db: Session = Depends(get_db)):
    """
    Rebuild missing preroll thumbnails.
    - category: optional category name filter (exact match)
    - force: regenerate even if a thumbnail file already exists
    """
    processed = 0
    generated = 0
    skipped = 0
    failures = []

    try:
        # Query prerolls with optional category name filter
        query = db.query(models.Preroll).join(models.Category, isouter=True)
        if category and category.strip():
            query = query.filter(models.Category.name == category.strip())

        prerolls = query.all()

        # Ensure root folders exist
        os.makedirs(THUMBNAILS_DIR, exist_ok=True)
        os.makedirs(PREROLLS_DIR, exist_ok=True)

        for p in prerolls:
            processed += 1

            # Determine category directory name (Default if none)
            cat_name = getattr(getattr(p, "category", None), "name", None) or "Default"
            cat_thumb_dir = os.path.join(THUMBNAILS_DIR, cat_name)
            os.makedirs(cat_thumb_dir, exist_ok=True)

            # Target thumbnail path: <thumbnails>/<Category>/<id>_<filename>.<ext>.jpg (id-prefixed for uniqueness)
            thumb_filename = f"{p.id}_{p.filename}.jpg"
            target_thumb = os.path.join(cat_thumb_dir, thumb_filename)

            # If not forcing and file exists, ensure DB path is set and skip
            if os.path.exists(target_thumb) and not force:
                if not p.thumbnail:
                    rel = os.path.relpath(target_thumb, data_dir).replace("\\", "/")
                    p.thumbnail = rel
                skipped += 1
                continue

            # Resolve video file path (handle legacy relative paths)
            video_path = p.path
            if not os.path.isabs(video_path):
                video_path = os.path.join(data_dir, video_path)

            if not os.path.exists(video_path):
                # Source video missing; generate a placeholder thumbnail instead of failing
                try:
                    # Ensure temp file has .jpg extension for ffmpeg/placeholder compatibility
                    tmp_thumb = target_thumb + ".tmp.jpg"
                    _generate_placeholder(tmp_thumb)
                    try:
                        if os.path.exists(target_thumb):
                            os.remove(target_thumb)
                    except Exception:
                        pass
                    os.replace(tmp_thumb, target_thumb)
                    rel = os.path.relpath(target_thumb, data_dir).replace("\\", "/")
                    p.thumbnail = rel
                    generated += 1
                except Exception:
                    failures.append({"id": p.id, "file": p.filename, "reason": "placeholder_failed"})
                continue

            # Generate thumbnail with ffmpeg
            try:
                # Use a .jpg temp name and force MJPEG so ffmpeg doesn't mis-detect format
                tmp_thumb = target_thumb + ".tmp.jpg"
                res = _run_subprocess(
                    [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", video_path, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp_thumb],
                    capture_output=True,
                    text=True,
                )
                if res.returncode != 0 or not os.path.exists(tmp_thumb):
                    _file_log(f"rebuild_thumbnail failed for '{video_path}': {res.stderr}")
                    try:
                        if os.path.exists(tmp_thumb):
                            os.remove(tmp_thumb)
                    except Exception:
                        pass
                    failures.append({"id": p.id, "file": p.filename, "reason": "ffmpeg_failed"})
                    continue

                # Atomic-ish move
                try:
                    if os.path.exists(target_thumb):
                        os.remove(target_thumb)
                except Exception:
                    pass
                os.replace(tmp_thumb, target_thumb)

                # Update DB with relative thumbnail path for static serving
                rel = os.path.relpath(target_thumb, data_dir).replace("\\", "/")
                p.thumbnail = rel
                generated += 1
            except FileNotFoundError:
                failures.append({"id": p.id, "file": p.filename, "reason": "ffmpeg_not_found"})
                # No point continuing if ffmpeg is absent; continue collecting other errors
                continue
            except Exception as e:
                _file_log(f"rebuild_thumbnail exception for '{video_path}': {e}")
                failures.append({"id": p.id, "file": p.filename, "reason": "exception"})
                continue

        try:
            db.commit()
        except Exception as e:
            db.rollback()
            _file_log(f"thumbnails_rebuild commit failed: {e}")
            raise HTTPException(status_code=500, detail=f"Thumbnail rebuild failed to commit: {str(e)}")

        return {
            "processed": processed,
            "generated": generated,
            "skipped": skipped,
            "failures": len(failures),
            "failure_details": failures[:15],  # cap details
            "category": category or None,
            "force": force,
        }
    except HTTPException:
        raise
    except Exception as e:
        _file_log(f"thumbnails_rebuild error: {e}")
        raise HTTPException(status_code=500, detail=f"Thumbnail rebuild error: {str(e)}")

# Debug: Print current working directory
print(f"Backend running from: {os.getcwd()}")

# Get absolute paths for static files relative to project root
# Determine install and resource roots
if getattr(sys, "frozen", False):
    # When frozen, use sys.executable for install_root and _MEIPASS for resource_root
    install_root = os.path.dirname(sys.executable)
    resource_root = getattr(sys, "_MEIPASS", install_root)
    # Try to find frontend in installation dir first, then _MEIPASS
    frontend_candidates = [
        os.path.join(install_root, "frontend", "build"),
        os.path.join(resource_root, "frontend", "build"),
        os.path.join(install_root, "frontend"),
        os.path.join(resource_root, "frontend"),
    ]
    frontend_dir = next((d for d in frontend_candidates if os.path.isdir(d)), frontend_candidates[0])
    print(f"Frontend candidates (frozen):")
    for candidate in frontend_candidates:
        print(f"  {candidate}: {'exists' if os.path.isdir(candidate) else 'missing'}")
    print(f"Selected: {frontend_dir}")
else:
    # In development, both roots are relative to __file__
    install_root = os.path.dirname(os.path.dirname(__file__))
    resource_root = install_root
    frontend_dir = os.path.join(resource_root, "frontend", "build")
# Prefer built React assets if present; fallback to source 'frontend'
# When running as a frozen onefile, prefer the installer-installed frontend under
# the install root (next to the exe) if it exists. This allows installers that
# place `frontend/build` alongside NeXroll.exe to serve the UI even when the
# PyInstaller _MEIPASS temporary extraction doesn't include the frontend assets.
if getattr(sys, "frozen", False):
    # Check installer-provided frontend first
    _inst_candidate = os.path.join(install_root, "frontend", "build")
    _res_candidate = os.path.join(resource_root, "frontend", "build")
    if os.path.isdir(_inst_candidate):
        frontend_dir = _inst_candidate
    elif os.path.isdir(_res_candidate):
        frontend_dir = _res_candidate
    else:
        frontend_dir = os.path.join(resource_root, "frontend")
else:
    _candidate = os.path.join(resource_root, "frontend", "build")
    frontend_dir = _candidate if os.path.isdir(_candidate) else os.path.join(resource_root, "frontend")

# Diagnostic logging: record which paths were considered and which was selected.
try:
    try:
        _file_log(f"Startup paths: install_root={install_root}, resource_root={resource_root}")
    except Exception:
        pass
    if getattr(sys, "frozen", False):
        try:
            _file_log(f"Frontend candidate (install): {_inst_candidate} exists={os.path.isdir(_inst_candidate)}")
        except Exception:
            pass
        try:
            _file_log(f"Frontend candidate (resource): {_res_candidate} exists={os.path.isdir(_res_candidate)}")
        except Exception:
            pass
        try:
            _file_log(f"Selected frontend_dir: {frontend_dir}")
        except Exception:
            pass
    else:
        try:
            _file_log(f"Frontend candidate (dev): {_candidate} exists={os.path.isdir(_candidate)}; selected={frontend_dir}")
        except Exception:
            pass
except Exception:
    # Never fail startup due to diagnostics
    try:
        _file_log("startup diagnostics logging failed")
    except Exception:
        pass

def _get_windows_preroll_path_from_registry():
    try:
        if sys.platform.startswith("win"):
            import winreg
            # Support both 64-bit and 32-bit registry views
            views = [
                getattr(winreg, "KEY_WOW64_64KEY", 0),
                getattr(winreg, "KEY_WOW64_32KEY", 0),
            ]
            for view in views:
                try:
                    key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, r"Software\NeXroll", 0, winreg.KEY_READ | view)
                    try:
                        value, _ = winreg.QueryValueEx(key, "PrerollPath")
                        if value and str(value).strip():
                            return str(value).strip()
                    finally:
                        winreg.CloseKey(key)
                except Exception:
                    continue
    except Exception:
        return None
    return None

def _resolve_data_dir(project_root_path: str) -> str:
    r"""
    Resolve a writable preroll root directory.
    Priority:
      1) NEXROLL_PREROLL_PATH env (must be writable)
      2) HKLM\Software\NeXroll\PrerollPath (must be writable)
      3) %ProgramData%\NeXroll\Prerolls (if writable)
      4) %LOCALAPPDATA% or %APPDATA%\NeXroll\Prerolls (if writable)
      5) project_root\data (last resort), but also check a repo-root sibling 'data' during dev
    """
    def _is_dir_writable(p: str) -> bool:
        try:
            os.makedirs(p, exist_ok=True)
            test = os.path.join(p, ".nexroll_write_test.tmp")
            with open(test, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(test)
            return True
        except Exception:
            return False

    env_path = os.getenv("NEXROLL_PREROLL_PATH")
    if env_path and env_path.strip():
        p = env_path.strip()
        if _is_dir_writable(p):
            return p

    reg_path = _get_windows_preroll_path_from_registry()
    if reg_path and reg_path.strip():
        p = reg_path.strip()
        if _is_dir_writable(p):
            return p

    if sys.platform.startswith("win"):
        pd = os.environ.get("ProgramData")
        if pd:
            pd_dir = os.path.join(pd, "NeXroll", "Prerolls")
            if _is_dir_writable(pd_dir):
                return pd_dir

        la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if la:
            user_dir = os.path.join(la, "NeXroll", "Prerolls")
            if _is_dir_writable(user_dir):
                return user_dir

    # Dev convenience: if a sibling 'data' folder exists (repo root), prefer it
    try:
        parent = os.path.dirname(project_root_path)
        sibling = os.path.join(parent, "data")
        if os.path.isdir(sibling) and _is_dir_writable(sibling):
            return sibling
    except Exception:
        pass

    # Final fallback to project root 'data'
    try:
        d = os.path.join(project_root_path, "data")
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

def migrate_legacy_data():
    """
    Migrate existing prerolls and thumbnails from legacy locations into PREROLLS_DIR
    if PREROLLS_DIR is empty. This preserves user assets across upgrades.
    Legacy candidates:
      - $INSTDIR\\data\\prerolls (previous installer layout)
      - <install_root>\\..\\data\\prerolls (portable/dev sibling)
      - %ProgramData%\\NeXroll\\Prerolls (standard ProgramData path)
    """
    try:
        candidates = []
        try:
            candidates.append(os.path.join(install_root, "data", "prerolls"))
        except Exception:
            pass
        try:
            parent = os.path.dirname(install_root)
            candidates.append(os.path.join(parent, "data", "prerolls"))
        except Exception:
            pass
        try:
            pd = os.environ.get("ProgramData")
            if pd:
                candidates.append(os.path.join(pd, "NeXroll", "Prerolls"))
        except Exception:
            pass

        # Only migrate if destination is empty or non-existent
        dest_empty = False
        try:
            if not os.path.isdir(PREROLLS_DIR) or not any(os.scandir(PREROLLS_DIR)):
                dest_empty = True
        except Exception:
            dest_empty = False

        if not dest_empty:
            return

        for src in candidates:
            try:
                if not src or not os.path.isdir(src):
                    continue
                # Avoid copying onto itself
                try:
                    if os.path.samefile(src, PREROLLS_DIR):
                        continue
                except Exception:
                    pass

                for root, dirs, files in os.walk(src):
                    rel = os.path.relpath(root, src)
                    out_dir = os.path.join(PREROLLS_DIR, rel) if rel != "." else PREROLLS_DIR
                    os.makedirs(out_dir, exist_ok=True)
                    for f in files:
                        try:
                            dst = os.path.join(out_dir, f)
                            if not os.path.exists(dst):
                                shutil.copy2(os.path.join(root, f), dst)
                        except Exception:
                            pass
                _file_log(f"migrate_legacy_data: migrated from {src}")
                break
            except Exception:
                continue
    except Exception as e:
        try:
            _file_log(f"migrate_legacy_data error: {e}")
        except Exception:
            pass
    # Fallback to install directory (portable/dev)
    d = os.path.join(install_root, "data")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d

data_dir = _resolve_data_dir(install_root)

# Create necessary directories (support both "data_dir" being a base dir OR the actual "Prerolls" dir)
basename = os.path.basename(os.path.normpath(data_dir)).lower()
PREROLLS_DIR = data_dir if basename == "prerolls" else os.path.join(data_dir, "prerolls")
THUMBNAILS_DIR = os.path.join(PREROLLS_DIR, "thumbnails")

def ensure_runtime_assets():
    """
    Copy bundled default preroll assets and thumbnails into the runtime data directory
    if they are missing. This restores out-of-the-box thumbnails for the UI and keeps
    parity across portable EXE, service, and tray startup contexts.
    """
    try:
        src_root = os.path.join(resource_root, "backend", "data", "prerolls")
        if not os.path.isdir(src_root):
            return

        # Ensure target directories exist
        os.makedirs(PREROLLS_DIR, exist_ok=True)
        os.makedirs(THUMBNAILS_DIR, exist_ok=True)

        # Copy category folders (excluding 'thumbnails') if missing or empty
        for name in os.listdir(src_root):
            src_path = os.path.join(src_root, name)
            if not os.path.isdir(src_path) or name.lower() == "thumbnails":
                continue

            dst_path = os.path.join(PREROLLS_DIR, name)
            need_copy = False
            if not os.path.isdir(dst_path):
                need_copy = True
            else:
                try:
                    if not any(os.scandir(dst_path)):
                        need_copy = True
                except Exception:
                    need_copy = False

            if need_copy:
                for root, dirs, files in os.walk(src_path):
                    rel = os.path.relpath(root, src_path)
                    out_dir = os.path.join(dst_path, rel) if rel != "." else dst_path
                    os.makedirs(out_dir, exist_ok=True)
                    for f in files:
                        try:
                            shutil.copy2(os.path.join(root, f), os.path.join(out_dir, f))
                        except Exception:
                            pass

        # Copy prebuilt thumbnails if missing or empty
        thumbs_src = os.path.join(src_root, "thumbnails")
        if os.path.isdir(thumbs_src):
            for name in os.listdir(thumbs_src):
                src_cat = os.path.join(thumbs_src, name)
                if not os.path.isdir(src_cat):
                    continue
                dst_cat = os.path.join(THUMBNAILS_DIR, name)

                need_copy = False
                if not os.path.isdir(dst_cat):
                    need_copy = True
                else:
                    try:
                        if not any(os.scandir(dst_cat)):
                            need_copy = True
                    except Exception:
                        need_copy = False

                if need_copy:
                    for root, dirs, files in os.walk(src_cat):
                        rel = os.path.relpath(root, src_cat)
                        out_dir = os.path.join(dst_cat, rel) if rel != "." else dst_cat
                        os.makedirs(out_dir, exist_ok=True)
                        for f in files:
                            try:
                                shutil.copy2(os.path.join(root, f), os.path.join(out_dir, f))
                            except Exception:
                                pass

        _file_log("ensure_runtime_assets: defaults ensured")
    except Exception as e:
        try:
            _file_log(f"ensure_runtime_assets error: {e}")
        except Exception:
            pass

os.makedirs(PREROLLS_DIR, exist_ok=True)
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
# Migrate legacy assets into PREROLLS_DIR if destination is empty
try:
    migrate_legacy_data()
except Exception:
    pass
# Ensure default runtime assets exist after migration
try:
    ensure_runtime_assets()
except Exception:
    pass

# Debug prints
print(f"Backend running from: {os.getcwd()}")
print(f"Frontend dir: {frontend_dir}")
print(f"Data dir: {data_dir}")
print(f"Prerolls dir: {PREROLLS_DIR}")
print(f"Thumbnails dir: {THUMBNAILS_DIR}")

# Static files for prerolls
# Dynamic thumbnail endpoint: generate on-demand if file is missing
@app.get("/static/prerolls/thumbnails/{category}/{thumb_name}")
def get_or_create_thumbnail(category: str, thumb_name: str):
    """
    Serve preroll thumbnail from THUMBNAILS_DIR, generating it on-demand from
    the corresponding video file in PREROLLS_DIR if missing.
    This preserves existing frontend URLs like:
      /static/prerolls/thumbnails/<Category>/<VideoName>.<ext>.jpg
    """
    # Decode URL-encoded parts then sanitize
    try:
        category = unquote(category or "")
        thumb_name = unquote(thumb_name or "")
    except Exception:
        pass

    for frag in (category, thumb_name):
        if ".." in frag or "/" in frag or "\\" in frag:
            raise HTTPException(status_code=400, detail="Invalid path")

    # Resolve target thumbnail path and ensure category directory exists (case-insensitive)
    def _resolve_category_dir(root_dir: str, cat: str) -> str:
        cand = os.path.join(root_dir, cat)
        if os.path.isdir(cand):
            return cand
        try:
            for d in os.listdir(root_dir):
                if d.lower() == cat.lower():
                    return os.path.join(root_dir, d)
        except Exception:
            pass
        # Fallback: use requested category (will be created under THUMBNAILS_DIR if missing)
        return cand

    cat_thumb_dir = _resolve_category_dir(THUMBNAILS_DIR, category)
    os.makedirs(cat_thumb_dir, exist_ok=True)
    thumb_path = os.path.join(cat_thumb_dir, thumb_name)

    # If already exists, serve it
    if os.path.exists(thumb_path):
        return FileResponse(thumb_path, media_type="image/jpeg")

    # Derive source video filename by stripping the .jpg suffix
    base, jpg_ext = os.path.splitext(thumb_name)
    if jpg_ext.lower() != ".jpg":
        # Unexpected extension; enforce .jpg thumbnails
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    # base is expected to include the video extension (e.g., Movie.mp4)
    # Support id-prefixed thumbnails "<id>_<filename>.<ext>.jpg" by stripping the numeric prefix
    video_base = base
    try:
        if "_" in base:
            maybe_id, rest = base.split("_", 1)
            if all(ch.isdigit() for ch in maybe_id):
                video_base = rest
    except Exception:
        video_base = base

    video_cat_dir = _resolve_category_dir(PREROLLS_DIR, category)
    video_path = os.path.join(video_cat_dir, video_base)

    if not os.path.exists(video_path):
        # Try to find case-insensitive match within the category folder
        try:
            if os.path.isdir(video_cat_dir):
                lower_target = video_base.lower()
                for fname in os.listdir(video_cat_dir):
                    if fname.lower() == lower_target:
                        video_path = os.path.join(video_cat_dir, fname)
                        break
        except Exception:
            pass

    if not os.path.exists(video_path):
        # Source video is missing; generate a placeholder thumbnail and serve it
        try:
            # Ensure temp file has .jpg extension for ffmpeg/placeholder compatibility
            tmp_thumb = thumb_path + ".tmp.jpg"
            _generate_placeholder(tmp_thumb)
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception:
                pass
            os.replace(tmp_thumb, thumb_path)
            return FileResponse(thumb_path, media_type="image/jpeg")
        except Exception:
            raise HTTPException(status_code=404, detail="Source video not found for thumbnail")

    # Generate the thumbnail using ffmpeg
    try:
        # Write to a temp path first, then move into place to avoid partial reads
        tmp_thumb = thumb_path + ".tmp.jpg"
        res = _run_subprocess(
            [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", video_path, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp_thumb],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0 or not os.path.exists(tmp_thumb):
            _file_log(f"Thumbnail generation failed for '{video_path}': {res.stderr}")
            # Fallback to placeholder
            _generate_placeholder(tmp_thumb)
        # Atomic-ish replace
        try:
            if os.path.exists(thumb_path):
                os.remove(thumb_path)
        except Exception:
            pass
        os.replace(tmp_thumb, thumb_path)
    except FileNotFoundError:
        # ffmpeg not present; fallback to placeholder
        try:
            tmp_thumb = thumb_path + ".tmp.jpg"
            _generate_placeholder(tmp_thumb)
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception:
                pass
            os.replace(tmp_thumb, thumb_path)
        except Exception:
            raise HTTPException(status_code=500, detail="ffmpeg is not available to generate thumbnails")
    except Exception as e:
        _file_log(f"Thumbnail generation exception for '{video_path}': {e}")
        # Fallback to placeholder to keep UI stable
        try:
            tmp_thumb = thumb_path + ".tmp.jpg"
            _generate_placeholder(tmp_thumb)
            try:
                if os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception:
                pass
            os.replace(tmp_thumb, thumb_path)
        except Exception:
            raise HTTPException(status_code=500, detail="Thumbnail generation error")

    return FileResponse(thumb_path, media_type="image/jpeg")

@app.get("/static/prerolls/{category}/{filename}")
def get_preroll_video(category: str, filename: str, db: Session = Depends(get_db)):
    """
    Serve preroll video file from PREROLLS_DIR.
    """
    # Decode URL-encoded parts then sanitize
    try:
        category = unquote(category or "")
        filename = unquote(filename or "")
    except Exception:
        pass

    for frag in (category, filename):
        if ".." in frag or "/" in frag or "\\" in frag:
            raise HTTPException(status_code=400, detail="Invalid path")

    # Resolve target video path and ensure category directory exists (case-insensitive)
    def _resolve_category_dir(root_dir: str, cat: str) -> str:
        cand = os.path.join(root_dir, cat)
        if os.path.isdir(cand):
            return cand
        try:
            for d in os.listdir(root_dir):
                if d.lower() == cat.lower():
                    return os.path.join(root_dir, d)
        except Exception:
            pass
        # Fallback: use requested category (will be created under PREROLLS_DIR if missing)
        return cand

    cat_dir = _resolve_category_dir(PREROLLS_DIR, category)
    video_path = os.path.join(cat_dir, filename)

    # If not exists, try case-insensitive match
    if not os.path.exists(video_path):
        try:
            if os.path.isdir(cat_dir):
                lower_target = filename.lower()
                for fname in os.listdir(cat_dir):
                    if fname.lower() == lower_target:
                        video_path = os.path.join(cat_dir, fname)
                        break
        except Exception:
            pass

    # If still not found, check for externally managed preroll
    if not os.path.exists(video_path):
        try:
            # Find category by name
            cat_obj = db.query(models.Category).filter(models.Category.name == category).first()
            print(f"[PREROLL DEBUG] Looking up in database:")
            print(f"  Category: {category}, Found cat_obj: {cat_obj.id if cat_obj else None}")
            if cat_obj:
                # Find preroll by filename and category_id
                preroll = db.query(models.Preroll).filter(
                    models.Preroll.filename == filename,
                    models.Preroll.category_id == cat_obj.id
                ).first()
                print(f"  Filename: {filename}, Found preroll: {preroll.id if preroll else None}")
                if preroll:
                    print(f"  Preroll.path: {preroll.path}")
                    print(f"  Preroll.managed: {getattr(preroll, 'managed', 'N/A')}")
                    # Use the preroll's path directly (whether managed or not)
                    # If it's externally managed (managed=False), path is absolute
                    # If it's managed (managed=True), path may be relative
                    if hasattr(preroll, 'managed') and preroll.managed == False:
                        video_path = preroll.path
                        print(f"  Using external path: {video_path}")
                    elif preroll.path and not os.path.isabs(preroll.path):
                        video_path = os.path.join(data_dir, preroll.path)
                        print(f"  Using relative path joined with data_dir: {video_path}")
                    else:
                        video_path = preroll.path
                        print(f"  Using absolute path as-is: {video_path}")
        except Exception as e:
            print(f"Error checking database for preroll: {e}")
            import traceback
            traceback.print_exc()
            pass

    if not os.path.exists(video_path):
        # Log for debugging
        print(f"Video not found at: {video_path}")
        print(f"  Category: {category}")
        print(f"  Filename: {filename}")
        print(f"  PREROLLS_DIR: {PREROLLS_DIR}")
        print(f"  Category dir: {cat_dir}")
        print(f"  Category dir exists: {os.path.isdir(cat_dir)}")
        raise HTTPException(status_code=404, detail="Video not found")

    # Detect mime type
    import mimetypes
    mime_type, _ = mimetypes.guess_type(video_path)
    if not mime_type or not mime_type.startswith("video/"):
        mime_type = "video/mp4"  # default

    return FileResponse(video_path, media_type=mime_type)

@app.get("/static/thumbnails/{category}/{thumb_name}")
def compat_static_thumbnails(category: str, thumb_name: str):
    return get_or_create_thumbnail(category, thumb_name)

# Alias endpoint for UI fallback: /thumbgen/<Category>/<VideoName.ext>.jpg
@app.get("/thumbgen/{category}/{thumb_name}")
def alias_thumbgen(category: str, thumb_name: str):
    return get_or_create_thumbnail(category, thumb_name)

# Fallback handlers for hashed frontend assets (avoid 404 when index.html points to old main.<hash>.{js,css})
# This serves the latest present main.* file when the requested hashed file is missing.
def _hashed_fallback_path(subdir: str, requested: str, main_prefix: str, ext: str) -> str | None:
    try:
        # Sanitize
        requested_safe = os.path.basename(requested or "")
        base_dir = os.path.join(frontend_dir, "static", subdir)
        candidate = os.path.join(base_dir, requested_safe)
        if os.path.exists(candidate):
            return candidate
        # Fallback only for main.* assets
        if requested_safe.startswith(main_prefix) and requested_safe.endswith(ext) and os.path.isdir(base_dir):
            try:
                files = [f for f in os.listdir(base_dir) if f.startswith(main_prefix) and f.endswith(ext)]
                if files:
                    files = sorted(files, key=lambda f: os.path.getmtime(os.path.join(base_dir, f)), reverse=True)
                    return os.path.join(base_dir, files[0])
            except Exception:
                pass
    except Exception:
        pass
    return None

@app.get("/static/js/{fname}")
def static_js_fallback(fname: str):
    p = _hashed_fallback_path("js", fname, "main.", ".js")
    if p and os.path.exists(p):
        resp = FileResponse(p, media_type="application/javascript")
        try:
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        except Exception:
            pass
        return resp
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/static/css/{fname}")
def static_css_fallback(fname: str):
    p = _hashed_fallback_path("css", fname, "main.", ".css")
    if p and os.path.exists(p):
        resp = FileResponse(p, media_type="text/css")
        try:
            resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            resp.headers["Pragma"] = "no-cache"
            resp.headers["Expires"] = "0"
        except Exception:
            pass
        return resp
    raise HTTPException(status_code=404, detail="Not found")

# --- Genre-based Pre-Roll Mapping APIs ---

def _norm_genre(s):
    """
    Normalize a genre string for case-insensitive, punctuation-tolerant matching.
    - Unicode NFKC normalization
    - Replace common separators (&, /, - and underscores) with single spaces
    - Collapse repeated whitespace and lowercase
    """
    try:
        import unicodedata, re
        t = unicodedata.normalize("NFKC", str(s or ""))
        # normalize separators
        t = t.replace("&", " and ")
        t = re.sub(r"[/_]", " ", t)
        t = re.sub(r"-+", " ", t)
        # collapse whitespace and lowercase
        t = " ".join(t.split()).strip().lower()
        return t
    except Exception:
        return ""

def _canonical_genre_key(s: str) -> str:
    """
    Apply synonym normalization on top of _norm_genre.
    Keeps mapping keys intuitive but tolerant to Plex naming variants.
    """
    g = _norm_genre(s)
    if not g:
        return ""
    # lightweight synonyms informed by Plex genre variants
    synonyms = {
        "sci fi": "science fiction",
        "scifi": "science fiction",
        "sci-fi": "science fiction",  # in case normalization changes later
        "kids and family": "family",
        "kids family": "family",
    }
    return synonyms.get(g, g)

def _genre_candidate_keys(s: str) -> list[str]:
    """
    Generate candidate normalized keys for a raw genre tag:
      1) canonical normalized form
      2) split components for composites like "action and adventure"
    """
    import re
    out: list[str] = []
    base = _canonical_genre_key(s)
    if base:
        out.append(base)
        # split composite tags into parts and try each
        parts = [p.strip() for p in re.split(r"(?:\s+and\s+|,|\||/)", base) if p and p.strip()]
        for p in parts:
            if p and p not in out:
                out.append(p)
    # unique while preserving order
    seen = set()
    uniq = [x for x in out if not (x in seen or seen.add(x))]
    return uniq

def _find_genre_map_case_insensitive(db, genre_norm):
    """
    Find a GenreMap by canonical key. Prefers genre_norm column; falls back to
    computing canonical on existing rows for legacy DBs (no column/backfill).
    """
    try:
        key = _canonical_genre_key(genre_norm)
        if not key:
            return None
        # Try direct match on canonical column (if present)
        try:
            gm = db.query(models.GenreMap).filter(models.GenreMap.genre_norm == key).first()
            if gm:
                return gm
        except Exception:
            gm = None
        # Fallback: scan rows and compare canonicalized raw genre (legacy rows)
        try:
            rows = db.query(models.GenreMap).all()
        except Exception:
            rows = []
        for r in rows or []:
            try:
                raw = getattr(r, "genre", None)
                if raw and _canonical_genre_key(raw) == key:
                    return r
            except Exception:
                continue
        return None
    except Exception:
        return None

def _resolve_genre_mapping(db, raw_genres):
    """
    Return (matched: bool, matched_genre: str | None, category: models.Category | None, mapping: models.GenreMap | None)
    Tries the provided genres in order; first match wins (case-insensitive).
    Also:
      - handles composite tags like "Action & Adventure" by trying "action" and "adventure"
      - applies light synonym normalization (e.g., "sci-fi" -> "science fiction")
      - collapses punctuation and Unicode variants per Plex MediaTag behavior
    """
    if not raw_genres:
        return (False, None, None, None)
    for raw in raw_genres:
        candidates = _genre_candidate_keys(raw)
        for key in candidates:
            if not key:
                continue
            gm = _find_genre_map_case_insensitive(db, key)
            if gm:
                cat = db.query(models.Category).filter(models.Category.id == gm.category_id).first()
                if cat:
                    return (True, raw, cat, gm)
    return (False, None, None, None)

@app.get("/genres/map")
def list_genre_maps(db: Session = Depends(get_db)):
    """
    List all genre->category mappings.
    """
    rows = db.query(models.GenreMap).all()
    out = []
    for r in rows:
        cat = None
        try:
            cat = db.query(models.Category).filter(models.Category.id == r.category_id).first()
        except Exception:
            cat = None
        out.append({
            "id": r.id,
            "genre": r.genre,
            "category_id": r.category_id,
            "category": {"id": cat.id, "name": cat.name} if cat else None
        })
    return {"mappings": out, "count": len(out)}

@app.post("/genres/map")
def create_or_update_genre_map(payload: GenreMapCreate, db: Session = Depends(get_db)):
    """
    Create or update a mapping for a Plex genre to a NeXroll category.
    Case-insensitive on 'genre'. Enforces uniqueness by canonical normalized key.
    """
    genre_raw = (payload.genre or "").strip()
    if not genre_raw:
        raise HTTPException(status_code=422, detail="genre is required")

    # Validate category exists
    cat = db.query(models.Category).filter(models.Category.id == int(payload.category_id)).first()
    if not cat:
        raise HTTPException(status_code=404, detail=f"Category id {payload.category_id} not found")

    # Compute canonical key and upsert by canonical
    canon = _canonical_genre_key(genre_raw)
    existing = _find_genre_map_case_insensitive(db, canon)
    if existing:
        existing.genre = genre_raw  # keep canonical casing as provided
        try:
            existing.genre_norm = canon
        except Exception:
            pass
        existing.category_id = cat.id
        try:
            db.commit()
            db.refresh(existing)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Failed to update mapping: {e}")
        return {
            "updated": True,
            "mapping": {"id": existing.id, "genre": existing.genre, "category_id": existing.category_id}
        }

    # Create new map
    try:
        m = models.GenreMap(genre=genre_raw, genre_norm=canon, category_id=cat.id)
    except Exception:
        # Legacy DB without genre_norm column
        m = models.GenreMap(genre=genre_raw, category_id=cat.id)
    db.add(m)
    try:
        db.commit()
        db.refresh(m)
    except Exception as e:
        db.rollback()
        # Handle possible unique constraint violation
        raise HTTPException(status_code=500, detail=f"Failed to create mapping: {e}")
    return {
        "created": True,
        "mapping": {"id": m.id, "genre": m.genre, "category_id": m.category_id}
    }

@app.put("/genres/map/{map_id}")
def update_genre_map(map_id: int, payload: GenreMapUpdate, db: Session = Depends(get_db)):
    """
    Update an existing genre map by id.
    """
    m = db.query(models.GenreMap).filter(models.GenreMap.id == map_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")

    # Update genre with case-insensitive uniqueness
    if payload.genre is not None:
        newg = (payload.genre or "").strip()
        if not newg:
            raise HTTPException(status_code=422, detail="genre cannot be empty")
        canon = _canonical_genre_key(newg)
        dup = _find_genre_map_case_insensitive(db, canon)
        if dup and dup.id != m.id:
            raise HTTPException(status_code=409, detail="Another mapping already exists for this genre (case-insensitive)")
        m.genre = newg
        try:
            m.genre_norm = canon
        except Exception:
            pass

    if payload.category_id is not None:
        cat = db.query(models.Category).filter(models.Category.id == int(payload.category_id)).first()
        if not cat:
            raise HTTPException(status_code=404, detail=f"Category id {payload.category_id} not found")
        m.category_id = cat.id

    try:
        db.commit()
        db.refresh(m)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update mapping: {e}")

    return {"message": "Mapping updated", "mapping": {"id": m.id, "genre": m.genre, "category_id": m.category_id}}

@app.delete("/genres/map/{map_id}")
def delete_genre_map(map_id: int, db: Session = Depends(get_db)):
    m = db.query(models.GenreMap).filter(models.GenreMap.id == map_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Mapping not found")
    try:
        db.delete(m)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete mapping: {e}")
    return {"deleted": True, "id": map_id}

@app.post("/genres/resolve")
def resolve_genres(req: ResolveGenresRequest, db: Session = Depends(get_db)):
    """
    Given a list of genre strings (as Plex would provide), resolve the target category using the mapping table.
    """
    matched, matched_genre, cat, gm = _resolve_genre_mapping(db, getattr(req, "genres", []) or [])
    if not matched:
        return {"matched": False}
    return {
        "matched": True,
        "matched_genre": matched_genre,
        "category": {"id": cat.id, "name": cat.name, "plex_mode": getattr(cat, "plex_mode", "shuffle")},
        "mapping": {"id": gm.id, "genre": gm.genre}
    }

def _apply_category_to_plex_and_track(db: Session, category_id: int, ttl: int = 15) -> bool:
    """
    Use scheduler's category application (which handles translation and apply_to_plex flag),
    then set Setting.active_category and a short-lived override window to prevent the scheduler
    from immediately reverting the change. ttl is in minutes.
    """
    ok = scheduler._apply_category_to_plex(category_id, db)
    if ok:
        try:
            st = db.query(models.Setting).first()
            if not st:
                st = models.Setting(plex_url=None, plex_token=None, active_category=category_id)
                db.add(st)
            st.active_category = category_id
            try:
                st.override_expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=int(ttl))
            except Exception:
                st.override_expires_at = None
            st.updated_at = datetime.datetime.utcnow()
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    return ok

@app.post("/genres/apply")
def apply_preroll_by_genres(req: ResolveGenresRequest, ttl: int = 15, db: Session = Depends(get_db)):
    """
    Resolve the category by genres and apply its prerolls to Plex immediately.
    ttl: override window in minutes to prevent the scheduler from overriding immediately.
    """
    input_genres = getattr(req, "genres", []) or []
    matched, matched_genre, cat, gm = _resolve_genre_mapping(db, input_genres)
    if not matched or not cat:
        # Return 200 for webhook consumers (e.g., Tautulli) to avoid treating "no mapping" as an error.
        return {
            "applied": False,
            "matched": False,
            "message": "No matching genre mapping found",
            "input_genres": input_genres
        }
    ok = _apply_category_to_plex_and_track(db, cat.id, ttl=ttl)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to set preroll in Plex (check Plex connection and path mappings)")
    return {
        "applied": True,
        "matched_genre": matched_genre,
        "category": {"id": cat.id, "name": cat.name, "plex_mode": getattr(cat, "plex_mode", "shuffle")},
        "mapping": {"id": gm.id, "genre": gm.genre},
        "override_ttl_minutes": ttl
    }

@app.get("/settings/active-category")
def get_active_category(db: Session = Depends(get_db)):
    """Get the currently applied category"""
    try:
        setting = db.query(models.Setting).first()
        if not setting or not getattr(setting, "active_category", None):
            return {"active_category": None}

        category_id = getattr(setting, "active_category", None)
        category = db.query(models.Category).filter(models.Category.id == category_id).first()
        if not category:
            return {"active_category": None}

        return {
            "active_category": {
                "id": category.id,
                "name": category.name,
                "plex_mode": getattr(category, "plex_mode", "shuffle")
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/settings/active-fallback")
def get_active_fallback(db: Session = Depends(get_db)):
    """Get the fallback category from the most recently active schedule"""
    try:
        setting = db.query(models.Setting).first()
        fallback_id = getattr(setting, "last_schedule_fallback", None) if setting else None
        
        _verbose_log(f"GET /settings/active-fallback: last_schedule_fallback={fallback_id}")
        
        return {"active_fallback_category_id": fallback_id}
    except Exception as e:
        _file_log(f"Error getting active fallback: {str(e)}", level="ERROR")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/settings/timezone")
def get_timezone(db: Session = Depends(get_db)):
    """Get the user's timezone setting"""
    try:
        setting = db.query(models.Setting).first()
        if not setting:
            return {"timezone": "UTC"}
        
        timezone = getattr(setting, "timezone", "UTC")
        return {"timezone": timezone or "UTC"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.put("/settings/timezone")
async def set_timezone(request: Request, db: Session = Depends(get_db)):
    """Set the user's timezone"""
    try:
        body = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Invalid request body")
    
    tz = body.get("timezone", "UTC")
    if isinstance(tz, str):
        tz = tz.strip()
    else:
        tz = "UTC"
    
    # Validate timezone
    try:
        import pytz
        pytz.timezone(tz)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz}")
    
    try:
        setting = db.query(models.Setting).first()
        if not setting:
            setting = models.Setting(plex_url=None, plex_token=None, timezone=tz)
            db.add(setting)
        else:
            setting.timezone = tz
        
        db.commit()
        return {"timezone": tz, "message": "Timezone updated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.get("/settings/timezones")
def get_available_timezones():
    """Get list of all available timezones"""
    import pytz
    timezones = []
    for tz in pytz.all_timezones:
        timezones.append({
            "value": tz,
            "label": tz.replace("_", " ")
        })
    return {"timezones": timezones}

@app.get("/settings/dashboard-tile-order")
def get_dashboard_tile_order(db: Session = Depends(get_db)):
    """Get the dashboard tile order from settings"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {"dashboard_tile_order": None}

    order_str = getattr(setting, "dashboard_tile_order", None)
    if not order_str:
        return {"dashboard_tile_order": None}

    try:
        order = json.loads(order_str)
        return {"dashboard_tile_order": order}
    except (json.JSONDecodeError, TypeError):
        return {"dashboard_tile_order": None}

@app.put("/settings/dashboard-tile-order")
def update_dashboard_tile_order(order: list[str], db: Session = Depends(get_db)):
    """Update the dashboard tile order in settings"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)

    try:
        order_json = json.dumps(order)
        setting.dashboard_tile_order = order_json
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
        return {"message": "Dashboard tile order updated"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update dashboard tile order: {e}")

@app.get("/settings/genre")
def get_genre_settings(db: Session = Depends(get_db)):
    """Get genre-based preroll settings"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {
            "genre_auto_apply": False,
            "genre_priority_mode": "schedules_override",
            "genre_override_ttl_seconds": 10,
            "genre_aggressive_intercept_enabled": False
        }
    return {
        "genre_auto_apply": getattr(setting, "genre_auto_apply", True),
        "genre_priority_mode": getattr(setting, "genre_priority_mode", "schedules_override"),
        "genre_override_ttl_seconds": getattr(setting, "genre_override_ttl_seconds", 10),
        "genre_aggressive_intercept_enabled": getattr(setting, "genre_aggressive_intercept_enabled", False)
    }

@app.get("/settings/dashboard-tile-order")
def get_dashboard_tile_order(db: Session = Depends(get_db)):
    """Get the saved dashboard tile order"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {"tile_order": []}

    try:
        tile_order = getattr(setting, "dashboard_tile_order", None)
        if tile_order:
            return {"tile_order": json.loads(tile_order)}
        else:
            return {"tile_order": []}
    except Exception:
        return {"tile_order": []}

@app.put("/settings/dashboard-tile-order")
def set_dashboard_tile_order(tile_order: list[str], db: Session = Depends(get_db)):
    """Save the dashboard tile order"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)

    try:
        setting.dashboard_tile_order = json.dumps(tile_order)
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
        return {"saved": True, "tile_order": tile_order}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save dashboard tile order: {str(e)}")

@app.put("/settings/genre")
def update_genre_settings(
    genre_auto_apply: bool = None,
    genre_priority_mode: str = None,
    genre_override_ttl_seconds: int = None,
    genre_aggressive_intercept_enabled: bool = None,
    db: Session = Depends(get_db)
):
    """Update genre-based preroll settings"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)

    updated = False
    if genre_auto_apply is not None:
        setting.genre_auto_apply = genre_auto_apply
        updated = True
    if genre_priority_mode is not None:
        if genre_priority_mode not in ["schedules_override", "genres_override"]:
            raise HTTPException(status_code=422, detail="Invalid priority mode")
        setting.genre_priority_mode = genre_priority_mode
        updated = True
    if genre_override_ttl_seconds is not None:
        if genre_override_ttl_seconds < 1 or genre_override_ttl_seconds > 300:
            raise HTTPException(status_code=422, detail="TTL must be between 1 and 300 seconds")
        setting.genre_override_ttl_seconds = genre_override_ttl_seconds
        updated = True
    if genre_aggressive_intercept_enabled is not None:
        setting.genre_aggressive_intercept_enabled = genre_aggressive_intercept_enabled
        updated = True

    if updated:
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()

    return {"message": "Settings updated"}

@app.get("/settings/verbose-logging")
def get_verbose_logging(db: Session = Depends(get_db)):
    """Get verbose logging setting"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {"verbose_logging": False}
    return {"verbose_logging": getattr(setting, 'verbose_logging', False)}

@app.put("/settings/verbose-logging")
def update_verbose_logging(verbose_logging: bool, db: Session = Depends(get_db)):
    """Update verbose logging setting"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    
    setting.verbose_logging = verbose_logging
    setting.updated_at = datetime.datetime.utcnow()
    db.commit()
    
    status = "enabled" if verbose_logging else "disabled"
    print(f"Verbose logging {status}")
    _file_log(f"Verbose logging {status}")
    
    return {"message": f"Verbose logging {status}", "verbose_logging": verbose_logging}

@app.get("/settings/passive-mode")
def get_passive_mode(db: Session = Depends(get_db)):
    """Get passive mode setting (coexistence mode for other preroll managers)"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {"passive_mode": False}
    return {"passive_mode": getattr(setting, 'passive_mode', False)}

@app.put("/settings/passive-mode")
def update_passive_mode(passive_mode: bool, db: Session = Depends(get_db)):
    """Update passive mode setting (coexistence mode for other preroll managers)"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    
    setting.passive_mode = passive_mode
    setting.updated_at = datetime.datetime.utcnow()
    db.commit()
    
    status = "enabled" if passive_mode else "disabled"
    print(f"Passive mode (coexistence) {status}")
    _file_log(f"Passive mode (coexistence) {status}")
    
    return {"message": f"Passive mode {status}", "passive_mode": passive_mode}

@app.get("/settings/clear-when-inactive")
def get_clear_when_inactive(db: Session = Depends(get_db)):
    """Get clear-when-inactive setting (clear prerolls when no schedule is active)"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {"clear_when_inactive": False}
    return {"clear_when_inactive": getattr(setting, 'clear_when_inactive', False)}

@app.put("/settings/clear-when-inactive")
def update_clear_when_inactive(clear_when_inactive: bool, db: Session = Depends(get_db)):
    """Update clear-when-inactive setting (clear prerolls when no schedule is active)"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    
    setting.clear_when_inactive = clear_when_inactive
    setting.updated_at = datetime.datetime.utcnow()
    db.commit()
    
    status = "enabled" if clear_when_inactive else "disabled"
    print(f"Clear when inactive {status}")
    _file_log(f"Clear when inactive {status}")
    
    return {"message": f"Clear when inactive {status}", "clear_when_inactive": clear_when_inactive}

# ==============================================================================
# NeX-Up: Radarr Integration for Upcoming Movie Trailers
# ==============================================================================

# Global sync progress state for SSE streaming
_nexup_sync_progress = {
    "syncing": False,
    "type": None,  # "radarr" or "sonarr"
    "status": "",
    "current_item": "",
    "progress": 0,
    "total": 0,
    "downloaded": 0,
    "skipped": 0,
    "errors": 0
}

@app.get("/nexup/sync-progress")
async def get_sync_progress():
    """
    Server-Sent Events endpoint for real-time sync progress
    """
    from starlette.responses import StreamingResponse
    import asyncio
    import json
    
    async def event_stream():
        try:
            while True:
                progress_data = _nexup_sync_progress.copy()
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Stop streaming when sync is complete
                if not progress_data.get("syncing", False) and progress_data.get("progress", 0) >= 100:
                    await asyncio.sleep(0.3)
                    break
                
                await asyncio.sleep(0.3)  # Update every 300ms
        except Exception as e:
            _file_log(f"Sync progress stream error: {e}")
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/nexup/settings")
def get_nexup_settings(db: Session = Depends(get_db)):
    """Get all NeX-Up settings"""
    setting = db.query(models.Setting).first()
    if not setting:
        return {
            "enabled": False,
            "radarr_url": None,
            "radarr_connected": False,
            "storage_path": None,
            "quality": "1080",
            "days_ahead": 90,
            "max_trailers": 10,
            "max_storage_gb": 5.0,
            "trailers_per_playback": 2,
            "playback_order": "release_date",
            "auto_refresh_hours": 24,
            "max_trailer_duration": 180,
            "last_sync": None,
            "category_id": None,
            "download_delay": 5,
            "max_concurrent": 1,
            "bulk_warning_threshold": 5,
            "sonarr_enabled": False,
            "sonarr_url": None,
            "sonarr_connected": False,
            "tv_category_id": None
        }
    
    return {
        "enabled": getattr(setting, 'nexup_enabled', False),
        "radarr_url": getattr(setting, 'nexup_radarr_url', None),
        "radarr_connected": bool(getattr(setting, 'nexup_radarr_url', None) and getattr(setting, 'nexup_radarr_api_key', None)),
        "storage_path": getattr(setting, 'nexup_storage_path', None),
        "quality": getattr(setting, 'nexup_quality', '1080'),
        "days_ahead": getattr(setting, 'nexup_days_ahead', 90),
        "max_trailers": getattr(setting, 'nexup_max_trailers', 10),
        "max_storage_gb": getattr(setting, 'nexup_max_storage_gb', 5.0),
        "trailers_per_playback": getattr(setting, 'nexup_trailers_per_playback', 2),
        "playback_order": getattr(setting, 'nexup_playback_order', 'release_date'),
        "auto_refresh_hours": getattr(setting, 'nexup_auto_refresh_hours', 24),
        "max_trailer_duration": getattr(setting, 'nexup_max_trailer_duration', 180),
        "last_sync": getattr(setting, 'nexup_last_sync', None).isoformat() if getattr(setting, 'nexup_last_sync', None) else None,
        "category_id": getattr(setting, 'nexup_category_id', None),
        "download_delay": getattr(setting, 'nexup_download_delay', 5),
        "max_concurrent": getattr(setting, 'nexup_max_concurrent', 1),
        "bulk_warning_threshold": getattr(setting, 'nexup_bulk_warning_threshold', 5),
        "tmdb_api_key": getattr(setting, 'nexup_tmdb_api_key', None),
        # Sonarr settings
        "sonarr_enabled": getattr(setting, 'nexup_sonarr_enabled', False),
        "sonarr_url": getattr(setting, 'nexup_sonarr_url', None),
        "sonarr_connected": bool(getattr(setting, 'nexup_sonarr_url', None) and getattr(setting, 'nexup_sonarr_api_key', None)),
        "tv_category_id": getattr(setting, 'nexup_tv_category_id', None),
        "last_sonarr_sync": getattr(setting, 'nexup_last_sonarr_sync', None).isoformat() if getattr(setting, 'nexup_last_sonarr_sync', None) else None
    }

@app.put("/nexup/settings")
def update_nexup_settings(
    enabled: Optional[bool] = None,
    sonarr_enabled: Optional[bool] = None,
    storage_path: Optional[str] = None,
    quality: Optional[str] = None,
    days_ahead: Optional[int] = None,
    max_trailers: Optional[int] = None,
    max_storage_gb: Optional[float] = None,
    trailers_per_playback: Optional[int] = None,
    playback_order: Optional[str] = None,
    auto_refresh_hours: Optional[int] = None,
    max_trailer_duration: Optional[int] = None,
    download_delay: Optional[int] = None,
    max_concurrent: Optional[int] = None,
    bulk_warning_threshold: Optional[int] = None,
    tmdb_api_key: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Update NeX-Up settings"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    
    if enabled is not None:
        setting.nexup_enabled = enabled
    if sonarr_enabled is not None:
        setting.nexup_sonarr_enabled = sonarr_enabled
    if storage_path is not None:
        setting.nexup_storage_path = storage_path
        # Create directory if it doesn't exist
        if storage_path:
            try:
                Path(storage_path).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                _file_log(f"Failed to create NeX-Up storage path: {e}")
        
        # Auto-create the NeX-Up Trailers system category for movies if it doesn't exist
        nexup_category = db.query(models.Category).filter(
            models.Category.name == "NeX-Up Movie Trailers"
        ).first()
        if not nexup_category:
            nexup_category = models.Category(
                name="NeX-Up Movie Trailers",
                description="System category for upcoming movie trailers from Radarr. Managed automatically by NeX-Up.",
                plex_mode="shuffle",
                apply_to_plex=False,
                is_system=True
            )
            db.add(nexup_category)
            db.commit()
            db.refresh(nexup_category)
            _file_log("Created NeX-Up Trailers system category")
        
        # Store the category ID in settings
        setting.nexup_category_id = nexup_category.id
        
        # Auto-create the NeX-Up TV Trailers system category for TV shows if it doesn't exist
        nexup_tv_category = db.query(models.Category).filter(
            models.Category.name == "NeX-Up TV Trailers"
        ).first()
        if not nexup_tv_category:
            nexup_tv_category = models.Category(
                name="NeX-Up TV Trailers",
                description="System category for upcoming TV show trailers from Sonarr. Managed automatically by NeX-Up.",
                plex_mode="shuffle",
                apply_to_plex=False,
                is_system=True
            )
            db.add(nexup_tv_category)
            db.commit()
            db.refresh(nexup_tv_category)
            _file_log("Created NeX-Up TV Trailers system category")
        elif not nexup_tv_category.description:
            # Update description if missing
            nexup_tv_category.description = "System category for upcoming TV show trailers from Sonarr. Managed automatically by NeX-Up."
            nexup_tv_category.is_system = True
            db.commit()
            _file_log("Updated NeX-Up TV Trailers category description")
        
        # Store the TV category ID in settings
        setting.nexup_tv_category_id = nexup_tv_category.id
    if quality is not None:
        setting.nexup_quality = quality
    if days_ahead is not None:
        setting.nexup_days_ahead = days_ahead
    if max_trailers is not None:
        setting.nexup_max_trailers = max_trailers
    if max_storage_gb is not None:
        setting.nexup_max_storage_gb = max_storage_gb
    if trailers_per_playback is not None:
        setting.nexup_trailers_per_playback = trailers_per_playback
    if playback_order is not None:
        setting.nexup_playback_order = playback_order
    if auto_refresh_hours is not None:
        setting.nexup_auto_refresh_hours = auto_refresh_hours
    if max_trailer_duration is not None:
        setting.nexup_max_trailer_duration = max(0, min(600, max_trailer_duration))  # 0-600 seconds (0 = no limit)
    if download_delay is not None:
        setting.nexup_download_delay = max(0, min(60, download_delay))  # 0-60 seconds
    if max_concurrent is not None:
        setting.nexup_max_concurrent = max(1, min(5, max_concurrent))  # 1-5 concurrent
    if bulk_warning_threshold is not None:
        setting.nexup_bulk_warning_threshold = max(1, min(50, bulk_warning_threshold))  # 1-50 trailers
    if tmdb_api_key is not None:
        setting.nexup_tmdb_api_key = tmdb_api_key if tmdb_api_key.strip() else None
    
    setting.updated_at = datetime.datetime.utcnow()
    db.commit()
    
    _file_log(f"NeX-Up settings updated")
    return {"message": "NeX-Up settings updated", "success": True}

@app.post("/nexup/radarr/connect")
async def connect_radarr(
    url: str,
    api_key: str,
    db: Session = Depends(get_db)
):
    """Connect to Radarr and test the connection"""
    try:
        from backend.radarr_connector import RadarrConnector
        
        # Clean up URL
        url = url.strip().rstrip('/')
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        
        # Test connection
        connector = RadarrConnector(url, api_key)
        result = await connector.test_connection()
        
        if result['success']:
            # Save credentials
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=None, plex_token=None)
                db.add(setting)
                db.commit()
                db.refresh(setting)
            
            setting.nexup_radarr_url = url
            setting.nexup_radarr_api_key = api_key
            setting.updated_at = datetime.datetime.utcnow()
            db.commit()
            
            _file_log(f"Radarr connected: {result.get('appName')} v{result.get('version')}")
            return {
                "success": True,
                "message": f"Connected to {result.get('appName', 'Radarr')} v{result.get('version', 'Unknown')}",
                "version": result.get('version'),
                "appName": result.get('appName'),
                "instanceName": result.get('instanceName')
            }
        else:
            return {
                "success": False,
                "message": result.get('message', 'Connection failed')
            }
    except Exception as e:
        _file_log(f"Radarr connect error: {str(e)}")
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }

@app.delete("/nexup/radarr/disconnect")
def disconnect_radarr(db: Session = Depends(get_db)):
    """Disconnect from Radarr"""
    setting = db.query(models.Setting).first()
    if setting:
        setting.nexup_radarr_url = None
        setting.nexup_radarr_api_key = None
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
    
    _file_log("Radarr disconnected")
    return {"success": True, "message": "Radarr disconnected"}

@app.get("/nexup/radarr/upcoming")
async def get_upcoming_movies(db: Session = Depends(get_db)):
    """Get list of upcoming movies from Radarr"""
    setting = db.query(models.Setting).first()
    if not setting or not setting.nexup_radarr_url or not setting.nexup_radarr_api_key:
        raise HTTPException(status_code=400, detail="Radarr not connected")
    
    from backend.radarr_connector import RadarrConnector
    
    connector = RadarrConnector(setting.nexup_radarr_url, setting.nexup_radarr_api_key)
    days_ahead = getattr(setting, 'nexup_days_ahead', 90) or 90
    
    movies = await connector.get_upcoming_movies(days_ahead)
    
    # Get existing trailers to mark which are already downloaded
    existing_trailers = db.query(models.ComingSoonTrailer).all()
    existing_radarr_ids = {t.radarr_movie_id for t in existing_trailers}
    
    for movie in movies:
        movie['downloaded'] = movie['radarr_id'] in existing_radarr_ids
    
    return {
        "movies": movies,
        "total": len(movies),
        "days_ahead": days_ahead
    }

@app.get("/nexup/radarr/debug/{radarr_id}")
async def debug_radarr_movie(radarr_id: int, db: Session = Depends(get_db)):
    """Debug endpoint to see raw Radarr movie data including trailer info"""
    setting = db.query(models.Setting).first()
    if not setting or not setting.nexup_radarr_url or not setting.nexup_radarr_api_key:
        raise HTTPException(status_code=400, detail="Radarr not connected")
    
    from backend.radarr_connector import RadarrConnector
    
    connector = RadarrConnector(setting.nexup_radarr_url, setting.nexup_radarr_api_key)
    movie = await connector.get_movie_by_id(radarr_id)
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found in Radarr")
    
    # Extract trailer-related fields
    return {
        "id": movie.get('id'),
        "title": movie.get('title'),
        "year": movie.get('year'),
        "tmdbId": movie.get('tmdbId'),
        "imdbId": movie.get('imdbId'),
        "youTubeTrailerId": movie.get('youTubeTrailerId'),
        "trailer_url": f"https://www.youtube.com/watch?v={movie['youTubeTrailerId']}" if movie.get('youTubeTrailerId') else None,
        "status": movie.get('status'),
        "hasFile": movie.get('hasFile'),
        "monitored": movie.get('monitored'),
        "digitalRelease": movie.get('digitalRelease'),
        "physicalRelease": movie.get('physicalRelease'),
        "inCinemas": movie.get('inCinemas'),
        # Include all fields for debugging
        "_raw_keys": list(movie.keys())
    }

# ============================================================================
# SONARR INTEGRATION ENDPOINTS
# ============================================================================

@app.post("/nexup/sonarr/connect")
async def connect_sonarr(
    url: str,
    api_key: str,
    db: Session = Depends(get_db)
):
    """Connect to Sonarr and test the connection"""
    try:
        from backend.sonarr_connector import SonarrConnector
        
        # Clean up URL
        url = url.strip().rstrip('/')
        if not url.startswith(('http://', 'https://')):
            url = f"http://{url}"
        
        # Test connection
        connector = SonarrConnector(url, api_key)
        result = await connector.test_connection()
        
        if result['success']:
            # Save credentials
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=None, plex_token=None)
                db.add(setting)
                db.commit()
                db.refresh(setting)
            
            setting.nexup_sonarr_url = url
            setting.nexup_sonarr_api_key = api_key
            setting.nexup_sonarr_enabled = True
            setting.updated_at = datetime.datetime.utcnow()
            db.commit()
            
            _file_log(f"Sonarr connected: {result.get('appName')} v{result.get('version')}")
            return {
                "success": True,
                "message": f"Connected to {result.get('appName', 'Sonarr')} v{result.get('version', 'Unknown')}",
                "version": result.get('version'),
                "appName": result.get('appName'),
                "instanceName": result.get('instanceName')
            }
        else:
            return {
                "success": False,
                "message": result.get('message', 'Connection failed')
            }
    except Exception as e:
        _file_log(f"Sonarr connect error: {str(e)}")
        return {
            "success": False,
            "message": f"Connection error: {str(e)}"
        }

@app.delete("/nexup/sonarr/disconnect")
def disconnect_sonarr(db: Session = Depends(get_db)):
    """Disconnect from Sonarr"""
    setting = db.query(models.Setting).first()
    if setting:
        setting.nexup_sonarr_url = None
        setting.nexup_sonarr_api_key = None
        setting.nexup_sonarr_enabled = False
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
    
    _file_log("Sonarr disconnected")
    return {"success": True, "message": "Sonarr disconnected"}

@app.get("/nexup/sonarr/upcoming")
async def get_upcoming_shows(db: Session = Depends(get_db)):
    """Get list of upcoming TV show premieres from Sonarr"""
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, 'nexup_sonarr_url', None) or not getattr(setting, 'nexup_sonarr_api_key', None):
        _file_log("Sonarr: Get upcoming shows failed - not connected")
        raise HTTPException(status_code=400, detail="Sonarr not connected")
    
    from backend.sonarr_connector import SonarrConnector
    
    _file_log(f"Sonarr: Fetching upcoming shows from {setting.nexup_sonarr_url}")
    connector = SonarrConnector(setting.nexup_sonarr_url, setting.nexup_sonarr_api_key)
    days_ahead = getattr(setting, 'nexup_days_ahead', 90) or 90
    
    # Use the calendar-based premiere detection for accurate dates
    shows = await connector.get_upcoming_premieres(days_ahead)
    _file_log(f"Sonarr: Found {len(shows)} upcoming shows within {days_ahead} days")
    
    # Get existing TV trailers to mark which are already downloaded (only successful downloads)
    existing_trailers = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.status == 'downloaded'
    ).all()
    existing_keys = {f"{t.sonarr_series_id}_S{t.season_number}" for t in existing_trailers}
    
    for show in shows:
        key = f"{show['sonarr_id']}_S{show['season_number']}"
        show['downloaded'] = key in existing_keys
        # Also check if trailer exists in DB
        show['has_trailer'] = True  # We'll try to find one via TMDB
    
    return {
        "shows": shows,
        "total": len(shows),
        "days_ahead": days_ahead
    }

@app.get("/nexup/sonarr/trailers")
def get_sonarr_trailers(db: Session = Depends(get_db)):
    """Get all downloaded TV show trailers"""
    trailers = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.status == 'downloaded'
    ).order_by(models.ComingSoonTVTrailer.release_date.asc()).all()
    
    return [{
        "id": t.id,
        "sonarr_series_id": t.sonarr_series_id,
        "tvdb_id": t.tvdb_id,
        "title": t.title,
        "year": t.year,
        "season_number": t.season_number,
        "network": t.network,
        "release_date": t.release_date.isoformat() if t.release_date else None,
        "release_type": t.release_type,
        "local_path": t.local_path,
        "file_size_mb": t.file_size_mb,
        "poster_url": t.poster_url,
        "is_enabled": t.is_enabled,
        "status": t.status
    } for t in trailers]

@app.get("/nexup/trailers/download/tv")
async def download_tv_trailer(
    sonarr_series_id: int,
    season_number: int = 1,
    db: Session = Depends(get_db)
):
    """Download a trailer for a TV show from Sonarr"""
    _file_log(f"Sonarr: Download request for series_id={sonarr_series_id}, season={season_number}")
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, 'nexup_sonarr_url', None):
        _file_log("Sonarr: Download failed - not connected")
        raise HTTPException(status_code=400, detail="Sonarr not connected")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        _file_log("Sonarr: Download failed - storage path not configured")
        raise HTTPException(status_code=400, detail="Storage path not configured")
    
    # Check if already downloaded
    existing = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.sonarr_series_id == sonarr_series_id,
        models.ComingSoonTVTrailer.season_number == season_number,
        models.ComingSoonTVTrailer.status == 'downloaded'
    ).first()
    
    if existing:
        _file_log(f"Sonarr: Trailer already downloaded for series_id={sonarr_series_id}")
        return {"success": False, "message": "Trailer already downloaded", "trailer_id": existing.id}
    
    # Delete any failed/error records so we can retry
    db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.sonarr_series_id == sonarr_series_id,
        models.ComingSoonTVTrailer.season_number == season_number,
        models.ComingSoonTVTrailer.status.in_(['error', 'downloading'])
    ).delete(synchronize_session=False)
    db.commit()
    
    from backend.sonarr_connector import SonarrConnector, TVTrailerFetcher
    from backend.radarr_connector import TrailerDownloader
    
    # Get show info from Sonarr
    connector = SonarrConnector(setting.nexup_sonarr_url, setting.nexup_sonarr_api_key)
    all_series = await connector.get_all_series()
    
    show_info = None
    for series in all_series:
        if series.get('id') == sonarr_series_id:
            show_info = series
            break
    
    if not show_info:
        _file_log(f"Sonarr: Show not found in Sonarr for series_id={sonarr_series_id}")
        raise HTTPException(status_code=404, detail="Show not found in Sonarr")
    
    _file_log(f"Sonarr: Found show '{show_info.get('title')}' (TVDB: {show_info.get('tvdbId')}, IMDB: {show_info.get('imdbId')})")
    
    # Get trailer URL from TMDB or IMDB
    tmdb_api_key = getattr(setting, 'nexup_tmdb_api_key', None)
    fetcher = TVTrailerFetcher(tmdb_api_key=tmdb_api_key)
    _file_log(f"Sonarr: Searching for trailers for '{show_info.get('title')}' S{season_number}")
    trailers = await fetcher.get_season_trailers(
        tmdb_id=None,
        tvdb_id=show_info.get('tvdbId'),
        imdb_id=show_info.get('imdbId'),
        season_number=season_number
    ) if show_info.get('tvdbId') or show_info.get('imdbId') else []
    
    # If no season-specific trailers, try show-level trailers
    if not trailers:
        _file_log(f"Sonarr: No season-specific trailers found, trying show-level trailers")
        trailers = await fetcher.get_tv_trailers(
            tvdb_id=show_info.get('tvdbId'),
            imdb_id=show_info.get('imdbId')
        )
    
    if not trailers:
        _file_log(f"Sonarr: No trailers found for '{show_info.get('title')}'")
        raise HTTPException(status_code=404, detail="No trailer found for this show")
    
    _file_log(f"Sonarr: Found {len(trailers)} trailer(s) for '{show_info.get('title')}'")
    
    # Use first available trailer
    trailer_info = trailers[0]
    trailer_url = trailer_info['url']
    
    # Create trailer record
    trailer = models.ComingSoonTVTrailer(
        sonarr_series_id=sonarr_series_id,
        tvdb_id=show_info.get('tvdbId'),
        imdb_id=show_info.get('imdbId'),
        title=show_info.get('title', 'Unknown'),
        year=show_info.get('year'),
        season_number=season_number,
        overview=show_info.get('overview'),
        network=show_info.get('network'),
        release_type='new_show' if season_number == 1 else 'new_season',
        trailer_url=trailer_url,
        status='downloading'
    )
    
    # Get poster URL
    for image in show_info.get('images', []):
        if image.get('coverType') == 'poster':
            trailer.poster_url = image.get('remoteUrl') or image.get('url')
        elif image.get('coverType') == 'fanart':
            trailer.fanart_url = image.get('remoteUrl') or image.get('url')
    
    db.add(trailer)
    db.commit()
    db.refresh(trailer)
    
    # Download the trailer
    quality = getattr(setting, 'nexup_quality', '1080') or '1080'
    downloader = TrailerDownloader(storage_path, quality, tmdb_api_key=tmdb_api_key)
    
    try:
        season_str = f"S{season_number:02d}" if season_number else ""
        safe_title = re.sub(r'[^\w\s-]', '', show_info.get('title', 'Unknown')).strip()
        filename = f"{safe_title} {season_str} Trailer"
        
        _file_log(f"Sonarr: Downloading trailer from {trailer_url}")
        result = await downloader.download_trailer(
            trailer_url, 
            filename, 
            tvdb_id=show_info.get('tvdbId')
        )
        
        if result and result.get('path'):
            trailer.local_path = result['path']
            trailer.file_size_mb = result.get('size_mb')
            trailer.duration_seconds = result.get('duration')
            trailer.resolution = result.get('resolution')
            trailer.status = 'downloaded'
            trailer.downloaded_at = datetime.datetime.utcnow()
            
            _file_log(f"Sonarr: Successfully downloaded '{show_info.get('title')}' trailer ({result.get('size_mb', 0):.1f} MB) to {result['path']}")
            
            # Create preroll entry
            await _create_preroll_from_tv_trailer(trailer, setting, db)
            
            db.commit()
            
            return {
                "success": True,
                "message": "Trailer downloaded successfully",
                "trailer_id": trailer.id,
                "path": result.get('path')
            }
        else:
            trailer.status = 'error'
            trailer.error_message = 'Download failed - no file returned'
            _file_log(f"Sonarr: Download failed for '{show_info.get('title')}'", level="ERROR")
            
            db.commit()
            
            return {
                "success": False,
                "message": "Download failed",
                "trailer_id": trailer.id,
                "path": None
            }
        
    except Exception as e:
        trailer.status = 'error'
        trailer.error_message = str(e)
        db.commit()
        _file_log(f"Sonarr: Download exception for series_id={sonarr_series_id}: {str(e)}", level="ERROR")
        raise HTTPException(status_code=500, detail=str(e))

async def _create_preroll_from_tv_trailer(trailer, setting, db):
    """Create a preroll entry from a downloaded TV trailer"""
    # Get or create the TV trailers category
    category_id = getattr(setting, 'nexup_tv_category_id', None)
    if not category_id:
        # Check if category already exists
        existing_category = db.query(models.Category).filter(
            models.Category.name == "NeX-Up TV Trailers"
        ).first()
        
        if existing_category:
            category = existing_category
            # Update description if missing
            if not category.description:
                category.description = "System category for upcoming TV show trailers from Sonarr. Managed automatically by NeX-Up."
                category.is_system = True
                db.commit()
        else:
            # Create a category for TV trailers
            category = models.Category(
                name="NeX-Up TV Trailers",
                description="System category for upcoming TV show trailers from Sonarr. Managed automatically by NeX-Up.",
                plex_mode="shuffle",
                apply_to_plex=False,
                is_system=True
            )
            db.add(category)
            db.commit()
            db.refresh(category)
        
        setting.nexup_tv_category_id = category.id
        category_id = category.id
        db.commit()
    
    # Check if preroll already exists
    existing = db.query(models.Preroll).filter(
        models.Preroll.path == trailer.local_path
    ).first()
    
    if existing:
        return existing
    
    # Create preroll
    season_str = f" S{trailer.season_number}" if trailer.season_number else ""
    display_name = f"{trailer.title}{season_str} - Trailer"
    filename = Path(trailer.local_path).name if trailer.local_path else f"tv_trailer_{trailer.id}.mp4"
    
    preroll = models.Preroll(
        filename=filename,
        display_name=display_name,
        path=trailer.local_path,
        category_id=category_id,
        thumbnail=trailer.poster_url or "",
        tags="[]",
        duration=trailer.duration_seconds,
        managed=False
    )
    db.add(preroll)
    db.commit()
    
    return preroll

@app.delete("/nexup/trailers/tv/{trailer_id}")
def delete_tv_trailer(trailer_id: int, db: Session = Depends(get_db)):
    """Delete a TV show trailer"""
    trailer = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.id == trailer_id
    ).first()
    
    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")
    
    # Delete the file
    if trailer.local_path and os.path.exists(trailer.local_path):
        try:
            os.remove(trailer.local_path)
        except Exception as e:
            _file_log(f"Failed to delete TV trailer file: {e}")
    
    # Delete associated preroll
    if trailer.local_path:
        preroll = db.query(models.Preroll).filter(
            models.Preroll.path == trailer.local_path
        ).first()
        if preroll:
            db.delete(preroll)
    
    db.delete(trailer)
    db.commit()
    
    return {"success": True, "message": "TV trailer deleted"}

@app.put("/nexup/trailers/tv/{trailer_id}/toggle")
def toggle_tv_trailer(trailer_id: int, db: Session = Depends(get_db)):
    """Toggle a TV show trailer's enabled state"""
    trailer = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.id == trailer_id
    ).first()
    
    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")
    
    trailer.is_enabled = not trailer.is_enabled
    trailer.updated_at = datetime.datetime.utcnow()
    
    # Also toggle the associated preroll
    if trailer.local_path:
        preroll = db.query(models.Preroll).filter(
            models.Preroll.path == trailer.local_path
        ).first()
        if preroll:
            preroll.enabled = trailer.is_enabled
    
    db.commit()
    
    return {"success": True, "is_enabled": trailer.is_enabled}

@app.post("/nexup/sonarr/sync")
async def sync_sonarr_trailers(db: Session = Depends(get_db)):
    """Sync TV show trailers from Sonarr - download new ones, expire old ones"""
    global _nexup_sync_progress
    
    _file_log("Sonarr Sync: Starting TV trailer sync")
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, 'nexup_sonarr_url', None):
        _file_log("Sonarr Sync: Failed - not connected")
        raise HTTPException(status_code=400, detail="Sonarr not connected")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        _file_log("Sonarr Sync: Failed - storage path not configured")
        raise HTTPException(status_code=400, detail="Storage path not configured")
    
    # Initialize progress tracking
    _nexup_sync_progress = {
        "syncing": True,
        "type": "sonarr",
        "status": "Connecting to Sonarr...",
        "current_item": "",
        "progress": 0,
        "total": 0,
        "downloaded": 0,
        "skipped": 0,
        "errors": 0
    }
    
    from backend.sonarr_connector import SonarrConnector, TVTrailerFetcher
    from backend.radarr_connector import TrailerDownloader
    
    connector = SonarrConnector(setting.nexup_sonarr_url, setting.nexup_sonarr_api_key)
    days_ahead = getattr(setting, 'nexup_days_ahead', 90) or 90
    max_trailers = getattr(setting, 'nexup_max_trailers', 10) or 10
    download_delay = getattr(setting, 'nexup_download_delay', 5) or 5
    
    _file_log(f"Sonarr Sync: Config - days_ahead={days_ahead}, max_trailers={max_trailers}, delay={download_delay}s")
    
    results = {
        "checked": 0,
        "downloaded": 0,
        "expired": 0,
        "errors": [],
        "eligible": 0
    }
    
    # ========================================
    # CLEANUP: Expire trailers for aired shows
    # ========================================
    _nexup_sync_progress["status"] = "Checking for expired TV trailers..."
    
    # Get all series from Sonarr to check download status
    all_series = await connector.get_all_series()
    
    # Build a map of series_id -> {season_number: episodeFileCount}
    series_download_status = {}
    for series in all_series:
        series_id = series.get('id')
        series_download_status[series_id] = {
            'title': series.get('title', 'Unknown'),
            'seasons': {}
        }
        for season in series.get('seasons', []):
            season_num = season.get('seasonNumber', 0)
            stats = season.get('statistics', {})
            series_download_status[series_id]['seasons'][season_num] = stats.get('episodeFileCount', 0)
    
    # Get existing trailers and check for expired ones
    existing_trailers = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.status == 'downloaded'
    ).all()
    
    today = datetime.datetime.now().date()
    grace_period_days = 5  # Keep trailer for 5 days after air date
    
    for trailer in existing_trailers:
        should_expire = False
        expire_reason = ""
        
        # Check 1: Has Sonarr downloaded episodes for this season?
        series_info = series_download_status.get(trailer.sonarr_series_id)
        if series_info:
            season_file_count = series_info['seasons'].get(trailer.season_number, 0)
            if season_file_count > 0:
                should_expire = True
                expire_reason = f"Season has {season_file_count} episode(s) downloaded"
        
        # Check 2: Has the release date passed by more than grace period?
        if not should_expire and trailer.release_date:
            release_date = trailer.release_date.date() if hasattr(trailer.release_date, 'date') else trailer.release_date
            days_since_release = (today - release_date).days
            if days_since_release > grace_period_days:
                should_expire = True
                expire_reason = f"Aired {days_since_release} days ago (grace period: {grace_period_days} days)"
        
        if should_expire:
            _file_log(f"Sonarr Sync: Expiring trailer for '{trailer.title}' S{trailer.season_number} - {expire_reason}")
            
            # Delete trailer file
            if trailer.local_path and os.path.exists(trailer.local_path):
                try:
                    os.remove(trailer.local_path)
                    _file_log(f"Sonarr Sync: Deleted trailer file: {trailer.local_path}")
                except Exception as e:
                    _file_log(f"Sonarr Sync: Failed to delete trailer file: {e}", level="ERROR")
            
            # Also remove from prerolls if it exists
            preroll = db.query(models.Preroll).filter(
                models.Preroll.path == trailer.local_path
            ).first()
            if preroll:
                db.delete(preroll)
                _file_log(f"Sonarr Sync: Removed preroll record for expired trailer")
            
            db.delete(trailer)
            results["expired"] += 1
    
    if results["expired"] > 0:
        db.commit()
        _file_log(f"Sonarr Sync: Expired {results['expired']} TV trailers")
    
    # ========================================
    # DOWNLOAD: Get new trailers
    # ========================================
    _nexup_sync_progress["status"] = "Fetching upcoming shows from Sonarr..."
    upcoming = await connector.get_upcoming_premieres(days_ahead)
    _file_log(f"Sonarr Sync: Found {len(upcoming)} upcoming shows")
    results["checked"] = len(upcoming)
    _nexup_sync_progress["total"] = len(upcoming)
    _nexup_sync_progress["status"] = f"Found {len(upcoming)} upcoming shows..."
    
    # Re-fetch existing trailers after cleanup
    existing_trailers = db.query(models.ComingSoonTVTrailer).filter(
        models.ComingSoonTVTrailer.status == 'downloaded'
    ).all()
    existing_keys = {f"{t.sonarr_series_id}_S{t.season_number}" for t in existing_trailers}
    
    # Find shows that need trailers
    tmdb_api_key = getattr(setting, 'nexup_tmdb_api_key', None)
    fetcher = TVTrailerFetcher(tmdb_api_key=tmdb_api_key)
    quality = getattr(setting, 'nexup_quality', '1080') or '1080'
    max_duration = getattr(setting, 'nexup_max_trailer_duration', 180) or 0
    downloader = TrailerDownloader(storage_path, quality, tmdb_api_key=tmdb_api_key, max_duration=max_duration)
    
    downloads_completed = 0
    skipped_no_trailer = 0
    skipped_already_exists = 0
    processed_count = 0
    
    for show in upcoming:
        processed_count += 1
        progress_pct = int((processed_count / len(upcoming)) * 100) if upcoming else 100
        _nexup_sync_progress["progress"] = progress_pct
        
        key = f"{show['sonarr_id']}_S{show['season_number']}"
        
        if key in existing_keys:
            skipped_already_exists += 1
            _nexup_sync_progress["skipped"] = skipped_already_exists
            _nexup_sync_progress["status"] = f"Skipping '{show['title']}' S{show['season_number']} (already have)"
            continue
        
        if downloads_completed >= max_trailers:
            _nexup_sync_progress["status"] = f"Reached max trailers limit ({max_trailers})"
            _file_log(f"Sonarr Sync: Reached max trailers limit ({max_trailers})")
            break
        
        results["eligible"] += 1
        
        # Try to find and download trailer
        try:
            _nexup_sync_progress["status"] = f"Looking for trailer: '{show['title']}' S{show['season_number']}..."
            _nexup_sync_progress["current_item"] = f"{show['title']} S{show['season_number']}"
            
            trailers = await fetcher.get_tv_trailers(
                tvdb_id=show.get('tvdb_id'),
                imdb_id=show.get('imdb_id')
            )
            
            if not trailers:
                skipped_no_trailer += 1
                _nexup_sync_progress["status"] = f"No trailer found for '{show['title']}' S{show['season_number']}"
                _file_log(f"Sonarr Sync: No trailer found for '{show['title']}' S{show.get('season_number', '?')} (TVDB: {show.get('tvdb_id')}, IMDB: {show.get('imdb_id')})")
                continue
            
            trailer_url = trailers[0]['url']
            
            # Create record
            tv_trailer = models.ComingSoonTVTrailer(
                sonarr_series_id=show['sonarr_id'],
                tvdb_id=show.get('tvdb_id'),
                imdb_id=show.get('imdb_id'),
                title=show['title'],
                year=show.get('year'),
                season_number=show['season_number'],
                overview=show.get('overview'),
                network=show.get('network'),
                release_date=datetime.datetime.fromisoformat(show['release_date']) if show.get('release_date') else None,
                release_type=show['release_type'],
                trailer_url=trailer_url,
                poster_url=show.get('poster_url'),
                fanart_url=show.get('fanart_url'),
                status='downloading'
            )
            db.add(tv_trailer)
            db.commit()
            db.refresh(tv_trailer)
            
            # Download
            _nexup_sync_progress["status"] = f"Downloading trailer for '{show['title']}' S{show['season_number']}..."
            season_str = f"S{show['season_number']:02d}" if show.get('season_number') else ""
            safe_title = re.sub(r'[^\w\s-]', '', show['title']).strip()
            filename = f"{safe_title} {season_str} Trailer"
            
            result = await downloader.download_trailer(
                trailer_url, 
                filename,
                tvdb_id=show.get('tvdb_id')
            )
            
            if result and result.get('path'):
                tv_trailer.local_path = result['path']
                tv_trailer.file_size_mb = result.get('size_mb')
                tv_trailer.duration_seconds = result.get('duration')
                tv_trailer.resolution = result.get('resolution')
                tv_trailer.status = 'downloaded'
                tv_trailer.downloaded_at = datetime.datetime.utcnow()
                
                await _create_preroll_from_tv_trailer(tv_trailer, setting, db)
                results["downloaded"] += 1
                downloads_completed += 1
                _nexup_sync_progress["downloaded"] = results["downloaded"]
                _nexup_sync_progress["status"] = f"Downloaded '{show['title']}' S{show['season_number']} successfully!"
                
                _file_log(f"Sonarr Sync: Downloaded trailer for '{show['title']}' S{show['season_number']} to {result['path']}")
                
                # Rate limiting delay
                if download_delay > 0 and downloads_completed < max_trailers:
                    _nexup_sync_progress["status"] = f"Rate limiting - waiting {download_delay}s..."
                    await asyncio.sleep(download_delay)
            else:
                tv_trailer.status = 'error'
                tv_trailer.error_message = "Download failed - no file returned"
                results["errors"].append(f"{show['title']}: Download failed")
                _nexup_sync_progress["errors"] = len(results["errors"])
                _nexup_sync_progress["status"] = f"Failed to download '{show['title']}' S{show['season_number']}"
                _file_log(f"Sonarr Sync: Failed to download trailer for '{show['title']}' S{show['season_number']}", level="ERROR")
            
            db.commit()
            
        except Exception as e:
            results["errors"].append(f"{show['title']}: {str(e)}")
            _nexup_sync_progress["errors"] = len(results["errors"])
            _nexup_sync_progress["status"] = f"Error: {show['title']} - {str(e)[:50]}"
            _file_log(f"Sonarr Sync: Error downloading '{show['title']}': {str(e)}", level="ERROR")
    
    # Add skip counts to results
    results["skipped_no_trailer"] = skipped_no_trailer
    results["skipped_already_exists"] = skipped_already_exists
    
    # Update last Sonarr sync time
    setting.nexup_last_sonarr_sync = datetime.datetime.now()
    db.commit()
    
    # Final progress update
    _nexup_sync_progress["status"] = f"Sync complete! Downloaded {results['downloaded']} trailers."
    _nexup_sync_progress["progress"] = 100
    _nexup_sync_progress["syncing"] = False
    
    _file_log(f"Sonarr Sync: Complete - checked={results['checked']}, eligible={results['eligible']}, downloaded={results['downloaded']}, skipped_no_trailer={skipped_no_trailer}, errors={len(results['errors'])}")
    
    # Add help message if no downloads and many skipped
    if results['downloaded'] == 0 and skipped_no_trailer > 0:
        results["help"] = f"No trailers were found for {skipped_no_trailer} shows. This usually happens because TMDB doesn't have trailers for these shows yet. Try adding a TMDB API key in settings for better results."
    
    return results

# ============================================================================
# END SONARR INTEGRATION
# ============================================================================

@app.get("/nexup/download/diagnostics")
async def download_diagnostics(db: Session = Depends(get_db)):
    """
    Get diagnostics about the download system including:
    - Available download sources
    - Browser cookie availability
    - yt-dlp version
    """
    import shutil
    import subprocess
    from backend.radarr_connector import TrailerDownloader
    
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None) or 'temp'
    quality = getattr(setting, 'nexup_quality', '1080p') or '1080p'
    
    diagnostics = {
        "yt_dlp_available": False,
        "yt_dlp_version": None,
        "ffmpeg_available": False,
        "ffmpeg_version": None,
        "browser_cookies_available": False,
        "detected_browser": None,
        "cookies_file_exists": False,
        "cookies_file_path": None,
        "download_sources": {
            "apple_trailers": "Enabled - No bot detection",
            "vimeo": "Enabled - No bot detection",
            "youtube": "Enabled - Requires authentication (cookies)"
        },
        "youtube_status": "Not configured - YouTube requires authentication",
        "youtube_help": "To download from YouTube, either: 1) Close your browser and try again, or 2) Export cookies to youtube_cookies.txt in your trailer storage folder"
    }
    
    # Check yt-dlp (Python module - works in bundled builds)
    try:
        import yt_dlp
        diagnostics['yt_dlp_available'] = True
        diagnostics['yt_dlp_version'] = yt_dlp.version.__version__
    except ImportError:
        # Fall back to checking CLI
        if shutil.which('yt-dlp'):
            diagnostics['yt_dlp_available'] = True
            try:
                result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
                diagnostics['yt_dlp_version'] = result.stdout.strip()
            except:
                pass
    
    # Check ffmpeg
    if shutil.which('ffmpeg'):
        diagnostics['ffmpeg_available'] = True
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
            first_line = result.stdout.split('\n')[0] if result.stdout else None
            diagnostics['ffmpeg_version'] = first_line
        except:
            pass
    
    # Check browser cookies
    downloader = TrailerDownloader(storage_path, quality)
    if downloader.cookie_browser:
        diagnostics['browser_cookies_available'] = True
        diagnostics['detected_browser'] = downloader.get_cookie_browser()
    
    # Check for cookies file
    cookies_file = Path(storage_path) / 'youtube_cookies.txt'
    diagnostics['cookies_file_path'] = str(cookies_file)
    if cookies_file.exists():
        diagnostics['cookies_file_exists'] = True
        diagnostics['youtube_status'] = "Configured - Using exported cookies file"
    elif diagnostics['browser_cookies_available']:
        diagnostics['youtube_status'] = "May work - Browser detected but may be locked. Close browser for best results"
    
    return diagnostics

@app.get("/nexup/youtube/status")
def get_youtube_status(db: Session = Depends(get_db)):
    """Check if YouTube authentication is set up and working"""
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None) or 'temp'
    
    status = {
        "configured": False,
        "method": None,
        "browser": None,
        "cookies_file": None,
        "oauth_file": None,
        "browser_available": False,
        "browser_locked": True,
        "message": "YouTube authentication not configured"
    }
    
    # Check for OAuth file first (most reliable, doesn't expire)
    oauth_file = Path(storage_path) / 'youtube_oauth.json'
    status['oauth_file'] = str(oauth_file)
    
    if oauth_file.exists():
        status['configured'] = True
        status['method'] = 'oauth'
        status['message'] = "YouTube configured via OAuth (recommended)"
        return status
    
    # Check for cookies file (reliable but can expire)
    cookies_file = Path(storage_path) / 'youtube_cookies.txt'
    status['cookies_file'] = str(cookies_file)
    
    if cookies_file.exists():
        status['configured'] = True
        status['method'] = 'cookies_file'
        status['message'] = "YouTube configured via cookies file"
        return status
    
    # Check for browser cookies
    from backend.radarr_connector import TrailerDownloader
    downloader = TrailerDownloader(storage_path, '1080')
    browser = downloader.get_cookie_browser()
    
    if browser:
        status['browser'] = browser
        status['browser_available'] = True
        
        # Try to test if browser is locked by checking if we can access cookies
        # We do this by checking if common browser processes are running
        import psutil
        browser_processes = {
            'chrome': ['chrome.exe', 'chrome'],
            'firefox': ['firefox.exe', 'firefox'],
            'edge': ['msedge.exe', 'msedge'],
            'brave': ['brave.exe', 'brave'],
        }
        
        running = False
        for proc in psutil.process_iter(['name']):
            try:
                proc_name = proc.info['name'].lower()
                for browser_name, proc_names in browser_processes.items():
                    if any(pn in proc_name for pn in proc_names):
                        running = True
                        break
            except:
                pass
            if running:
                break
        
        status['browser_locked'] = running
        
        if not running:
            status['configured'] = True
            status['method'] = 'browser_cookies'
            status['message'] = f"YouTube configured via {browser} browser cookies"
        else:
            status['message'] = f"Click 'Setup YouTube' to configure authentication. Browser cookies available from {browser}."
    
    return status

@app.post("/nexup/youtube/open-browser")
def open_youtube_browser(browser: str = Query('chrome', description="Browser to open")):
    """Open YouTube in a specific browser for user to sign in"""
    import webbrowser
    import subprocess
    import sys
    
    youtube_url = 'https://www.youtube.com'
    
    # Try to open in specific browser
    browser_commands = {
        'chrome': {
            'windows': ['start', 'chrome', youtube_url],
            'darwin': ['open', '-a', 'Google Chrome', youtube_url],
            'linux': ['google-chrome', youtube_url]
        },
        'edge': {
            'windows': ['start', 'msedge', youtube_url],
            'darwin': ['open', '-a', 'Microsoft Edge', youtube_url],
            'linux': ['microsoft-edge', youtube_url]
        },
        'firefox': {
            'windows': ['start', 'firefox', youtube_url],
            'darwin': ['open', '-a', 'Firefox', youtube_url],
            'linux': ['firefox', youtube_url]
        },
        'brave': {
            'windows': ['start', 'brave', youtube_url],
            'darwin': ['open', '-a', 'Brave Browser', youtube_url],
            'linux': ['brave-browser', youtube_url]
        }
    }
    
    platform = 'windows' if sys.platform == 'win32' else ('darwin' if sys.platform == 'darwin' else 'linux')
    
    try:
        if browser in browser_commands:
            cmd = browser_commands[browser].get(platform)
            if cmd and sys.platform == 'win32':
                # Windows needs shell=True for 'start' command
                subprocess.run(' '.join(cmd), shell=True)
                return {"success": True, "message": f"Opened YouTube in {browser}. Please sign in if not already."}
            elif cmd:
                subprocess.run(cmd)
                return {"success": True, "message": f"Opened YouTube in {browser}. Please sign in if not already."}
    except Exception as e:
        _file_log(f"Failed to open specific browser {browser}: {e}")
    
    # Fallback to default browser
    webbrowser.open(youtube_url)
    return {"success": True, "message": "Opened YouTube in default browser. Please sign in if not already."}

@app.post("/nexup/youtube/upload-cookies")
async def upload_youtube_cookies(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a cookies.txt file manually"""
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None)
    
    if not storage_path:
        return {"success": False, "error": "Storage path not configured"}
    
    cookies_file = Path(storage_path) / 'youtube_cookies.txt'
    
    try:
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Validate it looks like a cookies file
        if '.youtube.com' not in content_str and 'youtube' not in content_str.lower():
            return {"success": False, "error": "File doesn't appear to contain YouTube cookies"}
        
        # Check for auth tokens
        has_auth = any(auth in content_str for auth in ['SID', 'SSID', 'LOGIN_INFO', '__Secure-1PSID'])
        
        if not has_auth:
            return {
                "success": False, 
                "error": "Cookies file doesn't contain authentication. Make sure you export cookies while signed in to YouTube."
            }
        
        # Save the file
        with open(cookies_file, 'w', encoding='utf-8') as f:
            f.write(content_str)
        
        # Verify the file was written successfully
        if not cookies_file.exists():
            _file_log(f"YouTube cookies upload FAILED - file not found after write at: {cookies_file}")
            return {"success": False, "error": f"File write failed - not found at {cookies_file}"}
        
        file_size = cookies_file.stat().st_size
        _file_log(f"YouTube cookies uploaded successfully to {cookies_file} ({file_size} bytes)")
        return {"success": True, "message": f"Cookies file uploaded successfully! ({file_size} bytes)"}
        
    except Exception as e:
        _file_log(f"Cookie upload failed: {e}")
        return {"success": False, "error": f"Failed to process file: {str(e)}"}

@app.post("/nexup/youtube/extract-cookies")
async def extract_youtube_cookies(browser: str = Query(None, description="Specific browser to extract from"), db: Session = Depends(get_db)):
    """
    Attempt to extract cookies from browser and save to cookies file.
    This works best when the browser is closed.
    """
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None)
    
    if not storage_path:
        return {"success": False, "error": "Storage path not configured"}
    
    # Use specified browser or detect one
    if not browser:
        from backend.radarr_connector import TrailerDownloader
        downloader = TrailerDownloader(storage_path, '1080')
        browser = downloader.get_cookie_browser()
        if not browser:
            browser = 'chrome'  # Default fallback
    
    cookies_file = Path(storage_path) / 'youtube_cookies.txt'
    
    # Check if the browser process is running (cookie extraction usually fails with browser running)
    import subprocess
    import sys
    
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW
        
        # Map browser names to process names
        browser_processes = {
            'chrome': ['chrome.exe'],
            'edge': ['msedge.exe'],
            'firefox': ['firefox.exe'],
            'brave': ['brave.exe'],
            'chromium': ['chromium.exe'],
            'opera': ['opera.exe'],
            'vivaldi': ['vivaldi.exe']
        }
        
        # Check if browser is running
        target_browser = browser.lower()
        if target_browser in browser_processes:
            for proc_name in browser_processes[target_browser]:
                try:
                    check = subprocess.run(
                        ['tasklist', '/FI', f'IMAGENAME eq {proc_name}', '/NH'],
                        capture_output=True, text=True, timeout=5,
                        creationflags=creationflags
                    )
                    if proc_name.lower() in check.stdout.lower():
                        _file_log(f"Warning: {browser} browser appears to be running ({proc_name})")
                except Exception:
                    pass
    
    # Try to extract cookies using yt_dlp module
    try:
        import yt_dlp
        ydl_opts = {
            'cookiesfrombrowser': (browser,),
            'cookiefile': str(cookies_file),
            'skip_download': True,
            'quiet': True,
            'no_warnings': True,
        }
        
        # Just initialize and get cookies - don't actually download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Try to extract info from a simple video to trigger cookie extraction
            try:
                ydl.extract_info('https://www.youtube.com/watch?v=dQw4w9WgXcQ', download=False)
            except Exception:
                pass  # We don't care about the video, just the cookies
        
        # Check if cookies file was created and contains login cookies
        if cookies_file.exists() and cookies_file.stat().st_size > 100:
            cookie_content = cookies_file.read_text()
            has_auth = any(auth in cookie_content for auth in ['SID', 'SSID', 'LOGIN_INFO', '__Secure-1PSID'])
            
            if has_auth:
                _file_log(f"Successfully extracted authenticated YouTube cookies from {browser}")
                return {
                    "success": True,
                    "browser": browser,
                    "cookies_file": str(cookies_file),
                    "message": f"Successfully extracted authenticated cookies from {browser}"
                }
            else:
                _file_log(f"Cookies extracted from {browser} but no authentication found")
                cookies_file.unlink()
    except ImportError:
        _file_log("yt_dlp module not available, falling back to CLI")
    except Exception as e:
        _file_log(f"yt_dlp module cookie extraction failed: {e}")
    
    # Fallback: Try using CLI yt-dlp if module method failed
    browsers_to_try = [browser, 'chrome', 'edge', 'firefox', 'brave']
    browsers_to_try = list(dict.fromkeys(browsers_to_try))  # Remove duplicates
    
    for try_browser in browsers_to_try:
        try:
            import shutil
            ytdlp_path = shutil.which('yt-dlp')
            if not ytdlp_path:
                break  # No CLI available
                
            cmd = [
                'yt-dlp',
                '--cookies-from-browser', try_browser,
                '--cookies', str(cookies_file),
                '--skip-download',
                'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                creationflags=creationflags
            )
            
            if cookies_file.exists() and cookies_file.stat().st_size > 100:
                cookie_content = cookies_file.read_text()
                has_auth = any(auth in cookie_content for auth in ['SID', 'SSID', 'LOGIN_INFO', '__Secure-1PSID'])
                
                if has_auth:
                    _file_log(f"Successfully extracted authenticated YouTube cookies from {try_browser} (CLI)")
                    return {
                        "success": True,
                        "browser": try_browser,
                        "cookies_file": str(cookies_file),
                        "message": f"Successfully extracted authenticated cookies from {try_browser}"
                    }
                else:
                    if cookies_file.exists():
                        cookies_file.unlink()
        except subprocess.TimeoutExpired:
            continue
        except Exception as e:
            _file_log(f"Cookie extraction failed for {try_browser}: {e}")
            continue
    
    return {
        "success": False,
        "error": "Could not extract authenticated cookies.",
        "hint": f"Make sure you are SIGNED IN to YouTube in {browser.title()}, then CLOSE ALL {browser.title()} windows completely (check Task Manager) before trying again. Also ensure you've actually logged in - just visiting YouTube is not enough."
    }

@app.post("/nexup/youtube/test-download")
async def test_youtube_download(db: Session = Depends(get_db)):
    """Test if YouTube downloads are working with current configuration"""
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None)
    
    if not storage_path:
        return {"success": False, "error": "Storage path not configured"}
    
    import subprocess
    import sys
    
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW
    
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Short test video
    cookies_file = Path(storage_path) / 'youtube_cookies.txt'
    
    # Build command - we need to actually try to get video info, not just simulate
    # This properly tests if authentication is working
    base_cmd = ['yt-dlp', '--dump-json', '--no-download', test_url]
    
    if cookies_file.exists():
        cmd = ['yt-dlp', '--cookies', str(cookies_file), '--dump-json', '--no-download', test_url]
    else:
        from backend.radarr_connector import TrailerDownloader
        downloader = TrailerDownloader(storage_path, '1080')
        browser = downloader.get_cookie_browser()
        if browser:
            cmd = ['yt-dlp', '--cookies-from-browser', browser, '--dump-json', '--no-download', test_url]
        else:
            cmd = base_cmd
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=creationflags
        )
        
        if result.returncode == 0:
            return {"success": True, "message": "YouTube downloads are working!"}
        else:
            error = result.stderr or "Unknown error"
            if "Sign in to confirm" in error:
                return {"success": False, "error": "Authentication required", "hint": "Please complete the YouTube setup process"}
            return {"success": False, "error": error[:200]}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Test timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}

# YouTube OAuth state storage
YOUTUBE_OAUTH_SESSIONS: dict = {}

@app.post("/nexup/youtube/oauth/start")
def start_youtube_oauth(db: Session = Depends(get_db)):
    """
    Start YouTube OAuth flow. Returns a URL and verification code for the user.
    Uses yt-dlp's OAuth device flow.
    """
    import subprocess
    import sys
    import json
    import uuid
    import re
    
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None)
    
    if not storage_path:
        return {"success": False, "error": "Storage path not configured. Set your trailer storage path first."}
    
    # Ensure storage path exists
    Path(storage_path).mkdir(parents=True, exist_ok=True)
    
    session_id = str(uuid.uuid4())
    oauth_cache = Path(storage_path) / '.youtube_oauth_cache'
    
    # Start yt-dlp OAuth process
    # yt-dlp --username oauth --password "" will trigger device OAuth flow
    creationflags = 0
    startupinfo = None
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    
    try:
        # Run yt-dlp to initiate OAuth - it outputs the verification URL and code
        cmd = [
            'yt-dlp',
            '--username', 'oauth2',
            '--password', '',
            '--cache-dir', str(oauth_cache),
            '--dump-json',
            '--no-download',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        ]
        
        # Run with a timeout - OAuth will fail but print the URL first
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            creationflags=creationflags,
            startupinfo=startupinfo
        )
        
        # Read stderr where the OAuth URL is printed
        stderr_output = ""
        try:
            _, stderr_output = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
            _, stderr_output = process.communicate()
        
        _file_log(f"OAuth stderr: {stderr_output[:500]}")
        
        # Parse the verification URL and code from yt-dlp output
        # yt-dlp outputs something like: 
        # "To give yt-dlp access to your account, go to https://www.google.com/device and enter code ABC-DEF"
        url_match = re.search(r'https://[^\s]+device[^\s]*', stderr_output)
        code_match = re.search(r'enter code\s+([A-Z0-9-]+)', stderr_output, re.IGNORECASE)
        
        if not url_match:
            # Try alternate pattern
            url_match = re.search(r'(https://accounts\.google\.com/[^\s]+)', stderr_output)
        
        if url_match:
            verification_url = url_match.group(0).strip()
            user_code = code_match.group(1) if code_match else None
            
            # Store session
            YOUTUBE_OAUTH_SESSIONS[session_id] = {
                "created": datetime.datetime.now().isoformat(),
                "storage_path": storage_path,
                "status": "pending",
                "verification_url": verification_url,
                "user_code": user_code
            }
            
            return {
                "success": True,
                "session_id": session_id,
                "verification_url": verification_url,
                "user_code": user_code,
                "message": "Open the URL and enter the code to authorize NeXroll"
            }
        else:
            # No OAuth URL found - might mean yt-dlp version doesn't support it
            return {
                "success": False,
                "error": "Could not initiate OAuth. Your yt-dlp version may not support OAuth.",
                "hint": "Try updating yt-dlp: pip install -U yt-dlp",
                "debug": stderr_output[:300] if stderr_output else "No output"
            }
            
    except Exception as e:
        _file_log(f"OAuth start error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/nexup/youtube/oauth/poll/{session_id}")
def poll_youtube_oauth(session_id: str, db: Session = Depends(get_db)):
    """Poll the status of an OAuth session"""
    session = YOUTUBE_OAUTH_SESSIONS.get(session_id)
    if not session:
        return {"success": False, "error": "Session not found or expired"}
    
    # Check if OAuth file was created
    storage_path = session.get('storage_path')
    oauth_file = Path(storage_path) / 'youtube_oauth.json'
    oauth_cache = Path(storage_path) / '.youtube_oauth_cache'
    
    # Check in cache dir for OAuth tokens
    if oauth_cache.exists():
        for f in oauth_cache.rglob('*.json'):
            try:
                content = f.read_text()
                if 'access_token' in content or 'refresh_token' in content:
                    # Copy to our OAuth file
                    import shutil
                    shutil.copy(f, oauth_file)
                    session['status'] = 'completed'
                    return {
                        "success": True,
                        "status": "completed",
                        "message": "OAuth authorization completed!"
                    }
            except:
                continue
    
    return {
        "success": True,
        "status": session.get('status', 'pending'),
        "message": "Waiting for authorization..."
    }

@app.post("/nexup/youtube/oauth/complete/{session_id}")
async def complete_youtube_oauth(session_id: str, db: Session = Depends(get_db)):
    """
    Complete the OAuth flow by running yt-dlp again to finalize the token exchange.
    Call this after the user has authorized the device.
    """
    import subprocess
    import sys
    
    session = YOUTUBE_OAUTH_SESSIONS.get(session_id)
    if not session:
        return {"success": False, "error": "Session not found or expired"}
    
    storage_path = session.get('storage_path')
    oauth_cache = Path(storage_path) / '.youtube_oauth_cache'
    oauth_file = Path(storage_path) / 'youtube_oauth.json'
    
    creationflags = 0
    if sys.platform == 'win32':
        creationflags = subprocess.CREATE_NO_WINDOW
    
    try:
        # Run yt-dlp again - if user has authorized, it should work and cache the token
        cmd = [
            'yt-dlp',
            '--username', 'oauth2',
            '--password', '',
            '--cache-dir', str(oauth_cache),
            '--dump-json',
            '--no-download',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=creationflags
        )
        
        # Check if it worked (return code 0 and we got JSON output)
        if result.returncode == 0:
            # Look for the token file and copy it
            for f in oauth_cache.rglob('*.json'):
                try:
                    content = f.read_text()
                    if 'access_token' in content or 'refresh_token' in content or 'token' in content:
                        import shutil
                        shutil.copy(f, oauth_file)
                        _file_log(f"OAuth token saved to {oauth_file}")
                        
                        # Clean up session
                        YOUTUBE_OAUTH_SESSIONS.pop(session_id, None)
                        
                        return {
                            "success": True,
                            "message": "YouTube OAuth setup complete! You can now download trailers."
                        }
                except:
                    continue
            
            # Even if we can't find token file, if yt-dlp succeeded, OAuth is working
            return {
                "success": True,
                "message": "YouTube OAuth is working! Trailers can now be downloaded."
            }
        else:
            error = result.stderr or "Unknown error"
            if "enter code" in error.lower():
                return {
                    "success": False,
                    "status": "pending",
                    "message": "Please complete authorization in your browser first"
                }
            return {"success": False, "error": error[:300]}
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "OAuth timed out. Please try again."}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.delete("/nexup/youtube/oauth")
def delete_youtube_oauth(db: Session = Depends(get_db)):
    """Delete YouTube OAuth credentials"""
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None)
    
    if not storage_path:
        return {"success": False, "error": "Storage path not configured"}
    
    oauth_file = Path(storage_path) / 'youtube_oauth.json'
    oauth_cache = Path(storage_path) / '.youtube_oauth_cache'
    
    deleted = []
    try:
        if oauth_file.exists():
            oauth_file.unlink()
            deleted.append("OAuth token file")
        
        if oauth_cache.exists():
            import shutil
            shutil.rmtree(oauth_cache)
            deleted.append("OAuth cache")
        
        if deleted:
            return {"success": True, "message": f"Deleted: {', '.join(deleted)}"}
        else:
            return {"success": True, "message": "No OAuth credentials found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/nexup/trailers")
def get_nexup_trailers(db: Session = Depends(get_db)):
    """Get all downloaded trailers"""
    trailers = db.query(models.ComingSoonTrailer).order_by(
        models.ComingSoonTrailer.release_date.asc()
    ).all()
    
    def calc_days_until(release_dt):
        if not release_dt:
            return None
        try:
            if hasattr(release_dt, 'date'):
                release_date = release_dt.date()
            else:
                release_date = release_dt
            return (release_date - datetime.datetime.now().date()).days
        except:
            return None
    
    return {
        "trailers": [
            {
                "id": t.id,
                "radarr_movie_id": t.radarr_movie_id,
                "tmdb_id": t.tmdb_id,
                "title": t.title,
                "year": t.year,
                "overview": t.overview,
                "release_date": t.release_date.isoformat() if t.release_date else None,
                "release_type": t.release_type,
                "days_until": calc_days_until(t.release_date),
                "local_path": t.local_path,
                "file_size_mb": t.file_size_mb,
                "duration_seconds": t.duration_seconds,
                "resolution": t.resolution,
                "poster_url": t.poster_url,
                "status": t.status,
                "is_enabled": t.is_enabled,
                "play_count": t.play_count,
                "downloaded_at": t.downloaded_at.isoformat() if t.downloaded_at else None
            }
            for t in trailers
        ],
        "total": len(trailers)
    }

@app.post("/nexup/trailers/download")
async def download_trailer(radarr_movie_id: int, db: Session = Depends(get_db)):
    """Download a specific trailer by Radarr movie ID"""
    
    setting = db.query(models.Setting).first()
    if not setting or not setting.nexup_radarr_url or not setting.nexup_radarr_api_key:
        raise HTTPException(status_code=400, detail="Radarr not connected")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        raise HTTPException(status_code=400, detail="Storage path not configured")
    
    # Check if yt-dlp Python module is available (works in bundled builds)
    try:
        import yt_dlp
    except ImportError:
        import shutil
        if not shutil.which('yt-dlp'):
            _file_log("yt-dlp not available - trailer downloads will fail")
            raise HTTPException(status_code=500, detail="yt-dlp not found. Please install yt-dlp to download trailers.")
    
    # Check if already downloaded
    existing = db.query(models.ComingSoonTrailer).filter(
        models.ComingSoonTrailer.radarr_movie_id == radarr_movie_id
    ).first()
    if existing:
        return {"success": False, "message": "Trailer already downloaded", "trailer_id": existing.id}
    
    from backend.radarr_connector import RadarrConnector, TrailerDownloader
    
    try:
        # Get movie details from Radarr
        connector = RadarrConnector(setting.nexup_radarr_url, setting.nexup_radarr_api_key)
        movie = await connector.get_movie_by_id(radarr_movie_id)
        
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found in Radarr")
        
        trailer_url = None
        youtube_id = movie.get('youTubeTrailerId')
        if youtube_id:
            trailer_url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        _file_log(f"Downloading trailer for: {movie.get('title')} (TMDB: {movie.get('tmdbId')}, YouTube ID: {youtube_id}, URL: {trailer_url})")
        
        if not trailer_url:
            raise HTTPException(status_code=400, detail="No trailer available for this movie in Radarr")
        
        # Download trailer
        quality = getattr(setting, 'nexup_quality', '1080') or '1080'
        downloader = TrailerDownloader(storage_path, quality)
        
        # Log cookie status
        cookies_file = Path(storage_path) / 'youtube_cookies.txt'
        browser = downloader.get_cookie_browser()
        _file_log(f"Download config: cookies_file={cookies_file.exists()}, browser={browser}, quality={quality}")
        
        result = await downloader.download_trailer(
            trailer_url,
            movie.get('title', 'Unknown'),
            movie.get('tmdbId', 0),
            year=movie.get('year')
        )
        
        if not result:
            # Provide helpful error message
            help_msg = "YouTube is blocking the download. "
            if not cookies_file.exists() and not browser:
                help_msg += "Export your browser cookies to 'youtube_cookies.txt' in your NeX-Up storage folder, or close your browser and try again."
            elif not cookies_file.exists():
                help_msg += f"Detected browser: {browser}. Try closing {browser} completely and retry, or export cookies to youtube_cookies.txt."
            else:
                help_msg += "Cookies file exists but may be expired. Re-export fresh cookies from your browser."
            
            _file_log(f"Failed to download trailer for {movie.get('title')} - {help_msg}")
            raise HTTPException(status_code=500, detail=help_msg)
    except HTTPException:
        raise
    except Exception as e:
        _file_log(f"Error downloading trailer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error downloading trailer: {str(e)}")
    
    # Parse release date
    release_date = None
    for date_field in ['digitalRelease', 'physicalRelease', 'inCinemas']:
        if movie.get(date_field):
            try:
                release_date = datetime.datetime.fromisoformat(movie[date_field].replace('Z', '+00:00')).date()
                break
            except:
                pass
    
    # Create database entry
    trailer = models.ComingSoonTrailer(
        radarr_movie_id=radarr_movie_id,
        tmdb_id=movie.get('tmdbId'),
        imdb_id=movie.get('imdbId'),
        title=movie.get('title', 'Unknown'),
        year=movie.get('year'),
        overview=movie.get('overview', ''),
        release_date=release_date,
        trailer_url=trailer_url,
        local_path=result['path'],
        file_size_mb=result['size_mb'],
        duration_seconds=result.get('duration', 0),
        resolution=result.get('resolution', ''),
        downloaded_at=datetime.datetime.utcnow(),
        status='downloaded',
        is_enabled=True,
        play_count=0
    )
    
    # Get poster URL
    for img in movie.get('images', []):
        if img.get('coverType') == 'poster':
            trailer.poster_url = img.get('remoteUrl') or img.get('url')
            break
    
    db.add(trailer)
    db.commit()
    db.refresh(trailer)
    
    # Also create a Preroll record for sequence builder compatibility
    nexup_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Movie Trailers"
    ).first()
    
    if nexup_category:
        # Check if preroll already exists for this path
        existing_preroll = db.query(models.Preroll).filter(
            models.Preroll.path == result['path']
        ).first()
        
        if not existing_preroll:
            preroll_record = models.Preroll(
                filename=Path(result['path']).name,
                path=result['path'],
                display_name=f"{movie.get('title', 'Unknown')} ({movie.get('year', '')})",
                category_id=nexup_category.id,
                thumbnail=trailer.poster_url or "",
                tags="[]",
                duration=result.get('duration', 0),
                managed=False
            )
            db.add(preroll_record)
            db.commit()
            _file_log(f"NeX-Up: Created preroll record for '{movie.get('title')}'")
    
    _file_log(f"NeX-Up: Downloaded trailer for '{movie.get('title')}'")
    
    return {
        "success": True,
        "message": f"Downloaded trailer for {movie.get('title')}",
        "trailer_id": trailer.id,
        "file_size_mb": result['size_mb']
    }

@app.post("/nexup/trailers/manual")
async def add_manual_trailer(
    title: str,
    tmdb_id: Optional[int] = None,
    year: Optional[int] = None,
    release_date: Optional[str] = None,
    file_path: Optional[str] = None,
    url: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Manually add a trailer by providing either:
    - A local file path to an existing trailer video
    - A URL to download from (YouTube, Vimeo, etc.)
    """
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Settings not configured")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        raise HTTPException(status_code=400, detail="Storage path not configured")
    
    # Generate a unique tmdb_id for manual entries if not provided
    # Use negative numbers to avoid conflicts with real TMDB IDs
    if not tmdb_id:
        import random
        tmdb_id = -random.randint(100000, 999999)
    
    # Check if trailer already exists for this movie (only for real TMDB IDs)
    if tmdb_id > 0:
        existing = db.query(models.ComingSoonTrailer).filter(
            models.ComingSoonTrailer.tmdb_id == tmdb_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail=f"Trailer already exists for {title}")
    
    import shutil
    from pathlib import Path
    
    final_path = None
    file_size_mb = 0
    
    # Determine output directory - movies go to movies subdirectory
    movies_dir = Path(storage_path) / 'movies'
    movies_dir.mkdir(parents=True, exist_ok=True)
    
    if file_path:
        # User provided a local file path - copy it to storage
        source = Path(file_path)
        if not source.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
        
        # Sanitize filename
        safe_title = ''.join(c for c in title if c.isalnum() or c in ' -_').strip().replace(' ', '_')[:100]
        dest_filename = f"{safe_title}_{tmdb_id}_trailer{source.suffix}"
        dest = movies_dir / dest_filename
        
        shutil.copy2(source, dest)
        final_path = str(dest)
        file_size_mb = dest.stat().st_size / (1024 * 1024)
        _file_log(f"NeX-Up: Copied manual trailer for '{title}' from {file_path}")
        
    elif url:
        # User provided a URL - try to download it
        from backend.radarr_connector import TrailerDownloader
        
        quality = getattr(setting, 'nexup_quality', '1080') or '1080'
        downloader = TrailerDownloader(storage_path, quality)
        
        _file_log(f"NeX-Up: Starting manual download for '{title}' from {url}")
        try:
            result = await downloader.download_trailer(url, title, tmdb_id)
            if not result:
                _file_log(f"NeX-Up: Manual download failed for '{title}' - no result returned")
                raise HTTPException(status_code=500, detail=f"Failed to download trailer from {url}. Check if YouTube authentication is configured.")
            
            final_path = result['path']
            file_size_mb = result['size_mb']
        except HTTPException:
            raise
        except Exception as e:
            _file_log(f"NeX-Up: Manual download error for '{title}': {str(e)}")
            raise HTTPException(status_code=500, detail=f"Download error: {str(e)}")
        _file_log(f"NeX-Up: Downloaded manual trailer for '{title}' from {url}")
    else:
        raise HTTPException(status_code=400, detail="Must provide either file_path or url")
    
    # Parse release date
    parsed_release_date = None
    if release_date:
        try:
            parsed_release_date = datetime.datetime.fromisoformat(release_date).date()
        except:
            pass
    
    # Create database entry
    trailer = models.ComingSoonTrailer(
        radarr_movie_id=0,  # Manual entry
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        release_date=parsed_release_date,
        local_path=final_path,
        file_size_mb=round(file_size_mb, 2),
        downloaded_at=datetime.datetime.utcnow(),
        status='downloaded',
        is_enabled=True,
        play_count=0
    )
    db.add(trailer)
    db.commit()
    db.refresh(trailer)
    
    # Also create a Preroll record for sequence builder compatibility
    nexup_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Movie Trailers"
    ).first()
    
    if nexup_category:
        existing_preroll = db.query(models.Preroll).filter(
            models.Preroll.path == final_path
        ).first()
        
        if not existing_preroll:
            preroll_record = models.Preroll(
                filename=Path(final_path).name,
                path=final_path,
                display_name=f"{title} ({year or ''})",
                category_id=nexup_category.id,
                thumbnail="",
                tags="[]",
                managed=False
            )
            db.add(preroll_record)
            db.commit()
            _file_log(f"NeX-Up: Created preroll record for manual trailer '{title}'")
    
    return {
        "success": True,
        "message": f"Added trailer for {title}",
        "trailer_id": trailer.id,
        "file_size_mb": round(file_size_mb, 2)
    }

@app.post("/nexup/trailers/sync-prerolls")
def sync_nexup_trailers_to_prerolls(db: Session = Depends(get_db)):
    """Sync existing ComingSoonTrailer records to Preroll table for sequence builder compatibility"""
    nexup_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Movie Trailers"
    ).first()
    
    if not nexup_category:
        return {"success": False, "message": "NeX-Up Trailers category not found", "synced": 0}
    
    trailers = db.query(models.ComingSoonTrailer).filter(
        models.ComingSoonTrailer.status == 'downloaded'
    ).all()
    
    synced = 0
    for trailer in trailers:
        if not trailer.local_path:
            continue
            
        # Check if preroll already exists
        existing = db.query(models.Preroll).filter(
            models.Preroll.path == trailer.local_path
        ).first()
        
        if not existing:
            preroll_record = models.Preroll(
                filename=Path(trailer.local_path).name if trailer.local_path else f"trailer_{trailer.id}.mp4",
                path=trailer.local_path,
                display_name=f"{trailer.title} ({trailer.year or ''})" if trailer.title else "Unknown Trailer",
                category_id=nexup_category.id,
                thumbnail=trailer.poster_url or "",
                tags="[]",
                duration=trailer.duration_seconds,
                managed=False
            )
            db.add(preroll_record)
            synced += 1
    
    db.commit()
    _file_log(f"NeX-Up: Synced {synced} trailers to preroll records")
    
    return {"success": True, "message": f"Synced {synced} trailers to preroll records", "synced": synced}

@app.delete("/nexup/trailers/{trailer_id}")
def delete_nexup_trailer(trailer_id: int, db: Session = Depends(get_db)):
    """Delete a trailer"""
    trailer = db.query(models.ComingSoonTrailer).filter(
        models.ComingSoonTrailer.id == trailer_id
    ).first()
    
    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")
    
    # Delete the corresponding Preroll record if it exists
    if trailer.local_path:
        preroll_record = db.query(models.Preroll).filter(
            models.Preroll.path == trailer.local_path
        ).first()
        if preroll_record:
            db.delete(preroll_record)
    
    # Delete the file
    if trailer.local_path and os.path.exists(trailer.local_path):
        try:
            os.remove(trailer.local_path)
        except Exception as e:
            _file_log(f"Failed to delete trailer file: {e}")
    
    title = trailer.title
    db.delete(trailer)
    db.commit()
    
    _file_log(f"NeX-Up: Deleted trailer for '{title}'")
    
    return {"success": True, "message": f"Deleted trailer for {title}"}

@app.put("/nexup/trailers/{trailer_id}/toggle")
def toggle_nexup_trailer(trailer_id: int, db: Session = Depends(get_db)):
    """Enable/disable a trailer"""
    trailer = db.query(models.ComingSoonTrailer).filter(
        models.ComingSoonTrailer.id == trailer_id
    ).first()
    
    if not trailer:
        raise HTTPException(status_code=404, detail="Trailer not found")
    
    trailer.is_enabled = not trailer.is_enabled
    trailer.updated_at = datetime.datetime.utcnow()
    db.commit()
    
    status = "enabled" if trailer.is_enabled else "disabled"
    return {"success": True, "message": f"Trailer {status}", "is_enabled": trailer.is_enabled}

@app.post("/nexup/sync")
async def sync_nexup(db: Session = Depends(get_db)):
    """
    Full sync: Check Radarr for updates, download new trailers, cleanup expired ones.
    Optimized to batch API calls and avoid redundant requests.
    """
    global _nexup_sync_progress
    
    setting = db.query(models.Setting).first()
    if not setting or not setting.nexup_radarr_url or not setting.nexup_radarr_api_key:
        raise HTTPException(status_code=400, detail="Radarr not connected")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        raise HTTPException(status_code=400, detail="Storage path not configured")
    
    # Initialize progress tracking
    _nexup_sync_progress = {
        "syncing": True,
        "type": "radarr",
        "status": "Connecting to Radarr...",
        "current_item": "",
        "progress": 0,
        "total": 0,
        "downloaded": 0,
        "skipped": 0,
        "errors": 0
    }
    
    from backend.radarr_connector import RadarrConnector, TrailerDownloader
    
    connector = RadarrConnector(setting.nexup_radarr_url, setting.nexup_radarr_api_key)
    max_duration = getattr(setting, 'nexup_max_trailer_duration', 180) or 0
    
    # Debug: Log storage path and cookie file status
    cookies_file = Path(storage_path) / 'youtube_cookies.txt'
    _file_log(f"NeX-Up sync: storage_path={storage_path}")
    _file_log(f"NeX-Up sync: cookies_file={cookies_file} (exists={cookies_file.exists()})")
    
    downloader = TrailerDownloader(storage_path, getattr(setting, 'nexup_quality', '1080') or '1080', max_duration=max_duration)
    
    results = {
        "checked": 0,
        "downloaded": 0,
        "expired": 0,
        "skipped_no_trailer": 0,
        "skipped_already_exists": 0,
        "eligible": 0,
        "errors": []
    }
    
    try:
        # Get ALL movies from Radarr in ONE request (includes download status)
        days_ahead = getattr(setting, 'nexup_days_ahead', 90) or 90
        _nexup_sync_progress["status"] = "Fetching movies from Radarr..."
        _file_log(f"NeX-Up sync: Fetching movies from Radarr...")
        
        # This single call gets all movie info including hasFile status
        all_radarr_movies = await connector.get_all_movies_raw()
        _file_log(f"NeX-Up sync: Got {len(all_radarr_movies)} total movies from Radarr")
        
        # Build a map of radarr_id -> hasFile for quick lookups
        downloaded_movies = {m['id'] for m in all_radarr_movies if m.get('hasFile', False)}
        _file_log(f"NeX-Up sync: {len(downloaded_movies)} movies already downloaded")
        
        # Get existing trailers from our DB
        existing = db.query(models.ComingSoonTrailer).all()
        existing_radarr_ids = {t.radarr_movie_id for t in existing}
        _file_log(f"NeX-Up sync: {len(existing_radarr_ids)} existing trailers in DB")
        
        _nexup_sync_progress["status"] = "Cleaning up orphaned records..."
        
        # Verify existing trailer files exist - remove orphaned records
        orphaned_count = 0
        for trailer in existing:
            if trailer.local_path and not os.path.exists(trailer.local_path):
                _file_log(f"NeX-Up sync: Removing orphaned record for '{trailer.title}' - file missing: {trailer.local_path}")
                existing_radarr_ids.discard(trailer.radarr_movie_id)
                db.delete(trailer)
                orphaned_count += 1
        if orphaned_count > 0:
            db.commit()
            _file_log(f"NeX-Up sync: Cleaned up {orphaned_count} orphaned trailer records")
        
        _nexup_sync_progress["status"] = "Checking for expired trailers..."
        
        # Check for movies that have been downloaded (expire their trailers) - NO extra API calls!
        for trailer in existing:
            if trailer.radarr_movie_id in downloaded_movies:
                # Delete trailer file
                if trailer.local_path and os.path.exists(trailer.local_path):
                    try:
                        os.remove(trailer.local_path)
                    except:
                        pass
                db.delete(trailer)
                results["expired"] += 1
                _file_log(f"NeX-Up: Expired trailer for downloaded movie '{trailer.title}'")
        
        # Parse upcoming movies from the already-fetched data
        upcoming = connector.parse_upcoming_from_raw(all_radarr_movies, days_ahead)
        results["checked"] = len(upcoming)
        _file_log(f"NeX-Up sync: Found {len(upcoming)} upcoming movies")
        
        # Download new trailers (up to limit)
        max_trailers = getattr(setting, 'nexup_max_trailers', 10) or 10
        current_count = db.query(models.ComingSoonTrailer).count()
        storage_usage = downloader.get_storage_usage()
        max_storage = getattr(setting, 'nexup_max_storage_gb', 5.0) or 5.0
        
        _file_log(f"NeX-Up sync: max_trailers={max_trailers}, current_count={current_count}, storage={storage_usage['total_size_gb']}GB/{max_storage}GB")
        
        # Filter to only truly upcoming movies (positive days) with trailers
        eligible_movies = [m for m in upcoming if m.get('trailer_url') and (m.get('days_until_release') or 0) >= -7]
        _file_log(f"NeX-Up sync: {len(eligible_movies)} eligible movies (with trailer, releasing soon)")
        results["eligible"] = len(eligible_movies)
        
        # Update progress with total eligible
        _nexup_sync_progress["total"] = len(eligible_movies)
        _nexup_sync_progress["status"] = f"Found {len(eligible_movies)} movies with trailers..."
        
        # Get rate limiting settings
        download_delay = getattr(setting, 'nexup_download_delay', 5) or 5
        downloads_completed = 0
        processed_count = 0
        
        for movie in eligible_movies:
            processed_count += 1
            progress_pct = int((processed_count / len(eligible_movies)) * 100) if eligible_movies else 100
            _nexup_sync_progress["progress"] = progress_pct
            
            # Check limits
            if current_count >= max_trailers:
                _nexup_sync_progress["status"] = f"Reached max trailers limit ({max_trailers})"
                _file_log(f"NeX-Up sync: Reached max trailers limit ({max_trailers})")
                break
            if storage_usage['total_size_gb'] >= max_storage:
                _nexup_sync_progress["status"] = f"Reached storage limit ({max_storage}GB)"
                _file_log(f"NeX-Up sync: Reached storage limit ({max_storage}GB)")
                break
            
            # Skip if already have this movie
            if movie['radarr_id'] in existing_radarr_ids:
                results["skipped_already_exists"] += 1
                _nexup_sync_progress["skipped"] = results["skipped_already_exists"]
                _nexup_sync_progress["status"] = f"Skipping '{movie['title']}' (already have)"
                continue
            
            # Rate limiting: Add delay between downloads (except for first one)
            if downloads_completed > 0 and download_delay > 0:
                _nexup_sync_progress["status"] = f"Rate limiting - waiting {download_delay}s..."
                _file_log(f"NeX-Up sync: Waiting {download_delay}s before next download (rate limiting)")
                await asyncio.sleep(download_delay)
            
            _nexup_sync_progress["status"] = f"Downloading trailer for '{movie['title']}'..."
            _nexup_sync_progress["current_item"] = movie['title']
            _file_log(f"NeX-Up sync: Downloading trailer for '{movie['title']}' ({movie['days_until_release']} days away)")
            
            # Download trailer
            try:
                result = await downloader.download_trailer(
                    movie['trailer_url'],
                    movie['title'],
                    movie['tmdb_id']
                )
                
                # Check if result is a successful download (has 'path') vs an error dict (has 'error')
                if result and isinstance(result, dict) and 'path' in result:
                    _nexup_sync_progress["status"] = f"Downloaded '{movie['title']}' successfully!"
                    _nexup_sync_progress["downloaded"] = results["downloaded"] + 1
                    _file_log(f"NeX-Up sync: Downloaded '{movie['title']}' to {result['path']} ({result['size_mb']}MB)")
                    # Create database entry
                    trailer = models.ComingSoonTrailer(
                        radarr_movie_id=movie['radarr_id'],
                        tmdb_id=movie['tmdb_id'],
                        imdb_id=movie.get('imdb_id'),
                        title=movie['title'],
                        year=movie.get('year'),
                        overview=movie.get('overview', ''),
                        release_date=datetime.datetime.fromisoformat(movie['release_date']).date() if movie.get('release_date') else None,
                        release_type=movie.get('release_type'),
                        trailer_url=movie['trailer_url'],
                        local_path=result['path'],
                        file_size_mb=result['size_mb'],
                        duration_seconds=result.get('duration', 0),
                        resolution=result.get('resolution', ''),
                        poster_url=movie.get('poster_url'),
                        fanart_url=movie.get('fanart_url'),
                        downloaded_at=datetime.datetime.utcnow(),
                        status='downloaded',
                        is_enabled=True,
                        play_count=0
                    )
                    db.add(trailer)
                    current_count += 1
                    results["downloaded"] += 1
                    existing_radarr_ids.add(movie['radarr_id'])
                    downloads_completed += 1
                    
                    # Update storage tracking
                    storage_usage = downloader.get_storage_usage()
                else:
                    # Check if result contains YouTube bot block error
                    error_code = str(result.get('error', '')) if result and isinstance(result, dict) else ''
                    if 'YOUTUBE_BOT_BLOCK' in error_code or 'STALE_COOKIES' in error_code:
                        error_msg = "⚠️ YouTube bot detection. Re-export cookies from Incognito: login → youtube.com/robots.txt → export"
                        _nexup_sync_progress["status"] = f"YouTube blocked '{movie['title']}' - try re-exporting cookies"
                        _nexup_sync_progress["cookie_error"] = True  # Flag for UI to show help
                        results["errors"].append(f"{movie['title']}: {error_msg}")
                        _file_log(f"NeX-Up sync: YOUTUBE BOT BLOCK - '{movie['title']}' - cookies may be invalid or IP is rate-limited")
                    else:
                        _nexup_sync_progress["status"] = f"Failed to download '{movie['title']}'"
                        results["errors"].append(f"{movie['title']}: No trailer source available")
                        _file_log(f"NeX-Up sync: Download FAILED for '{movie['title']}' - no trailer source worked")
                    _nexup_sync_progress["errors"] = len(results["errors"])
                    
            except Exception as e:
                _nexup_sync_progress["status"] = f"Error downloading '{movie['title']}'"
                _nexup_sync_progress["errors"] = len(results["errors"]) + 1
                _file_log(f"NeX-Up sync: ERROR downloading '{movie['title']}': {e}")
                results["errors"].append(f"{movie['title']}: {str(e)}")
        
        # Update last sync time (use local time for display)
        setting.nexup_last_sync = datetime.datetime.now()
        db.commit()
        
        _nexup_sync_progress["status"] = f"Sync complete! Downloaded {results['downloaded']} trailers."
        _nexup_sync_progress["progress"] = 100
        _nexup_sync_progress["syncing"] = False
        _file_log(f"NeX-Up sync complete: {results['downloaded']} downloaded, {results['expired']} expired")
        
    except Exception as e:
        _nexup_sync_progress["status"] = f"Sync error: {str(e)}"
        _nexup_sync_progress["syncing"] = False
        _nexup_sync_progress["progress"] = 100
        results["errors"].append(str(e))
        _file_log(f"NeX-Up sync error: {e}")
    
    return results

@app.get("/nexup/storage")
def get_nexup_storage(db: Session = Depends(get_db)):
    """Get storage usage for NeX-Up trailers"""
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None) if setting else None
    
    if not storage_path:
        return {
            "configured": False,
            "path": None,
            "total_size_mb": 0,
            "total_size_gb": 0,
            "file_count": 0,
            "max_gb": getattr(setting, 'nexup_max_storage_gb', 5.0) if setting else 5.0
        }
    
    from backend.radarr_connector import TrailerDownloader
    
    downloader = TrailerDownloader(storage_path)
    usage = downloader.get_storage_usage()
    
    return {
        "configured": True,
        "path": storage_path,
        "total_size_mb": usage['total_size_mb'],
        "total_size_gb": usage['total_size_gb'],
        "file_count": usage['file_count'],
        "max_gb": getattr(setting, 'nexup_max_storage_gb', 5.0) if setting else 5.0,
        "percentage_used": round((usage['total_size_gb'] / (getattr(setting, 'nexup_max_storage_gb', 5.0) or 5.0)) * 100, 1)
    }

@app.get("/nexup/trailers/playback")
def get_nexup_playback_trailers(db: Session = Depends(get_db)):
    """
    Get trailers to include in current preroll playback.
    Returns the configured number of trailers based on playback settings,
    plus any generated dynamic preroll (e.g., "Coming Soon to X").
    """
    setting = db.query(models.Setting).first()
    
    if not setting or not getattr(setting, 'nexup_enabled', False):
        return {"trailers": [], "enabled": False, "dynamic_preroll": None}
    
    count = getattr(setting, 'nexup_trailers_per_playback', 2) or 2
    order = getattr(setting, 'nexup_playback_order', 'release_date') or 'release_date'
    
    query = db.query(models.ComingSoonTrailer).filter(
        models.ComingSoonTrailer.is_enabled == True,
        models.ComingSoonTrailer.status == 'downloaded'
    )
    
    if order == 'release_date':
        query = query.order_by(models.ComingSoonTrailer.release_date.asc())
    elif order == 'random':
        # For random, we'll shuffle in Python
        all_trailers = query.all()
        random.shuffle(all_trailers)
        trailers = all_trailers[:count]
    elif order == 'download_date':
        query = query.order_by(models.ComingSoonTrailer.downloaded_at.desc())
    
    if order != 'random':
        trailers = query.limit(count).all()
    
    # Check for dynamic preroll
    dynamic_preroll = None
    storage_path = getattr(setting, 'nexup_storage_path', None)
    preroll_template = getattr(setting, 'nexup_dynamic_preroll_template', None)
    
    if storage_path and preroll_template:
        preroll_path = Path(storage_path) / "dynamic_prerolls" / f"{preroll_template}_preroll.mp4"
        if preroll_path.exists():
            dynamic_preroll = {
                "path": str(preroll_path),
                "template": preroll_template,
                "server_name": getattr(setting, 'nexup_dynamic_preroll_server_name', ''),
                "duration": getattr(setting, 'nexup_dynamic_preroll_duration', 5)
            }
    
    return {
        "trailers": [
            {
                "id": t.id,
                "title": t.title,
                "year": t.year,
                "path": t.local_path,
                "release_date": t.release_date.isoformat() if t.release_date else None,
                "days_until": (t.release_date - datetime.datetime.now().date()).days if t.release_date else None,
                "poster_url": t.poster_url,
                "duration_seconds": t.duration_seconds
            }
            for t in trailers
        ],
        "enabled": True,
        "count": len(trailers),
        "dynamic_preroll": dynamic_preroll
    }

# --- Dynamic Preroll Generation Endpoints ---

@app.get("/nexup/preroll/templates")
def get_preroll_templates():
    """Get available dynamic preroll templates and color themes"""
    from backend.dynamic_preroll import DynamicPrerollGenerator
    
    generator = DynamicPrerollGenerator()
    templates = generator.get_available_templates()
    color_themes = generator.get_color_themes()
    
    return {
        "templates": templates,
        "ffmpeg_available": generator.check_ffmpeg_available(),
        "color_themes": color_themes
    }

@app.get("/nexup/preroll/ffmpeg-status")
def get_ffmpeg_status():
    """Check if FFmpeg is available for video generation"""
    from backend.dynamic_preroll import DynamicPrerollGenerator
    
    generator = DynamicPrerollGenerator()
    available = generator.check_ffmpeg_available()
    
    return {
        "available": available,
        "message": "FFmpeg is ready for video generation" if available else "FFmpeg not found. Please install FFmpeg to generate dynamic prerolls."
    }

@app.post("/nexup/preroll/generate")
async def generate_dynamic_preroll(
    template: str = "coming_soon_cinematic",
    server_name: str = "Your Server",
    duration: int = 5,
    theme: str = "midnight",
    db: Session = Depends(get_db)
):
    """
    Generate a dynamic preroll video with visual effects.
    
    Args:
        template: Template name ('coming_soon_cinematic', 'coming_soon_neon', 'coming_soon_minimal', 
                                 'feature_presentation', 'feature_presentation_modern', 'now_showing')
        server_name: Server name to display in the video
        duration: Video duration in seconds (default 5)
        theme: Color theme ('midnight', 'sunset', 'forest', 'royal', 'monochrome')
    """
    from backend.dynamic_preroll import DynamicPrerollGenerator, set_verbose_logger
    
    # Wire up verbose logging if enabled
    if _is_verbose_logging_enabled():
        def preroll_verbose_log(msg: str):
            _file_log(f"[PREROLL] {msg}", level="DEBUG")
            print(f"[PREROLL] {msg}")
        set_verbose_logger(preroll_verbose_log)
        _file_log(f"[PREROLL] === Starting preroll generation ===", level="DEBUG")
        _file_log(f"[PREROLL] Template: {template}, Server: {server_name}, Duration: {duration}s, Theme: {theme}", level="DEBUG")
    
    # Get storage path
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None) if setting else None
    
    if not storage_path:
        raise HTTPException(status_code=400, detail="NeX-Up storage path not configured")
    
    output_dir = Path(storage_path) / "dynamic_prerolls"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = DynamicPrerollGenerator(str(output_dir))
    
    if not generator.check_ffmpeg_available():
        raise HTTPException(status_code=500, detail="FFmpeg not found. Please install FFmpeg to generate dynamic prerolls.")
    
    # Generate the video using the template router
    variables = {"server_name": server_name}
    
    try:
        output_path = generator.generate_from_template(template, variables, duration, theme=theme)
        
        if output_path:
            # Save settings for regeneration
            db.execute(
                models.Setting.__table__.update().values(
                    nexup_dynamic_preroll_template=template,
                    nexup_dynamic_preroll_server_name=server_name,
                    nexup_dynamic_preroll_duration=duration,
                    nexup_dynamic_preroll_theme=theme
                )
            )
            db.commit()
            
            if _is_verbose_logging_enabled():
                _file_log(f"[PREROLL] === Generation complete: {output_path} ===", level="DEBUG")
            
            return {
                "success": True,
                "path": str(output_path),
                "template": template,
                "server_name": server_name,
                "duration": duration,
                "theme": theme,
                "message": f"Generated '{template}' preroll with {theme} theme successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate preroll video")
    except Exception as e:
        _file_log(f"Error generating dynamic preroll: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/nexup/preroll/generate-from-preview")
async def generate_preroll_from_preview(
    image_data: str = Body(..., description="Base64 encoded PNG image from CSS preview"),
    duration: int = Body(5, description="Video duration in seconds"),
    template: str = Body("custom", description="Template name for filename"),
    server_name: str = Body("", description="Server name (for metadata)"),
    theme: str = Body("custom", description="Theme name (for metadata)"),
    db: Session = Depends(get_db)
):
    """
    Generate a preroll video from a captured CSS preview image.
    
    This is the "What You See Is What You Get" approach - the frontend captures
    the live CSS preview as a PNG image, and we create a video from it with
    smooth fade in/out effects.
    
    Benefits:
    - Pixel-perfect match to the CSS preview
    - No complex FFmpeg text rendering needed
    - Supports any CSS effects (gradients, shadows, custom fonts, etc.)
    - Much simpler and more maintainable
    
    Args:
        image_data: Base64 encoded PNG image (with or without data:image/png;base64, prefix)
        duration: Video duration in seconds
        template: Template name (used for filename)
        server_name: Server name (stored for reference)
        theme: Theme name (stored for reference)
    """
    import base64
    from backend.dynamic_preroll import DynamicPrerollGenerator, set_verbose_logger
    
    # Wire up verbose logging if enabled
    if _is_verbose_logging_enabled():
        def preroll_verbose_log(msg: str):
            _file_log(f"[PREROLL-IMG] {msg}", level="DEBUG")
            print(f"[PREROLL-IMG] {msg}")
        set_verbose_logger(preroll_verbose_log)
        _file_log(f"[PREROLL-IMG] === Starting image-to-video generation ===", level="DEBUG")
    
    # Get storage path
    setting = db.query(models.Setting).first()
    storage_path = getattr(setting, 'nexup_storage_path', None) if setting else None
    
    if not storage_path:
        raise HTTPException(status_code=400, detail="NeX-Up storage path not configured")
    
    output_dir = Path(storage_path) / "dynamic_prerolls"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    generator = DynamicPrerollGenerator(str(output_dir))
    
    if not generator.check_ffmpeg_available():
        raise HTTPException(status_code=500, detail="FFmpeg not found. Please install FFmpeg to generate prerolls.")
    
    try:
        # Decode base64 image
        # Strip data URL prefix if present
        if ',' in image_data:
            image_data = image_data.split(',', 1)[1]
        
        image_bytes = base64.b64decode(image_data)
        _file_log(f"[PREROLL-IMG] Decoded image: {len(image_bytes)} bytes")
        
        # Generate filename based on template AND theme (unique file per combination)
        import re
        safe_template = re.sub(r'[^a-zA-Z0-9_-]', '_', template)
        safe_theme = re.sub(r'[^a-zA-Z0-9_-]', '_', theme) if theme else 'custom'
        output_filename = f"{safe_template}_{safe_theme}_preroll.mp4"
        
        # Calculate fade duration - 1 second fades look smooth and professional
        # For shorter videos, use proportionally shorter fades
        fade_duration = max(0.5, min(1.0, duration * 0.2))
        
        output_path = generator.generate_from_image(
            image_data=image_bytes,
            duration=float(duration),
            output_filename=output_filename,
            width=1920,
            height=1080,
            fade_duration=fade_duration
        )
        
        if output_path:
            # Save settings for reference
            db.execute(
                models.Setting.__table__.update().values(
                    nexup_dynamic_preroll_template=template,
                    nexup_dynamic_preroll_server_name=server_name,
                    nexup_dynamic_preroll_duration=duration,
                    nexup_dynamic_preroll_theme=theme
                )
            )
            db.commit()
            
            _file_log(f"[PREROLL-IMG] === Generation complete: {output_path} ===")
            
            return {
                "success": True,
                "path": str(output_path),
                "filename": output_filename,
                "template": template,
                "server_name": server_name,
                "duration": duration,
                "theme": theme,
                "method": "preview_capture",
                "message": f"Generated preroll from CSS preview successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to generate video from preview image")
            
    except base64.binascii.Error as e:
        _file_log(f"[PREROLL-IMG] Base64 decode error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid base64 image data: {e}")
    except Exception as e:
        _file_log(f"[PREROLL-IMG] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/nexup/preroll/settings")
def get_preroll_settings(db: Session = Depends(get_db)):
    """Get saved dynamic preroll settings"""
    setting = db.query(models.Setting).first()
    
    if not setting:
        return {
            "configured": False,
            "template": "coming_soon",
            "server_name": "",
            "duration": 5,
            "theme": "midnight"
        }
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    preroll_path = None
    
    if storage_path:
        # Check if a preroll already exists
        output_dir = Path(storage_path) / "dynamic_prerolls"
        template = getattr(setting, 'nexup_dynamic_preroll_template', 'coming_soon')
        expected_file = output_dir / f"{template}_preroll.mp4"
        if expected_file.exists():
            preroll_path = str(expected_file)
    
    return {
        "configured": True,
        "template": getattr(setting, 'nexup_dynamic_preroll_template', 'coming_soon'),
        "server_name": getattr(setting, 'nexup_dynamic_preroll_server_name', ''),
        "duration": getattr(setting, 'nexup_dynamic_preroll_duration', 5),
        "theme": getattr(setting, 'nexup_dynamic_preroll_theme', 'midnight'),
        "preroll_path": preroll_path
    }

@app.get("/nexup/preroll/list")
def list_generated_prerolls(db: Session = Depends(get_db)):
    """List all generated dynamic preroll videos"""
    setting = db.query(models.Setting).first()
    
    if not setting:
        return {"prerolls": []}
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        return {"prerolls": []}
    
    output_dir = Path(storage_path) / "dynamic_prerolls"
    prerolls = []
    
    if output_dir.exists():
        for file in output_dir.glob("*_preroll.mp4"):
            # Extract template name from filename (e.g., "coming_soon_cinematic_preroll.mp4" -> "coming_soon_cinematic")
            template_id = file.stem.replace("_preroll", "")
            
            # Get file stats
            stat = file.stat()
            
            prerolls.append({
                "filename": file.name,
                "template_id": template_id,
                "path": str(file),
                "size_bytes": stat.st_size,
                "created_at": stat.st_mtime
            })
    
    # Sort by creation time (newest first)
    prerolls.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {"prerolls": prerolls}

@app.delete("/nexup/preroll/{filename}")
def delete_specific_preroll(filename: str, db: Session = Depends(get_db)):
    """Delete a specific generated dynamic preroll"""
    setting = db.query(models.Setting).first()
    
    if not setting:
        return {"success": False, "message": "No settings found"}
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        return {"success": False, "message": "Storage path not configured"}
    
    # Sanitize filename
    if ".." in filename or "/" in filename or "\\" in filename:
        return {"success": False, "message": "Invalid filename"}
    
    file_path = Path(storage_path) / "dynamic_prerolls" / filename
    
    if file_path.exists():
        try:
            file_path.unlink()
            return {"success": True, "message": f"Deleted {filename}"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    return {"success": False, "message": "File not found"}

@app.get("/nexup/preroll/video/{filename}")
def serve_dynamic_preroll_video(filename: str, db: Session = Depends(get_db)):
    """Serve a generated dynamic preroll video file for preview"""
    setting = db.query(models.Setting).first()
    
    if not setting:
        raise HTTPException(status_code=404, detail="Settings not found")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        raise HTTPException(status_code=404, detail="Storage path not configured")
    
    # Sanitize filename
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    video_path = Path(storage_path) / "dynamic_prerolls" / filename
    
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")
    
    import mimetypes
    mime_type, _ = mimetypes.guess_type(str(video_path))
    if not mime_type or not mime_type.startswith("video/"):
        mime_type = "video/mp4"
    
    # Add no-cache headers to prevent browser caching stale videos
    from starlette.responses import FileResponse as StarletteFileResponse
    response = StarletteFileResponse(str(video_path), media_type=mime_type)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.delete("/nexup/preroll")
def delete_dynamic_preroll(db: Session = Depends(get_db)):
    """Delete the generated dynamic preroll"""
    setting = db.query(models.Setting).first()
    
    if not setting:
        return {"success": False, "message": "No settings found"}
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        return {"success": False, "message": "Storage path not configured"}
    
    output_dir = Path(storage_path) / "dynamic_prerolls"
    deleted = []
    
    # Delete all preroll files
    if output_dir.exists():
        for file in output_dir.glob("*_preroll.mp4"):
            try:
                file.unlink()
                deleted.append(str(file))
            except Exception as e:
                _file_log(f"Failed to delete {file}: {e}")
    
    # Clear settings
    db.execute(
        models.Setting.__table__.update().values(
            nexup_dynamic_preroll_template=None,
            nexup_dynamic_preroll_server_name=None,
            nexup_dynamic_preroll_duration=None
        )
    )
    db.commit()
    
    return {
        "success": True,
        "deleted": deleted,
        "message": f"Deleted {len(deleted)} preroll file(s)"
    }

# NeX-Up Sequence Builder Integration
@app.get("/nexup/sequence/presets")
def get_nexup_sequence_presets(db: Session = Depends(get_db)):
    """Get pre-built sequence presets for NeX-Up integration"""
    setting = db.query(models.Setting).first()
    
    # Get the NeX-Up Movie Trailers category
    nexup_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Movie Trailers"
    ).first()
    
    # Get the NeX-Up TV Trailers category
    tv_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up TV Trailers"
    ).first()
    
    # Get the NeX-Up Dynamic Prerolls category (or create if needed)
    preroll_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Prerolls"
    ).first()
    
    # Check if we have a dynamic preroll generated
    has_dynamic_preroll = False
    preroll_files = []
    available_prerolls = []
    if setting:
        storage_path = getattr(setting, 'nexup_storage_path', None)
        if storage_path:
            preroll_dir = Path(storage_path) / "dynamic_prerolls"
            if preroll_dir.exists():
                preroll_files = list(preroll_dir.glob("*_preroll.mp4"))
                has_dynamic_preroll = len(preroll_files) > 0
                # Build list of available prerolls with display names
                for pf in preroll_files:
                    display_name = pf.stem.replace('_preroll', '').replace('_', ' ').title()
                    available_prerolls.append({
                        "filename": pf.name,
                        "path": str(pf),
                        "display_name": display_name
                    })
    
    # Count trailers in each category
    movie_trailer_count = db.query(models.Preroll).filter(
        models.Preroll.category_id == nexup_category.id
    ).count() if nexup_category else 0
    
    tv_trailer_count = db.query(models.Preroll).filter(
        models.Preroll.category_id == tv_category.id
    ).count() if tv_category else 0
    
    # Build presets based on available content
    presets = []
    trailers_per_playback = getattr(setting, 'nexup_trailers_per_playback', 2) if setting else 2
    playback_order = getattr(setting, 'nexup_playback_order', 'release_date') if setting else 'release_date'
    
    # Preset 1: Coming Soon + Movie Trailers (classic)
    if nexup_category and movie_trailer_count > 0:
        presets.append({
            "id": "coming_soon_trailers",
            "name": "🎬 Coming Soon + Movie Trailers",
            "description": f"Plays your Coming Soon intro followed by {trailers_per_playback} random movie trailer(s)",
            "requires_dynamic_preroll": True,
            "has_requirements": has_dynamic_preroll,
            "trailer_source": "movies",
            "blocks": [
                {
                    "type": "fixed",
                    "source": "nexup_preroll",
                    "label": "Coming Soon Intro",
                    "description": "Your generated dynamic preroll"
                },
                {
                    "type": "random",
                    "category_id": nexup_category.id,
                    "count": trailers_per_playback,
                    "label": f"Movie Trailers ({trailers_per_playback})",
                    "description": f"Random trailers ordered by {playback_order.replace('_', ' ')}"
                }
            ]
        })
    
    # Preset 2: Coming Soon + TV Trailers
    if tv_category and tv_trailer_count > 0:
        presets.append({
            "id": "coming_soon_tv_trailers",
            "name": "📺 Coming Soon + TV Trailers",
            "description": f"Plays your Coming Soon intro followed by {trailers_per_playback} random TV show trailer(s)",
            "requires_dynamic_preroll": True,
            "has_requirements": has_dynamic_preroll,
            "trailer_source": "tv",
            "blocks": [
                {
                    "type": "fixed",
                    "source": "nexup_preroll",
                    "label": "Coming Soon Intro"
                },
                {
                    "type": "random",
                    "category_id": tv_category.id,
                    "count": trailers_per_playback,
                    "label": f"TV Trailers ({trailers_per_playback})"
                }
            ]
        })
    
    # Preset 3: Mixed - Movie + TV Trailers
    if nexup_category and tv_category and movie_trailer_count > 0 and tv_trailer_count > 0:
        presets.append({
            "id": "mixed_trailers",
            "name": "🎭 Mixed: Movies + TV",
            "description": f"Coming Soon intro, then 1 movie trailer and 1 TV trailer",
            "requires_dynamic_preroll": True,
            "has_requirements": has_dynamic_preroll,
            "trailer_source": "mixed",
            "blocks": [
                {
                    "type": "fixed",
                    "source": "nexup_preroll",
                    "label": "Coming Soon Intro"
                },
                {
                    "type": "random",
                    "category_id": nexup_category.id,
                    "count": 1,
                    "label": "Movie Trailer"
                },
                {
                    "type": "random",
                    "category_id": tv_category.id,
                    "count": 1,
                    "label": "TV Trailer"
                }
            ]
        })
    
    # Preset 4: Movie Trailers Only
    if nexup_category and movie_trailer_count > 0:
        presets.append({
            "id": "movie_trailers_only",
            "name": "🎞️ Movie Trailers Only",
            "description": f"Plays {trailers_per_playback} random movie trailer(s) without an intro",
            "requires_dynamic_preroll": False,
            "has_requirements": True,
            "trailer_source": "movies",
            "blocks": [
                {
                    "type": "random",
                    "category_id": nexup_category.id,
                    "count": trailers_per_playback,
                    "label": f"Movie Trailers ({trailers_per_playback})"
                }
            ]
        })
    
    # Preset 5: TV Trailers Only
    if tv_category and tv_trailer_count > 0:
        presets.append({
            "id": "tv_trailers_only",
            "name": "📺 TV Trailers Only",
            "description": f"Plays {trailers_per_playback} random TV show trailer(s) without an intro",
            "requires_dynamic_preroll": False,
            "has_requirements": True,
            "trailer_source": "tv",
            "blocks": [
                {
                    "type": "random",
                    "category_id": tv_category.id,
                    "count": trailers_per_playback,
                    "label": f"TV Trailers ({trailers_per_playback})"
                }
            ]
        })
    
    # Preset 6: Theater Experience (intro + 4 movie trailers)
    if nexup_category and movie_trailer_count > 0:
        presets.append({
            "id": "theater_experience",
            "name": "🌟 Theater Experience",
            "description": "Full cinema experience with Coming Soon intro and 4 movie trailers",
            "requires_dynamic_preroll": True,
            "has_requirements": has_dynamic_preroll,
            "trailer_source": "movies",
            "blocks": [
                {
                    "type": "fixed",
                    "source": "nexup_preroll",
                    "label": "Coming Soon Intro"
                },
                {
                    "type": "random",
                    "category_id": nexup_category.id,
                    "count": 4,
                    "label": "Movie Trailers (4)"
                }
            ]
        })
    
    return {
        "presets": presets,
        "nexup_category_id": nexup_category.id if nexup_category else None,
        "tv_category_id": tv_category.id if tv_category else None,
        "preroll_category_id": preroll_category.id if preroll_category else None,
        "has_dynamic_preroll": has_dynamic_preroll,
        "dynamic_preroll_files": [str(f.name) for f in preroll_files],
        "available_prerolls": available_prerolls,
        "movie_trailers_count": movie_trailer_count,
        "tv_trailers_count": tv_trailer_count,
        "trailers_count": movie_trailer_count + tv_trailer_count
    }

@app.post("/nexup/sequence/create")
def create_nexup_sequence(
    preset_id: str,
    name: str = None,
    description: str = None,
    trailer_count: int = None,
    movie_trailer_count: int = None,
    tv_trailer_count: int = None,
    include_preroll: bool = True,
    selected_preroll_path: str = None,
    playback_order: str = None,
    db: Session = Depends(get_db)
):
    """Create a saved sequence from a NeX-Up preset
    
    playback_order options: 'random', 'release_date', 'download_date'
    movie_trailer_count/tv_trailer_count: Used for mixed_trailers preset
    """
    _file_log(f"Creating NeX-Up sequence: preset={preset_id}, include_preroll={include_preroll}, selected_preroll_path={selected_preroll_path}")
    setting = db.query(models.Setting).first()
    
    # Get the NeX-Up Movie Trailers category
    nexup_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Movie Trailers"
    ).first()
    
    # Get the NeX-Up TV Trailers category
    tv_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up TV Trailers"
    ).first()
    
    # Determine which category to use based on preset
    if preset_id in ["coming_soon_tv_trailers", "tv_trailers_only"]:
        if not tv_category:
            raise HTTPException(status_code=400, detail="NeX-Up TV Trailers category not found. Please configure Sonarr and sync TV trailers first.")
        primary_category = tv_category
        trailer_label = "TV Trailers"
    elif preset_id == "mixed_trailers":
        if not nexup_category or not tv_category:
            raise HTTPException(status_code=400, detail="Both Movie and TV Trailers categories are required for mixed mode.")
    else:
        if not nexup_category:
            raise HTTPException(status_code=400, detail="NeX-Up Movie Trailers category not found. Please configure NeX-Up first.")
        primary_category = nexup_category
        trailer_label = "Movie Trailers"
    
    # Get dynamic preroll if available - auto-register if not in database
    preroll_preroll_ids = []
    if include_preroll and setting:
        storage_path = getattr(setting, 'nexup_storage_path', None)
        if storage_path:
            preroll_dir = Path(storage_path) / "dynamic_prerolls"
            if preroll_dir.exists():
                # If a specific preroll was selected, only use that one
                if selected_preroll_path:
                    # URL decode the path in case it was encoded
                    from urllib.parse import unquote
                    decoded_path = unquote(selected_preroll_path)
                    preroll_path = Path(decoded_path)
                    _file_log(f"Selected preroll path: {decoded_path}, exists: {preroll_path.exists()}")
                    preroll_files = [preroll_path] if preroll_path.exists() else []
                    if not preroll_files:
                        _file_log(f"WARNING: Selected preroll path does not exist: {decoded_path}")
                else:
                    # Fallback to first preroll if none selected
                    all_prerolls = list(preroll_dir.glob("*_preroll.mp4"))
                    preroll_files = [all_prerolls[0]] if all_prerolls else []
                    _file_log(f"Using fallback preroll, found {len(all_prerolls)} prerolls")
                
                if preroll_files:
                    # Get or create the NeX-Up Prerolls category for auto-registration
                    preroll_category = db.query(models.Category).filter(
                        models.Category.name == "NeX-Up Prerolls"
                    ).first()
                    
                    if not preroll_category:
                        preroll_category = models.Category(
                            name="NeX-Up Prerolls",
                            description="Dynamic preroll intros generated by NeX-Up",
                            plex_mode="shuffle",
                            apply_to_plex=False,
                            is_system=True
                        )
                        db.add(preroll_category)
                        db.commit()
                        db.refresh(preroll_category)
                        _file_log("Auto-created NeX-Up Prerolls category for sequence")
                    
                    # Check and auto-register prerolls
                    for pf in preroll_files:
                        existing_preroll = db.query(models.Preroll).filter(
                            models.Preroll.path == str(pf)
                        ).first()
                        
                        if existing_preroll:
                            preroll_preroll_ids.append(existing_preroll.id)
                        else:
                            # Auto-register the preroll
                            display_name = pf.stem.replace('_preroll', '').replace('_', ' ').title()
                            new_preroll = models.Preroll(
                                filename=pf.name,
                                path=str(pf),
                                category_id=preroll_category.id,
                                display_name=f"NeX-Up: {display_name}",
                                thumbnail="",
                                tags="[]",
                                managed=False
                            )
                            db.add(new_preroll)
                            db.commit()
                            db.refresh(new_preroll)
                            preroll_preroll_ids.append(new_preroll.id)
                            _file_log(f"Auto-registered preroll for sequence: {pf.name}")
    
    _file_log(f"Preroll IDs collected: {preroll_preroll_ids}, include_preroll={include_preroll}")
    
    # Determine trailer count from settings or parameter
    default_count = getattr(setting, 'nexup_trailers_per_playback', 2) if setting else 2
    count = trailer_count if trailer_count else default_count
    
    # Determine block type based on playback order
    # 'random' = random selection, 'release_date' or 'download_date' = sequential (first N items)
    selection_type = "random" if playback_order == "random" or not playback_order else "sequential"
    
    # Build the sequence blocks
    blocks = []
    
    if preset_id == "coming_soon_trailers" or preset_id == "theater_experience":
        # Add preroll if available
        if preroll_preroll_ids and include_preroll:
            blocks.append({
                "type": "fixed",
                "preroll_ids": preroll_preroll_ids,
                "label": "Coming Soon Intro"
            })
        
        # Add movie trailers
        blocks.append({
            "type": selection_type,
            "category_id": nexup_category.id,
            "count": 4 if preset_id == "theater_experience" else count,
            "label": "Movie Trailers",
            "order": playback_order or "random"
        })
    
    elif preset_id == "coming_soon_tv_trailers":
        # Add preroll if available
        if preroll_preroll_ids and include_preroll:
            blocks.append({
                "type": "fixed",
                "preroll_ids": preroll_preroll_ids,
                "label": "Coming Soon Intro"
            })
        
        # Add TV trailers
        blocks.append({
            "type": selection_type,
            "category_id": tv_category.id,
            "count": count,
            "label": "TV Trailers",
            "order": playback_order or "random"
        })
    
    elif preset_id == "mixed_trailers":
        # Add preroll if available
        if preroll_preroll_ids and include_preroll:
            blocks.append({
                "type": "fixed",
                "preroll_ids": preroll_preroll_ids,
                "label": "Coming Soon Intro"
            })
        
        # Use explicit movie/tv counts if provided, otherwise split the total count
        movie_count = movie_trailer_count if movie_trailer_count is not None else max(1, count // 2)
        tv_count = tv_trailer_count if tv_trailer_count is not None else max(1, count // 2)
        
        # Add movie trailer(s) if count > 0
        if movie_count > 0:
            blocks.append({
                "type": selection_type,
                "category_id": nexup_category.id,
                "count": movie_count,
                "label": "Movie Trailers",
                "order": playback_order or "random"
            })
        
        # Add TV trailer(s) if count > 0
        if tv_count > 0:
            blocks.append({
                "type": selection_type,
                "category_id": tv_category.id,
                "count": tv_count,
                "label": "TV Trailers",
                "order": playback_order or "random"
            })
    
    elif preset_id == "movie_trailers_only":
        # Add preroll if available
        if preroll_preroll_ids and include_preroll:
            blocks.append({
                "type": "fixed",
                "preroll_ids": preroll_preroll_ids,
                "label": "Intro Preroll"
            })
        blocks.append({
            "type": selection_type,
            "category_id": nexup_category.id,
            "count": count,
            "label": "Movie Trailers",
            "order": playback_order or "random"
        })
    
    elif preset_id == "tv_trailers_only":
        # Add preroll if available
        if preroll_preroll_ids and include_preroll:
            blocks.append({
                "type": "fixed",
                "preroll_ids": preroll_preroll_ids,
                "label": "Intro Preroll"
            })
        blocks.append({
            "type": selection_type,
            "category_id": tv_category.id,
            "count": count,
            "label": "TV Trailers",
            "order": playback_order or "random"
        })
    
    elif preset_id == "custom":
        # Allow fully custom configuration - default to movie trailers
        if include_preroll and preroll_preroll_ids:
            blocks.append({
                "type": "fixed",
                "preroll_ids": preroll_preroll_ids,
                "label": "Preroll"
            })
        # Use movie category if available, otherwise TV
        custom_category = nexup_category if nexup_category else tv_category
        if custom_category:
            blocks.append({
                "type": selection_type,
                "category_id": custom_category.id,
                "count": count,
                "label": "Movie Trailers" if nexup_category else "TV Trailers",
                "order": playback_order or "random"
            })
    
    if not blocks:
        raise HTTPException(status_code=400, detail="No valid blocks could be created. Check your configuration.")
    
    # Create the saved sequence
    sequence_name = name or f"NeX-Up {preset_id.replace('_', ' ').title()}"
    sequence_desc = description or f"Auto-generated NeX-Up sequence"
    
    new_sequence = models.SavedSequence(
        name=sequence_name,
        description=sequence_desc,
        blocks=json.dumps(blocks)
    )
    db.add(new_sequence)
    db.commit()
    db.refresh(new_sequence)
    
    _file_log(f"Created NeX-Up sequence: {sequence_name}")
    
    return {
        "success": True,
        "sequence": {
            "id": new_sequence.id,
            "name": new_sequence.name,
            "description": new_sequence.description,
            "blocks": blocks
        },
        "message": f"Sequence '{sequence_name}' created successfully!"
    }

@app.post("/nexup/preroll/register")
def register_nexup_preroll(db: Session = Depends(get_db)):
    """Register generated dynamic prerolls as preroll files in the NeX-Up Prerolls category"""
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Settings not configured")
    
    storage_path = getattr(setting, 'nexup_storage_path', None)
    if not storage_path:
        raise HTTPException(status_code=400, detail="NeX-Up storage path not configured")
    
    preroll_dir = Path(storage_path) / "dynamic_prerolls"
    if not preroll_dir.exists():
        return {"success": True, "registered": [], "message": "No prerolls to register"}
    
    # Get or create the NeX-Up Prerolls category
    preroll_category = db.query(models.Category).filter(
        models.Category.name == "NeX-Up Prerolls"
    ).first()
    
    if not preroll_category:
        preroll_category = models.Category(
            name="NeX-Up Prerolls",
            description="Dynamic preroll intros generated by NeX-Up (Coming Soon, Feature Presentation, etc.)",
            plex_mode="shuffle",
            apply_to_plex=False,
            is_system=True
        )
        db.add(preroll_category)
        db.commit()
        db.refresh(preroll_category)
        _file_log("Created NeX-Up Prerolls system category")
    
    registered = []
    preroll_files = list(preroll_dir.glob("*_preroll.mp4"))
    
    for pf in preroll_files:
        # Check if already registered
        existing = db.query(models.Preroll).filter(
            models.Preroll.path == str(pf)
        ).first()
        
        if not existing:
            # Create a display name from the filename
            display_name = pf.stem.replace('_preroll', '').replace('_', ' ').title()
            
            new_preroll = models.Preroll(
                filename=pf.name,
                path=str(pf),
                display_name=f"NeX-Up: {display_name}",
                category_id=preroll_category.id,
                thumbnail="",
                tags="[]",
                managed=False
            )
            db.add(new_preroll)
            registered.append({
                "filename": pf.name,
                "display_name": display_name
            })
    
    db.commit()
    
    return {
        "success": True,
        "registered": registered,
        "category_id": preroll_category.id,
        "message": f"Registered {len(registered)} new preroll(s)"
    }

# ==============================================================================
# End NeX-Up Routes
# ==============================================================================

@app.get("/genres/recent-applications")
def get_recent_genre_applications(limit: int = 10):
    """Get recent genre preroll applications for UI feedback"""
    return {"applications": RECENT_GENRE_APPLICATIONS[-limit:] if RECENT_GENRE_APPLICATIONS else []}

@app.get("/genres/apply")
def apply_preroll_by_genres_query(genres: str, ttl: int = 15, db: Session = Depends(get_db)):
    """
    Convenience GET for integrations like Tautulli/Webhooks:
    /genres/apply?genres=Horror,Thriller&ttl=15
    """
    # Accept multiple delimiters just in case: comma, semicolon, pipe, slash
    raw = str(genres or "")
    parts: list[str] = []
    for sep in [",", ";", "|", "/"]:
        if sep in raw:
            parts = [g.strip() for g in raw.split(sep)]
            break
    if not parts:
        parts = [g.strip() for g in raw.split(",")]
    genre_list = [g for g in parts if g]
    matched, matched_genre, cat, gm = _resolve_genre_mapping(db, genre_list)
    if not matched or not cat:
        # Return 200 for webhook consumers (e.g., Tautulli) to avoid treating "no mapping" as an error.
        return {
            "applied": False,
            "matched": False,
            "message": "No matching genre mapping found",
            "input_genres": genre_list
        }
    ok = _apply_category_to_plex_and_track(db, cat.id, ttl=ttl)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to set preroll in Plex (check Plex connection and path mappings)")
    return {
        "applied": True,
        "matched_genre": matched_genre,
        "category": {"id": cat.id, "name": cat.name, "plex_mode": getattr(cat, "plex_mode", "shuffle")},
        "mapping": {"id": gm.id, "genre": gm.genre},
        "override_ttl_minutes": ttl
    }
# --- Tautulli-friendly: apply by Plex rating key (server-side genre lookup) ---
@app.get("/genres/apply-by-key")
@app.get("/genres/apply/by-key")
def apply_preroll_by_rating_key(key: str | None = None, rating_key: str | None = None, ttl: int = 15, intercept: bool | None = None, db: Session = Depends(get_db)):
    """
    Resolve genres directly from Plex using a rating key (metadata id) and apply the mapped category.
    This avoids relying on Tautulli template variables for genres.

    Usage from Tautulli Webhook (Playback Start):
      GET http://&lt;nexroll-host&gt;:9393/genres/apply-by-key?key={rating_key}&amp;ttl=30
    """
    key_str = (rating_key or key or "").strip()
    if not key_str:
        raise HTTPException(status_code=422, detail="key (rating_key) is required")

    _file_log(f"apply_preroll_by_rating_key: key={key_str}, intercept={intercept}")

    # Plex settings
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, "plex_url", None):
        raise HTTPException(status_code=400, detail="Plex not configured (missing URL)")

    # Resolve token (allow secure-store fallback)
    token = None
    try:
        token = getattr(setting, "plex_token", None) or secure_store.get_plex_token()
    except Exception:
        token = getattr(setting, "plex_token", None)

    # Build request to Plex metadata API
    connector = PlexConnector(setting.plex_url, token)
    headers = connector.headers or ({"X-Plex-Token": token} if token else {})
    verify = getattr(connector, "_verify", True)
    chosen_key: str | None = None
    # Aggressive intercept helpers: optionally stop and relaunch the client at playback start
    def _bool_env_local(name: str):
        try:
            v = os.environ.get(name)
            if v is None:
                return None
            s = str(v).strip().lower()
            if s in ("1","true","yes","on"):
                return True
            if s in ("0","false","no","off"):
                return False
        except Exception:
            pass
        return None

    def _intercept_threshold_ms_default() -> int:
        try:
            v = os.environ.get("NEXROLL_INTERCEPT_THRESHOLD_MS")
            if v and str(v).strip().isdigit():
                return int(str(v).strip())
        except Exception:
            pass
        return 15000

    def _want_intercept_flag() -> bool:
        if intercept is not None:
            try:
                return bool(intercept)
            except Exception:
                return False
        # Accept either env name for convenience
        env1 = _bool_env_local("NEXROLL_INTERCEPT_ALWAYS")
        if env1 is not None:
            return bool(env1)
        env2 = _bool_env_local("NEXROLL_AGGRESSIVE_INTERCEPT")
        return bool(env2) if env2 is not None else False

    def _find_client_for_key(rk: str) -> tuple[str | None, int | None, str | None, str | None]:
        """Return (client_machine_id, viewOffsetMs, state, client_address) for current session matching rk, or (None,None,None,None)."""
        try:
            import xml.etree.ElementTree as _ET
            _sess = requests.get(f"{str(setting.plex_url).rstrip('/')}/status/sessions", headers=headers, timeout=5, verify=verify)
            if getattr(_sess, "status_code", 0) != 200 or not getattr(_sess, "content", None):
                return (None, None, None, None)
            _root = _ET.fromstring(_sess.content)
            for video in _root.iter():
                t = str(getattr(video, "tag", "") or "")
                if t.endswith("Video") or t == "Video":
                    _rk = (video.get("ratingKey") or "").strip()
                    _prk = (video.get("parentRatingKey") or "").strip()
                    _grk = (video.get("grandparentRatingKey") or "").strip()
                    if rk in (_rk, _prk, _grk):
                        vo = None
                        try:
                            vo = int(video.get("viewOffset") or "0")
                        except Exception:
                            vo = None
                        st = None
                        cid = None
                        client_addr = None
                        for child in list(video):
                            try:
                                ct = str(getattr(child, "tag", "") or "")
                                if ct.endswith("Player") or ct == "Player":
                                    st = (child.get("state") or "").lower()
                                    cid = (child.get("machineIdentifier") or "").strip() or None
                                    client_addr = (child.get("address") or "").strip() or None
                                    break
                            except Exception:
                                pass
                        return (cid, vo, st, client_addr)
            return (None, None, None, None)
        except Exception:
            return (None, None, None, None)

    def _aggressive_intercept(client_id: str, rk: str, view_offset_ms: int | None, client_address: str | None = None) -> bool:
        """
        Stop current playback and re-launch with correct preroll.

        NOTE: This approach is DISABLED by default due to fundamental Plex architecture limitations.
        The CinemaTrailersPrerollID setting is read when playback INITIATES, not dynamically during playback.
        Attempting to stop/restart after receiving the webhook results in 404s because:
        1) Plex Web/Desktop don't expose full Player control endpoints via the server API
        2) By the time we set the preroll and try to restart, the session is already in progress

        This is a known limitation - prerolls must be set BEFORE playback starts.
        Webhooks can only apply prerolls to FUTURE playback, not currently playing content.

        Set NEXROLL_FORCE_INTERCEPT=1 to attempt anyway (will fail with 404s for most clients).
        """
        try:
            # Check if forced (disabled by default due to 404s with Plex Web)
            force = False
            try:
                force_env = os.environ.get("NEXROLL_FORCE_INTERCEPT")
                if force_env and str(force_env).strip().lower() in ("1", "true", "yes"):
                    force = True
            except Exception:
                pass

            if not force:
                try:
                    _file_log("_aggressive_intercept: DISABLED by default. Plex prerolls are read at playback start, not dynamically. Webhooks can only affect future playback. Set NEXROLL_FORCE_INTERCEPT=1 to attempt anyway (will 404).")
                except Exception:
                    pass
                return False

            if not client_id:
                return False

            # Allow Plex server time to process the new CinemaTrailersPrerollID preference
            import time as _time
            try:
                delay_ms = int(os.environ.get("NEXROLL_INTERCEPT_DELAY_MS", "1000"))
            except Exception:
                delay_ms = 1000
            try:
                _file_log(f"_aggressive_intercept: waiting {delay_ms}ms for preroll propagation before relaunch")
            except Exception:
                pass
            _time.sleep(delay_ms / 1000.0)

            # Build headers with client target
            h = dict(headers or {})
            try:
                h.update(_build_plex_headers())
            except Exception:
                pass
            h["X-Plex-Target-Client-Identifier"] = client_id

            # Log what we're attempting
            try:
                _file_log(f"_aggressive_intercept: attempting control of client={client_id}, address={client_address}, ratingKey={rk}")
            except Exception:
                pass

            # Stop current playback
            stop_url = f"{str(setting.plex_url).rstrip('/')}/player/playback/stop"
            try:
                stop_resp = requests.post(stop_url, headers=h, timeout=4, verify=verify)
                status = getattr(stop_resp, 'status_code', 'unknown')
                try:
                    _file_log(f"_aggressive_intercept: POST {stop_url} → HTTP {status}")
                except Exception:
                    pass
                if status == 404:
                    try:
                        _file_log(f"_aggressive_intercept: Client {client_id} does not support remote control (stop endpoint 404), skipping intercept")
                    except Exception:
                        pass
                    return False
            except Exception as e:
                try:
                    _file_log(f"_aggressive_intercept: stop request failed: {e}")
                except Exception:
                    pass

            # Server identity and connection details
            mid = None
            scheme = "http"
            host = "127.0.0.1"
            port = 32400
            try:
                si = connector.get_server_info() or {}
                mid = si.get("machine_identifier") or si.get("machineIdentifier")
            except Exception:
                mid = None
            try:
                from urllib.parse import urlparse as _urlparse
                u = _urlparse(str(setting.plex_url).strip())
                if getattr(u, "scheme", None):
                    scheme = u.scheme
                if getattr(u, "hostname", None):
                    host = u.hostname
                if getattr(u, "port", None):
                    port = u.port or (443 if scheme == "https" else 32400)
                else:
                    port = 443 if scheme == "https" else 32400
            except Exception:
                pass

            # First attempt: playMedia with full connection metadata
            params = {
                "key": f"/library/metadata/{rk}",
                "offset": 0,
                "autoplay": 1,
                "protocol": scheme,
                "address": host,
                "port": port,
                "path": f"{scheme}://{host}:{port}/library/metadata/{rk}",
            }
            if mid:
                params["machineIdentifier"] = mid
            play_url = f"{str(setting.plex_url).rstrip('/')}/player/playback/playMedia"
            try:
                rplay = requests.post(play_url, headers=h, params=params, timeout=8, verify=verify)
                status = getattr(rplay, "status_code", 0)
                try:
                    _file_log(f"_aggressive_intercept: POST {play_url} → HTTP {status}, params={params}")
                except Exception:
                    pass
                if 200 <= status < 300:
                    return True
            except Exception as e:
                try:
                    _file_log(f"_aggressive_intercept: playMedia request failed: {e}")
                except Exception:
                    pass

            # Fallback: create a playQueue and start it on the client
            try:
                if not mid:
                    # Without server machine identifier, playQueue URIs cannot be formed
                    return False
                # Create playQueue for this item
                pq_uri = f"server://{mid}/com.plexapp.plugins.library/library/metadata/{rk}"
                pq_params = {
                    "type": "video",
                    "uri": pq_uri,
                    "shuffle": 0,
                    "continuous": 1,
                    "repeat": 0,
                }
                # Build server headers (no target for this call)
                hs = dict(headers or {})
                try:
                    hs.update(_build_plex_headers())
                except Exception:
                    pass

                pq_resp = requests.post(
                    f"{str(setting.plex_url).rstrip('/')}/playQueues",
                    headers=hs,
                    params=pq_params,
                    timeout=8,
                    verify=verify,
                )

                play_queue_id = None
                if getattr(pq_resp, "status_code", 0) == 200 and getattr(pq_resp, "content", None):
                    # Try JSON first, then XML
                    parsed_ok = False
                    try:
                        if "json" in (pq_resp.headers.get("Content-Type", "") or "").lower():
                            j = pq_resp.json()
                            play_queue_id = j.get("MediaContainer", {}).get("playQueueID")
                            parsed_ok = True
                    except Exception:
                        parsed_ok = False
                    if not parsed_ok:
                        try:
                            import xml.etree.ElementTree as _ETPQ
                            root = _ETPQ.fromstring(pq_resp.content)
                            play_queue_id = root.get("playQueueID")
                        except Exception:
                            play_queue_id = None

                if not play_queue_id:
                    return False

                pq_play_params = {
                    "playQueueID": play_queue_id,
                    "protocol": scheme,
                    "address": host,
                    "port": port,
                    "machineIdentifier": mid,
                    "offset": 0,
                    "autoplay": 1,
                }
                playq_url = f"{str(setting.plex_url).rstrip('/')}/player/playback/playQueue"
                rplayq = requests.post(playq_url, headers=h, params=pq_play_params, timeout=8, verify=verify)
                status = getattr(rplayq, "status_code", 0)
                try:
                    _file_log(f"_aggressive_intercept: POST {playq_url} → HTTP {status}, queueID={play_queue_id}, params={pq_play_params}")
                except Exception:
                    pass
                return 200 <= status < 300
            except Exception as e:
                try:
                    _file_log(f"_aggressive_intercept: playQueue fallback failed: {e}")
                except Exception:
                    pass
                return False
        except Exception:
            return False
    # Sessions-first: tolerant resolution (handles placeholder/non-numeric keys and multi-session)
    try:
        import xml.etree.ElementTree as ET
        sess_url = f"{str(setting.plex_url).rstrip('/')}/status/sessions"
        rs = requests.get(sess_url, headers=headers, timeout=5, verify=verify)
        if rs.status_code != 200:
            _file_log(f"sessions fetch failed: {rs.status_code}")
        if rs.status_code == 200:
            videos = []

            # Prefer JSON only when server indicates JSON; otherwise parse XML (default)
            is_json = False
            try:
                ctype = (rs.headers.get("Content-Type") or rs.headers.get("content-type") or "").lower()
                is_json = "json" in ctype
            except Exception:
                is_json = False

            if is_json:
                try:
                    data = rs.json()
                    for item in (data.get("MediaContainer", {}) or {}).get("Metadata", []) or []:
                        try:
                            rk = str(item.get("ratingKey", "")).strip()
                            prk = str(item.get("parentRatingKey", "")).strip()
                            grk = str(item.get("grandparentRatingKey", "")).strip()
                            vo = item.get("viewOffset")
                            if vo is not None:
                                vo = int(vo)
                            player = item.get("Player", {}) or {}
                            st = str(player.get("state", "") or "").lower()
                            cid = (player.get("machineIdentifier", "") or "").strip() or None
                            genres = [g.get("tag", "") for g in (item.get("Genre", []) or []) if g.get("tag", "")]
                            videos.append({"rk": rk, "prk": prk, "grk": grk, "vo": vo, "state": st, "client_id": cid, "genres": genres})
                        except Exception:
                            continue
                except Exception as je:
                    try:
                        _file_log(f"/genres/apply-by-key sessions json parse failed: {je}")
                    except Exception:
                        pass
                    videos = []

            # Fallback to XML when JSON not present or failed
            if not videos:
                try:
                    root = ET.fromstring(rs.content)
                    for video in root.iter():
                        t = str(getattr(video, "tag", "") or "")
                        if t.endswith("Video") or t == "Video":
                            rk = (video.get("ratingKey") or "").strip()
                            prk = (video.get("parentRatingKey") or "").strip()
                            grk = (video.get("grandparentRatingKey") or "").strip()
                            vo = None
                            try:
                                vo = int(video.get("viewOffset") or "0")
                            except Exception:
                                vo = None
                            st = None
                            cid = None
                            genres = []
                            for child in list(video):
                                try:
                                    ct = str(getattr(child, "tag", "") or "")
                                    if ct.endswith("Player") or ct == "Player":
                                        st = (child.get("state") or "").lower()
                                        cid = (child.get("machineIdentifier") or "").strip() or None
                                    elif ct.endswith("Genre") or ct == "Genre":
                                        g = child.get("tag")
                                        if g and str(g).strip():
                                            genres.append(str(g).strip())
                                except Exception:
                                    continue
                            videos.append({"rk": rk, "prk": prk, "grk": grk, "vo": vo, "state": st or "", "client_id": cid, "genres": genres})
                except Exception as xe:
                    try:
                        _file_log(f"/genres/apply-by-key sessions xml parse failed: {xe}")
                    except Exception:
                        pass
                    videos = []

            chosen_info = None
            # Prefer exact match if caller provided a numeric rating key
            if key_str and key_str.isdigit():
                for info in videos:
                    if key_str in (info.get("rk"), info.get("prk"), info.get("grk")):
                        chosen_info = info
                        break

            # If no exact match (placeholder/non-numeric or early webhook), pick the best active session
            if chosen_info is None and videos:
                def _rank(info):
                    st = str(info.get("state") or "").lower()
                    vo = info.get("vo")
                    active = 1 if st in ("playing", "buffering") else (0.5 if st == "paused" else 0)
                    vo_score = -int(vo) if isinstance(vo, int) else -999999
                    return (active, vo_score)
                chosen_info = sorted(videos, key=_rank, reverse=True)[0]

            if chosen_info is None:
                _file_log(f"no matching session found for key={key_str}")

            genres_sess: list[str] = []
            if chosen_info is not None:
                try:
                    chosen_key = (chosen_info.get("rk") or chosen_info.get("prk") or chosen_info.get("grk") or None)
                except Exception:
                    chosen_key = chosen_info.get("rk") if isinstance(chosen_info, dict) else None

                genres_sess = chosen_info.get("genres", []) or []

            # Dedupe (case-insensitive) while preserving order
            seen = set()
            genres_sess = [g for g in genres_sess if not (g.lower() in seen or seen.add(g.lower()))]

            if genres_sess:
                matched, matched_genre, cat, gm = _resolve_genre_mapping(db, genres_sess)
                if matched and cat:
                    ok = _apply_category_to_plex_and_track(db, cat.id, ttl=ttl)
                    if not ok:
                        raise HTTPException(status_code=500, detail="Failed to set preroll in Plex (check Plex connection and path mappings)")

                    client_id = chosen_info.get("client_id") if chosen_info else None
                    view_offset_ms = chosen_info.get("vo") if chosen_info else None
                    intercepted = False
                    if _want_intercept_flag() and client_id:
                        try:
                            threshold = _intercept_threshold_ms_default()
                        except Exception:
                            threshold = 5000
                        try:
                            cond = (view_offset_ms is None) or (int(view_offset_ms) < int(threshold))
                        except Exception:
                            cond = True
                        relaunch_key = (chosen_key or key_str)
                        if cond:
                            intercepted = _aggressive_intercept(client_id, relaunch_key, view_offset_ms)

                    return {
                        "applied": True,
                        "via": "rating_key",
                        "rating_key": (chosen_key or key_str),
                        "extracted_genres": genres_sess,
                        "matched_genre": matched_genre,
                        "category": {"id": cat.id, "name": cat.name, "plex_mode": getattr(cat, "plex_mode", "shuffle")},
                        "mapping": {"id": gm.id, "genre": gm.genre},
                        "override_ttl_minutes": ttl,
                        "source": "sessions",
                        "intercepted": intercepted,
                        "client_id": client_id,
                        "view_offset_ms": view_offset_ms,
                    }
    except Exception as _e:
        try:
            _file_log(f"/genres/apply-by-key sessions-first error: {_e}")
        except Exception:
            pass
    meta_key = (chosen_key or key_str)
    meta_url = f"{str(setting.plex_url).rstrip('/')}/library/metadata/{meta_key}?includeChildren=1"

    try:
        r = requests.get(meta_url, headers=headers, timeout=8, verify=getattr(connector, "_verify", True))
    except Exception as e:
        try:
            _file_log(f"/genres/apply-by-key metadata fetch error for key={meta_key}: {e}")
        except Exception:
            pass
        return {
            "applied": False,
            "matched": False,
            "message": f"Plex metadata fetch error: {e}",
            "rating_key": key_str,
            "extracted_genres": [],
            "source": "metadata",
        }

    if r.status_code != 200:
        try:
            _file_log(f"/genres/apply-by-key metadata HTTP {r.status_code} for key={meta_key}")
        except Exception:
            pass
        return {
            "applied": False,
            "matched": False,
            "message": f"Plex metadata HTTP {r.status_code} (may be temporarily unavailable at start)",
            "rating_key": meta_key,
            "extracted_genres": [],
            "source": "metadata",
        }

    # Parse XML for Genre tags
    genres: list[str] = []
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(r.content)
        # Typical structure: &lt;MediaContainer&gt;&lt;Video ...&gt;&lt;Genre tag="Horror"/&gt;...&lt;/Video&gt;&lt;/MediaContainer&gt;
        for node in root.iter():
            try:
                tagname = str(getattr(node, "tag", "") or "")
                if tagname.endswith("Genre") or tagname == "Genre":
                    g = node.get("tag")
                    if g and str(g).strip():
                        genres.append(str(g).strip())
            except Exception:
                continue
        # Dedupe preserve order
        seen = set()
        genres = [g for g in genres if not (g.lower() in seen or seen.add(g.lower()))]
        # If no genres present on this item (e.g., Episode), try parent/grandparent metadata
        if not genres:
            try:
                primary_video = None
                for _n in root.iter():
                    _t = str(getattr(_n, "tag", "") or "")
                    if _t.endswith("Video") or _t == "Video":
                        primary_video = _n
                        break
                prk = (primary_video.get("parentRatingKey") or "").strip() if primary_video is not None else ""
                grk = (primary_video.get("grandparentRatingKey") or "").strip() if primary_video is not None else ""
                for rk2 in [k for k in [prk, grk] if k]:
                    try:
                        r2 = requests.get(f"{str(setting.plex_url).rstrip('/')}/library/metadata/{rk2}", headers=headers, timeout=6, verify=verify)
                        if getattr(r2, "status_code", 0) == 200 and getattr(r2, "content", None):
                            import xml.etree.ElementTree as _ET2
                            root2 = _ET2.fromstring(r2.content)
                            for node2 in root2.iter():
                                try:
                                    t2 = str(getattr(node2, "tag", "") or "")
                                    if t2.endswith("Genre") or t2 == "Genre":
                                        g2 = node2.get("tag")
                                        if g2 and str(g2).strip():
                                            genres.append(str(g2).strip())
                                except Exception:
                                    continue
                    except Exception:
                        continue
                # Dedupe after merging
                _seen2 = set()
                genres = [g for g in genres if not (g.lower() in _seen2 or _seen2.add(g.lower()))]
            except Exception:
                # Ignore parent/grandparent fallback errors
                pass
    except Exception as e:
        try:
            _file_log(f"/genres/apply-by-key metadata XML parse error for key={key_str}: {e}")
        except Exception:
            pass
        return {
            "applied": False,
            "matched": False,
            "message": f"Plex metadata XML parse error: {e}",
            "rating_key": key_str,
            "extracted_genres": [],
            "source": "metadata",
        }

    # Resolve mapping and apply
    matched, matched_genre, cat, gm = _resolve_genre_mapping(db, genres)
    if not matched or not cat:
        # Keep webhook-friendly contract (200 + applied:false)
        return {
            "applied": False,
            "matched": False,
            "message": "No matching genre mapping found",
            "rating_key": key_str,
            "extracted_genres": genres,
        }

    ok = _apply_category_to_plex_and_track(db, cat.id, ttl=ttl)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to set preroll in Plex (check Plex connection and path mappings)")

    # Attempt aggressive intercept via current sessions (fresh playback)
    intercepted = False
    cid, vo_ms, st, client_addr = _find_client_for_key(meta_key)
    if _want_intercept_flag() and cid:
        try:
            threshold = _intercept_threshold_ms_default()
        except Exception:
            threshold = 5000
        try:
            cond = (vo_ms is None) or (int(vo_ms) < int(threshold))
        except Exception:
            cond = True
        if cond:
            intercepted = _aggressive_intercept(cid, key_str, vo_ms, client_addr)

    return {
        "applied": True,
        "via": "rating_key",
        "rating_key": meta_key,
        "extracted_genres": genres,
        "matched_genre": matched_genre,
        "category": {"id": cat.id, "name": cat.name, "plex_mode": getattr(cat, "plex_mode", "shuffle")},
        "mapping": {"id": gm.id, "genre": gm.genre},
        "source": "metadata",
        "override_ttl_minutes": ttl,
        "intercepted": intercepted,
        "client_id": cid,
        "view_offset_ms": vo_ms
    }

# --- Plex Webhook: immediate genre-based preroll application ---
def _verify_plex_webhook_signature(request: Request, raw_body: bytes) -> bool:
    try:
        secret = os.environ.get("NEXROLL_PLEX_WEBHOOK_SECRET")
        if not secret:
            return True
        sig_hdr = request.headers.get("X-Plex-Signature") or request.headers.get("x-plex-signature")
        if not sig_hdr:
            return False
        computed = base64.b64encode(hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha1).digest()).decode("utf-8")
        return hmac.compare_digest(sig_hdr.strip(), computed.strip())
    except Exception:
        return False

@app.post("/plex/webhook")
async def plex_webhook(request: Request, ttl: int = 15, intercept: bool | None = None, db: Session = Depends(get_db)):
    """
    Plex webhook receiver. Responds to media.play/media.resume by applying mapped genre prerolls.
    Supports application/json or multipart/form-data with 'payload' JSON field.
    Optionally verifies X-Plex-Signature when NEXROLL_PLEX_WEBHOOK_SECRET is set.
    """
    raw = await request.body()
    if not _verify_plex_webhook_signature(request, raw):
        raise HTTPException(status_code=403, detail="Invalid Plex webhook signature")

    # Parse payload
    data = {}
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            data = await request.json()
        except Exception:
            data = {}
    elif "multipart/form-data" in ctype:
        try:
            form = await request.form()
            payload = form.get("payload")
            payload_text = None
            try:
                if hasattr(payload, "read"):
                    payload_bytes = await payload.read()
                    payload_text = payload_bytes.decode("utf-8", errors="ignore")
                elif payload is not None:
                    payload_text = str(payload)
            except Exception:
                payload_text = None
            if payload_text:
                try:
                    data = json.loads(payload_text)
                except Exception:
                    data = {}
        except Exception:
            data = {}
    else:
        try:
            data = json.loads(raw.decode("utf-8"))
        except Exception:
            data = {}

    event = str((data or {}).get("event") or "").lower()
    if event not in ("media.play", "media.resume", "media.start"):
        return {"received": True, "ignored": True, "event": event}

    meta = (data.get("Metadata") or data.get("metadata") or {}) if isinstance(data, dict) else {}
    # Try ratingKey first (most reliable)
    rating_key = None
    try:
        rating_key = str(meta.get("ratingKey") or meta.get("ratingkey") or "").strip() or None
    except Exception:
        rating_key = None

    # Compute TTL minutes (fallback 15)
    ttl_minutes = 15
    try:
        st = db.query(models.Setting).first()
        sec_ttl = getattr(st, "genre_override_ttl_seconds", None)
        if isinstance(sec_ttl, int) and sec_ttl > 0:
            ttl_minutes = max(1, int(round(sec_ttl / 60)))  # seconds -> minutes
    except Exception:
        pass
    try:
        if ttl is not None:
            ttl_minutes = int(ttl)
    except Exception:
        pass

    if rating_key:
        try:
            # Reuse existing logic by calling our route function directly
            intercept_eff = intercept if intercept is not None else True
            try:
                _file_log(f"plex_webhook: ratingKey={rating_key}, intercept={intercept_eff}")
            except Exception:
                pass
            result = apply_preroll_by_rating_key(key=rating_key, ttl=ttl_minutes, intercept=intercept_eff, db=db)
            return {"handled": True, "via": "rating_key", **(result if isinstance(result, dict) else {"result": result})}
        except HTTPException as he:
            # Surface structured error to webhook caller without 500s
            return {"handled": False, "via": "rating_key", "status": he.status_code, "detail": str(he.detail)}
        except Exception as e:
            return {"handled": False, "via": "rating_key", "error": str(e)}

    # Fallback: extract genres directly if ratingKey is absent
    genres: list[str] = []
    try:
        g_list = meta.get("Genre") or []
        for g in g_list:
            try:
                tag = g.get("tag") if isinstance(g, dict) else None
                if tag:
                    genres.append(str(tag))
            except Exception:
                continue
        for g in (meta.get("genres") or []):
            if isinstance(g, str):
                genres.append(g)
        # Dedupe case-insensitive
        seen = set()
        genres = [g for g in genres if not (g.lower() in seen or seen.add(g.lower()))]
    except Exception:
        genres = []

    if genres:
        try:
            payload = ResolveGenresRequest(genres=genres)
            result = apply_preroll_by_genres(payload, ttl=ttl_minutes, db=db)
            return {"handled": True, "via": "genres", **(result if isinstance(result, dict) else {"result": result})}
        except HTTPException as he:
            return {"handled": False, "via": "genres", "status": he.status_code, "detail": str(he.detail)}
        except Exception as e:
            return {"handled": False, "via": "genres", "error": str(e)}

    return {"received": True, "ignored": True, "reason": "no ratingKey or genres in payload"}

@app.post("/webhooks/plex")
async def plex_webhook_alias(request: Request, ttl: int = 15, intercept: bool | None = None, db: Session = Depends(get_db)):
    """Alias path for Plex Webhooks configuration."""
    return await plex_webhook(request, ttl, intercept, db)

app.mount("/data", StaticFiles(directory=data_dir), name="data")

# Thumbnails are served by dynamic endpoints to support on-demand generation:
# - /static/prerolls/thumbnails/{category}/{thumb_name}
# - /static/thumbnails/{category}/{thumb_name} (compat)
# No static mount here to avoid shadowing the dynamic generator.



# Mount frontend static files LAST so API routes are checked first
# Diagnostics bundle (ZIP)
@app.get("/diagnostics/bundle")
def diagnostics_bundle():
    """
    Create a diagnostics ZIP with:
    - info.json (version, scheduler status, secure provider, resolved paths)
    - db/schema.sql (SQLite schema dump)
    - logs (app.log, service.log if present)
    - config/plex_config.sanitized.json (token removed if file exists)
    """
    try:
        import tempfile

        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        tmp_path = os.path.join(tempfile.gettempdir(), f"NeXroll_Diagnostics_{ts}.zip")

        # Collect info
        info = {
            "api_version": getattr(app, "version", None),
            "scheduler": {"running": scheduler.running},
            "secure_provider": secure_store.provider_info()[1],
            "paths": system_paths(),
            "timestamp_utc": datetime.datetime.utcnow().isoformat() + "Z",
        }

        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as z:
            # info.json
            z.writestr("info.json", json.dumps(info, indent=2))

            # DB schema
            try:
                schema_lines = []
                with engine.connect() as conn:
                    rows = conn.exec_driver_sql(
                        "SELECT type, name, sql FROM sqlite_master "
                        "WHERE type IN ('table','index','view') ORDER BY type,name"
                    ).fetchall()
                    for t, n, s in rows:
                        if s:
                            schema_lines.append(f"-- {t}: {n}\n{s};\n")
                if schema_lines:
                    z.writestr("db/schema.sql", "\n".join(schema_lines))
            except Exception as e:
                z.writestr("db/schema_error.txt", str(e))

            # Logs
            try:
                log_file = _log_file_path()
                if log_file and os.path.exists(log_file):
                    z.write(log_file, arcname=os.path.join("logs", os.path.basename(log_file)))
            except Exception:
                pass
            # Common service log location
            try:
                pd = os.environ.get("ProgramData")
                if pd:
                    svc_log = os.path.join(pd, "NeXroll", "logs", "service.log")
                    if os.path.exists(svc_log):
                        z.write(svc_log, arcname=os.path.join("logs", "service.log"))
            except Exception:
                pass

            # Sanitized legacy config
            try:
                if os.path.exists("plex_config.json"):
                    with open("plex_config.json", "r", encoding="utf-8") as f:
                        cfg = json.load(f) or {}
                    cfg.pop("plex_token", None)
                    z.writestr("config/plex_config.sanitized.json", json.dumps(cfg, indent=2))
            except Exception:
                pass

        return FileResponse(
            tmp_path,
            media_type="application/zip",
            filename=os.path.basename(tmp_path),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build diagnostics bundle: {e}")

# Server-Sent Events stream for lightweight live status
@app.get("/events")
async def events(request: Request):
    """
    Basic SSE endpoint emitting scheduler status and heartbeat every ~5s.
    Adds an SSE retry hint and hardens against disconnect races to reduce
    browser 'ERR_INCOMPLETE_CHUNKED_ENCODING' noise on transient network changes.
    """
    import asyncio as _asyncio
    import json as _json

    async def _gen():
        # Advise EventSource to wait ~5s before reconnect attempts
        yield "retry: 5000\n\n"
        try:
            while True:
                payload = {
                    "type": "status",
                    "time": datetime.datetime.utcnow().isoformat() + "Z",
                    "scheduler": {"running": scheduler.running},
                }
                yield f"data: {_json.dumps(payload)}\n\n"
                await _asyncio.sleep(5)
        except Exception:
            # Swallow cancellation / network errors to end stream cleanly
            return

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
    }
    return StreamingResponse(_gen(), media_type="text/event-stream", headers=headers)

# --- Jellyfin Integration ---
class JellyfinConnectRequest(BaseModel):
    url: str
    api_key: str

@app.post("/jellyfin/connect")
def connect_jellyfin(request: JellyfinConnectRequest, db: Session = Depends(get_db)):
    url = (request.url or "").strip()
    api_key = (request.api_key or "").strip()

    if not url:
        raise HTTPException(status_code=422, detail="Jellyfin server URL is required")
    if not api_key:
        raise HTTPException(status_code=422, detail="Jellyfin API key is required")

    # Normalize URL format (default to http:// when scheme missing)
    if not url.startswith(('http://', 'https://')):
        url = f"http://{url}"

    try:
        # Deferred import to avoid top-level import churn
        from backend.jellyfin_connector import JellyfinConnector
        connector = JellyfinConnector(url, api_key)

        # Reachability (public info/ping)
        if not connector.test_connection():
            raise HTTPException(status_code=422, detail="Failed to connect to Jellyfin server. Please check your URL.")

        # Persist URL (no plaintext key in DB)
        setting = db.query(models.Setting).first()
        if not setting:
            setting = models.Setting(plex_url=None, plex_token=None, jellyfin_url=url)
            db.add(setting)
        else:
            setting.jellyfin_url = url
            try:
                setting.updated_at = datetime.datetime.utcnow()
            except Exception:
                pass

        # Save API key to secure store (best-effort)
        try:
            secure_store.set_jellyfin_api_key(api_key)
        except Exception:
            pass

        db.commit()
        return {
            "connected": True,
            "message": "Successfully connected to Jellyfin server",
            "token_storage": secure_store.provider_info()[1]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Connection error: {str(e)}")

@app.get("/jellyfin/status")
def get_jellyfin_status(db: Session = Depends(get_db)):
    """
    Return Jellyfin connection status without throwing 500s.
    Always returns 200 with a JSON object. Logs internal errors where applicable.
    """
    try:
        setting = db.query(models.Setting).first()
    except Exception:
        setting = None

    jellyfin_url = getattr(setting, "jellyfin_url", None) if setting else None
    # Resolve API key from secure store
    api_key = None
    try:
        api_key = secure_store.get_jellyfin_api_key()
    except Exception:
        api_key = None

    # If URL missing, report disconnected with hints
    if not jellyfin_url:
        out = {"connected": False}
        try:
            out["url"] = jellyfin_url
            out["has_api_key"] = bool(api_key)
            out["provider"] = secure_store.provider_info()[1]
        except Exception:
            pass
        return out

    try:
        from backend.jellyfin_connector import JellyfinConnector
        connector = JellyfinConnector(jellyfin_url, api_key)
        info = connector.get_server_info() or {}
        if not isinstance(info, dict):
            info = {}
        info.setdefault("connected", False)
        try:
            info.setdefault("url", jellyfin_url)
            info.setdefault("has_api_key", bool(api_key))
            info.setdefault("provider", secure_store.provider_info()[1])
        except Exception:
            pass
        return info
    except Exception:
        return {
            "connected": False,
            "url": jellyfin_url,
            "has_api_key": bool(api_key)
        }

@app.post("/jellyfin/disconnect")
def disconnect_jellyfin(db: Session = Depends(get_db)):
    """Disconnect from Jellyfin server by clearing stored credentials"""
    setting = db.query(models.Setting).first()

    # Clear secure API key (best-effort)
    try:
        secure_store.delete_jellyfin_api_key()
    except Exception:
        pass

    if setting:
        setting.jellyfin_url = None
        try:
            setting.updated_at = datetime.datetime.utcnow()
        except Exception:
            pass
        db.commit()

    return {"disconnected": True, "message": "Successfully disconnected from Jellyfin server"}

# --- Jellyfin Category Apply/Remove (stub plan) ---
@app.post("/categories/{category_id}/apply-to-jellyfin")
def apply_category_to_jellyfin(category_id: int, db: Session = Depends(get_db)):
    """
    Apply a category's prerolls to Jellyfin by configuring the 'Local Intros' plugin when available.
    Always returns a 'plan' for visibility, and attempts to write the derived intro folders
    into the plugin configuration automatically.
    """
    # Validate Jellyfin configuration
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, "jellyfin_url", None):
        raise HTTPException(status_code=400, detail="Jellyfin not configured")

    # Resolve API key from secure store
    try:
        api_key = secure_store.get_jellyfin_api_key()
    except Exception:
        api_key = None
    if not api_key:
        raise HTTPException(status_code=400, detail="Jellyfin API key not available")

    # Validate category
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Collect prerolls (primary and many-to-many)
    prerolls = db.query(models.Preroll) \
        .outerjoin(models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id) \
        .filter(or_(models.Preroll.category_id == category_id,
                    models.preroll_categories.c.category_id == category_id)) \
        .distinct().all()
    if not prerolls:
        return {
            "applied": False,
            "supported": False,
            "message": "No prerolls found in this category",
            "preroll_count": 0
        }

    # Build absolute local paths
    preroll_paths_local = [os.path.abspath(p.path) for p in prerolls]

    # Translate local paths to server-visible paths using configured mappings (reuse existing mapping store)
    mappings = []
    try:
        raw = getattr(setting, "path_mappings", None)
        if raw:
            data = json.loads(raw)
            if isinstance(data, list):
                mappings = [m for m in data if isinstance(m, dict) and m.get("local") and m.get("plex")]
    except Exception:
        mappings = []

    def _translate_for_server(local_path: str) -> str:
        try:
            lp = os.path.normpath(local_path)
            best = None
            best_src = None
            best_len = -1
            for m in mappings:
                src = os.path.normpath(str(m.get("local")))
                if sys.platform.startswith("win"):
                    if lp.lower().startswith(src.lower()) and len(src) > best_len:
                        best = m
                        best_src = src
                        best_len = len(src)
                else:
                    if lp.startswith(src) and len(src) > best_len:
                        best = m
                        best_src = src
                        best_len = len(src)
            if best:
                dst_prefix = str(best.get("plex"))
                rest = lp[len(best_src):].lstrip("\\/")
                try:
                    if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                        out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                    elif "\\" in dst_prefix:
                        out = dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
                    else:
                        out = dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
                except Exception:
                    out = dst_prefix + (("/" if not dst_prefix.endswith(("/", "\\")) else "") + rest)
                return out
        except Exception:
            pass
        return local_path

    translated_paths = [_translate_for_server(p) for p in preroll_paths_local]

    # Best-effort server info and connector instance
    connector = None
    try:
        from backend.jellyfin_connector import JellyfinConnector
        connector = JellyfinConnector(setting.jellyfin_url, api_key)
        server_info = connector.get_server_info() or {}
    except Exception:
        server_info = {}

    plan = {
        "category": {"id": category.id, "name": category.name},
        "preroll_count": len(translated_paths),
        "translated_paths": translated_paths,
        "playlist_name": f"NeXroll - {category.name} Prerolls",
        "server": server_info,
        "notes": [
            "Jellyfin core does not support global pre-rolls.",
            "This endpoint attempts to configure the 'Local Intros' plugin automatically.",
            "Ensure the translated paths are visible to the Jellyfin server."
        ]
    }

    # Attempt to apply into 'Local Intros' plugin
    if connector is None:
        return {
            "applied": False,
            "supported": False,
            "message": "Jellyfin connector unavailable; returning plan only.",
            "plan": plan
        }

    try:
        # Locate the plugin by name (case-insensitive substring)
        plugin = (
            connector.find_plugin_by_name("Local Intros")
            or connector.find_plugin_by_name("Intros")
            or connector.find_plugin_by_name("Intro")
        )
        if not plugin:
            try:
                names = [(p.get("Name") or p.get("name") or "") for p in (connector.list_plugins() or [])]
                names = [n for n in names if n]
            except Exception:
                names = []
            return {
                "applied": False,
                "supported": False,
                "message": "Local Intros plugin was not found on this Jellyfin server. Install/enable it and try again.",
                "available_plugins": names,
                "plan": plan
            }

        plugin_id = plugin.get("Id") or plugin.get("id") or plugin.get("Guid") or plugin.get("guid")
        cfg = connector.get_plugin_configuration(plugin_id) or {}
        if not isinstance(cfg, dict):
            cfg = {}

        # Derive unique parent directories from translated file paths (plugin may expect directories to scan)
        def _parent_dir(pth: str) -> str:
            try:
                s = str(pth).rstrip("\\/")
                return os.path.dirname(s) if s else ""
            except Exception:
                return ""

        intro_dirs: list[str] = []
        for pth in translated_paths:
            d = _parent_dir(pth)
            if d and d not in intro_dirs:
                intro_dirs.append(d)
        intro_items: list[str] = intro_dirs

        # Heuristics to find a writable field in plugin configuration
        candidate_list_keys = [
            "IntroPaths", "Paths", "PrerollPaths", "Folders", "Directories",
            "IntroFolders", "FolderPaths", "paths", "folders", "directories"
        ]
        candidate_string_keys = [
            "Path", "IntroPath", "Folder", "Directory", "IntroFolder", "Root", "BasePath",
            "path", "folder", "directory"
        ]

        target_key = None
        mode = None  # "list" | "string"

        for k in candidate_list_keys:
            if k in cfg and isinstance(cfg.get(k), list):
                target_key = k
                mode = "list"
                break
        if not target_key:
            for k in candidate_string_keys:
                if k in cfg and isinstance(cfg.get(k), str):
                    target_key = k
                    mode = "string"
                    break

        # If no existing key found, try to force set a common one
        if not target_key:
            target_key = "IntroPaths"
            mode = "list"

        # Apply new values (always try to set, even if key didn't exist)
        # For Jellyfin Local Intros plugin, set "Local" to the primary directory
        if intro_items:
            cfg["Local"] = intro_items[0]
        if mode == "list":
            cfg[target_key] = intro_items
            new_count = len(intro_items)
        else:
            cfg[target_key] = intro_items[0] if intro_items else ""
            new_count = 1 if intro_items else 0

        _file_log(f"Attempting to set Jellyfin plugin {plugin_id} config: {json.dumps(cfg, indent=2)}")
        current_cfg = connector.get_plugin_configuration(plugin_id) or {}
        _file_log(f"Jellyfin plugin current config before update: {json.dumps(current_cfg, indent=2)}")
        # Set DefaultLocalVideos to detected video IDs that match the category's preroll filenames
        detected = current_cfg.get("DetectedLocalVideos", [])
        if detected:
            # Get normalized names from category preroll filenames
            preroll_filenames = [os.path.basename(p) for p in translated_paths]
            normalized_names = set()
            for f in preroll_filenames:
                name = os.path.splitext(f)[0].replace('_', ' ')
                normalized_names.add(name)
            # Match detected videos to category prerolls
            cfg["DefaultLocalVideos"] = [d.get("ItemId") for d in detected if d.get("ItemId") and d.get("Name") in normalized_names]
        _file_log(f"Jellyfin plugin config to set: {json.dumps(cfg, indent=2)}")
        saved = connector.set_plugin_configuration(plugin_id, cfg)
        _file_log(f"Jellyfin plugin config update result: {saved}")
        if saved:
            # Also save it as the active category in the Setting
            db.query(models.Category).update({"apply_to_plex": False})
            cat = db.query(models.Category).filter(models.Category.id == category_id).first()
            if cat:
                cat.apply_to_plex = True
                setting = db.query(models.Setting).first()
                if setting:
                    setting.active_category = category_id
                db.commit()
            
            return {
                "applied": True,
                "supported": True,
                "message": f"Injected {new_count} {'path' if new_count == 1 else 'paths'} into Jellyfin 'Local Intros' plugin.",
                "details": {
                    "plugin": {"id": plugin_id, "name": (plugin.get("Name") or plugin.get("name"))},
                    "updated_key": target_key,
                    "value_count": new_count,
                    "paths_preview": intro_items[:5]
                },
                "plan": plan
            }
        else:
            # If failed, try alternative keys
            alt_keys = ["Paths", "IntroPath", "Folder"]
            for alt_key in alt_keys:
                if alt_key != target_key:
                    cfg_alt = cfg.copy()
                    cfg_alt[alt_key] = intro_dirs if mode == "list" else (intro_dirs[0] if intro_dirs else "")
                    if connector.set_plugin_configuration(plugin_id, cfg_alt):
                        # Also save it as the active category in the Setting
                        db.query(models.Category).update({"apply_to_plex": False})
                        cat = db.query(models.Category).filter(models.Category.id == category_id).first()
                        if cat:
                            cat.apply_to_plex = True
                            setting = db.query(models.Setting).first()
                            if setting:
                                setting.active_category = category_id
                            db.commit()
                        
                        return {
                            "applied": True,
                            "supported": True,
                            "message": f"Injected {new_count} {'path' if new_count == 1 else 'paths'} into Jellyfin 'Local Intros' plugin using alternative key '{alt_key}'.",
                            "details": {
                                "plugin": {"id": plugin_id, "name": (plugin.get("Name") or plugin.get("name"))},
                                "updated_key": alt_key,
                                "value_count": new_count,
                                "paths_preview": intro_items[:5]
                            },
                            "plan": plan
                        }
            return {
                "applied": False,
                "supported": False,
                "message": "Failed to update Local Intros plugin configuration with any key.",
                "plugin": {"id": plugin_id, "name": (plugin.get("Name") or plugin.get("name"))},
                "tried_keys": [target_key] + alt_keys,
                "plan": plan
            }

    except Exception as e:
        return {
            "applied": False,
            "supported": False,
            "message": f"Jellyfin plugin update error: {e}",
            "plan": plan
        }

@app.post("/categories/{category_id}/remove-from-jellyfin")
def remove_category_from_jellyfin(category_id: int, db: Session = Depends(get_db)):
    """
    Stub endpoint mirroring Plex remove semantics. There is no global Jellyfin pre-roll to remove.
    Returns a structured response to keep UI stable.
    """
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail="Category not found")
    return {
        "removed": False,
        "supported": False,
        "message": "Jellyfin preroll removal is not applicable yet."
    }

# --- Community Prerolls Feature ---

# Cache for community preroll health check (5 minute TTL)
_community_health_cache = {"status": None, "checked_at": None, "error": None}
COMMUNITY_HEALTH_CACHE_TTL = 300  # 5 minutes in seconds

@app.get("/community-prerolls/health")
def check_community_prerolls_health():
    """
    Check if prerolls.uk is accessible.
    Results are cached for 5 minutes to avoid excessive requests.
    Returns: {
        "online": bool,
        "response_time_ms": int or None,
        "last_checked": datetime,
        "error": str or None
    }
    """
    now = datetime.datetime.utcnow()
    
    # Check cache first
    if (_community_health_cache["checked_at"] and 
        (now - _community_health_cache["checked_at"]).total_seconds() < COMMUNITY_HEALTH_CACHE_TTL):
        return {
            "online": _community_health_cache["status"],
            "response_time_ms": _community_health_cache.get("response_time_ms"),
            "last_checked": _community_health_cache["checked_at"].isoformat() + "Z",
            "error": _community_health_cache.get("error"),
            "cached": True
        }
    
    # Perform health check
    try:
        start_time = time.time()
        response = requests.get(
            "https://prerolls.uk/",
            timeout=10,
            headers={"User-Agent": f"NeXroll/{app_version}"}
        )
        response_time_ms = int((time.time() - start_time) * 1000)
        
        is_online = response.status_code == 200
        error_msg = None if is_online else f"HTTP {response.status_code}"
        
        # Update cache
        _community_health_cache.update({
            "status": is_online,
            "checked_at": now,
            "response_time_ms": response_time_ms,
            "error": error_msg
        })
        
        return {
            "online": is_online,
            "response_time_ms": response_time_ms,
            "last_checked": now.isoformat() + "Z",
            "error": error_msg,
            "cached": False
        }
        
    except requests.exceptions.Timeout:
        error_msg = "Request timeout (>10s)"
        _community_health_cache.update({
            "status": False,
            "checked_at": now,
            "response_time_ms": None,
            "error": error_msg
        })
        return {
            "online": False,
            "response_time_ms": None,
            "last_checked": now.isoformat() + "Z",
            "error": error_msg,
            "cached": False
        }
    except Exception as e:
        error_msg = f"Connection error: {str(e)}"
        _community_health_cache.update({
            "status": False,
            "checked_at": now,
            "response_time_ms": None,
            "error": error_msg
        })
        return {
            "online": False,
            "response_time_ms": None,
            "last_checked": now.isoformat() + "Z",
            "error": error_msg,
            "cached": False
        }

@app.get("/community-prerolls/fair-use-policy")
def get_community_fair_use_policy():
    """
    Return the Fair Use Policy text from Typical Nerds.
    Fetched from: https://prerolls.uk/%23%20FAIR%20USE%20POLICY%20-%20READ%20ME.txt
    """
    policy_text = """------------------------------------------------
Fair Use Policy Disclosure
------------------------------------------------

We appreciate your interest in our community's assets, which are intended for informational and educational purposes only. We encourage their appropriate use within the boundaries of copyright law. Please read the following Fair Use Policy carefully before utilizing our assets:

	1.	Ownership: All assets, including but not limited to text, images, videos, and audio files, available on our platform may be protected by copyright and belong to their respective owners. Ownership rights are not transferred or assigned to users.
	2.	Permissible Use: Users are granted a non-exclusive, non-transferable, revocable license to use the assets provided on our platform for personal, non-commercial purposes, unless otherwise specified. Such use should be in compliance with applicable copyright laws.
	3.	Prohibited Actions: Users must not copy, reproduce, distribute, modify, publicly display, or create derivative works from the assets without obtaining explicit permission from the creator. 
	4.	Enforcement: We reserve the right to monitor and enforce compliance with this Fair Use Policy. We may take appropriate action, including but not limited to disabling access, removing content, and pursuing legal remedies against individuals or entities found to be infringing upon copyrights or violating this policy.
	5.	Reporting Infringements: If you believe that any content on our platform infringes upon your copyright or violates this Fair Use Policy, please contact me immediately via email at contact@typicalnerds.uk. We will promptly investigate and take appropriate action.
	6.	Disclaimer: This Fair Use Policy does not override or replace any additional terms or conditions that may apply to specific assets or services offered on our platform. Users are advised to review such terms and conditions in conjunction with this policy.

By accessing and using these assets, you acknowledge that you have read, understood, and agreed to comply with this Fair Use Policy. Failure to adhere to this policy may result in the termination of your access to our assets and potential legal consequences.
"""
    return {
        "policy": policy_text,
        "source": "https://prerolls.uk/",
        "credit": "https://typicalnerds.uk/"
    }

@app.post("/community-prerolls/fair-use/accept")
def accept_fair_use_policy(db: Session = Depends(get_db)):
    """
    Record user's acceptance of the Fair Use Policy.
    Stored in settings so users only see the agreement once.
    """
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting(plex_url=None, plex_token=None)
        db.add(setting)
        db.commit()
        db.refresh(setting)
    
    try:
        setting.community_fair_use_accepted = True
        setting.community_fair_use_accepted_at = datetime.datetime.utcnow()
        db.commit()
        return {
            "accepted": True,
            "accepted_at": setting.community_fair_use_accepted_at.isoformat() + "Z",
            "message": "Fair Use Policy accepted"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record acceptance: {str(e)}")

@app.get("/community-prerolls/fair-use/status")
def get_fair_use_status(db: Session = Depends(get_db)):
    """
    Check if user has accepted the Fair Use Policy.
    Returns acceptance status and timestamp.
    """
    setting = db.query(models.Setting).first()
    if not setting:
        return {
            "accepted": False,
            "accepted_at": None
        }
    
    accepted = getattr(setting, "community_fair_use_accepted", False)
    accepted_at = getattr(setting, "community_fair_use_accepted_at", None)
    
    return {
        "accepted": bool(accepted),
        "accepted_at": accepted_at.isoformat() + "Z" if accepted_at else None
    }

@app.get("/community-prerolls/test-scrape")
def test_community_scrape():
    """Test endpoint to verify scraping works"""
    try:
        import requests
        from bs4 import BeautifulSoup
        
        url = "https://prerolls.uk/Holidays/Halloween/Carving%20Pumpkin%20-%20AwesomeAustn/"
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        videos = []
        for link in soup.find_all('a'):
            href = link.get('href', '')
            if href.endswith('.mp4'):
                videos.append(href)
        
        return {
            "status": "success",
            "url": url,
            "status_code": response.status_code,
            "videos_found": len(videos),
            "videos": videos
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "traceback": str(__import__('traceback').format_exc())
        }

# ===== LOCAL INDEX SYSTEM FOR FASTER SEARCHES =====

# Global progress tracking for index building
_index_build_progress = {
    "building": False,
    "progress": 0,
    "current_dir": "",
    "files_found": 0,
    "dirs_visited": 0,
    "message": ""
}

def _build_prerolls_index(progress_callback=None) -> dict:
    """
    Build a complete index of Typical Nerds prerolls by scraping the directory.
    This is a one-time operation that caches everything locally for fast searches.
    Returns the index dict with metadata.
    
    Args:
        progress_callback: Optional callback function for progress updates
    """
    import urllib.parse
    from urllib.parse import urljoin
    from bs4 import BeautifulSoup
    import time
    import json
    
    global _index_build_progress
    _index_build_progress["building"] = True
    _index_build_progress["progress"] = 0
    _index_build_progress["message"] = "Starting index build..."
    
    _file_log("Building Typical Nerds prerolls index (this may take a few minutes)...")
    
    base_url = "https://prerolls.uk"
    headers = {
        "Accept": "text/html,application/json",
        "User-Agent": f"NeXroll/{app_version} (Index Builder; +https://github.com/JFLXCLOUD/NeXroll)"
    }
    
    index_data = {
        "version": "1.0",
        "created_at": datetime.datetime.now().isoformat(),
        "base_url": base_url,
        "prerolls": []
    }
    
    visited_urls = set()
    prerolls = []
    json_count = 0
    html_count = 0
    estimated_total_dirs = 400  # Rough estimate for progress calculation
    
    def update_progress():
        """Update global progress state"""
        dirs_done = len(visited_urls)
        # Progress is 0-95% during scanning, then 95-100% for final processing
        # Only update progress percentage if it hasn't been manually set higher
        current_progress = _index_build_progress.get("progress", 0)
        if current_progress < 95:
            progress_pct = min(95, int((dirs_done / estimated_total_dirs) * 95))
            _index_build_progress["progress"] = progress_pct
        _index_build_progress["dirs_visited"] = dirs_done
        _index_build_progress["files_found"] = len(prerolls)
        
        if progress_callback:
            progress_callback(_index_build_progress.copy())
    
    def scrape_directory(url, depth=0, max_depth=999):
        """Recursively scrape all directories for video files"""
        url = url.rstrip('/') + '/'
        
        # Skip utility folders that don't contain prerolls
        # Note: We DO index "prerolls.video - Archive" since it has content
        skip_folders = ['site-assets', 'templates']
        if any(skip in url.lower() for skip in skip_folders):
            _file_log(f"⊘ Skipping utility folder: {url}")
            return
        
        # Only check if already visited (no depth limit - scan everything!)
        if url in visited_urls:
            return
        visited_urls.add(url)
        
        # Update progress
        path_display = url.replace(base_url, '') or '/'
        _index_build_progress["current_dir"] = path_display
        update_progress()
        
        _file_log(f"{'  ' * depth}→ Indexing (depth={depth}): {path_display} [{len(prerolls)} files]")
        
        # Respectful delay between requests (0.15s = ~7 requests/sec)
        time.sleep(0.15)
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                _file_log(f"⚠ HTTP {response.status_code} for {url}")
                return
            
            # Caddy can return either HTML or JSON depending on context
            # We need to handle both formats!
            content_type = response.headers.get('Content-Type', '')
            
            if 'application/json' in content_type:
                # Parse JSON response from Caddy
                nonlocal json_count
                json_count += 1
                try:
                    items = json.loads(response.text)
                    _file_log(f"  📋 JSON format detected, parsing {len(items)} items")
                    
                    for item in items:
                        name = item.get('name', '')
                        is_dir = item.get('is_dir', False)
                        item_url = item.get('url', name)
                        
                        if not name or name in ['.', '..']:
                            continue
                        
                        # Build full URL
                        full_url = urljoin(url, item_url)
                        
                        if not full_url.startswith(base_url):
                            continue
                        
                        # Recursively explore directories
                        if is_dir:
                            scrape_directory(full_url, depth + 1, max_depth)
                        # Index video files
                        elif any(name.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']):
                            title = name
                            
                            # Extract category from path
                            path_parts = full_url.replace(base_url, '').split('/')
                            folder_category = path_parts[1] if len(path_parts) > 1 and path_parts[1] else "Community"
                            
                            # Extract creator from parent folder
                            creator = "Typical Nerds"
                            if len(path_parts) >= 2:
                                try:
                                    parent_folder = urllib.parse.unquote(path_parts[-2])
                                    if ' - ' in parent_folder:
                                        creator = parent_folder.split(' - ')[-1].strip()
                                except:
                                    pass
                            
                            # Create searchable keywords from path and title
                            keywords = []
                            for part in path_parts:
                                decoded = urllib.parse.unquote(part).lower()
                                # Split by common delimiters
                                words = decoded.replace('_', ' ').replace('-', ' ').replace('/', ' ').split()
                                keywords.extend(words)
                            keywords.extend(title.lower().replace('_', ' ').replace('-', ' ').split())
                            keywords = list(set([k for k in keywords if len(k) > 2]))  # Deduplicate and filter short words
                            
                            preroll_entry = {
                                "id": full_url.replace(base_url, ''),  # Use URL path as ID (e.g., "/Holidays/Christmas/file.mp4")
                                "title": title.replace('.mp4', '').replace('.mkv', '').replace('_', ' ').replace('-', ' ').title(),
                                "creator": creator,
                                "category": folder_category,
                                "url": full_url,
                                "path": full_url.replace(base_url, ''),
                                "keywords": keywords,  # For fast local searching
                                "tags": folder_category.lower()
                            }
                            
                            prerolls.append(preroll_entry)
                            _file_log(f"  ✓ Found: {title[:60]}")
                except json.JSONDecodeError as e:
                    _file_log(f"✗ Failed to parse JSON from {url}: {e}")
                    return
            else:
                # Parse HTML response with BeautifulSoup
                nonlocal html_count
                html_count += 1
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    text = link.get_text().strip()
                    
                    if not href or href.startswith('?') or href in ['../', './', '..', '.', '', '../']:
                        continue
                    
                    if href == '../' or text in ['Up', '/', '..']:
                        continue
                    
                    full_url = urljoin(url, href)
                    
                    if not full_url.startswith(base_url):
                        continue
                    
                    # Recursively explore directories
                    if href.endswith('/'):
                        scrape_directory(full_url, depth + 1, max_depth)
                    # Index video files
                    elif any(href.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']):
                        filename = href.split('/')[-1]
                        title = text or filename
                        
                        # Extract category from path
                        path_parts = full_url.replace(base_url, '').split('/')
                        folder_category = path_parts[1] if len(path_parts) > 1 and path_parts[1] else "Community"
                        
                        # Extract creator from parent folder
                        creator = "Typical Nerds"
                        if len(path_parts) >= 2:
                            try:
                                parent_folder = urllib.parse.unquote(path_parts[-2])
                                if ' - ' in parent_folder:
                                    creator = parent_folder.split(' - ')[-1].strip()
                            except:
                                pass
                        
                        # Create searchable keywords from path and title
                        keywords = []
                        for part in path_parts:
                            decoded = urllib.parse.unquote(part).lower()
                            # Split by common delimiters
                            words = decoded.replace('_', ' ').replace('-', ' ').replace('/', ' ').split()
                            keywords.extend(words)
                        keywords.extend(title.lower().replace('_', ' ').replace('-', ' ').split())
                        keywords = list(set([k for k in keywords if len(k) > 2]))  # Deduplicate and filter short words
                        
                        preroll_entry = {
                            "id": full_url.replace(base_url, ''),  # Use URL path as ID (e.g., "/Holidays/Christmas/file.mp4")
                            "title": title.replace('.mp4', '').replace('.mkv', '').replace('_', ' ').replace('-', ' ').title(),
                            "creator": creator,
                            "category": folder_category,
                            "url": full_url,
                            "path": full_url.replace(base_url, ''),
                            "keywords": keywords,  # For fast local searching
                            "tags": folder_category.lower()
                        }
                        
                        prerolls.append(preroll_entry)
                        _file_log(f"  ✓ Found: {title[:60]}")
        except json.JSONDecodeError as e:
            _file_log(f"✗ JSON parse error for {url}: {e}")
        except Exception as e:
            import traceback
            _file_log(f"✗ Error indexing {url}: {e}")
            _file_log(f"  Traceback: {traceback.format_exc()}")
    
    # Build the index by scraping from root to discover all folders
    # No depth limit - scan all subdirectories recursively!
    _file_log(f"{'='*60}")
    _file_log(f"Starting comprehensive index from root: {base_url}")
    _file_log(f"{'='*60}")
    
    _index_build_progress["message"] = "Scanning directories..."
    scrape_directory(base_url, depth=0, max_depth=999)
    
    _index_build_progress["message"] = "Finalizing index..."
    _index_build_progress["progress"] = 98
    update_progress()
    
    index_data["prerolls"] = prerolls
    index_data["total_prerolls"] = len(prerolls)
    index_data["directories_visited"] = len(visited_urls)
    
    _index_build_progress["progress"] = 100
    _index_build_progress["message"] = f"Complete! Found {len(prerolls)} prerolls"
    _index_build_progress["building"] = False
    update_progress()
    
    _file_log(f"{'='*60}")
    _file_log(f"✓ Index building complete!")
    _file_log(f"  Total prerolls indexed: {len(prerolls)}")
    _file_log(f"  Directories scanned: {len(visited_urls)}")
    _file_log(f"  HTML responses: {html_count}")
    _file_log(f"  JSON responses: {json_count}")
    _file_log(f"  Categories found: {len(set(p['category'] for p in prerolls))}")
    _file_log(f"  Creators found: {len(set(p['creator'] for p in prerolls))}")
    _file_log(f"{'='*60}")
    
    return index_data


def _save_prerolls_index(index_data: dict) -> bool:
    """Save the prerolls index to disk as JSON"""
    try:
        PREROLLS_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(PREROLLS_INDEX_PATH, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)
        _file_log(f"Saved prerolls index to: {PREROLLS_INDEX_PATH}")
        return True
    except Exception as e:
        _file_log(f"Error saving prerolls index: {e}")
        return False


def _load_prerolls_index() -> Optional[dict]:
    """Load the prerolls index from disk"""
    try:
        if not PREROLLS_INDEX_PATH.exists():
            _file_log("No local prerolls index found")
            return None
        
        # Check if index is too old
        file_age = time.time() - PREROLLS_INDEX_PATH.stat().st_mtime
        if file_age > PREROLLS_INDEX_MAX_AGE:
            _file_log(f"Prerolls index is {file_age / 86400:.1f} days old (max {PREROLLS_INDEX_MAX_AGE / 86400} days)")
            return None
        
        with open(PREROLLS_INDEX_PATH, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        # Only log on first load or errors (too verbose for every call)
        # _file_log(f"Loaded prerolls index: {index_data.get('total_prerolls', 0)} prerolls (created {index_data.get('created_at', 'unknown')})")
        return index_data
    except Exception as e:
        _file_log(f"Error loading prerolls index: {e}")
        return None


def _search_local_index(index_data: dict, query: str = "", category: str = "", platform: str = "", limit: int = 50) -> List[dict]:
    """
    Search the local prerolls index (FAST - milliseconds vs seconds)
    
    Args:
        index_data: The loaded index dict
        query: Search term to match against keywords
        category: Filter by category
        platform: Filter by platform name in title
        limit: Maximum results to return
    
    Returns:
        List of matching preroll dicts
    """
    prerolls = index_data.get("prerolls", [])
    results = []
    
    query_lower = query.lower() if query else ""
    category_lower = category.lower() if category else ""
    platform_lower = platform.lower() if platform else ""
    
    # Build expanded search terms using synonyms
    search_terms = [query_lower] if query_lower else []
    if query_lower:
        # Check if query matches any synonym groups
        for key, synonyms in SEARCH_SYNONYMS.items():
            if query_lower in key or key in query_lower:
                # Add all related terms
                search_terms.extend(synonyms)
                search_terms.append(key)
                break
        # Remove duplicates
        search_terms = list(set(search_terms))
    
    for preroll in prerolls:
        # Apply filters
        if search_terms:
            # Check if ANY search term matches keywords or title
            match_found = False
            preroll_title = preroll.get("title", "").lower()
            preroll_keywords = preroll.get("keywords", [])
            
            for term in search_terms:
                # Check keywords
                if any(term in keyword for keyword in preroll_keywords):
                    match_found = True
                    break
                # Check title
                if term in preroll_title:
                    match_found = True
                    break
            
            if not match_found:
                continue
        
        if category_lower:
            if category_lower not in preroll.get("category", "").lower():
                continue
        
        if platform_lower:
            title_lower = preroll.get("title", "").lower()
            if platform_lower not in title_lower:
                continue
        
        results.append(preroll)
        
        if len(results) >= limit:
            break
    
    return results


@app.get("/community-prerolls/build-index")
def build_community_prerolls_index(request: Request):
    """
    Build the local prerolls index by scraping Typical Nerds directory.
    This is a manual operation triggered by the user (e.g., "Refresh Index" button).
    
    WARNING: This may take several minutes and makes many HTTP requests.
    Only use when needed (e.g., weekly or when new prerolls are added).
    """
    import time
    
    # Rate limiting: Only allow one build per IP every 10 minutes
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    rate_limit_key = f"index_build_{client_ip}"
    
    if rate_limit_key in community_search_rate_limit:
        last_build = community_search_rate_limit[rate_limit_key]
        time_since_last = current_time - last_build
        if time_since_last < 600:  # 10 minutes cooldown
            remaining = int(600 - time_since_last)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining // 60} minutes {remaining % 60} seconds before rebuilding the index. Building the index is resource-intensive."
            )
    
    community_search_rate_limit[rate_limit_key] = current_time
    
    try:
        index_data = _build_prerolls_index()
        success = _save_prerolls_index(index_data)
        
        if success:
            return {
                "status": "success",
                "message": "Prerolls index built successfully",
                "total_prerolls": index_data.get("total_prerolls", 0),
                "directories_visited": index_data.get("directories_visited", 0),
                "created_at": index_data.get("created_at"),
                "index_path": str(PREROLLS_INDEX_PATH)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save index to disk")
    except Exception as e:
        _file_log(f"Error building prerolls index: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to build index: {str(e)}")


@app.get("/community-prerolls/build-progress")
async def get_build_progress():
    """
    Server-Sent Events endpoint for real-time index build progress
    """
    from starlette.responses import StreamingResponse
    import asyncio
    import json
    
    async def event_stream():
        try:
            while True:
                # Send current progress state
                progress_data = _index_build_progress.copy()
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                # Stop streaming when build is complete
                # Send final message, wait to ensure delivery, then stop
                if not progress_data.get("building", False) and progress_data.get("progress", 0) == 100:
                    await asyncio.sleep(0.5)  # Give time for final message to be received
                    break
                
                await asyncio.sleep(0.5)  # Update every 500ms
        except Exception as e:
            _file_log(f"Progress stream error: {e}")
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/community-prerolls/index-status")
def get_community_prerolls_index_status():
    """
    Get status of the local prerolls index (exists, age, size, etc.)
    """
    import time
    
    if not PREROLLS_INDEX_PATH.exists():
        return {
            "exists": False,
            "message": "No local index found. Build it for faster searches!",
            "index_path": str(PREROLLS_INDEX_PATH)
        }
    
    try:
        file_stats = PREROLLS_INDEX_PATH.stat()
        file_age = time.time() - file_stats.st_mtime
        file_size_mb = file_stats.st_size / (1024 * 1024)
        
        index_data = _load_prerolls_index()
        
        is_stale = file_age > PREROLLS_INDEX_MAX_AGE
        
        return {
            "exists": True,
            "is_stale": is_stale,
            "age_days": file_age / 86400,
            "max_age_days": PREROLLS_INDEX_MAX_AGE / 86400,
            "size_mb": round(file_size_mb, 2),
            "total_prerolls": index_data.get("total_prerolls", 0) if index_data else 0,
            "created_at": index_data.get("created_at") if index_data else None,
            "index_path": str(PREROLLS_INDEX_PATH),
            "message": "Index is stale. Refresh recommended." if is_stale else "Index is up to date."
        }
    except Exception as e:
        return {
            "exists": True,
            "error": str(e),
            "index_path": str(PREROLLS_INDEX_PATH)
        }


@app.get("/community-prerolls/search")
def search_community_prerolls(request: Request, query: str = "", category: str = "", platform: str = "", limit: int = 50, db: Session = Depends(get_db)):
    """
    Search the Typical Nerds preroll library (LOCAL INDEX PREFERRED - FAST!).
    
    Query: search term (title, description)
    Category: filter by category (holiday, theme, etc.)
    Platform: filter by platform (plex, jellyfin, emby, or empty for all)
    Limit: max results (default 50, max 100)
    
    Returns list of prerolls with metadata and download URLs.
    
    NEW: Uses local index first for instant results (milliseconds).
    Fallback: If no index, falls back to slow remote scraping (rate limited).
    
    Requires Fair Use Policy acceptance to protect Typical Nerds community.
    """
    # Check Fair Use Policy acceptance first
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, "community_fair_use_accepted", False):
        raise HTTPException(
            status_code=403,
            detail="You must accept the Fair Use Policy before searching community prerolls. Please accept the policy in the Community Prerolls tab."
        )
    
    import urllib.parse
    from urllib.parse import urljoin, urlparse
    from bs4 import BeautifulSoup
    import time
    
    if limit > 100:
        limit = 100
    
    # ===== NEW: TRY LOCAL INDEX FIRST (FAST!) =====
    _file_log(f"Community search: query='{query}' category='{category}' platform='{platform}' limit={limit}")
    
    index_data = _load_prerolls_index()
    if index_data:
        # LOCAL INDEX FOUND - Use it for instant search!
        _file_log("Using local prerolls index for fast search")
        results = _search_local_index(index_data, query, category, platform, limit)
        
        return {
            "found": len(results),
            "results": results,
            "total": len(results),
            "query": query,
            "category": category,
            "source": "local_index",
            "index_created": index_data.get("created_at"),
            "message": f"Searched {index_data.get('total_prerolls', 0)} prerolls from local index (instant!)"
        }
    
    # ===== FALLBACK: NO INDEX - Use slow remote scraping =====
    _file_log("No local index found - falling back to slow remote scraping")
    _file_log("TIP: Build the index for much faster searches (Community Prerolls > Refresh Index button)")
    
    # Rate limiting for remote scraping only
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    _file_log(f"Community search from IP: {client_ip}, last search: {community_search_rate_limit.get(client_ip, 'never')}")
    
    if client_ip in community_search_rate_limit:
        last_search = community_search_rate_limit[client_ip]
        time_since_last = current_time - last_search
        _file_log(f"Time since last search: {time_since_last:.2f}s (cooldown: {COMMUNITY_SEARCH_COOLDOWN}s)")
        if time_since_last < COMMUNITY_SEARCH_COOLDOWN:
            remaining = int(COMMUNITY_SEARCH_COOLDOWN - time_since_last)
            raise HTTPException(
                status_code=429,
                detail=f"Please wait {remaining} seconds before searching again. Build the local index for instant searches without cooldown!"
            )
    
    community_search_rate_limit[client_ip] = current_time
    
    # Clean old entries (older than 1 hour) to prevent memory leak
    cutoff = current_time - 3600
    expired_ips = [ip for ip, ts in community_search_rate_limit.items() if ts < cutoff]
    for ip in expired_ips:
        del community_search_rate_limit[ip]
    
    try:
        # Try to connect to the community library
        base_url = "https://prerolls.uk"
        
        headers = {
            "Accept": "text/html,application/json",
            "User-Agent": f"NeXroll/{app_version} (Rate-Limited Scraper; +https://github.com/JFLXCLOUD/NeXroll)"
        }
        
        # First, try the API endpoint if it exists (unlikely)
        search_url = f"{base_url}/api/search"
        params = {
            "q": query or "",
            "category": category or "",
            "limit": limit
        }
        
        try:
            # Attempt to query the live API (with short timeout since it likely doesn't exist)
            response = requests.get(search_url, params=params, headers=headers, timeout=2)
            if response.status_code == 200:
                try:
                    data = response.json()
                    _file_log(f"Community preroll search (API): found {len(data.get('results', []))} results")
                    return {
                        "found": len(data.get("results", [])),
                        "results": data.get("results", []),
                        "total": data.get("total", 0),
                        "query": query,
                        "category": category,
                        "source": "api"
                    }
                except:
                    pass  # Not JSON, try directory listing
        except Exception as api_err:
            _file_log(f"Community preroll search API failed: {api_err}")
        
        # Try to scrape the directory listing - explore folders recursively
        try:
            _file_log(f"Starting directory scrape for query='{query}' category='{category}' platform='{platform}' limit={limit}")
            _file_log(f"BeautifulSoup available: {BeautifulSoup is not None}")
            
            results = []
            visited_urls = set()
            
            # Start with broad category paths for faster searching
            # Starting from specific categories is faster than root
            start_paths = [
                f"{base_url}/Community/",
                f"{base_url}/Holidays/",
                f"{base_url}/Seasons/",
                f"{base_url}/Clips/"
            ]
            
            def scrape_directory(url, depth=0, max_depth=4):
                """Recursively scrape directories for video files"""
                # Normalize URL (using urljoin and urlparse from parent scope)
                url = url.rstrip('/') + '/'
                
                # Early exit conditions for speed
                if depth > max_depth or url in visited_urls or len(results) >= limit:
                    return
                visited_urls.add(url)
                
                _file_log(f"Scraping URL: {url} (depth={depth}, results so far={len(results)})")
                
                # Rate limiting: Reduced to 200ms for faster searches while still being respectful
                # This is a balance between speed and not overwhelming the server
                time.sleep(0.2)  # 200ms delay between requests (was 500ms)
                
                try:
                    # Reduced timeout from 10s to 5s for faster failure on slow responses
                    response = requests.get(url, headers=headers, timeout=5)
                    if response.status_code != 200:
                        return
                    
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    for link in soup.find_all('a'):
                        if len(results) >= limit:
                            break
                            
                        href = link.get('href', '')
                        text = link.get_text().strip()
                        
                        # Log first few links from each directory for debugging
                        if depth >= 3:  # Only log deeper directories to reduce noise
                            _file_log(f"  Link found: {href}")
                        
                        # Skip navigation links
                        if not href or href.startswith('?') or href in ['../', './', '..', '.', '']:
                            continue
                        
                        # Skip parent directory links
                        if href == '../' or text in ['Up', '/', '..']:
                            continue
                        
                        # Build full URL using urljoin to properly handle relative paths
                        full_url = urljoin(url, href)
                        
                        # Skip if URL goes outside base domain
                        if not full_url.startswith(base_url):
                            continue
                        
                        # Check if it's a directory (ends with /)
                        if href.endswith('/'):
                            # Recursively explore ALL subdirectories
                            # Query filtering happens at the file level, not directory level
                            scrape_directory(full_url, depth + 1, max_depth)
                        # Check if it's a video file
                        elif any(href.lower().endswith(ext) for ext in ['.mp4', '.mkv', '.avi', '.mov', '.webm']):
                            _file_log(f"Found video file: {href} at {url}")
                            # Extract filename without extension for title
                            filename = href.split('/')[-1]
                            title = text or filename
                            
                            # Apply query filter
                            # Check if query matches the URL path (including parent directories) OR the filename
                            if query:
                                query_lower = query.lower()
                                url_lower = full_url.lower()
                                title_lower = title.lower()
                                
                                # Extract the parent directory path to check if we're in a matching category
                                # e.g., /Holidays/Christmas/ should match query "christmas"
                                path_parts = url_lower.split('/')
                                
                                # Check if query matches:
                                # 1. Any part of the directory path (e.g., /Christmas/)
                                # 2. The filename itself
                                matches = any(query_lower in part for part in path_parts) or query_lower in title_lower
                                
                                if not matches:
                                    continue
                                
                                _file_log(f"✓ Matched '{query}': {title}")
                            
                            # Apply category filter
                            if category:
                                category_lower = category.lower()
                                if category_lower not in full_url.lower() and category_lower not in title.lower():
                                    continue
                            
                            # Apply platform filter
                            if platform:
                                platform_lower = platform.lower()
                                # Check if title contains the platform name (e.g., "Plex", "Jellyfin", "Emby")
                                if platform_lower not in title.lower() and platform_lower not in filename.lower():
                                    continue
                            
                            # Extract category from folder path
                            path_parts = full_url.replace(base_url, '').split('/')
                            folder_category = path_parts[1] if len(path_parts) > 1 and path_parts[1] else "Community"
                            
                            # Extract creator from parent folder name
                            # Format is typically: /Category/Theme/Title - Creator/video.mp4
                            # So the creator is the last part after " - " in the parent folder
                            creator = "Typical Nerds"
                            if len(path_parts) >= 2:
                                try:
                                    parent_folder = urllib.parse.unquote(path_parts[-2])  # Decode URL encoding
                                    if ' - ' in parent_folder:
                                        creator = parent_folder.split(' - ')[-1].strip()
                                except:
                                    pass  # Keep default creator on any error
                            
                            results.append({
                                "id": full_url.replace(base_url, '').replace('/', '_').replace('.', '_'),
                                "title": title.replace('.mp4', '').replace('.mkv', '').replace('_', ' ').replace('-', ' ').title(),
                                "creator": creator,
                                "duration": None,
                                "file_size": "Unknown",
                                "category": folder_category,
                                "thumbnail": None,
                                "url": full_url,
                                "tags": folder_category.lower(),
                                "path": full_url.replace(base_url, '')
                            })
                except Exception as dir_err:
                    pass  # Silently continue on errors
            
            # Start scraping from category paths (faster than root)
            for start_path in start_paths:
                if len(results) < limit:
                    _file_log(f"Scraping path: {start_path}")
                    scrape_directory(start_path, depth=0, max_depth=4)  # Max depth 4 to find nested content
            
            _file_log(f"Scraping completed: found {len(results)} results from {len(visited_urls)} directories")
            
            # Return results even if empty - this allows proper "no results" message instead of demo fallback
            _file_log(f"Community preroll search (scrape): found {len(results)} results from {len(visited_urls)} directories")
            return {
                "found": len(results),
                "results": results,
                "total": len(results),
                "query": query,
                "category": category,
                "source": "directory",
                "message": f"Searched {len(visited_urls)} directories" if len(results) == 0 else None
            }
        except Exception as scrape_err:
            import traceback
            _file_log(f"Community preroll scrape error: {scrape_err}\n{traceback.format_exc()}")
        
        # Fallback: if API unavailable, return demo/sample prerolls
        # This allows testing the UI without a live API
        demo_results = []
        
        # Include demo results if search is empty or matches demo keywords
        search_lower = (query or "").lower()
        category_lower = (category or "").lower()
        
        if not query or "test" in search_lower or "demo" in search_lower or "sample" in search_lower:
            demo_results = [
                {
                    "id": "demo_001",
                    "title": "Classic Film Noir Intro",
                    "creator": "Demo Creator",
                    "duration": 15,
                    "file_size": "2.3 MB",
                    "category": "Movies",
                    "thumbnail": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120'%3E%3Crect fill='%23333'/%3E%3Ctext x='100' y='60' text-anchor='middle' fill='%23fff' font-size='14'%3EFilm Noir%3C/text%3E%3C/svg%3E",
                    "url": "https://example.com/demo1.mp4",
                    "tags": "intro,movie,demo"
                },
                {
                    "id": "demo_002",
                    "title": "Sci-Fi Digital Intro",
                    "creator": "Demo Creator",
                    "duration": 12,
                    "file_size": "1.8 MB",
                    "category": "SciFi",
                    "thumbnail": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120'%3E%3Crect fill='%23003366'/%3E%3Ctext x='100' y='60' text-anchor='middle' fill='%23fff' font-size='14'%3ESci-Fi%3C/text%3E%3C/svg%3E",
                    "url": "https://example.com/demo2.mp4",
                    "tags": "intro,scifi,demo"
                },
                {
                    "id": "demo_003",
                    "title": "Holiday Special Opener",
                    "creator": "Demo Creator",
                    "duration": 10,
                    "file_size": "1.5 MB",
                    "category": "Holiday",
                    "thumbnail": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120'%3E%3Crect fill='%23008000'/%3E%3Ctext x='100' y='60' text-anchor='middle' fill='%23fff' font-size='14'%3EHoliday%3C/text%3E%3C/svg%3E",
                    "url": "https://example.com/demo3.mp4",
                    "tags": "holiday,seasonal,demo"
                }
            ]
        
        # Filter demo results based on search query/category
        filtered_results = []
        for preroll in demo_results:
            matches_query = not query or (
                query.lower() in preroll["title"].lower() or 
                query.lower() in preroll.get("tags", "").lower()
            )
            matches_category = not category or category.lower() in preroll["category"].lower()
            
            if matches_query and matches_category:
                filtered_results.append(preroll)
        
        _file_log(f"Community preroll demo search: query='{query}' category='{category}' found {len(filtered_results)} results")
        
        return {
            "found": len(filtered_results),
            "results": filtered_results[:limit],
            "total": len(filtered_results),
            "query": query,
            "category": category,
            "note": "API currently unavailable - showing demo results. Visit https://prerolls.uk/ to browse the live library."
        }
        
    except Exception as e:
        _file_log(f"Community search exception: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.post("/community-prerolls/download")
def download_community_preroll(
    request: CommunityPrerollDownloadRequest,
    db: Session = Depends(get_db)
):
    """
    Download a preroll from the community library and import into local storage.
    
    Downloads the file into PREROLLS_DIR and creates a Preroll database entry.
    """
    import urllib.request
    import urllib.parse
    
    if not (request.preroll_id or request.url):
        raise HTTPException(status_code=422, detail="Either preroll_id or url is required")
    
    _file_log(f"[DOWNLOAD] Received request - preroll_id: {request.preroll_id}, title: {request.title}, category_id: {request.category_id}")
    
    # Determine download URL
    download_url = request.url
    if request.preroll_id and not request.url:
        # Community library uses URL paths as IDs (e.g., "/Holidays/Christmas/file.mp4")
        # Validate format - reject only obviously invalid patterns (starts with underscore from old mangled IDs)
        preroll_id_str = str(request.preroll_id)
        if preroll_id_str.startswith('_') or '\\' in preroll_id_str:
            _file_log(f"[DOWNLOAD] Invalid community_id format (mangled ID): {request.preroll_id}")
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid community preroll ID format. This appears to be a mangled ID. Please refresh the community search."
            )
        
        # Build download URL - community library serves files directly by path
        # The preroll_id is already the URL path (e.g., "/Holidays/Christmas/file.mp4")
        base_url = "https://prerolls.uk"
        download_url = f"{base_url}{preroll_id_str}"
        _file_log(f"[DOWNLOAD] Resolved download URL: {download_url}")
    
    if not download_url:
        raise HTTPException(status_code=422, detail="No download URL available")
    
    try:
        # Ensure directories exist
        os.makedirs(PREROLLS_DIR, exist_ok=True)
        os.makedirs(THUMBNAILS_DIR, exist_ok=True)
        
        # Resolve target category
        category = None
        if request.category_id:
            category = db.query(models.Category).filter(models.Category.id == request.category_id).first()
        if not category:
            category = db.query(models.Category).filter(models.Category.name == "Default").first()
            if not category:
                category = models.Category(name="Default", description="Default category")
                db.add(category)
                db.commit()
                db.refresh(category)
        
        category_dir = os.path.join(PREROLLS_DIR, category.name)
        thumbnail_category_dir = os.path.join(THUMBNAILS_DIR, category.name)
        os.makedirs(category_dir, exist_ok=True)
        os.makedirs(thumbnail_category_dir, exist_ok=True)
        
        # Download the file
        filename = request.title or "community_preroll"
        if not filename.lower().endswith(('.mp4', '.mkv', '.mov', '.avi', '.m4v', '.webm')):
            filename += ".mp4"
        
        file_path = os.path.join(category_dir, filename)
        
        # Avoid filename collisions
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(file_path):
            file_path = os.path.join(category_dir, f"{base}_{counter}{ext}")
            counter += 1
        
        # Download file using requests for better timeout control
        try:
            response = requests.get(download_url, stream=True, timeout=60)
            response.raise_for_status()
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        except Exception as dl_err:
            raise HTTPException(status_code=500, detail=f"Download failed: {str(dl_err)}")
        
        # Get file info
        file_size = os.path.getsize(file_path)
        duration = None
        
        # Probe duration
        try:
            result = _run_subprocess(
                [get_ffprobe_cmd(), "-v", "quiet", "-print_format", "json", "-show_format", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0 and result.stdout:
                probe_data = json.loads(result.stdout)
                duration = float(probe_data.get("format", {}).get("duration"))
        except Exception:
            duration = None
        
        # Community prerolls should have no tags by default
        # Users can add their own tags later if desired
        processed_tags = None
        
        # Create database record
        # Build kwargs conditionally to handle old DBs without community_preroll_id column
        preroll_kwargs = {
            "filename": os.path.basename(file_path),
            "display_name": request.title or os.path.splitext(os.path.basename(file_path))[0],
            "path": file_path,
            "thumbnail": None,
            "tags": None,  # No auto-tagging for community prerolls
            "category_id": category.id,
            "description": f"Downloaded from Community Prerolls library",
            "duration": duration,
            "file_size": file_size,
            "managed": True,
        }
        
        # Only add community_preroll_id if the model has the attribute (handles old schemas + pre-restart state)
        has_attr = hasattr(models.Preroll, 'community_preroll_id')
        has_id = bool(request.preroll_id)
        _file_log(f"[DOWNLOAD] community_preroll_id check - has_attr: {has_attr}, has_id: {has_id}, preroll_id: '{request.preroll_id}'")
        
        if has_attr and request.preroll_id:
            preroll_kwargs["community_preroll_id"] = str(request.preroll_id)
            _file_log(f"[DOWNLOAD] Setting community_preroll_id to: {preroll_kwargs['community_preroll_id']}")
        else:
            _file_log(f"[DOWNLOAD] NOT setting community_preroll_id - will not be exportable!")
        
        preroll = models.Preroll(**preroll_kwargs)
        db.add(preroll)
        db.commit()
        db.refresh(preroll)
        
        # Verify it was saved
        _file_log(f"[DOWNLOAD] Saved preroll ID {preroll.id} - community_preroll_id in DB: '{getattr(preroll, 'community_preroll_id', 'ATTRIBUTE_MISSING')}'")
        
        # Generate thumbnail
        thumbnail_path = None
        try:
            thumb_abs = os.path.join(thumbnail_category_dir, f"{preroll.id}_{os.path.basename(file_path)}.jpg")
            tmp_thumb = thumb_abs + ".tmp.jpg"
            res = _run_subprocess(
                [get_ffmpeg_cmd(), "-v", "error", "-y", "-ss", "5", "-i", file_path, "-vframes", "1", "-q:v", "2", "-f", "mjpeg", tmp_thumb],
                capture_output=True,
                text=True,
                timeout=30
            )
            if getattr(res, "returncode", 1) != 0 or not os.path.exists(tmp_thumb):
                _generate_placeholder(tmp_thumb)
            try:
                if os.path.exists(thumb_abs):
                    os.remove(thumb_abs)
            except Exception:
                pass
            os.replace(tmp_thumb, thumb_abs)
            thumbnail_path = os.path.relpath(thumb_abs, data_dir).replace("\\", "/")
            preroll.thumbnail = thumbnail_path
        except Exception as e:
            _file_log(f"Community preroll thumbnail generation error: {e}")
        
        # Add to category if requested
        if request.add_to_category and request.category_id:
            try:
                cat = db.query(models.Category).filter(models.Category.id == request.category_id).first()
                if cat and cat not in (preroll.categories or []):
                    preroll.categories = (preroll.categories or []) + [cat]
            except Exception:
                pass
        
        try:
            db.commit()
            db.refresh(preroll)
        except Exception as e:
            _file_log(f"Community preroll DB commit error: {e}")
        
        # Auto-apply to Plex/Jellyfin if category is already applied or currently active
        auto_applied = False
        if category:
            should_apply = getattr(category, "apply_to_plex", False)
            
            # Also check if this category is currently active via scheduler
            if not should_apply:
                try:
                    setting = db.query(models.Setting).first()
                    if setting and getattr(setting, "active_category", None) == category.id:
                        should_apply = True
                        _file_log(f"download_community_preroll: Category '{category.name}' (ID {category.id}) is currently active via schedule")
                except Exception as e:
                    _file_log(f"download_community_preroll: Error checking active category: {e}")
            
            if should_apply:
                try:
                    _file_log(f"download_community_preroll: Auto-applying category '{category.name}' (ID {category.id}) to Plex after download")
                    ok = _apply_category_to_plex_and_track(db, category.id, ttl=15)
                    if ok:
                        auto_applied = True
                        _file_log(f"download_community_preroll: Successfully auto-applied category '{category.name}' to Plex")
                    else:
                        _file_log(f"download_community_preroll: Failed to auto-apply category '{category.name}' to Plex")
                except Exception as e:
                    _file_log(f"download_community_preroll: Error auto-applying to Plex: {e}")
        
        return {
            "downloaded": True,
            "id": preroll.id,
            "filename": preroll.filename,
            "display_name": preroll.display_name,
            "category_id": preroll.category_id,
            "category": {"id": category.id, "name": category.name},
            "thumbnail": thumbnail_path,
            "duration": duration,
            "file_size": file_size,
            "source": "community_prerolls",
            "credit": "https://typicalnerds.uk/",
            "auto_applied": auto_applied,
        }
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        _file_log(f"DOWNLOAD ERROR: {error_details}")
        print(f"DOWNLOAD ERROR: {error_details}", flush=True)
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Download import failed: {str(e)}")

@app.get("/community-prerolls/downloaded-ids")
def get_downloaded_community_preroll_ids(db: Session = Depends(get_db)):
    """
    Get a list of community preroll IDs that have been downloaded.
    Used by the frontend to mark community prerolls as "Downloaded".
    """
    try:
        # Check if model has the attribute (handles old schemas + pre-restart state)
        if not hasattr(models.Preroll, 'community_preroll_id'):
            return {"downloaded_ids": []}
        
        downloaded = db.query(models.Preroll.community_preroll_id).filter(
            models.Preroll.community_preroll_id.isnot(None)
        ).all()

        # Extract IDs and convert to list (removing duplicates)
        ids = list(set([str(row[0]) for row in downloaded if row[0]]))

        return {"downloaded_ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get downloaded IDs: {str(e)}")

@app.post("/community-prerolls/clear-matches")
def clear_community_matches_endpoint(db: Session = Depends(get_db)):
    """
    Clear all community_preroll_id links from prerolls.
    This allows rematching with improved algorithms.
    Does NOT delete or modify preroll files.
    """
    try:
        # Check if model has the attribute
        if not hasattr(models.Preroll, 'community_preroll_id'):
            return {"cleared": 0, "message": "Database schema too old, community_preroll_id column not present"}
        
        # Count how many have community IDs
        count = db.query(models.Preroll).filter(
            models.Preroll.community_preroll_id.isnot(None)
        ).count()
        
        # Clear all community_preroll_ids
        db.query(models.Preroll).filter(
            models.Preroll.community_preroll_id.isnot(None)
        ).update({models.Preroll.community_preroll_id: None})
        
        db.commit()
        
        _file_log(f"Cleared community_preroll_id from {count} prerolls for rematching")
        
        return {
            "cleared": count,
            "message": f"Successfully cleared {count} community preroll links",
            "success": True
        }
    except Exception as e:
        db.rollback()
        _file_log(f"Failed to clear community matches: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to clear matches: {str(e)}")

@app.post("/community-prerolls/migrate-legacy")
def migrate_legacy_community_prerolls_endpoint(
    match_all: bool = Query(False, description="If True, attempt to match ALL prerolls without IDs (not just those marked as community downloads)"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger migration of legacy community prerolls (those downloaded before ID tracking).
    Attempts to match them with community library by searching by title.
    Returns count of matched prerolls.
    
    Args:
        match_all: If True, attempts to match ALL prerolls without community_preroll_id,
                   not just those with "Downloaded from Community Prerolls" in description.
                   Useful for users who manually downloaded community prerolls before using NeXroll.
    """
    try:
        # Check if model has the attribute (handles old schemas + pre-restart state)
        if not hasattr(models.Preroll, 'community_preroll_id'):
            return {"matched": 0, "message": "Database schema too old, community_preroll_id column not present"}
        
        import json
        import os
        import re
        
        # Find prerolls without community_preroll_id
        if match_all:
            # Match ALL prerolls that don't have a community ID yet
            legacy_prerolls = db.query(models.Preroll).filter(
                models.Preroll.community_preroll_id.is_(None)
            ).all()
            _file_log(f"[MATCH DEBUG] Match ALL mode - Found {len(legacy_prerolls)} prerolls without community_preroll_id")
        else:
            # Only match prerolls explicitly marked as community downloads
            legacy_prerolls = db.query(models.Preroll).filter(
                models.Preroll.description.like("%Downloaded from Community Prerolls%"),
                models.Preroll.community_preroll_id.is_(None)
            ).all()
            _file_log(f"[MATCH DEBUG] Match downloaded only - Found {len(legacy_prerolls)} prerolls")

        # Log all prerolls being processed
        for p in legacy_prerolls:
            filename = os.path.basename(p.path)
            _file_log(f"[MATCH DEBUG]   Will process: {filename} (id={p.id}, comm_id={p.community_preroll_id})")

        if not legacy_prerolls:
            return {"matched": 0, "total_scanned": 0, "message": "No prerolls found to match"}
        
        # Load the local community index
        if not PREROLLS_INDEX_PATH.exists():
            return {
                "matched": 0,
                "total_scanned": len(legacy_prerolls),
                "failed": len(legacy_prerolls),
                "failed_titles": [os.path.basename(p.path) for p in legacy_prerolls],
                "message": "Community index not found. Please build the index first.",
                "success": False
            }
        
        with open(PREROLLS_INDEX_PATH, 'r', encoding='utf-8') as f:
            index_data = json.load(f)
        
        community_prerolls = index_data.get('prerolls', [])
        
        # Helper function to normalize titles for matching
        def normalize_title(title):
            # First, add spaces before camelCase patterns (e.g., "PolarExpressPreRoll" -> "Polar Express Pre Roll")
            title = re.sub(r'([a-z])([A-Z])', r'\1 \2', title)
            
            title = title.lower()
            
            # Remove common variations BEFORE replacing separators
            # Remove "plex", "pre roll", "preroll", "pre-roll" - often added/omitted inconsistently
            title = re.sub(r'(plex|pre[\s\-_]*roll|preroll)', '', title, flags=re.IGNORECASE)
            
            # Remove version numbers - handle multiple formats:
            # V01, V02, V1, V2, v01, v1, Vol1, Vol01, Volume1, etc.
            title = re.sub(r'\b(v|vol|volume)[\s\-_]*\d+\b', '', title, flags=re.IGNORECASE)
            # Also catch standalone patterns like "Pack V01" or "Part 2"
            title = re.sub(r'(pack|part|episode|ep)[\s\-_]*(v|vol|volume)?[\s\-_]*\d+', '', title, flags=re.IGNORECASE)
            
            # Remove year numbers (2020, 2023, etc.) - often added to versions
            title = re.sub(r'\b(19|20)\d{2}\b', '', title)
            
            # Remove "4k", "hd", "1080p", etc.
            title = re.sub(r'\b(4k|hd|1080p|720p|2160p|uhd)\b', '', title, flags=re.IGNORECASE)
            
            # Remove common suffixes like "final", "new", "old"
            title = re.sub(r'\b(final|new|old|updated|remastered)\b', '', title, flags=re.IGNORECASE)
            
            # NOW convert separators to spaces (after removing prefixes/suffixes that use them)
            title = title.replace('_', ' ')  # Convert underscores to spaces
            title = title.replace('-', ' ')  # Convert dashes to spaces
            
            title = re.sub(r'[^\w\s]', '', title)  # Remove non-alphanumeric except spaces
            title = re.sub(r'\s+', ' ', title).strip()  # Normalize whitespace
            return title
        
        matched_count = 0
        failed_titles = []
        
        for preroll in legacy_prerolls:
            try:
                # Get filename without extension
                filename = os.path.basename(preroll.path)
                filename_no_ext = os.path.splitext(filename)[0]
                normalized_filename = normalize_title(filename_no_ext)
                
                # Try to find match in community index
                matched = False
                best_match = None
                best_score = 0
                
                for cp in community_prerolls:
                    cp_title_normalized = normalize_title(cp['title'])
                    
                    # Exact match - highest priority
                    if normalized_filename == cp_title_normalized:
                        preroll.community_preroll_id = cp['id']
                        matched_count += 1
                        matched = True
                        break
                    
                    # Partial matching - check if one contains the other with good overlap
                    if len(normalized_filename) >= 5 and len(cp_title_normalized) >= 5:
                        # Calculate similarity score
                        if normalized_filename in cp_title_normalized:
                            # Filename is contained in community title
                            score = len(normalized_filename) / len(cp_title_normalized)
                            if score > best_score and score >= 0.6:
                                best_score = score
                                best_match = cp
                        elif cp_title_normalized in normalized_filename:
                            # Community title is contained in filename
                            score = len(cp_title_normalized) / len(normalized_filename)
                            if score > best_score and score >= 0.6:
                                best_score = score
                                best_match = cp
                        
                        # Always check for significant word overlap as a fallback
                        filename_words = set(normalized_filename.split())
                        cp_words = set(cp_title_normalized.split())
                        if len(filename_words) >= 2 and len(cp_words) >= 2:
                            common_words = filename_words & cp_words
                            if len(common_words) >= 2:
                                score = len(common_words) / max(len(filename_words), len(cp_words))
                                if score > best_score and score >= 0.5:
                                    best_score = score
                                    best_match = cp
                
                # Use best match if found
                if not matched and best_match and best_score >= 0.5:
                    preroll.community_preroll_id = best_match['id']
                    matched_count += 1
                    matched = True
                
                if not matched:
                    failed_titles.append(filename)
                
            except Exception as e:
                _file_log(f"Failed to match preroll {preroll.id}: {e}")
                failed_titles.append(filename)
                continue
        
        if matched_count > 0:
            db.commit()
        
        return {
            "matched": matched_count,
            "total_scanned": len(legacy_prerolls),
            "failed": len(failed_titles),
            "failed_titles": failed_titles[:10] if failed_titles else [],
            "message": f"Successfully matched {matched_count} out of {len(legacy_prerolls)} prerolls",
            "success": True
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")

@app.get("/community-prerolls/random")
def get_random_community_preroll(
    platform: str = Query("", description="Filter by platform (plex/emby/jellyfin)"),
    category: str = Query("", description="Filter by category (optional)"),
    db: Session = Depends(get_db)
):
    """
    Get a random preroll from the community library.
    Uses local index for instant selection when available, falls back to remote scraping.
    Supports platform filtering (Plex/Emby/Jellyfin).
    """
    import random
    
    # Check Fair Use Policy acceptance
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, "community_fair_use_accepted", False):
        raise HTTPException(
            status_code=403, 
            detail="Fair Use Policy must be accepted before accessing community prerolls"
        )
    
    try:
        _file_log(f"Random community preroll request: platform='{platform}' category='{category}'")
        
        # TRY LOCAL INDEX FIRST (INSTANT!)
        index_data = _load_prerolls_index()
        if index_data:
            _file_log("Using local index for random selection (instant)")
            
            # Get all prerolls from index and apply filters
            all_prerolls = index_data.get("prerolls", [])
            filtered_prerolls = []
            
            platform_lower = platform.lower() if platform else ""
            category_lower = category.lower() if category else ""
            
            for preroll in all_prerolls:
                # Apply platform filter
                if platform_lower:
                    title_lower = preroll.get("title", "").lower()
                    if platform_lower not in title_lower:
                        continue
                
                # Apply category filter
                if category_lower:
                    preroll_category = preroll.get("category", "").lower()
                    if category_lower not in preroll_category:
                        continue
                
                filtered_prerolls.append(preroll)
            
            if filtered_prerolls:
                random_preroll = random.choice(filtered_prerolls)
                _file_log(f"Random preroll selected from index: {random_preroll['title']}")
                
                return {
                    "found": True,
                    "result": random_preroll,
                    "source": "local_index",
                    "message": "⚡ Instant random selection from local index"
                }
            else:
                _file_log(f"No matching prerolls in index for filters")
                return {
                    "found": False,
                    "message": f"No prerolls found matching filters",
                    "result": None
                }
        
        # FALLBACK: Remote scraping (slow but works without index)
        _file_log("No local index available, falling back to remote scraping for random selection")
        
        import requests
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin, unquote
        
        base_url = "https://prerolls.uk/"
        start_paths = ["Community/", "Holidays/", "Seasons/", "Clips/"]
        
        # If category specified, focus on that category
        if category:
            if category.lower() in ["holidays", "holiday"]:
                start_paths = ["Holidays/"]
            elif category.lower() in ["seasons", "seasonal"]:
                start_paths = ["Seasons/"]
            elif category.lower() in ["clips", "clip"]:
                start_paths = ["Clips/"]
            else:
                start_paths = ["Community/"]
        
        all_files = []
        platform_lower = platform.lower() if platform else ""
        
        def scrape_directory(url, depth=0, max_depth=4):
            """Recursively scrape directories to find all video files"""
            if depth > max_depth:
                return
            
            try:
                response = requests.get(url, timeout=5)
                if response.status_code != 200:
                    return
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    if not href or href.startswith('..'):
                        continue
                    
                    full_url = urljoin(url, href)
                    
                    # Check if it's a directory
                    if href.endswith('/'):
                        scrape_directory(full_url, depth + 1, max_depth)
                    # Check if it's a video file
                    elif href.endswith('.mp4'):
                        title = unquote(href.replace('.mp4', '').replace('%20', ' '))
                        
                        # Apply platform filter
                        if platform_lower:
                            title_lower = title.lower()
                            if platform_lower not in title_lower:
                                continue
                        
                        all_files.append({
                            "id": f"random_{len(all_files)}",
                            "title": title,
                            "url": full_url,
                            "creator": "Community",
                            "category": url.split('/')[-2] if '/' in url else "Community",
                            "thumbnail": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120'%3E%3Crect fill='%23444'/%3E%3Ctext x='100' y='60' text-anchor='middle' fill='%23fff' font-size='12'%3ERandom%3C/text%3E%3C/svg%3E"
                        })
                        
                        # Stop after finding 50 files (for performance)
                        if len(all_files) >= 50:
                            return
            
            except Exception as e:
                _file_log(f"Error scraping {url}: {e}")
        
        # Scrape directories
        for start_path in start_paths:
            start_url = urljoin(base_url, start_path)
            scrape_directory(start_url, depth=0, max_depth=3)
            
            # Stop early if we have enough files
            if len(all_files) >= 50:
                break
        
        if not all_files:
            _file_log(f"Random: No files found for platform='{platform}' category='{category}'")
            return {
                "found": False,
                "message": f"No prerolls found for platform '{platform}'" if platform else "No prerolls found",
                "result": None
            }
        
        # Select random file
        random_preroll = random.choice(all_files)
        _file_log(f"Random preroll selected: {random_preroll['title']}")
        
        return {
            "found": True,
            "result": random_preroll
        }
    
    except Exception as e:
        _file_log(f"Random preroll exception: {e}")
        raise HTTPException(status_code=500, detail=f"Random selection failed: {str(e)}")

@app.get("/community-prerolls/top5")
def get_top5_community_prerolls(
    platform: str = Query("", description="Filter by platform (plex/emby/jellyfin)"),
    db: Session = Depends(get_db)
):
    """
    Get top 5 featured/popular prerolls from the community library.
    These are curated selections from popular categories.
    """
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin, unquote
    
    # Check Fair Use Policy acceptance
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, "community_fair_use_accepted", False):
        raise HTTPException(
            status_code=403, 
            detail="Fair Use Policy must be accepted before accessing community prerolls"
        )
    
    try:
        _file_log(f"Top 5 community prerolls request: platform='{platform}'")
        
        base_url = "https://prerolls.uk/"
        
        # Featured directories with popular content
        featured_paths = [
            "Community/Matrix/",
            "Community/Star%20Wars%20Hyperspace%20Logo%20-%20AwesomeAustn/",
            "Community/Marvel%20Studios%20-%20AwesomeAustn/",
            "Community/Retrowave%202%20-%20AwesomeAustn/",
            "Community/Neon%20-%20AwesomeAustn/",
            "Community/Universal%20Pictures%20-%20AwesomeAustn/",
            "Community/20th%20Century%20Fox%20-%20AwesomeAustn/"
        ]
        
        top_prerolls = []
        platform_lower = platform.lower() if platform else ""
        
        for path in featured_paths:
            if len(top_prerolls) >= 5:
                break
            
            try:
                url = urljoin(base_url, path)
                response = requests.get(url, timeout=5)
                
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                
                for link in soup.find_all('a'):
                    href = link.get('href', '')
                    if not href or not href.endswith('.mp4'):
                        continue
                    
                    title = unquote(href.replace('.mp4', '').replace('%20', ' '))
                    full_url = urljoin(url, href)
                    
                    # Apply platform filter
                    if platform_lower:
                        title_lower = title.lower()
                        if platform_lower not in title_lower:
                            continue
                    
                    category_name = unquote(path.split('/')[-2])
                    
                    top_prerolls.append({
                        "id": f"top_{len(top_prerolls)}",
                        "title": title,
                        "url": full_url,
                        "creator": category_name,
                        "category": category_name,
                        "thumbnail": "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='120'%3E%3Crect fill='%23FFD700'/%3E%3Ctext x='100' y='60' text-anchor='middle' fill='%23000' font-size='14'%3E⭐ Top 5%3C/text%3E%3C/svg%3E",
                        "featured": True
                    })
                    
                    if len(top_prerolls) >= 5:
                        break
            
            except Exception as e:
                _file_log(f"Error fetching from {path}: {e}")
                continue
        
        _file_log(f"Top 5 prerolls found: {len(top_prerolls)}")
        
        return {
            "found": len(top_prerolls),
            "results": top_prerolls[:5]
        }
    
    except Exception as e:
        _file_log(f"Top 5 prerolls exception: {e}")
        raise HTTPException(status_code=500, detail=f"Top 5 fetch failed: {str(e)}")

def _fetch_movie_poster(title: str) -> str:
    """
    Fetch movie/TV show poster from free APIs based on title.
    Returns poster URL or None if not found.
    Uses TVMaze API (free, no key needed) and falls back to placeholder.
    """
    try:
        # Clean up title - remove common patterns
        clean_title = title.lower()
        
        # Remove platform indicators
        for platform in ['plex', 'jellyfin', 'emby', '- plex', '- jellyfin', '- emby']:
            clean_title = clean_title.replace(platform, '')
        
        # Remove creator names and common patterns
        patterns_to_remove = [
            'awesomeaustn', 'the -', 'studios', 'pictures', 'entertainment',
            'intro', 'bumper', 'logo', 'opening', 'trailer',
            '(', ')', '[', ']', '  '
        ]
        for pattern in patterns_to_remove:
            clean_title = clean_title.replace(pattern, ' ')
        
        # Clean up whitespace
        clean_title = ' '.join(clean_title.split()).strip()
        
        if not clean_title or len(clean_title) < 3:
            return None
        
        _file_log(f"Searching for poster: '{title}' -> '{clean_title}'")
        
        # Try TVMaze API first (free, no key needed, great for TV shows and movies)
        try:
            search_url = f"https://api.tvmaze.com/search/shows?q={requests.utils.quote(clean_title)}"
            response = requests.get(search_url, timeout=3)
            
            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0:
                    show = results[0].get("show", {})
                    image = show.get("image", {})
                    poster_url = image.get("original") or image.get("medium")
                    
                    if poster_url:
                        _file_log(f"✅ Found TVMaze poster for '{clean_title}': {poster_url}")
                        return poster_url
        except Exception as e:
            _file_log(f"TVMaze search failed for '{clean_title}': {e}")
        
        # Try extracting just the main title (first few words)
        # E.g., "Star Wars The Empire Strikes Back" -> "Star Wars"
        words = clean_title.split()
        if len(words) > 2:
            short_title = ' '.join(words[:2])
            try:
                search_url = f"https://api.tvmaze.com/search/shows?q={requests.utils.quote(short_title)}"
                response = requests.get(search_url, timeout=3)
                
                if response.status_code == 200:
                    results = response.json()
                    if results and len(results) > 0:
                        show = results[0].get("show", {})
                        image = show.get("image", {})
                        poster_url = image.get("original") or image.get("medium")
                        
                        if poster_url:
                            _file_log(f"✅ Found TVMaze poster with short title '{short_title}': {poster_url}")
                            return poster_url
            except Exception as e:
                _file_log(f"TVMaze short search failed: {e}")
        
        _file_log(f"❌ No poster found for '{clean_title}'")
        return None
        
    except Exception as e:
        _file_log(f"Error fetching poster for '{title}': {e}")
        return None

@app.get("/community-prerolls/latest")
def get_latest_community_prerolls(
    limit: int = Query(6, description="Number of latest prerolls to return (default 6)"),
    platform: str = Query("", description="Filter by platform (plex/emby/jellyfin)"),
    db: Session = Depends(get_db)
):
    """
    Get the latest/newest prerolls from the community library.
    Uses local index to find recently added prerolls sorted by modification time.
    Returns prerolls with thumbnail support for discovery section.
    """
    # Check Fair Use Policy acceptance
    setting = db.query(models.Setting).first()
    if not setting or not getattr(setting, "community_fair_use_accepted", False):
        raise HTTPException(
            status_code=403, 
            detail="Fair Use Policy must be accepted before accessing community prerolls"
        )
    
    try:
        _file_log(f"Latest community prerolls request: limit={limit}, platform='{platform}'")
        
        # Load local index (required for latest prerolls - no fallback)
        index_data = _load_prerolls_index()
        if not index_data:
            _file_log("No local index available for latest prerolls")
            return {
                "found": False,
                "results": [],
                "message": "⚠️ Build local index to see latest prerolls",
                "needs_index": True
            }
        
        _file_log("Using local index for latest prerolls")
        
        # Get all prerolls from index
        all_prerolls = index_data.get("prerolls", [])
        
        # Apply platform filter if specified
        platform_lower = platform.lower() if platform else ""
        filtered_prerolls = []
        
        for preroll in all_prerolls:
            # Apply platform filter
            if platform_lower:
                title_lower = preroll.get("title", "").lower()
                if platform_lower not in title_lower:
                    continue
            
            filtered_prerolls.append(preroll)
        
        # Sort by modified_time (newest first) - the index stores this timestamp
        # If modified_time is not available, use creation order
        sorted_prerolls = sorted(
            filtered_prerolls,
            key=lambda x: x.get("modified_time", 0),
            reverse=True
        )
        
        # Take only the requested limit
        latest_prerolls = sorted_prerolls[:limit]
        
        # Try to fetch movie posters for each preroll, fallback to gradients
        import base64
        for idx, preroll in enumerate(latest_prerolls):
            # Try to get movie poster from OMDb
            poster_url = _fetch_movie_poster(preroll.get("title", ""))
            
            if poster_url:
                # Use the movie poster
                preroll["thumbnail"] = poster_url
                _file_log(f"Using movie poster for: {preroll.get('title')}")
            elif "thumbnail" not in preroll or not preroll["thumbnail"]:
                # Fallback to colorful SVG placeholder with gradient
                colors = [
                    ("#667eea", "#764ba2"),  # Purple gradient
                    ("#f093fb", "#f5576c"),  # Pink gradient
                    ("#4facfe", "#00f2fe"),  # Blue gradient
                    ("#43e97b", "#38f9d7"),  # Green gradient
                    ("#fa709a", "#fee140"),  # Yellow-Pink gradient
                    ("#30cfd0", "#330867"),  # Teal gradient
                ]
                color_pair = colors[idx % len(colors)]
                
                # Create SVG with proper encoding
                svg_content = f"""<svg xmlns='http://www.w3.org/2000/svg' width='300' height='180'>
                    <defs>
                        <linearGradient id='grad{idx}' x1='0%' y1='0%' x2='100%' y2='100%'>
                            <stop offset='0%' style='stop-color:{color_pair[0]};stop-opacity:1' />
                            <stop offset='100%' style='stop-color:{color_pair[1]};stop-opacity:1' />
                        </linearGradient>
                    </defs>
                    <rect width='300' height='180' fill='url(#grad{idx})'/>
                    <text x='150' y='80' text-anchor='middle' fill='#fff' font-size='40' font-weight='bold' opacity='0.9'>🎬</text>
                    <text x='150' y='110' text-anchor='middle' fill='#fff' font-size='16' font-weight='bold' opacity='0.8'>NEW</text>
                    <text x='150' y='130' text-anchor='middle' fill='#fff' font-size='12' opacity='0.7'>Latest Addition</text>
                </svg>"""
                
                # Base64 encode the SVG
                svg_base64 = base64.b64encode(svg_content.encode('utf-8')).decode('utf-8')
                preroll["thumbnail"] = f"data:image/svg+xml;base64,{svg_base64}"
        
        _file_log(f"Latest prerolls found: {len(latest_prerolls)}")
        
        return {
            "found": True,
            "results": latest_prerolls,
            "total": len(latest_prerolls),
            "message": f"✨ Showing {len(latest_prerolls)} latest prerolls",
            "source": "local_index"
        }
    
    except Exception as e:
        _file_log(f"Latest prerolls exception: {e}")
        raise HTTPException(status_code=500, detail=f"Latest prerolls fetch failed: {str(e)}")

# IMPORTANT: Generic /settings/{key} endpoints MUST come after specific /settings/* endpoints
# to avoid FastAPI route matching the generic pattern first
@app.get("/settings/{key}")
def get_setting(key: str, db: Session = Depends(get_db)):
    """Get a setting value by key"""
    setting = db.query(models.Setting).first()
    if not setting:
        # Create a default Setting record if one doesn't exist
        setting = models.Setting()
        db.add(setting)
        db.commit()
    value = setting.get_json_value(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting key not found")
    return value

@app.put("/settings/{key}")
def update_setting(key: str, value: dict | list | str, db: Session = Depends(get_db)):
    """Update a setting value"""
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting()
        db.add(setting)
    
    if setting.set_json_value(key, value):
        try:
            db.commit()
            return {"status": "success"}
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Failed to set value")


try:
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
    print(f"Successfully mounted frontend directory: {frontend_dir}")
except Exception as e:
    print(f"Error mounting frontend directory: {e}")
    sys.exit(1)

# Auto-start when running as packaged EXE (PyInstaller onefile)
if getattr(sys, "frozen", False):
    _file_log("Starting FastAPI (frozen build)")
    try:
        import uvicorn
        port = int(os.environ.get("NEXROLL_PORT", "9393"))
        uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
    except Exception as e:
        _file_log(f"Uvicorn failed: {e}")
        raise

def _bootstrap_jellyfin_from_env() -> None:
    """
    Best-effort auto-connect for Jellyfin:
    - Reads NEXROLL_JELLYFIN_URL and NEXROLL_JELLYFIN_API_KEY
    - Persists to settings and secure store when successful
    """
    try:
        url_env = (os.environ.get("NEXROLL_JELLYFIN_URL") or "").strip() or None
        key_env = (os.environ.get("NEXROLL_JELLYFIN_API_KEY") or "").strip() or None
        if not url_env and not key_env:
            return

        db = SessionLocal()
        try:
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=None, plex_token=None)
                db.add(setting)
                db.commit()
                db.refresh(setting)

            # Prefer existing working configuration
            cur_url = getattr(setting, "jellyfin_url", None)
            cur_key = None
            try:
                cur_key = secure_store.get_jellyfin_api_key()
            except Exception:
                cur_key = None
            if cur_url and (cur_key or key_env):
                try:
                    from backend.jellyfin_connector import JellyfinConnector
                    if JellyfinConnector(cur_url, cur_key or key_env).test_connection():
                        return
                except Exception:
                    pass

            # Persist API key from env to secure store
            if key_env:
                try:
                    secure_store.set_jellyfin_api_key(key_env)
                except Exception:
                    pass

            # If URL provided, test it first
            if url_env:
                try:
                    from backend.jellyfin_connector import JellyfinConnector
                    test_url = url_env if url_env.startswith(("http://", "https://")) else f"http://{url_env}"
                    ok = JellyfinConnector(test_url, key_env or cur_key).test_connection()
                except Exception:
                    ok = False
                if ok:
                    setting.jellyfin_url = test_url
                    try:
                        setting.updated_at = datetime.datetime.utcnow()
                    except Exception:
                        pass
                    db.commit()
                    return
            # If only key present, leave URL untouched
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception:
        # keep server healthy regardless of failures here
        pass

# ============================================================================
# Dashboard Statistics Endpoint
# ============================================================================

@app.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get aggregated statistics for the dashboard overview.
    Returns preroll stats, category breakdown, schedule info, and NeX-Up data.
    """
    try:
        # --- Preroll Statistics ---
        prerolls = db.query(models.Preroll).all()
        total_prerolls = len(prerolls)
        total_duration = sum((p.duration or 0) for p in prerolls)
        total_size_bytes = sum((p.file_size or 0) for p in prerolls)
        
        # Resolution breakdown (parse from filename or estimate from file size)
        resolution_breakdown = {"4k": 0, "1080p": 0, "720p": 0, "480p": 0, "unknown": 0}
        for p in prerolls:
            filename = (p.filename or "").lower()
            if "4k" in filename or "2160" in filename or "uhd" in filename:
                resolution_breakdown["4k"] += 1
            elif "1080" in filename:
                resolution_breakdown["1080p"] += 1
            elif "720" in filename:
                resolution_breakdown["720p"] += 1
            elif "480" in filename or "sd" in filename:
                resolution_breakdown["480p"] += 1
            else:
                # Estimate based on file size per second
                if p.duration and p.duration > 0 and p.file_size:
                    bitrate = (p.file_size * 8) / p.duration  # bits per second
                    if bitrate > 30_000_000:  # >30 Mbps likely 4K
                        resolution_breakdown["4k"] += 1
                    elif bitrate > 8_000_000:  # >8 Mbps likely 1080p
                        resolution_breakdown["1080p"] += 1
                    elif bitrate > 3_000_000:  # >3 Mbps likely 720p
                        resolution_breakdown["720p"] += 1
                    else:
                        resolution_breakdown["480p"] += 1
                else:
                    resolution_breakdown["unknown"] += 1
        
        # --- Category Statistics ---
        categories = db.query(models.Category).all()
        category_stats = []
        for cat in categories:
            # Count prerolls in this category (primary + many-to-many)
            primary_count = db.query(models.Preroll).filter(models.Preroll.category_id == cat.id).count()
            # Also count many-to-many associations
            m2m_count = db.query(models.preroll_categories).filter(
                models.preroll_categories.c.category_id == cat.id
            ).count()
            total_in_cat = primary_count + m2m_count
            
            # Calculate storage for this category
            cat_prerolls = db.query(models.Preroll).filter(models.Preroll.category_id == cat.id).all()
            cat_size = sum((p.file_size or 0) for p in cat_prerolls)
            
            category_stats.append({
                "id": cat.id,
                "name": cat.name,
                "preroll_count": total_in_cat,
                "storage_bytes": cat_size,
                "is_system": getattr(cat, "is_system", False)
            })
        
        # Sort by preroll count descending
        category_stats.sort(key=lambda x: x["preroll_count"], reverse=True)
        
        # --- Schedule Statistics ---
        schedules = db.query(models.Schedule).all()
        now = datetime.datetime.now()
        
        active_schedules = 0
        inactive_schedules = 0
        upcoming_schedules = 0
        schedule_types = {"one-time": 0, "recurring": 0, "holiday": 0, "indefinite": 0}
        
        for s in schedules:
            if not s.is_active:
                inactive_schedules += 1
            else:
                # Check if currently in window
                if s.start_date and s.start_date <= now:
                    if s.end_date is None or s.end_date >= now:
                        active_schedules += 1
                    else:
                        inactive_schedules += 1
                elif s.start_date and s.start_date > now:
                    upcoming_schedules += 1
                else:
                    inactive_schedules += 1
            
            # Count by type
            stype = (s.type or "one-time").lower()
            if "holiday" in stype:
                schedule_types["holiday"] += 1
            elif s.recurrence_pattern:
                schedule_types["recurring"] += 1
            elif s.end_date is None and s.start_date:
                schedule_types["indefinite"] += 1
            else:
                schedule_types["one-time"] += 1
        
        # --- NeX-Up Statistics ---
        setting = db.query(models.Setting).first()
        nexup_stats = {
            "enabled": False,
            "radarr_connected": False,
            "sonarr_connected": False,
            "movie_trailers": 0,
            "tv_trailers": 0,
            "storage_used_gb": 0,
            "storage_limit_gb": 5.0,
            "storage_percent": 0
        }
        
        if setting:
            nexup_stats["enabled"] = getattr(setting, 'nexup_enabled', False) or getattr(setting, 'nexup_sonarr_enabled', False)
            nexup_stats["radarr_connected"] = bool(getattr(setting, 'nexup_radarr_url', None) and getattr(setting, 'nexup_radarr_api_key', None))
            nexup_stats["sonarr_connected"] = bool(getattr(setting, 'nexup_sonarr_url', None) and getattr(setting, 'nexup_sonarr_api_key', None))
            nexup_stats["storage_limit_gb"] = getattr(setting, 'nexup_max_storage_gb', 5.0) or 5.0
            
            # Count trailers by category
            movie_cat_id = getattr(setting, 'nexup_category_id', None)
            tv_cat_id = getattr(setting, 'nexup_tv_category_id', None)
            
            if movie_cat_id:
                nexup_stats["movie_trailers"] = db.query(models.Preroll).filter(models.Preroll.category_id == movie_cat_id).count()
            if tv_cat_id:
                nexup_stats["tv_trailers"] = db.query(models.Preroll).filter(models.Preroll.category_id == tv_cat_id).count()
            
            # Calculate storage usage
            storage_path = getattr(setting, 'nexup_storage_path', None)
            if storage_path and os.path.exists(storage_path):
                total_storage = 0
                try:
                    for f in os.listdir(storage_path):
                        fpath = os.path.join(storage_path, f)
                        if os.path.isfile(fpath):
                            total_storage += os.path.getsize(fpath)
                    nexup_stats["storage_used_gb"] = round(total_storage / (1024**3), 2)
                    if nexup_stats["storage_limit_gb"] > 0:
                        nexup_stats["storage_percent"] = round((nexup_stats["storage_used_gb"] / nexup_stats["storage_limit_gb"]) * 100, 1)
                except Exception:
                    pass
        
        # --- Saved Sequences Statistics ---
        saved_sequences = db.query(models.SavedSequence).count() if hasattr(models, 'SavedSequence') else 0
        
        # --- Recently Added Prerolls ---
        recent_prerolls = db.query(models.Preroll).order_by(models.Preroll.upload_date.desc()).limit(5).all()
        recent_list = [{
            "id": p.id,
            "filename": p.filename,
            "display_name": getattr(p, "display_name", None),
            "upload_date": p.upload_date.isoformat() if p.upload_date else None,
            "category": {"id": p.category.id, "name": p.category.name} if p.category else None
        } for p in recent_prerolls]
        
        return {
            "prerolls": {
                "total": total_prerolls,
                "total_duration_seconds": total_duration,
                "total_size_bytes": total_size_bytes,
                "resolution_breakdown": resolution_breakdown
            },
            "categories": {
                "total": len(categories),
                "breakdown": category_stats[:10]  # Top 10 categories
            },
            "schedules": {
                "total": len(schedules),
                "active": active_schedules,
                "inactive": inactive_schedules,
                "upcoming": upcoming_schedules,
                "types": schedule_types
            },
            "nexup": nexup_stats,
            "saved_sequences": saved_sequences,
            "recent_prerolls": recent_list
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to gather stats: {str(e)}")

if __name__ == "__main__" and not getattr(sys, "frozen", False):
    import uvicorn
    port = int(os.environ.get("NEXROLL_PORT", "9393"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
