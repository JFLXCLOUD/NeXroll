from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
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

            # Schedules: ensure fallback_category_id
            if not _sqlite_has_column("schedules", "fallback_category_id"):
                _sqlite_add_column("schedules", "fallback_category_id INTEGER")
            # Schedules: ensure sequence JSON field
            if not _sqlite_has_column("schedules", "sequence"):
                _sqlite_add_column("schedules", "sequence TEXT")

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
                    'https://prerolls.typicalnerds.uk/api/search',
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
            _file_log(f">>> SCHEMA MIGRATION ERROR: {e}")
        except Exception:
            pass

# Run schema upgrades early so requests won't hit missing columns
ensure_schema()

# Run legacy community preroll migration in background (one-time, safe to call multiple times)
import threading
threading.Thread(target=migrate_legacy_community_prerolls, daemon=True).start()

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

def _file_log(msg: str):
    try:
        with open(_log_file_path(), "a", encoding="utf-8") as f:
            ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass

# Global logging helpers: write unhandled exceptions and stdout/stderr to ProgramData\NeXroll\logs\app.log
def _install_global_excepthook():
    try:
        import traceback
        def _hook(exc_type, exc, tb):
            try:
                lines = "".join(traceback.format_exception(exc_type, exc, tb))
                _file_log(f"Unhandled exception: {lines}")
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

def _init_global_logging():
    try:
        _install_global_excepthook()
        _redirect_std_streams()
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
    end_date: str = None  # Accept as string from frontend
    category_id: int
    shuffle: bool = False
    playlist: bool = False
    recurrence_pattern: str = None
    preroll_ids: str = None
    sequence: Optional[str] = None
    fallback_category_id: Optional[int] = None

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
            _file_log(f"Unhandled error {request.method} {request.url.path}: {e}")
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
            _file_log(f"Schema migration error: {e}")
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
                _file_log(f"Startup normalization commit failed: {e}")
    except Exception as e:
        try:
            _file_log(f"Startup normalization error: {e}")
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

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
        db.close()
    except Exception as e:
        try:
            _file_log(f"Startup Setting initialization error: {e}")
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
            _file_log("⚠ CHANGELOG.md not found in any location")
    except Exception as e:
        logger.error(f"Failed to read CHANGELOG.md: {e}")
        _file_log(f"Changelog read error: {e}")
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
                    _file_log(f"/plex/connect: ⚠ Failed to save token to secure store")
                    raise HTTPException(status_code=500, detail="Failed to save token to secure storage. Please ensure Windows Credential Manager is available.")
            except HTTPException:
                raise
            except Exception as e:
                _file_log(f"/plex/connect: ⚠ Exception saving token: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to save token securely: {str(e)}")

            db.commit()
            _file_log(f"/plex/connect: ✓ Connection successful - URL: {url}, Token storage: {provider_name}")
            return {
                "connected": True,
                "message": "Successfully connected to Plex server",
                "token_storage": provider_name
            }
        else:
            _file_log(f"/plex/connect: ✗ Connection test failed for {url}")
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
                _file_log(f"/plex/status: Error building disconnected response: {e}")
                pass
            return out

        connector = PlexConnector(plex_url, token)
        try:
            info = connector.get_server_info() or {}
        except Exception as e:
            _file_log(f"/plex/status: Connection test failed for {plex_url}: {e}")
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
            if is_connected:
                _file_log(f"/plex/status: Connected successfully (token from {token_source})")
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

@app.post("/prerolls/upload")
def upload_preroll(
    file: UploadFile = File(...),
    tags: str = Form(""),
    category_id: str = Form(""),
    category_ids: str = Form(""),
    description: str = Form(""),
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

    # Save file to disk (single physical copy regardless of multi-category assignment)
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
            "upload_date": p.upload_date
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

    # Check if category is used by prerolls (primary) or via many-to-many, or by schedules
    preroll_primary_count = db.query(models.Preroll).filter(models.Preroll.category_id == category_id).count()
    m2m_count = db.query(models.Preroll).join(
        models.preroll_categories, models.Preroll.id == models.preroll_categories.c.preroll_id
    ).filter(models.preroll_categories.c.category_id == category_id).count()
    schedule_count = db.query(models.Schedule).filter(models.Schedule.category_id == category_id).count()

    if (preroll_primary_count + m2m_count) > 0 or schedule_count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete category that is in use")

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
    } for c in categories]

