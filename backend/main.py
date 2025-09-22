from fastapi import FastAPI, Depends, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, select, func
from sqlalchemy.exc import IntegrityError, OperationalError
from pydantic import BaseModel
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

import sys
import os

# Add the current directory and parent directory to Python path (dev only; avoid in frozen builds)
if not getattr(sys, "frozen", False):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    sys.path.insert(0, current_dir)
    sys.path.insert(0, parent_dir)

from nexroll_backend.database import SessionLocal, engine
import nexroll_backend.models as models
from nexroll_backend.plex_connector import PlexConnector
from nexroll_backend.scheduler import scheduler

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
            ]:
                if not _sqlite_has_column("settings", col):
                    _sqlite_add_column("settings", ddl)

            # Prerolls: ensure display_name column for UI-friendly naming separate from disk file
            if not _sqlite_has_column("prerolls", "display_name"):
                _sqlite_add_column("prerolls", "display_name TEXT")
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
ensure_schema()
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

class PlexConnectRequest(BaseModel):
    url: str
    token: str

class PlexStableConnectRequest(BaseModel):
    url: str | None = None
    token: str | None = None  # accepted but ignored for stable-token flow
    stableToken: str | None = None  # alias some UIs might send

app = FastAPI(title="NeXroll Backend", version="1.0.16")

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
        if path in ("/", "/index.html", "/manifest.json"):
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


