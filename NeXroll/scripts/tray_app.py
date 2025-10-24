import sys
import os
import webbrowser
import threading
import time
import subprocess
import ctypes
import socket
import urllib.request
import json

# Third-party (packaged into the EXE)
from PIL import Image, ImageDraw
import pystray


APP_URL = "http://localhost:9393"
GITHUB_URL = "https://github.com/JFLXCLOUD/NeXroll"
LATEST_RELEASE_API = "https://api.github.com/repos/JFLXCLOUD/NeXroll/releases/latest"
LATEST_RELEASE_URL = "https://github.com/JFLXCLOUD/NeXroll/releases/latest"
APP_NAME = "NeXroll"

def _tray_log_dir():
    try:
        base = (
            os.environ.get("PROGRAMDATA")
            or os.environ.get("ProgramData")
            or os.environ.get("ALLUSERSPROFILE")
            or os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or os.path.dirname(sys.executable)
        )
        d = os.path.join(base, "NeXroll", "logs")
        os.makedirs(d, exist_ok=True)
        return d
    except Exception:
        try:
            d = os.path.join(os.path.dirname(sys.executable), "logs")
            os.makedirs(d, exist_ok=True)
            return d
        except Exception:
            return os.getcwd()

def _log_tray(msg: str):
    try:
        log_dir = _tray_log_dir()
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(os.path.join(log_dir, "tray.log"), "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {msg}\n")
    except Exception:
        pass


def _message_box(title: str, text: str):
    # Show a topmost, foreground info dialog on a background thread to avoid blocking the tray UI
    def _show():
        try:
            MB_OK = 0x00000000
            MB_ICONINFORMATION = 0x00000040
            MB_SETFOREGROUND = 0x00010000
            MB_TOPMOST = 0x00040000
            MB_TASKMODAL = 0x00002000
            flags = MB_OK | MB_ICONINFORMATION | MB_SETFOREGROUND | MB_TOPMOST | MB_TASKMODAL
            # Allow the MessageBox to take focus from background process
            try:
                ctypes.windll.user32.AllowSetForegroundWindow(-1)
            except Exception:
                pass
            ctypes.windll.user32.MessageBoxW(None, text, title, flags)
        except Exception:
            pass
    try:
        t = threading.Thread(target=_show, daemon=True)
        t.start()
    except Exception:
        # Fallback to synchronous display
        try:
            ctypes.windll.user32.MessageBoxW(None, text, title, 0x00000040)
        except Exception:
            pass


def _reg_get_value(subkey: str, value_name: str) -> str | None:
    """Read a registry value from HKLM in both 64-bit and 32-bit views (handles NSIS x86 writes)."""
    try:
        if not sys.platform.startswith("win"):
            return None
        import winreg
        # Try 64-bit view first, then 32-bit (Wow6432Node)
        for access in (
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_64KEY", 0),
            winreg.KEY_READ | getattr(winreg, "KEY_WOW64_32KEY", 0),
        ):
            try:
                key = winreg.OpenKeyEx(winreg.HKEY_LOCAL_MACHINE, subkey, 0, access)
                try:
                    val, _ = winreg.QueryValueEx(key, value_name)
                    s = str(val).strip() if val is not None else ""
                    if s:
                        return s
                finally:
                    winreg.CloseKey(key)
            except Exception:
                continue
    except Exception:
        pass
    return None


def _reg_install_dir() -> str | None:
    return _reg_get_value(r"Software\NeXroll", "InstallDir")


def _paths():
    inst = _reg_install_dir() or os.path.dirname(sys.executable)
    svc = os.path.join(inst, "NeXrollService.exe")
    app = os.path.join(inst, "NeXroll.exe")
    return inst, svc, app


