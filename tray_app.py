import sys
import os
import webbrowser
import threading
import time
import subprocess
import ctypes

# Third-party (packaged into the EXE)
from PIL import Image, ImageDraw
import pystray


APP_URL = "http://localhost:9393"
GITHUB_URL = "https://github.com/JFLXCLOUD/NeXroll"
APP_NAME = "NeXroll"


def _message_box(title: str, text: str):
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION
    except Exception:
        pass


def open_app(icon: pystray.Icon, item=None):
    try:
        webbrowser.open(APP_URL)
    except Exception:
        _message_box("Open NeXroll", f"Could not open {APP_URL}")


def open_github(icon: pystray.Icon, item=None):
    try:
        webbrowser.open(GITHUB_URL)
    except Exception:
        _message_box("Open GitHub", f"Could not open {GITHUB_URL}")


def about(icon: pystray.Icon, item=None):
    _message_box(
        "About NeXroll",
        "NeXroll\n\nPlex Preroll Management System\n\n"
        "Web UI: http://localhost:9393\n"
        "GitHub: https://github.com/JFLXCLOUD/NeXroll"
    )


def on_exit(icon: pystray.Icon, item=None):
    # Stop the tray loop
    try:
        icon.visible = False
        icon.stop()
    except Exception:
        pass
    # Give UI thread time to unwind
    time.sleep(0.2)
    os._exit(0)


def _ensure_health_probe():
    # Best-effort: if the service is installed and stopped, the user can still open manually.
    # We keep tray lightweight and do not auto-start/stop services here.
    pass


def _build_icon_image():
    # Create a small 16x16 tray icon with a stylized 'N'
    size = (16, 16)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    draw.ellipse((0, 0, 15, 15), fill=(30, 144, 255, 255))  # DodgerBlue

    # Letter 'N'
    draw.line((4, 11, 4, 4), fill=(255, 255, 255, 255), width=2)
    draw.line((4, 4, 11, 11), fill=(255, 255, 255, 255), width=2)
    draw.line((11, 11, 11, 4), fill=(255, 255, 255, 255), width=2)

    return img


def resource_path(rel_path: str) -> str:
    """
    Resolve resource path for both dev mode and PyInstaller onefile.
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
    return os.path.join(base_path, rel_path)


def get_tray_image():
    """
    Try to load the packaged favicon.ico, fall back to generated glyph.
    """
    try:
        candidates = [
            resource_path(os.path.join("frontend", "favicon.ico")),
            resource_path("favicon.ico"),
            resource_path("NeXroll.ico"),
        ]
        for p in candidates:
            if os.path.exists(p):
                img = Image.open(p).convert("RGBA")
                # Ensure a sensible tray size; keep aspect ratio if already small
                if max(img.size) > 32:
                    img = img.resize((16, 16))
                return img
    except Exception:
        pass
    return _build_icon_image()


def run_tray():
    menu = pystray.Menu(
        pystray.MenuItem("Open", open_app, default=True),
        pystray.MenuItem("About", about),
        pystray.MenuItem("GitHub: JFLXCLOUD/NeXroll", open_github),
        pystray.MenuItem("Exit", on_exit)
    )

    icon = pystray.Icon("NeXrollTray", get_tray_image(), APP_NAME, menu)
    # Start a background health probe (optional, presently no-ops)
    t = threading.Thread(target=_ensure_health_probe, daemon=True)
    t.start()

    icon.run()


if __name__ == "__main__":
    # Run as GUI app (no console when packaged)
    run_tray()