"""PO-Token provider management for YouTube trailer downloads.

YouTube now requires a Proof-of-Origin (PO) token to access most video streams.
Without one, yt-dlp hits "Sign in to confirm you're not a bot" or only sees
image formats ("Requested format is not available"). The fix is the
`bgutil-ytdlp-pot-provider` yt-dlp plugin plus a small local provider that mints
tokens.

We run the bgutil PO-token HTTP server as a managed subprocess. The plugin
(installed in the Python env) auto-fetches tokens from http://127.0.0.1:<port>,
so no per-download wiring into yt-dlp is required — the whole download path
benefits just by having the server up and the plugin importable.

Everything here degrades gracefully: if Node or the provider files aren't
present, downloads continue exactly as before (no PO token), so this never makes
things worse than today.

Layout resolved for the provider server (`build/main.js`), first match wins:
  1. $NEXROLL_BGUTIL_DIR                         (explicit override / dev)
  2. /opt/bgutil-provider/server                 (baked into the Docker image)
  3. <base_dir>/bgutil-provider/server           (one-click install on Windows)
"""

import os
import sys
import shutil
import subprocess
import threading
import json
import time
import importlib.util
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError

# bgutil's default port; the yt-dlp plugin auto-connects here with no config.
DEFAULT_PORT = 4416

_IS_WIN = sys.platform.startswith("win")


def _default_port() -> int:
    try:
        return int(os.environ.get("NEXROLL_POT_PORT", "") or DEFAULT_PORT)
    except (ValueError, TypeError):
        return DEFAULT_PORT


def find_node() -> Optional[str]:
    """Locate the Node.js executable (PATH first, then common install dirs)."""
    p = shutil.which("node")
    if p:
        return p
    exe = "node.exe" if _IS_WIN else "node"
    candidates = []
    if _IS_WIN:
        for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            base = os.environ.get(var)
            if base:
                candidates.append(os.path.join(base, "nodejs", exe))
        la = os.environ.get("LOCALAPPDATA")
        if la:
            candidates.append(os.path.join(la, "Programs", "nodejs", exe))
        home = os.path.expanduser("~")
        # Our managed install location (mirrors how Deno is handled)
        candidates.append(os.path.join(home, ".nexroll", "node", exe))
        candidates.append(os.path.join(home, ".nexroll", "node", "bin", exe))
    else:
        candidates += [
            "/usr/local/bin/node",
            "/usr/bin/node",
            os.path.join(os.path.expanduser("~"), ".nexroll", "node", "bin", exe),
        ]
    for c in candidates:
        try:
            if c and os.path.isfile(c):
                return c
        except Exception:
            pass
    return None


def node_major_minor(node: str) -> tuple:
    """Return (major, minor) of the Node binary, or (0, 0) if undetermined."""
    try:
        out = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10)
        ver = (out.stdout or "").strip().lstrip("v")  # e.g. "20.18.1"
        parts = ver.split(".")
        return (int(parts[0]), int(parts[1]))
    except Exception:
        return (0, 0)


def _needs_require_module_flag(major: int, minor: int) -> bool:
    """True when Node needs --experimental-require-module to ``require()`` an
    ESM dependency.

    The provider's jsdom stack pulls an ESM-only ``@exodus/bytes`` that
    ``html-encoding-sniffer`` loads via CommonJS ``require()``. On Node < 22.12
    that raises ERR_REQUIRE_ESM and the server exits rc=1 at startup (the
    bundled Node 20.18.1 hit exactly this). ``require(esm)`` ships enabled by
    default on Node >= 22.12 and all of 23/24, and is available behind the flag
    from 20.17 up to that cutoff. Below 20.17 the flag doesn't exist (those
    users need a newer Node); at/above the cutoff it's unnecessary, so we omit
    it to stay future-proof against the flag eventually being removed.
    """
    if major == 20:
        return minor >= 17
    if major == 21:
        return True
    if major == 22:
        return minor < 12
    return False


def is_plugin_installed() -> bool:
    """True if the bgutil PO-token yt-dlp plugin is importable."""
    try:
        # The plugin registers under the yt_dlp_plugins namespace package.
        if importlib.util.find_spec("yt_dlp_plugins") is None:
            return False
        # Be specific: look for the bgutil provider module.
        for name in (
            "yt_dlp_plugins.extractor.getpot_bgutil",
            "yt_dlp_plugins.extractor.getpot_bgutil_http",
        ):
            try:
                if importlib.util.find_spec(name) is not None:
                    return True
            except Exception:
                continue
        # Fall back to "some yt_dlp plugin present" — better than a false negative.
        return True
    except Exception:
        return False


