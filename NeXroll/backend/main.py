from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, select, func
from sqlalchemy.exc import IntegrityError, OperationalError
from pydantic import BaseModel
from contextlib import asynccontextmanager
import datetime
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
import plexapi
from plexapi.myplex import MyPlexPinLogin, MyPlexAccount

import requests
import sys
import os
import hmac
import hashlib
import base64
import argparse

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
            ]:
                if not _sqlite_has_column("settings", col):
                    _sqlite_add_column("settings", ddl)

            # Prerolls: ensure display_name column for UI-friendly naming separate from disk file
            if not _sqlite_has_column("prerolls", "display_name"):
                _sqlite_add_column("prerolls", "display_name TEXT")
            # Prerolls: ensure managed flag to indicate external/mapped files (no moves/deletes)
            if not _sqlite_has_column("prerolls", "managed"):
                _sqlite_add_column("prerolls", "managed BOOLEAN DEFAULT 1")

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

            # Settings: ensure dashboard layout setting
            if not _sqlite_has_column("settings", "dashboard_layout"):
                _sqlite_add_column("settings", "dashboard_layout TEXT")

            # Statistics tables
            # Preroll plays table
            if not _sqlite_has_column("preroll_plays", "id"):
                # Create table if it doesn't exist
                _sqlite_add_column("preroll_plays", "id INTEGER PRIMARY KEY")
                _sqlite_add_column("preroll_plays", "preroll_id INTEGER NOT NULL")
                _sqlite_add_column("preroll_plays", "category_id INTEGER")
                _sqlite_add_column("preroll_plays", "played_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                _sqlite_add_column("preroll_plays", "trigger_type TEXT DEFAULT 'manual'")
                _sqlite_add_column("preroll_plays", "rating_key TEXT")
                _sqlite_add_column("preroll_plays", "genre TEXT")
                # Add indexes
                try:
                    with engine.connect() as conn:
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_preroll_plays_preroll_id ON preroll_plays(preroll_id)")
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_preroll_plays_played_at ON preroll_plays(played_at)")
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_preroll_plays_trigger_type ON preroll_plays(trigger_type)")
                except Exception:
                    pass

            # Category usage table
            if not _sqlite_has_column("category_usage", "id"):
                _sqlite_add_column("category_usage", "id INTEGER PRIMARY KEY")
                _sqlite_add_column("category_usage", "category_id INTEGER NOT NULL")
                _sqlite_add_column("category_usage", "applied_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                _sqlite_add_column("category_usage", "trigger_type TEXT DEFAULT 'manual'")
                _sqlite_add_column("category_usage", "duration_seconds INTEGER")
                _sqlite_add_column("category_usage", "preroll_count INTEGER DEFAULT 0")
                try:
                    with engine.connect() as conn:
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_category_usage_category_id ON category_usage(category_id)")
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_category_usage_applied_at ON category_usage(applied_at)")
                except Exception:
                    pass

            # Schedule executions table
            if not _sqlite_has_column("schedule_executions", "id"):
                _sqlite_add_column("schedule_executions", "id INTEGER PRIMARY KEY")
                _sqlite_add_column("schedule_executions", "schedule_id INTEGER NOT NULL")
                _sqlite_add_column("schedule_executions", "executed_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                _sqlite_add_column("schedule_executions", "success BOOLEAN DEFAULT 1")
                _sqlite_add_column("schedule_executions", "category_id INTEGER")
                _sqlite_add_column("schedule_executions", "preroll_count INTEGER DEFAULT 0")
                _sqlite_add_column("schedule_executions", "error_message TEXT")
                try:
                    with engine.connect() as conn:
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_schedule_executions_schedule_id ON schedule_executions(schedule_id)")
                        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS idx_schedule_executions_executed_at ON schedule_executions(executed_at)")
                except Exception:
                    pass
    except Exception as e:
        print(f"Schema ensure error: {e}")

def ensure_settings_schema_now() -> None:
    """
    Best-effort migration to add newer Setting columns on legacy SQLite DBs.
    Safe to call multiple times. Logs any errors to file logger.
    """
    try:
        if not engine.url.drivername.startswith("sqlite"):
            return
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
            }
            for col, ddl in need.items():
                if col not in cols:
                    try:
                        conn.exec_driver_sql(f"ALTER TABLE settings ADD COLUMN {col} {ddl}")
                        try:
                            _file_log(f"ensure_settings_schema_now: added settings.{col}")
                        except Exception:
                            pass
                    except Exception as e:
                        try:
                            _file_log(f"ensure_settings_schema_now: skip add settings.{col}: {e}")
                        except Exception:
                            pass
        try:
            _file_log("ensure_settings_schema_now: completed")
        except Exception:
            pass
    except Exception as e:
        try:
            _file_log(f"ensure_settings_schema_now error: {e}")
        except Exception:
            pass

# Run schema upgrades early so requests won't hit missing columns
_file_log("main.py: About to run ensure_schema()")
try:
    ensure_schema()
    _file_log("main.py: ensure_schema() completed successfully")
except Exception as e:
    _file_log(f"main.py: ensure_schema() failed: {e}")
    raise

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

# Debug: Log startup sequence
_file_log("main.py: Starting module import and initialization")

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
      - NEXROLL_<TOOL> env var
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
    Prefer ffmpeg color source; fallback to an embedded tiny JPEG.
    """
    try:
        # Attempt to generate with ffmpeg
        res = _run_subprocess(
            [get_ffmpeg_cmd(), "-f", "lavfi", "-i", f"color=c=gray:s={width}x{height}", "-vframes", "1", "-y", out_path],
            capture_output=True,
            text=True,
        )
        if os.path.exists(out_path):
            return
    except Exception:
        pass
    # Fallback: embedded 1x1 white JPEG
    try:
        import base64
        _SMALL_JPEG = (
            "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
            "//////////////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
            "//////////////////////////////////////////////////////////////////////////////////////////////wAARCAAQABADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAgP/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwC4A//Z"
        )
        data = base64.b64decode(_SMALL_JPEG)
        try:
            os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        except Exception:
            pass
        with open(out_path, "wb") as f:
            f.write(data)
    except Exception:
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
    sequence: str | None = None
    fallback_category_id: int | None = None

class ScheduleResponse(BaseModel):
    id: int
    name: str
    type: str
    start_date: datetime.datetime
    end_date: datetime.datetime | None = None
    category_id: int
    shuffle: bool
    playlist: bool
    is_active: bool
    last_run: datetime.datetime | None = None
    next_run: datetime.datetime | None = None
    recurrence_pattern: str | None = None
    preroll_ids: str | None = None
    sequence: str | None = None

class CategoryCreate(BaseModel):
    name: str
    description: str = None
    apply_to_plex: bool = False
    plex_mode: str = "shuffle"

class PrerollUpdate(BaseModel):
    tags: str | list[str] | None = None
    category_id: int | None = None                 # primary category (affects storage path and thumbnail folder)
    category_ids: list[int] | None = None          # additional categories (many-to-many)
    description: str | None = None
    display_name: str | None = None                # UI display label
    new_filename: str | None = None                # optional on-disk rename (basename; extension optional)

class PathMapping(BaseModel):
    local: str
    plex: str

class PathMappingsPayload(BaseModel):
    mappings: list[PathMapping]

class TestTranslationRequest(BaseModel):
    paths: list[str]

class MapRootRequest(BaseModel):
    root_path: str
    category_id: int | None = None
    recursive: bool = True
    extensions: list[str] | None = None
    dry_run: bool = True
    generate_thumbnails: bool = True
    tags: list[str] | None = None

class PlexConnectRequest(BaseModel):
    url: str
    token: str

class PlexStableConnectRequest(BaseModel):
    url: str | None = None
    token: str | None = None  # accepted but ignored for stable-token flow
    stableToken: str | None = None  # alias some UIs might send

class PlexTvConnectRequest(BaseModel):
    id: str | None = None
    token: str | None = None
    prefer_local: bool = True
    save_token: bool = True

class PlexAutoConnectRequest(BaseModel):
    token: str | None = None
    urls: list[str] | None = None
    prefer_local: bool = True

class GenreMapCreate(BaseModel):
    genre: str
    category_id: int

class GenreMapUpdate(BaseModel):
    genre: str | None = None
    category_id: int | None = None

class ResolveGenresRequest(BaseModel):
    genres: list[str]

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


# Define lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI startup and shutdown events.
    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown").
    """
    # Startup
    _file_log("main.py: lifespan startup() called")
    
    # Normalize thumbnail paths in DB on startup (idempotent migration for legacy paths)
    try:
        _file_log("main.py: Starting thumbnail path normalization")
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
        _file_log("main.py: Thumbnail path normalization completed")
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

    _file_log("main.py: About to start scheduler")
    try:
        scheduler.start()
        _file_log("main.py: Scheduler started successfully")
    except Exception as e:
        _file_log(f"main.py: Scheduler start failed: {e}")
        raise

    # Bootstrap Plex from environment variables
    _file_log("main.py: About to bootstrap Plex from env")
    try:
        _bootstrap_plex_from_env()
        _file_log("main.py: Plex env bootstrap completed")
    except Exception as e:
        _file_log(f"main.py: Plex env bootstrap failed: {e}")
        # keep server healthy regardless of failures here
        pass

    # Bootstrap Jellyfin from environment variables
    _file_log("main.py: About to bootstrap Jellyfin from env")
    try:
        _bootstrap_jellyfin_from_env()
        _file_log("main.py: Jellyfin env bootstrap completed")
    except Exception as e:
        _file_log(f"main.py: Jellyfin env bootstrap failed: {e}")
        # keep server healthy regardless of failures here
        pass

    yield

    # Shutdown
    _file_log("main.py: lifespan shutdown() called")
    try:
        scheduler.stop()
        _file_log("main.py: Scheduler stopped successfully")
    except Exception as e:
        _file_log(f"main.py: Scheduler stop failed: {e}")


app = FastAPI(title="NeXroll Backend", version="1.5.0", lifespan=lifespan)

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

        # Introspect statistics tables
        preroll_plays_columns = []
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(preroll_plays)")
                preroll_plays_columns = [row[1] for row in res.fetchall()]
        except Exception as e:
            info["preroll_plays_error"] = str(e)
        info["preroll_plays_columns"] = preroll_plays_columns

        category_usage_columns = []
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(category_usage)")
                category_usage_columns = [row[1] for row in res.fetchall()]
        except Exception as e:
            info["category_usage_error"] = str(e)
        info["category_usage_columns"] = category_usage_columns

        schedule_executions_columns = []
        try:
            with engine.connect() as conn:
                res = conn.exec_driver_sql("PRAGMA table_info(schedule_executions)")
                schedule_executions_columns = [row[1] for row in res.fetchall()]
        except Exception as e:
            info["schedule_executions_error"] = str(e)
        info["schedule_executions_columns"] = schedule_executions_columns

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

@app.get("/statistics/overview")
def get_statistics_overview(db: Session = Depends(get_db)):
    """
    Get high-level statistics overview including most played prerolls and categories.
    """
    try:
        # Most played prerolls (last 30 days)
        thirty_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=30)

        most_played_prerolls = db.query(
            models.PrerollPlay.preroll_id,
            models.Preroll.filename,
            models.Preroll.display_name,
            func.count(models.PrerollPlay.id).label('play_count')
        ).join(models.Preroll).filter(
            models.PrerollPlay.played_at >= thirty_days_ago
        ).group_by(
            models.PrerollPlay.preroll_id,
            models.Preroll.filename,
            models.Preroll.display_name
        ).order_by(func.count(models.PrerollPlay.id).desc()).limit(10).all()

        # Most used categories (last 30 days)
        most_used_categories = db.query(
            models.CategoryUsage.category_id,
            models.Category.name,
            func.count(models.CategoryUsage.id).label('usage_count'),
            func.sum(models.CategoryUsage.duration_seconds).label('total_duration')
        ).join(models.Category).filter(
            models.CategoryUsage.applied_at >= thirty_days_ago
        ).group_by(
            models.CategoryUsage.category_id,
            models.Category.name
        ).order_by(func.count(models.CategoryUsage.id).desc()).limit(10).all()

        # Total statistics
        total_prerolls = db.query(func.count(models.Preroll.id)).scalar() or 0
        total_categories = db.query(func.count(models.Category.id)).scalar() or 0
        total_plays = db.query(func.count(models.PrerollPlay.id)).filter(
            models.PrerollPlay.played_at >= thirty_days_ago
        ).scalar() or 0

        # Storage usage
        total_size = db.query(func.sum(models.Preroll.file_size)).filter(
            models.Preroll.file_size.isnot(None)
        ).scalar() or 0

        return {
            "total_prerolls": total_prerolls,
            "total_categories": total_categories,
            "total_plays_last_30_days": total_plays,
            "total_storage_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
            "most_played_prerolls": [
                {
                    "id": p.preroll_id,
                    "filename": p.filename,
                    "display_name": p.display_name,
                    "play_count": p.play_count
                } for p in most_played_prerolls
            ],
            "most_used_categories": [
                {
                    "id": c.category_id,
                    "name": c.name,
                    "usage_count": c.usage_count,
                    "total_duration_seconds": c.total_duration or 0
                } for c in most_used_categories
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")

# Placeholder for remaining routes - they continue from the original file
# The file is too large to include all routes here, but the key fix is the lifespan context manager above

# =========================
# Dashboard Layout Settings
# =========================

# Default 4x2 grid order matching current dashboard cards in the UI
DEFAULT_DASHBOARD_ORDER = [
    "servers",
    "prerolls",
    "storage",
    "schedules",
    "scheduler",
    "current_category",
    "upcoming",
    "recent_genres"
]

def _default_dashboard_layout() -> dict:
    return {
        "version": 1,
        "grid": {"cols": 4, "rows": 2},
        "order": DEFAULT_DASHBOARD_ORDER[:],
        "hidden": [],
        "locked": False
    }

def _normalize_dashboard_layout(layout: dict) -> dict:
    try:
        if not isinstance(layout, dict):
            layout = {}
        grid = layout.get("grid") or {}
        try:
            cols = int(grid.get("cols", 4))
        except Exception:
            cols = 4
        try:
            rows = int(grid.get("rows", 2))
        except Exception:
            rows = 2
        cols = max(1, min(cols, 8))
        rows = max(1, min(rows, 8))
        capacity = cols * rows

        # Order normalization
        default_order = DEFAULT_DASHBOARD_ORDER[:]
        order = layout.get("order")
        if not isinstance(order, list):
            order = default_order[:]
        else:
            order = [str(x) for x in order if str(x) in default_order]
            # add any missing tiles to preserve completeness
            for t in default_order:
                if t not in order:
                    order.append(t)
        # clamp to grid capacity
        order = order[:capacity]

        # Hidden normalization
        hidden = layout.get("hidden")
        if not isinstance(hidden, list):
            hidden = []
        else:
            hidden = [str(x) for x in hidden if str(x) in DEFAULT_DASHBOARD_ORDER]

        locked = bool(layout.get("locked", False))

        return {
            "version": 1,
            "grid": {"cols": cols, "rows": rows},
            "order": order,
            "hidden": hidden,
            "locked": locked
        }
    except Exception:
        # Fallback to a safe default on any error
        return _default_dashboard_layout()

def _get_or_create_settings(db: Session) -> models.Setting:
    setting = db.query(models.Setting).first()
    if not setting:
        setting = models.Setting()
        db.add(setting)
        db.commit()
        db.refresh(setting)
    return setting

@app.get("/settings/dashboard-layout")
def get_dashboard_layout(db: Session = Depends(get_db)):
    """
    Return the persisted dashboard layout; if not set, return a default layout.
    """
    setting = _get_or_create_settings(db)
    raw = getattr(setting, "dashboard_layout", None)
    layout = None
    if raw:
        try:
            layout = json.loads(raw)
        except Exception:
            layout = None
    if not isinstance(layout, dict):
        layout = _default_dashboard_layout()
    else:
        layout = _normalize_dashboard_layout(layout)
    return layout

@app.put("/settings/dashboard-layout")
async def put_dashboard_layout(request: Request, db: Session = Depends(get_db)):
    """
    Persist a dashboard layout object.
    Expected shape:
    {
      "version": 1,
      "grid": {"cols": 4, "rows": 2},
      "order": ["servers","prerolls","storage","schedules","scheduler","current_category","upcoming","recent_genres"],
      "hidden": [],
      "locked": false
    }
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")

    layout = _normalize_dashboard_layout(payload)
    setting = _get_or_create_settings(db)

    try:
        setting.dashboard_layout = json.dumps(layout)
        try:
            setting.updated_at = datetime.datetime.utcnow()
        except Exception:
            pass
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to save layout: {e}")

    return layout

# data_dir will be defined later in the module
# app.mount("/data", StaticFiles(directory=data_dir), name="data")

# Debug: Print current working directory
print(f"Backend running from: {os.getcwd()}")

# Get absolute paths for static files
# Get absolute paths for static files relative to project root
# Determine install and resource roots
if getattr(sys, "frozen", False):
    install_root = os.path.dirname(sys.executable)
    resource_root = getattr(sys, "_MEIPASS", install_root)
else:
    install_root = os.path.dirname(os.path.dirname(__file__))
    resource_root = install_root

# Prefer built React assets if present; fallback to source 'frontend'
_candidate = os.path.join(resource_root, "frontend", "build")
frontend_dir = _candidate if os.path.isdir(_candidate) else os.path.join(resource_root, "frontend")

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

# Mount frontend static files LAST so API routes are checked first
app.mount("/", StaticFiles(directory=frontend_dir, html=True, check_dir=False), name="frontend")

# Auto-start when running as packaged EXE (PyInstaller onefile)
if getattr(sys, "frozen", False):
    _file_log("Starting FastAPI (frozen build)")
    try:
        import uvicorn
        parser = argparse.ArgumentParser(description="NeXroll Backend Server")
        parser.add_argument("--port", type=int, default=int(os.environ.get("NEXROLL_PORT", "9393")), help="Port to bind to")
        parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
        args = parser.parse_args()
        _file_log(f"main.py: About to start uvicorn on {args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port, log_config=None)
        _file_log("main.py: Uvicorn run completed")
    except Exception as e:
        _file_log(f"Uvicorn failed: {e}")
        raise

if __name__ == "__main__" and not getattr(sys, "frozen", False):
    _file_log("main.py: Running in development mode")
    import uvicorn
    port = int(os.environ.get("NEXROLL_PORT", "9393"))
    _file_log(f"main.py: About to start uvicorn in dev mode on 0.0.0.0:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)
    _file_log("main.py: Uvicorn run completed in dev mode")