@app.get("/system/version")
def system_version():
    """Expose backend version and installed version (from Windows registry if present)."""
    reg_version = None
    install_dir = None
    try:
        if sys.platform.startswith("win"):
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"Software\NeXroll")
            try:
                reg_version, _ = winreg.QueryValueEx(key, "Version")
            except Exception:
                reg_version = None
            try:
                install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
            except Exception:
                install_dir = None
            winreg.CloseKey(key)
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
body{font-family:Segoe UI, Arial, sans-serif; margin:24px; color:#222; background:#fafafa}
h1{margin:0 0 12px 0}
small{color:#666}
button{padding:8px 12px; margin:8px 8px 8px 0; cursor:pointer}
pre{background:#0b1020;color:#d1f7c4;padding:12px;border-radius:6px;white-space:pre-wrap;max-width:100%;overflow:auto}
.card{background:#fff;padding:16px;border:1px solid #e5e7eb;border-radius:8px;box-shadow:0 1px 2px rgba(0,0,0,0.04);margin-bottom:16px}
</style>
</head>
<body>
  <h1>NeXroll Dashboard</h1>
  <div class="card">
    <div>
      <button onclick="reinit()">Reinitialize Thumbnails</button>
      <button onclick="ffmpeg()">FFmpeg Info</button>
      <button onclick="plex()">Plex Status</button>
      <button onclick="version()">Version</button>
      <small id="status"></small>
    </div>
  </div>
  <div class="card">
    <pre id="out">Ready.</pre>
  </div>
<script>
function setOut(t){document.getElementById('out').textContent=t;}
function setStatus(t){document.getElementById('status').textContent=t;}

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
        connector = PlexConnector(url, token)
        if connector.test_connection():
            # Save to settings
            setting = db.query(models.Setting).first()
            if not setting:
                setting = models.Setting(plex_url=url, plex_token=token)
                db.add(setting)
            else:
                setting.plex_url = url
                setting.plex_token = token
                setting.updated_at = datetime.datetime.utcnow()
            db.commit()
            return {"connected": True, "message": "Successfully connected to Plex server"}
        else:
            raise HTTPException(status_code=422, detail="Failed to connect to Plex server. Please check your URL and token.")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Connection error: {str(e)}")

@app.get("/plex/status")
def get_plex_status(db: Session = Depends(get_db)):
    """
    Return Plex connection status without throwing 500s.
    Always returns 200 with a JSON object. Logs internal errors.
    Triggers a best-effort settings schema migration if a legacy DB is detected.
    """
    def _do_fetch():
        setting = db.query(models.Setting).first()
        if not setting or not getattr(setting, "plex_url", None) or not getattr(setting, "plex_token", None):
            return {"connected": False}
        connector = PlexConnector(setting.plex_url, setting.plex_token)
        info = connector.get_server_info() or {}
        if not isinstance(info, dict):
            info = {}
        info.setdefault("connected", False)
        return info

    try:
        return _do_fetch()
    except OperationalError as oe:
        # Auto-migrate settings schema then retry once
        try:
            _file_log(f"/plex/status OperationalError: {oe} (attempting schema ensure)")
        except Exception:
            pass
        try:
            ensure_settings_schema_now()
            return _do_fetch()
        except Exception as e2:
            try:
                _file_log(f"/plex/status post-migration fetch failed: {e2}")
            except Exception:
                pass
            return {"connected": False}
    except Exception as e:
        try:
            _file_log(f"/plex/status error: {e}")
        except Exception:
            pass
        # Never propagate error to the UI; keep the dashboard stable
        return {"connected": False}

@app.post("/plex/disconnect")
def disconnect_plex(db: Session = Depends(get_db)):
    """Disconnect from Plex server by clearing stored credentials"""
    setting = db.query(models.Setting).first()
    if setting:
        # Clear Plex settings
        setting.plex_url = None
        setting.plex_token = None
        setting.updated_at = datetime.datetime.utcnow()
        db.commit()
        return {"disconnected": True, "message": "Successfully disconnected from Plex server"}
    else:
        return {"disconnected": True, "message": "No Plex connection found"}

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

    return {
        "total_files": len(files),
        "successful_uploads": successful_uploads,
        "failed_uploads": len(files) - successful_uploads,
        "results": results
    }

@app.get("/prerolls")
def get_prerolls(db: Session = Depends(get_db), category_id: str = "", tags: str = ""):
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

    # Handle tag filtering (contains string; tags stored as JSON)
    if tags and tags.strip():
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        for tag in tag_list:
            query = query.filter(models.Preroll.tags.contains(tag))

    prerolls = query.distinct().all()
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
    if payload.new_filename and str(payload.new_filename).strip():
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
    preroll = db.query(models.Preroll).filter(models.Preroll.id == preroll_id).first()
    if not preroll:
        raise HTTPException(status_code=404, detail="Preroll not found")

    # Delete the actual files
    try:
        # Handle new path structure
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

    # Delete from database
    db.delete(preroll)
    db.commit()

    return {"message": "Preroll deleted successfully"}

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

    try:
        db.commit()
        db.refresh(p)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to add preroll to category: {str(e)}")

    return {
        "message": "Preroll added to category" + (" and set as primary" if set_primary else ""),
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

    # Create semicolon-separated list of all preroll file paths
    preroll_paths = []
    for preroll in prerolls:
        full_local_path = os.path.abspath(preroll.path)
        preroll_paths.append(full_local_path)

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
    multi_preroll_path = delimiter.join(preroll_paths)

    # Get Plex settings
    setting = db.query(models.Setting).first()
    if not setting:
        raise HTTPException(status_code=400, detail="Plex not configured")

    # Apply to Plex
    connector = PlexConnector(setting.plex_url, setting.plex_token)

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

    # Parse dates from strings
    start_date = None
    end_date = None

    try:
        # Normalize to UTC (naive) for consistent server-side scheduling
        if schedule.start_date:
            sd = schedule.start_date
            dt = datetime.datetime.fromisoformat(sd.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                local_tz = datetime.datetime.now().astimezone().tzinfo
                dt = dt.replace(tzinfo=local_tz)
            start_date = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        if schedule.end_date:
            ed = schedule.end_date
            dt2 = datetime.datetime.fromisoformat(ed.replace('Z', '+00:00'))
            if dt2.tzinfo is None:
                local_tz = datetime.datetime.now().astimezone().tzinfo
                dt2 = dt2.replace(tzinfo=local_tz)
            end_date = dt2.astimezone(datetime.timezone.utc).replace(tzinfo=None)
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
    schedules = db.query(models.Schedule).options(joinedload(models.Schedule.category)).all()
    return [{
        "id": s.id,
        "name": s.name,
        "type": s.type,
        "start_date": s.start_date.isoformat() + "Z" if s.start_date else None,
        "end_date": s.end_date.isoformat() + "Z" if s.end_date else None,
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
    } for s in schedules]

@app.put("/schedules/{schedule_id}")
def update_schedule(schedule_id: int, schedule: ScheduleCreate, db: Session = Depends(get_db)):
    db_schedule = db.query(models.Schedule).filter(models.Schedule.id == schedule_id).first()
    if not db_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    # Parse dates from strings
    start_date = None
    end_date = None

    try:
        # Normalize to UTC (naive) for consistent server-side scheduling
        if schedule.start_date:
            sd = schedule.start_date
            dt = datetime.datetime.fromisoformat(sd.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                local_tz = datetime.datetime.now().astimezone().tzinfo
                dt = dt.replace(tzinfo=local_tz)
            start_date = dt.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        if schedule.end_date:
            ed = schedule.end_date
            dt2 = datetime.datetime.fromisoformat(ed.replace('Z', '+00:00'))
            if dt2.tzinfo is None:
                local_tz = datetime.datetime.now().astimezone().tzinfo
                dt2 = dt2.replace(tzinfo=local_tz)
            end_date = dt2.astimezone(datetime.timezone.utc).replace(tzinfo=None)
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
    connector = PlexConnector(None)  # Will try to load from config
    return {
        "has_stable_token": bool(connector.token),
        "config_file_exists": os.path.exists("plex_config.json"),
        "token_length": len(connector.token) if connector.token else 0
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
    """Get current stable token configuration"""
    try:
        if os.path.exists("plex_config.json"):
            with open("plex_config.json", "r") as f:
                config = json.load(f)
                # Don't return the actual token for security
                return {
                    "configured": True,
                    "setup_date": config.get("setup_date"),
                    "note": config.get("note"),
                    "token_length": len(config.get("plex_token", ""))
                }
        else:
            return {"configured": False}
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
        # Clear existing data
        db.query(models.Preroll).delete()
        db.query(models.Category).delete()
        db.query(models.Schedule).delete()
        db.query(models.HolidayPreset).delete()
        db.commit()

        # Restore categories first (needed for foreign keys)
        for cat_data in backup_data.get("categories", []):
            category = models.Category(
                name=cat_data["name"],
                description=cat_data.get("description")
            )
            db.add(category)
        db.commit()

        # Build quick lookup by name
        name_to_category = {c.name: c for c in db.query(models.Category).all()}

        # Restore prerolls (including display_name and many-to-many categories if present)
        for preroll_data in backup_data.get("prerolls", []):
            p = models.Preroll(
                filename=preroll_data["filename"],
                display_name=preroll_data.get("display_name"),
                path=preroll_data["path"],
                thumbnail=preroll_data.get("thumbnail"),
                tags=preroll_data.get("tags"),
                category_id=preroll_data.get("category_id"),
                description=preroll_data.get("description"),
                upload_date=datetime.datetime.fromisoformat(preroll_data["upload_date"]) if preroll_data.get("upload_date") else None
            )
            db.add(p)
            db.flush()  # get p.id without full commit

            # Restore associated categories by name (IDs in backup may not match new DB)
            assoc = []
            try:
                for c in preroll_data.get("categories", []):
                    nm = c.get("name")
                    if nm and nm in name_to_category:
                        assoc.append(name_to_category[nm])
            except Exception:
                assoc = []
            if assoc:
                p.categories = assoc

        # Restore schedules
        for schedule_data in backup_data.get("schedules", []):
            schedule = models.Schedule(
                name=schedule_data["name"],
                type=schedule_data["type"],
                start_date=datetime.datetime.fromisoformat(schedule_data["start_date"]) if schedule_data.get("start_date") else None,
                end_date=datetime.datetime.fromisoformat(schedule_data["end_date"]) if schedule_data.get("end_date") else None,
                category_id=schedule_data.get("category_id"),
                shuffle=schedule_data.get("shuffle", False),
                playlist=schedule_data.get("playlist", False),
                is_active=schedule_data.get("is_active", True),
                recurrence_pattern=schedule_data.get("recurrence_pattern"),
                preroll_ids=schedule_data.get("preroll_ids")
            )
            db.add(schedule)

        # Restore holiday presets
        for holiday_data in backup_data.get("holiday_presets", []):
            holiday = models.HolidayPreset(
                name=holiday_data["name"],
                description=holiday_data.get("description"),
                month=holiday_data["month"],
                day=holiday_data["day"],
                category_id=holiday_data.get("category_id")
            )
            db.add(holiday)

        db.commit()
        return {"message": "Database restored successfully"}
    except Exception as e:
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

# Get absolute paths for static files
# Get absolute paths for static files relative to project root
# Determine install and resource roots
if getattr(sys, "frozen", False):
    install_root = os.path.dirname(sys.executable)
    resource_root = getattr(sys, "_MEIPASS", install_root)
# Alias endpoint for UI fallback: /thumbgen/&lt;Category&gt;/&lt;VideoName.ext&gt;.jpg

else:
    install_root = os.path.dirname(os.path.dirname(__file__))
    resource_root = install_root
# Prefer built React assets during dev if present; fallback to source 'frontend'
_candidate = os.path.join(resource_root, "frontend", "build")
frontend_dir = _candidate if (not getattr(sys, "frozen", False) and os.path.isdir(_candidate)) else os.path.join(resource_root, "frontend")

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
        src_root = os.path.join(resource_root, "nexroll_backend", "data", "prerolls")
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

@app.get("/static/thumbnails/{category}/{thumb_name}")
def compat_static_thumbnails(category: str, thumb_name: str):
    return get_or_create_thumbnail(category, thumb_name)

# Alias endpoint for UI fallback: /thumbgen/<Category>/<VideoName.ext>.jpg
@app.get("/thumbgen/{category}/{thumb_name}")
def alias_thumbgen(category: str, thumb_name: str):
    return get_or_create_thumbnail(category, thumb_name)

app.mount("/data", StaticFiles(directory=data_dir), name="data")

# Thumbnails are served by dynamic endpoints to support on-demand generation:
# - /static/prerolls/thumbnails/{category}/{thumb_name}
# - /static/thumbnails/{category}/{thumb_name} (compat)
# No static mount here to avoid shadowing the dynamic generator.



# Mount frontend static files LAST so API routes are checked first
app.mount("/", StaticFiles(directory=frontend_dir, html=True, check_dir=False), name="frontend")

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