def _is_listening(port: int = 9393, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except Exception:
        return False


def _probe_health(url: str = f"{APP_URL}/health", timeout: float = 2.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def _service_installed() -> bool:
    """Return True if the Windows service 'NeXrollService' is installed."""
    try:
        # 'sc query' returns 0 if service exists, non-zero otherwise
        rc = subprocess.run(
            ["sc", "query", "NeXrollService"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        return getattr(rc, "returncode", 1) == 0
    except Exception:
        return False


def _start_service_blocking(wait_seconds: int = 20) -> bool:
    """Attempt to start the service quickly; fall back to app if not installed or fails."""
    inst, svc, _ = _paths()
    if not os.path.exists(svc):
        return False
    # If the service is not installed, do not wait
    if not _service_installed():
        return False
    try:
        r = subprocess.run(
            [svc, "start"],
            cwd=inst,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        # If start failed, do not wait for long health timeout
        if getattr(r, "returncode", 1) != 0:
            return False
    except Exception:
        return False

    # Short health wait (reduce tray startup delay when service cannot become healthy)
    start = time.time()
    while time.time() - start < wait_seconds:
        if _probe_health() or _is_listening():
            return True
        time.sleep(1.0)
    return False


def _start_app_blocking(wait_seconds: int = 20) -> bool:
    inst, _, app = _paths()
    if not os.path.exists(app):
        _log_tray("start_app: app executable not found at " + app)
        return False
    try:
        # Best-effort: ensure no prior instances are locking port 9393
        try:
            subprocess.run(
                ["taskkill", "/F", "/IM", "NeXroll.exe", "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            )
        except Exception:
            pass
        subprocess.Popen(
            [app],
            cwd=inst,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
        _log_tray("start_app: launched NeXroll.exe from " + inst)
    except Exception as e:
        _log_tray(f"start_app: failed to launch NeXroll.exe: {e}")
        return False
    start = time.time()
    while time.time() - start < wait_seconds:
        if _probe_health() or _is_listening():
            return True
        time.sleep(1.0)
    return False


def ensure_backend_running():
    _log_tray("ensure_backend_running: invoked")
    # If already good, nothing to do
    if _probe_health() or _is_listening():
        _log_tray("ensure_backend_running: backend already healthy")
        return
    # Try to start service first; if fails (e.g., no admin rights), fall back to app
    _log_tray("ensure_backend_running: attempting to start service")
    if _start_service_blocking():
        _log_tray("ensure_backend_running: service reported healthy")
        return
    _log_tray("ensure_backend_running: service not available, trying portable app")
    ok = _start_app_blocking()
    if ok:
        _log_tray("ensure_backend_running: portable app reported healthy")
    else:
        _log_tray("ensure_backend_running: portable app did not reach healthy state")


def start_service(icon: object | None = None, item: object | None = None) -> None:
    _log_tray("start_service: invoked")
    ok = _start_service_blocking()
    if ok:
        _log_tray("start_service: service reported healthy")
        return
    _log_tray("start_service: service not available; attempting portable app")
    _message_box("NeXroll Service", "Failed to start service (may require admin). "
                 "Attempting to start app instead.")
    if not _start_app_blocking():
        _log_tray("start_service: portable app launch failed")
        _message_box("NeXroll", "Could not start NeXroll. Please run NeXroll.exe manually.")
    else:
        _log_tray("start_service: portable app reported healthy")


def stop_service(icon: object | None = None, item: object | None = None) -> None:
    _log_tray("stop_service: invoked")
    inst, svc, _ = _paths()
    if not os.path.exists(svc):
        _log_tray("stop_service: service executable not found")
        _message_box("NeXroll Service", "Service executable not found.")
        return
    try:
        subprocess.run([svc, "stop"], cwd=inst, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        _log_tray("stop_service: stop command issued")
    except Exception as e:
        _log_tray(f"stop_service: error: {e}")
        _message_box("NeXroll Service", f"Failed to stop service: {e}")


def restart_service(icon: object | None = None, item: object | None = None) -> None:
    _log_tray("restart_service: invoked")
    stop_service()
    time.sleep(1.5)
    start_service()


def start_app(icon: object | None = None, item: object | None = None) -> None:
    _log_tray("start_app: invoked")
    if not _start_app_blocking():
        _log_tray("start_app: failed to start portable app")
        _message_box("NeXroll", "Failed to start NeXroll application.")
    else:
        _log_tray("start_app: portable app reported healthy")


def open_app(icon: object | None = None, item: object | None = None) -> None:
    try:
        _log_tray(f"open_app: opening {APP_URL}")
        webbrowser.open(APP_URL)
    except Exception as e:
        _log_tray(f"open_app: error: {e}")
        _message_box("Open NeXroll", f"Could not open {APP_URL}")


def open_github(icon: object | None = None, item: object | None = None) -> None:
    try:
        _log_tray(f"open_github: opening {GITHUB_URL}")
        webbrowser.open(GITHUB_URL)
    except Exception as e:
        _log_tray(f"open_github: error: {e}")
        _message_box("Open GitHub", f"Could not open {GITHUB_URL}")


def rebuild_thumbnails(icon: object | None = None, item: object | None = None) -> None:
    _log_tray("rebuild_thumbnails: POST /thumbnails/rebuild?force=true")
    try:
        req = urllib.request.Request(f"{APP_URL}/thumbnails/rebuild?force=true", method="POST")
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        msg = (
            "Rebuild complete.\n"
            f"Processed: {data.get('processed')}\n"
            f"Generated: {data.get('generated')}\n"
            f"Skipped: {data.get('skipped')}\n"
            f"Failures: {data.get('failures')}"
        )
        _log_tray(f"rebuild_thumbnails: done processed={data.get('processed')} generated={data.get('generated')} skipped={data.get('skipped')} failures={data.get('failures')}")
    except Exception as e:
        msg = f"Rebuild failed: {e}"
        _log_tray(f"rebuild_thumbnails: error: {e}")
    _message_box("Rebuild Thumbnails", msg)

def _reg_version() -> str | None:
    # Read HKLM\Software\NeXroll\Version from both 64-bit and 32-bit views
    return _reg_get_value(r"Software\NeXroll", "Version")


def _backend_version() -> str | None:
    """Fallback: query the backend /system/version endpoint for installed/api version."""
    try:
        req = urllib.request.Request(
            f"{APP_URL}/system/version",
            headers={"User-Agent": "NeXrollTray/1.0", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            if getattr(resp, "status", 200) == 200:
                import json as _json
                data = _json.loads(resp.read().decode("utf-8"))
                # Prefer registry_version if provided by backend, else api_version
                ver = data.get("registry_version") or data.get("api_version") or ""
                ver = str(ver).strip()
                return ver if ver else None
    except Exception:
        return None
    return None


def _parse_version(s: str) -> tuple[int, int, int]:
    if not s:
        return (0, 0, 0)
    try:
        s = s.strip()
        if s and (s[0] == "v" or s[0] == "V"):
            s = s[1:]
        parts = s.split(".")
        nums = []
        for p in parts:
            # keep digits only
            digits = "".join(ch for ch in p if ch.isdigit())
            nums.append(int(digits) if digits else 0)
        while len(nums) < 3:
            nums.append(0)
        return tuple(nums[:3])
    except Exception:
        return (0, 0, 0)


def check_for_updates(icon: object | None = None, item: object | None = None) -> None:
    # Prefer registry version, then backend-reported version, else 0.0.0
    current = _reg_version() or _backend_version() or "0.0.0"
    latest_tag = None
    try:
        req = urllib.request.Request(
            LATEST_RELEASE_API,
            headers={"User-Agent": "NeXrollTray/1.0", "Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latest_tag = data.get("tag_name") or data.get("name")
    except Exception as e:
        latest_tag = None
        _log_tray(f"check_for_updates: error contacting GitHub: {e}")

    if not latest_tag:
        _log_tray("check_for_updates: latest release not resolved; opening releases page")
        _message_box("NeXroll Update", "Could not check for updates. Opening releases page.")
        try:
            webbrowser.open(LATEST_RELEASE_URL)
        except Exception:
            pass
        return

    _log_tray(f"check_for_updates: installed={current} latest={latest_tag}")

    curr_v = _parse_version(current)
    latest_v = _parse_version(latest_tag)

    if latest_v > curr_v:
        _message_box("NeXroll Update", f"New version available: {latest_tag} (installed: {current}). Opening download page.")
        try:
            webbrowser.open(LATEST_RELEASE_URL)
        except Exception:
            pass
    else:
        _message_box("NeXroll Update", f"You are up to date.\nInstalled: {current}\nLatest: {latest_tag}")


def about(icon: object | None = None, item: object | None = None) -> None:
    _message_box(
        "About NeXroll",
        "NeXroll\n\nPlex Preroll Management System\n\n"
        "Web UI: http://localhost:9393\n"
        "GitHub: https://github.com/JFLXCLOUD/NeXroll"
    )


def on_exit(icon: object | None = None, item: object | None = None) -> None:
    try:
        icon.visible = False
        icon.stop()
    except Exception:
        pass
    time.sleep(0.2)
    os._exit(0)


def _build_icon_image():
    size = (16, 16)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, 15, 15), fill=(30, 144, 255, 255))
    draw.line((4, 11, 4, 4), fill=(255, 255, 255, 255), width=2)
    draw.line((4, 4, 11, 11), fill=(255, 255, 255, 255), width=2)
    draw.line((11, 11, 11, 4), fill=(255, 255, 255, 255), width=2)
    return img


def resource_path(rel_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base_path, rel_path)


def get_tray_image():
    try:
        # Prefer packaged dedicated icons if present
        try:
            icon_dir = resource_path("NeXroll_ICON")
            if os.path.isdir(icon_dir):
                # Prefer specific sizes first, then any .ico
                ordered = []
                for fname in os.listdir(icon_dir):
                    fn = fname.lower()
                    if fn.endswith("16x16.ico"):
                        ordered.append(os.path.join(icon_dir, fname))
                for fname in os.listdir(icon_dir):
                    fn = fname.lower()
                    if fn.endswith("32x32.ico"):
                        ordered.append(os.path.join(icon_dir, fname))
                for fname in os.listdir(icon_dir):
                    fn = fname.lower()
                    if fn.endswith("64x64.ico"):
                        ordered.append(os.path.join(icon_dir, fname))
                for fname in os.listdir(icon_dir):
                    fn = fname.lower()
                    if fn.endswith(".ico") and os.path.join(icon_dir, fname) not in ordered:
                        ordered.append(os.path.join(icon_dir, fname))

                for p in ordered:
                    if os.path.exists(p):
                        img = Image.open(p).convert("RGBA")
                        if max(img.size) > 32:
                            img = img.resize((16, 16))
                        return img
        except Exception:
            pass

        # Fallbacks (packaged resources)
        candidates = [
            resource_path(os.path.join("frontend", "favicon.ico")),
            resource_path("favicon.ico"),
            resource_path("NeXroll.ico"),
        ]
        for p in candidates:
            if os.path.exists(p):
                img = Image.open(p).convert("RGBA")
                if max(img.size) > 32:
                    img = img.resize((16, 16))
                return img

        # Also check alongside the installed executable (e.g., C:\ProgramData or Program Files\NeXroll)
        try:
            exe_dir = os.path.dirname(sys.executable)
            extra = [
                os.path.join(exe_dir, "favicon.ico"),
                os.path.join(exe_dir, "NeXroll.ico"),
            ]
            for p in extra:
                if os.path.exists(p):
                    img = Image.open(p).convert("RGBA")
                    if max(img.size) > 32:
                        img = img.resize((16, 16))
                    return img
        except Exception:
            pass
    except Exception:
        pass
    return _build_icon_image()


def run_tray():
    _log_tray("NeXrollTray starting")
    menu = pystray.Menu(
        pystray.MenuItem("Open", open_app, default=True),
        pystray.MenuItem("Start Service", start_service),
        pystray.MenuItem("Stop Service", stop_service),
        pystray.MenuItem("Restart Service", restart_service),
        pystray.MenuItem("Start App (portable)", start_app),
        pystray.MenuItem("Rebuild Thumbnails", rebuild_thumbnails),
        pystray.MenuItem("Check for updates", check_for_updates),
        pystray.MenuItem("About", about),
        pystray.MenuItem("GitHub: JFLXCLOUD/NeXroll", open_github),
        pystray.MenuItem("Exit", on_exit)
    )

    icon = pystray.Icon("NeXrollTray", get_tray_image(), APP_NAME, menu)
    t = threading.Thread(target=ensure_backend_running, daemon=True)
    t.start()
    icon.run()


if __name__ == "__main__":
    # Install a global excepthook to capture unhandled exceptions to ProgramData\NeXroll\logs\tray.log
    def _tray_excepthook(exc_type, exc, tb):
        try:
            import traceback
            lines = "".join(traceback.format_exception(exc_type, exc, tb))
            _log_tray(f"Unhandled exception: {lines}")
        except Exception:
            pass
        # Also show a minimal message box to surface fatal errors when running interactively
        try:
            _message_box("NeXroll Tray Error", f"{exc_type.__name__}: {exc}")
        except Exception:
            pass
    try:
        sys.excepthook = _tray_excepthook
    except Exception:
        pass
    # Run as GUI app (no console when packaged)
    run_tray()