@app.put("/categories/{category_id}")
def update_category(category_id: int, category: CategoryCreate, db: Session = Depends(get_db)):
    db_category = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not db_category:
        raise HTTPException(status_code=404, detail="Category not found")

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
    # Validate category exists
    category = db.query(models.Category).filter(models.Category.id == schedule.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Get user's timezone for conversion
    settings = db.query(models.Setting).first()
    user_tz_str = settings.timezone if settings and settings.timezone else "UTC"
    try:
        user_tz = pytz.timezone(user_tz_str)
    except:
        user_tz = pytz.UTC

    # Parse dates from strings
    start_date = None
    end_date = None

    try:
        # Frontend sends times in user's local timezone (without timezone info)
        # We need to convert them to UTC for storage
        if schedule.start_date:
            sd = schedule.start_date
            print(f"DEBUG CREATE: Raw start_date from frontend: {sd}")
            # Parse as naive datetime (local time)
            dt = datetime.datetime.fromisoformat(sd.replace('Z', '+00:00'))
            print(f"DEBUG CREATE: Parsed datetime: {dt}")
            # If it has timezone info, strip it. Then treat as user's local time
            naive_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            # Localize to user's timezone, then convert to UTC
            local_dt = user_tz.localize(naive_dt)
            start_date = local_dt.astimezone(pytz.UTC)
            print(f"DEBUG CREATE: Converted to UTC: {start_date}")
        if schedule.end_date:
            ed = schedule.end_date
            print(f"DEBUG CREATE: Raw end_date from frontend: {ed}")
            dt2 = datetime.datetime.fromisoformat(ed.replace('Z', '+00:00'))
            print(f"DEBUG CREATE: Parsed datetime: {dt2}")
            naive_dt2 = dt2.replace(tzinfo=None) if dt2.tzinfo else dt2
            local_dt2 = user_tz.localize(naive_dt2)
            end_date = local_dt2.astimezone(pytz.UTC)
            print(f"DEBUG CREATE: Converted to UTC: {end_date}")
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
        sequence=schedule.sequence
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

    return {
        "id": created_schedule.id,
        "name": created_schedule.name,
        "type": created_schedule.type,
        "start_date": created_schedule.start_date.isoformat() + "Z" if created_schedule.start_date else None,
        "end_date": created_schedule.end_date.isoformat() + "Z" if created_schedule.end_date else None,
        "category_id": created_schedule.category_id,
        "category": {"id": created_schedule.category.id, "name": created_schedule.category.name} if created_schedule.category else None,
        "shuffle": created_schedule.shuffle,
        "playlist": created_schedule.playlist,
        "is_active": created_schedule.is_active,
        "last_run": created_schedule.last_run.isoformat() + "Z" if created_schedule.last_run else None,
        "next_run": created_schedule.next_run.isoformat() + "Z" if created_schedule.next_run else None,
        "recurrence_pattern": created_schedule.recurrence_pattern,
        "preroll_ids": created_schedule.preroll_ids,
        "fallback_category_id": getattr(created_schedule, "fallback_category_id", None),
        "sequence": getattr(created_schedule, "sequence", None)
    }

@app.get("/schedules")
def get_schedules(db: Session = Depends(get_db)):
    # Get user's timezone for conversion
    settings = db.query(models.Setting).first()
    user_tz_str = settings.timezone if settings and settings.timezone else "UTC"
    try:
        user_tz = pytz.timezone(user_tz_str)
    except:
        user_tz = pytz.UTC
    
    schedules = db.query(models.Schedule).options(joinedload(models.Schedule.category)).all()
    result = []
    for s in schedules:
        # Convert times from UTC back to user's local timezone for display
        start_iso = None
        end_iso = None
        
        if s.start_date:
            # Assume times stored in DB are UTC (though may be naive if from old data)
            if s.start_date.tzinfo is None:
                # If naive, assume UTC
                utc_dt = pytz.UTC.localize(s.start_date)
            else:
                utc_dt = s.start_date
            # Convert to user's timezone
            local_dt = utc_dt.astimezone(user_tz)
            start_iso = local_dt.isoformat()
        
        if s.end_date:
            if s.end_date.tzinfo is None:
                utc_dt = pytz.UTC.localize(s.end_date)
            else:
                utc_dt = s.end_date
            local_dt = utc_dt.astimezone(user_tz)
            end_iso = local_dt.isoformat()
        
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
            "last_run": s.last_run.isoformat() + "Z" if s.last_run else None,
            "next_run": s.next_run.isoformat() + "Z" if s.next_run else None,
            "recurrence_pattern": s.recurrence_pattern,
            "preroll_ids": s.preroll_ids,
            "fallback_category_id": getattr(s, "fallback_category_id", None),
            "sequence": getattr(s, "sequence", None)
        })
    
    return result