def provider_server_dir(base_dir: Optional[str]) -> Optional[Path]:
    """Resolve the bgutil provider server directory containing build/main.js."""
    candidates = []
    env = os.environ.get("NEXROLL_BGUTIL_DIR")
    if env and env.strip():
        candidates.append(Path(env.strip()))
    candidates.append(Path("/opt/bgutil-provider/server"))
    if base_dir:
        candidates.append(Path(base_dir) / "bgutil-provider" / "server")
    for c in candidates:
        try:
            if (c / "build" / "main.js").is_file():
                return c
        except Exception:
            pass
    return None


class POTokenManager:
    """Starts/heals/stops the bgutil PO-token HTTP provider and reports status."""

    def __init__(self, base_dir: Optional[str] = None,
                 log: Optional[Callable[[str], None]] = None,
                 port: Optional[int] = None):
        self.base_dir = base_dir
        self.port = int(port or _default_port())
        self._log = log or (lambda m: None)
        self._proc: Optional[subprocess.Popen] = None
        self._adopted = False  # True when an already-running server was reused
        self._lock = threading.Lock()

    # -- helpers ---------------------------------------------------------
    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def log_path(self) -> Optional[str]:
        if not self.base_dir:
            return None
        return os.path.join(self.base_dir, "bgutil-provider.log")

    def server_dir(self) -> Optional[Path]:
        return provider_server_dir(self.base_dir)

    def log_tail(self, lines: int = 25) -> Optional[str]:
        """Last lines of bgutil-provider.log — the Node server's own stdout/stderr.
        Surfaced in status/install responses so an rc=1 crash (e.g. a missing
        canvas/VC++ runtime) is visible without hunting for the file on disk."""
        lp = self.log_path
        if not lp or not os.path.exists(lp):
            return None
        try:
            with open(lp, "rb") as f:
                data = f.read()[-8000:]  # last ~8 KB is plenty for a crash trace
            text = data.decode("utf-8", "replace")
            tail = "\n".join(text.splitlines()[-lines:]).strip()
            return tail or None
        except Exception:
            return None

    def is_healthy(self, timeout: float = 3.0) -> bool:
        try:
            with urlopen(f"{self.base_url}/ping", timeout=timeout) as r:
                if r.status != 200:
                    return False
                data = json.loads(r.read().decode("utf-8", "replace") or "{}")
                return "version" in data or "server_uptime" in data
        except (URLError, OSError, ValueError, json.JSONDecodeError):
            return False
        except Exception:
            return False

    def provider_version(self, timeout: float = 3.0) -> Optional[str]:
        try:
            with urlopen(f"{self.base_url}/ping", timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8", "replace") or "{}")
                return data.get("version")
        except Exception:
            return None

    def test_mint(self, timeout: float = 30.0) -> Dict[str, Any]:
        """Ask the provider to actually mint a PO token now — the definitive
        "it's working" check. Exercises the full chain (plugin present + server
        running + Google BotGuard reachable) independent of any YouTube video."""
        from urllib.request import Request
        if not is_plugin_installed():
            return {"ok": False, "reason": "The yt-dlp PO-token plugin isn't installed."}
        if not self.is_healthy():
            return {"ok": False, "reason": "The PO-token provider server isn't running."}
        try:
            body = json.dumps({"content_binding": "nexroll-selftest"}).encode("utf-8")
            req = Request(f"{self.base_url}/get_pot", data=body,
                          headers={"Content-Type": "application/json"}, method="POST")
            with urlopen(req, timeout=timeout) as r:
                payload = json.loads(r.read().decode("utf-8", "replace") or "{}")
            token = payload.get("poToken") or payload.get("po_token")
            if token:
                return {"ok": True, "minted": True, "token_preview": str(token)[:10] + "…"}
            return {"ok": False, "reason": payload.get("error") or "No token returned by provider."}
        except Exception as e:
            return {"ok": False, "reason": f"Mint request failed: {e}"}

    # -- lifecycle -------------------------------------------------------
    def start(self) -> Dict[str, Any]:
        """Start the provider server if needed. Adopts an already-running one
        (dev, or a user-managed sidecar) instead of spawning a duplicate."""
        with self._lock:
            if self.is_healthy():
                # Something is already serving on the port — reuse it.
                if self._proc is None:
                    self._adopted = True
                self._log(f"[potoken] provider already healthy at {self.base_url}")
                return self.status()

            node = find_node()
            sdir = self.server_dir()
            if not node or not sdir:
                self._log(
                    f"[potoken] not starting (node={'yes' if node else 'no'}, "
                    f"server_dir={'yes' if sdir else 'no'}) — downloads will run "
                    f"without PO tokens"
                )
                return self.status()

            main_js = sdir / "build" / "main.js"
            cmd = [node]
            maj, minr = node_major_minor(node)
            if _needs_require_module_flag(maj, minr):
                # Without this, Node 20.17–22.11 crash at startup (rc=1,
                # ERR_REQUIRE_ESM) loading the provider's ESM-only @exodus/bytes.
                cmd.append("--experimental-require-module")
            cmd += [str(main_js), "--port", str(self.port)]
            creationflags = 0
            if _IS_WIN:
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                logf = None
                if self.log_path:
                    try:
                        logf = open(self.log_path, "ab", buffering=0)
                    except Exception:
                        logf = None
                self._proc = subprocess.Popen(
                    cmd,
                    cwd=str(sdir),
                    stdout=(logf or subprocess.DEVNULL),
                    stderr=(logf or subprocess.DEVNULL),
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags,
                )
                self._adopted = False
                self._log(f"[potoken] started provider: {' '.join(cmd)} (pid={self._proc.pid})")
            except Exception as e:
                self._log(f"[potoken] failed to start provider: {e}")
                self._proc = None
                return self.status()

        # Wait (outside the lock) for the server to become healthy.
        for _ in range(24):  # ~12s
            if self.is_healthy(timeout=2.0):
                self._log(f"[potoken] provider healthy at {self.base_url}")
                break
            if self._proc is not None and self._proc.poll() is not None:
                self._log(f"[potoken] provider process exited early (rc={self._proc.returncode})")
                break
            time.sleep(0.5)
        return self.status()

    def stop(self) -> None:
        with self._lock:
            if self._proc is not None and not self._adopted:
                try:
                    self._proc.terminate()
                    try:
                        self._proc.wait(timeout=5)
                    except Exception:
                        self._proc.kill()
                    self._log("[potoken] provider stopped")
                except Exception as e:
                    self._log(f"[potoken] error stopping provider: {e}")
            self._proc = None

    def ensure_running(self) -> Dict[str, Any]:
        """Start the provider if it isn't healthy (cheap to call repeatedly)."""
        if self.is_healthy():
            return self.status()
        return self.start()

    # -- reporting -------------------------------------------------------
    def status(self) -> Dict[str, Any]:
        node = find_node()
        sdir = self.server_dir()
        healthy = self.is_healthy()
        running = healthy or (self._proc is not None and self._proc.poll() is None)
        return {
            "plugin_installed": is_plugin_installed(),
            "node_path": node,
            "node_available": bool(node),
            "server_dir": str(sdir) if sdir else None,
            "provider_present": bool(sdir),
            "running": bool(running),
            "healthy": bool(healthy),
            "adopted": self._adopted,
            "port": self.port,
            "base_url": self.base_url,
            "version": self.provider_version() if healthy else None,
            # Usable means yt-dlp will actually get tokens: plugin importable AND
            # a healthy server to talk to.
            "usable": bool(is_plugin_installed() and healthy),
            "log_path": self.log_path,
            # When the provider isn't healthy, surface the server's own log tail so
            # the crash reason (e.g. canvas/VC++ load failure) is visible directly.
            "log_excerpt": (None if healthy else self.log_tail()),
        }


# Module-level singleton --------------------------------------------------
_manager: Optional[POTokenManager] = None


def init(base_dir: Optional[str], log: Optional[Callable[[str], None]] = None,
         port: Optional[int] = None) -> POTokenManager:
    global _manager
    _manager = POTokenManager(base_dir=base_dir, log=log, port=port)
    return _manager


def get_manager() -> Optional[POTokenManager]:
    return _manager
