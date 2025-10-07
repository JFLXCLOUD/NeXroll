import os
import sys
import shutil
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

def _is_elevated() -> bool:
    try:
        if sys.platform.startswith("win"):
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        pass
    return False
def _is_dir_writable(p: str) -> bool:
    try:
        os.makedirs(p, exist_ok=True)
        test = os.path.join(p, f".nexroll_write_test_{os.getpid()}.tmp")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        try:
            os.remove(test)
        except Exception:
            pass
        return True
    except Exception:
        return False

def _is_file_writable(fp: str) -> bool:
    """
    Check if a specific file is writable and if its directory allows creating side files
    (SQLite requires creating -wal / -shm next to db).
    """
    try:
        # File-level check (may fail if read-only attribute or ACL denies write)
        if os.path.exists(fp):
            try:
                with open(fp, "a", encoding="utf-8"):
                    pass
            except Exception:
                return False
        # Directory-level side-file check
        d = os.path.dirname(fp) or "."
        if not _is_dir_writable(d):
            return False
        side = os.path.join(d, f".nexroll_sqlite_side_{os.getpid()}.tmp")
        with open(side, "w", encoding="utf-8") as f:
            f.write("ok")
        try:
            os.remove(side)
        except Exception:
            pass
        return True
    except Exception:
        return False




def _install_root() -> str:
    try:
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        return os.path.dirname(os.path.abspath(__file__))
    except Exception:
        return os.getcwd()


def _program_data_dir() -> str:
    """
    Prefer ProgramData\\NeXroll (system-wide writable via installer ACLs).
    If not writable (portable, no installer), fall back to ProgramData\\NeXroll,
    then to ProgramData\\NeXroll, then to ProgramData\\NeXroll.
    """
    # Windows
    if sys.platform.startswith("win"):
        pd = os.environ.get("ProgramData")
        if pd:
            pd_dir = os.path.join(pd, "NeXroll")
            try:
                os.makedirs(pd_dir, exist_ok=True)
                return pd_dir
            except Exception:
                pass
        # Fallback to user-local
        la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        try:
            user_dir = os.path.join(la, "NeXroll")
            os.makedirs(user_dir, exist_ok=True)
            return user_dir
        except Exception:
            pass
    # Dev/other platforms
    d = os.path.join(_install_root(), "data")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _resolve_db_path() -> str:
    # 1) Explicit file override
    env_path = os.environ.get("NEXROLL_DB_PATH")
    if env_path and env_path.strip():
        dest_path = os.path.abspath(env_path.strip())
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        return dest_path

    # 2) Directory override
    env_dir = os.environ.get("NEXROLL_DB_DIR")
    if env_dir and env_dir.strip():
        target_dir = os.path.abspath(env_dir.strip())
    else:
        target_dir = _program_data_dir()

    # Ensure we end up with a writable directory (ProgramData may exist but not be writable for standard users)
    if not _is_dir_writable(target_dir):
        la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
        user_dir = os.path.join(la, "NeXroll")
        if _is_dir_writable(user_dir):
            target_dir = user_dir
        else:
            fallback = os.path.join(_install_root(), "data")
            try:
                os.makedirs(fallback, exist_ok=True)
            except Exception:
                pass
            target_dir = fallback

    # Migrate legacy DB from install root (e.g., Program Files) to ProgramData on first run
    legacy_path = os.path.join(_install_root(), "nexroll.db")
    target_path = os.path.join(target_dir, "nexroll.db")
    try:
        if not os.path.exists(target_path) and os.path.exists(legacy_path):
            shutil.copy2(legacy_path, target_path)
    except Exception:
        # Non-fatal; continue with empty/new DB
        pass

    # Ensure the database file is writable; if not, attempt to fix or relocate to user-local
    try:
        if os.path.exists(target_path) and not _is_file_writable(target_path):
            # Try to drop read-only attribute (may help if only FILE_ATTRIBUTE_READONLY is set)
            try:
                import stat
                os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD)
            except Exception:
                pass
            # Re-check; if still not writable, relocate to user-local app data
            if not _is_file_writable(target_path):
                la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
                user_dir = os.path.join(la, "NeXroll")
                try:
                    os.makedirs(user_dir, exist_ok=True)
                except Exception:
                    # Fallback to install-root data if user dir cannot be created
                    user_dir = os.path.join(_install_root(), "data")
                    try:
                        os.makedirs(user_dir, exist_ok=True)
                    except Exception:
                        pass
                alt_path = os.path.join(user_dir, "nexroll.db")
                try:
                    shutil.copy2(target_path, alt_path)
                except Exception:
                    # As a last resort, create an empty DB file
                    try:
                        with open(alt_path, "a", encoding="utf-8"):
                            pass
                    except Exception:
                        # Give up on relocation; keep original path
                        return target_path
                return alt_path
    except Exception:
        # Ignore relocation failures and continue using target_path
        pass

    return target_path


DB_PATH = _resolve_db_path()
DB_URL_PATH = DB_PATH.replace("\\", "/")
SQLALCHEMY_DATABASE_URL = "sqlite:///" + DB_URL_PATH
 
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)

# Apply SQLite pragmas for better concurrency and reliability
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            # Enable WAL for concurrent reads/writes
            cursor.execute("PRAGMA journal_mode=WAL;")
            # Reasonable sync for performance
            cursor.execute("PRAGMA synchronous=NORMAL;")
            # Enforce foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON;")
            # Increase busy timeout to mitigate 'database is locked'
            cursor.execute("PRAGMA busy_timeout=10000;")
            cursor.close()
        except Exception:
            # Best-effort; continue without raising
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()