@app.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, schedule: ScheduleCreate, db: Session = Depends(get_db)):
    db_schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Get user's timezone for conversion
    settings = db.query(models.Setting).first()
    user_tz_str = settings.timezone if settings and settings.timezone else "UTC"
    try:
        user_tz = pytz.timezone(user_tz_str)
    except:
        user_tz = pytz.UTC

    # Parse dates from strings
    start_date = None
    end_date = None

    try:
        # Frontend sends times in user's local timezone (without timezone info)
        # We need to convert them to UTC for storage
        if schedule.start_date:
            sd = schedule.start_date
            print(f"DEBUG UPDATE: Raw start_date from frontend: {sd}")
            dt = datetime.datetime.fromisoformat(sd.replace('Z', '+00:00'))
            print(f"DEBUG UPDATE: Parsed datetime: {dt}")
            naive_dt = dt.replace(tzinfo=None) if dt.tzinfo else dt
            local_dt = user_tz.localize(naive_dt)
            start_date = local_dt.astimezone(pytz.UTC)
            print(f"DEBUG UPDATE: Converted to UTC: {start_date}")
        if schedule.end_date:
            ed = schedule.end_date
            print(f"DEBUG UPDATE: Raw end_date from frontend: {ed}")
            dt2 = datetime.datetime.fromisoformat(ed.replace('Z', '+00:00'))
            print(f"DEBUG UPDATE: Parsed datetime: {dt2}")
            naive_dt2 = dt2.replace(tzinfo=None) if dt2.tzinfo else dt2
            local_dt2 = user_tz.localize(naive_dt2)
            end_date = local_dt2.astimezone(pytz.UTC)
            print(f"DEBUG UPDATE: Converted to UTC: {end_date}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")

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

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        _file_log(f"Schedule update failed for id={schedule_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update schedule: {str(e)}")
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

# Holiday presets
@app.post("/holiday-presets/init")
def initialize_holiday_presets(db: Session = Depends(get_db)):
    # Create default category for holidays if it doesn't exist
    holiday_category = db.query(models.Category).filter(models.Category.name == "Holidays").first()
    if not holiday_category:
        holiday_category = models.Category(name="Holidays", description="Holiday-themed prerolls")
        db.add(holiday_category)
        db.commit()
        db.refresh(holiday_category)

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

        # Upsert holiday preset bound to that category
        existing = db.query(models.HolidayPreset).filter(models.HolidayPreset.name == holiday["name"]).first()
        if not existing:
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
    return {"message": "Holiday presets initialized"}

@app.get("/holiday-presets")
def get_holiday_presets(db: Session = Depends(get_db)):
    presets = db.query(models.HolidayPreset).all()
    return presets

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

    # Helper: check existing by case-insensitive path on Windows
    def _exists_in_db(abs_path: str) -> bool:
        try:
            row = db.query(models.Preroll).filter(models.Preroll.path == abs_path).first()
            if row:
                return True
            if sys.platform.startswith("win"):
                lp = abs_path.lower()
                row = db.query(models.Preroll).filter(func.lower(models.Preroll.path) == lp).first()
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
        if _exists_in_db(ap):
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

        if _exists_in_db(abs_src):
            continue

        filename = os.path.basename(abs_src)
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
            "exported_at": datetime.datetime.utcnow().isoformat()
        }

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

@app.post("/backup/files")
def backup_files():
    """Create ZIP archive of all preroll files"""
    try:
        # Create in-memory ZIP file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add preroll files
            prerolls_dir = Path(os.path.join(data_dir, "prerolls"))
            if prerolls_dir.exists():
                for file_path in prerolls_dir.rglob("*"):
                    if file_path.is_file():
                        # Add file to ZIP with relative path
                        zip_file.write(file_path, file_path.relative_to(prerolls_dir.parent))

        zip_buffer.seek(0)
        return {
            "filename": f"prerolls_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            "content": zip_buffer.getvalue(),
            "content_type": "application/zip"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File backup failed: {str(e)}")

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
        
        # 6. Delete prerolls (has FK to categories via category_id)
        print("RESTORE: Deleting prerolls...")
        db.query(models.Preroll).delete(synchronize_session=False)
        
        # 7. Finally delete categories (all FKs cleared)
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

        db.commit()
        return {"message": "Database restored successfully (v1.7.7-FIXED)", "version": "1.7.7"}
    except Exception as e:
        print(f"Critical restore error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

@app.post("/restore/files")
def restore_files(file: UploadFile = File(...)):
    """Import preroll files from ZIP archive"""
    try:
        # Create backup directory if it doesn't exist
        backup_dir = Path("prerolls_backup")
        backup_dir.mkdir(exist_ok=True)

        # Save uploaded ZIP file temporarily
        zip_path = backup_dir / "temp_restore.zip"
        with open(zip_path, "wb") as f:
            content = file.file.read()
            f.write(content)

        # Extract ZIP file
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(os.path.join(data_dir, "prerolls"))

        # Clean up temp file
        zip_path.unlink()

        return {"message": "Files restored successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File restore failed: {str(e)}")

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

@app.get("/community-prerolls/fair-use-policy")
def get_community_fair_use_policy():
    """
    Return the Fair Use Policy text from Typical Nerds.
    Fetched from: https://prerolls.typicalnerds.uk/%23%20FAIR%20USE%20POLICY%20-%20READ%20ME.txt
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
        "source": "https://prerolls.typicalnerds.uk/",
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
        
        url = "https://prerolls.typicalnerds.uk/Holidays/Halloween/Carving%20Pumpkin%20-%20AwesomeAustn/"
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
    
    base_url = "https://prerolls.typicalnerds.uk"
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
                                "id": full_url.replace(base_url, '').replace('/', '_').replace('.', '_'),
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
                            "id": full_url.replace(base_url, '').replace('/', '_').replace('.', '_'),
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
        
        _file_log(f"Loaded prerolls index: {index_data.get('total_prerolls', 0)} prerolls (created {index_data.get('created_at', 'unknown')})")
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
        base_url = "https://prerolls.typicalnerds.uk"
        
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
            "note": "API currently unavailable - showing demo results. Visit https://prerolls.typicalnerds.uk/ to browse the live library."
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
    
    # Determine download URL
    download_url = request.url
    if request.preroll_id and not request.url:
        # Resolve from community library
        download_url = f"https://prerolls.typicalnerds.uk/api/prerolls/{request.preroll_id}/download"
    
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
        
        # Only add community_preroll_id if the column exists (handles old DB schemas)
        try:
            if _sqlite_has_column("prerolls", "community_preroll_id") and request.preroll_id:
                preroll_kwargs["community_preroll_id"] = str(request.preroll_id)
        except Exception:
            pass  # Column doesn't exist yet, will be added on next restart
        
        preroll = models.Preroll(**preroll_kwargs)
        db.add(preroll)
        db.commit()
        db.refresh(preroll)
        
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
        # Check if column exists before querying (handles old DB schemas)
        if not _sqlite_has_column("prerolls", "community_preroll_id"):
            return {"downloaded_ids": []}
        
        downloaded = db.query(models.Preroll.community_preroll_id).filter(
            models.Preroll.community_preroll_id.isnot(None)
        ).all()

        # Extract IDs and convert to list (removing duplicates)
        ids = list(set([str(row[0]) for row in downloaded if row[0]]))

        return {"downloaded_ids": ids}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get downloaded IDs: {str(e)}")@app.post("/community-prerolls/migrate-legacy")
def migrate_legacy_community_prerolls_endpoint(db: Session = Depends(get_db)):
    """
    Manually trigger migration of legacy community prerolls (those downloaded before ID tracking).
    Attempts to match them with community library by searching by title.
    Returns count of matched prerolls.
    """
    try:
        # Check if column exists before querying (handles old DB schemas)
        if not _sqlite_has_column("prerolls", "community_preroll_id"):
            return {"matched": 0, "message": "Database schema too old, community_preroll_id column not present"}
        
        # Find prerolls that were downloaded from community but don't have an ID yet
        legacy_prerolls = db.query(models.Preroll).filter(
            models.Preroll.description.like("%Downloaded from Community Prerolls%"),
            models.Preroll.community_preroll_id.is_(None)
        ).all()

        if not legacy_prerolls:
            return {"matched": 0, "message": "No legacy community prerolls found"}
        
        import requests
        import re
        matched_count = 0
        failed_titles = []
        
        for preroll in legacy_prerolls:
            try:
                # Try to find this preroll in the community library by searching its display name or filename
                search_title = preroll.display_name or preroll.filename.replace('.mp4', '').replace('.mkv', '').replace('.avi', '')
                
                # Search community API
                response = requests.get(
                    'https://prerolls.typicalnerds.uk/api/search',
                    params={'query': search_title, 'limit': 10},
                    timeout=10
                )
                
                if response.ok:
                    results = response.json().get('results', [])
                    
                    # Look for exact or very close title match
                    matched = False
                    for result in results:
                        result_title = re.sub(r'^\d+\s*-\s*', '', result.get('title', '')).strip().lower()
                        search_lower = search_title.lower().strip()
                        
                        # Match if titles are very similar (exact match or one contains the other with >80% overlap)
                        if result_title == search_lower:
                            preroll.community_preroll_id = str(result.get('id'))
                            matched_count += 1
                            matched = True
                            break
                        elif len(search_lower) > 5 and (search_lower in result_title or result_title in search_lower):
                            # Additional check: titles must be at least 80% similar in length
                            len_ratio = min(len(search_lower), len(result_title)) / max(len(search_lower), len(result_title))
                            if len_ratio >= 0.8:
                                preroll.community_preroll_id = str(result.get('id'))
                                matched_count += 1
                                matched = True
                                break
                    
                    if not matched:
                        failed_titles.append(search_title)
                
            except Exception as e:
                _file_log(f"Failed to match preroll {preroll.id}: {e}")
                failed_titles.append(search_title)
                continue
        
        if matched_count > 0:
            db.commit()
        
        return {
            "matched": matched_count,
            "total_legacy": len(legacy_prerolls),
            "failed": len(failed_titles),
            "failed_titles": failed_titles[:10] if failed_titles else [],
            "message": f"Successfully matched {matched_count} out of {len(legacy_prerolls)} legacy community prerolls"
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
        
        base_url = "https://prerolls.typicalnerds.uk/"
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
        
        base_url = "https://prerolls.typicalnerds.uk/"
        
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

if __name__ == "__main__" and not getattr(sys, "frozen", False):
    import uvicorn
    port = int(os.environ.get("NEXROLL_PORT", "9393"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
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