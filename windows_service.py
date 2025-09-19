import os
import sys
import time
import signal
import socket
import subprocess
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import win32event
import win32service
import win32serviceutil
import servicemanager


class NeXrollService(win32serviceutil.ServiceFramework):
    _svc_name_ = "NeXrollService"
    _svc_display_name_ = "NeXroll Background Service"
    _svc_description_ = "Runs the NeXroll FastAPI backend as a Windows service."

    def __init__(self, args):
        super().__init__(args)
        # Event to listen for stop requests
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None
        self.stopping = False
        self.startup_checkpoint = 0
        self.log_dir = self._get_log_dir()
        try:
            os.makedirs(self.log_dir, exist_ok=True)
        except Exception:
            pass
        self._log("info", "Service initialized.")

    def _get_install_dir(self) -> str:
        # When frozen by PyInstaller, sys.executable is the service exe path
        if getattr(sys, "frozen", False):
            return os.path.dirname(sys.executable)
        # Else, use this script's directory
        return os.path.dirname(os.path.abspath(__file__))

    def _build_launch_command(self):
        inst_dir = self._get_install_dir()
        nexroll_exe = os.path.join(inst_dir, "NeXroll.exe")

        # Prefer the packaged executable
        if os.path.exists(nexroll_exe):
            return {"cmd": [nexroll_exe], "cwd": inst_dir}

        # Fall back to Python (system) if available
        python = None
        for cand in ["python", "python3", sys.executable]:
            try:
                # Hide any flash of console windows when probing python
                si = None
                try:
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
                except Exception:
                    si = None
                completed = subprocess.run(
                    [cand, "--version"],
                    capture_output=True,
                    startupinfo=si,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if completed.returncode == 0:
                    python = cand
                    break
            except Exception:
                continue

        if python:
            # Note: In installed layout, backend sources are not present; this fallback
            # is best-effort for developer installs only.
            return {
                "cmd": [python, "-m", "uvicorn", "nexroll_backend.main:app", "--host", "0.0.0.0", "--port", "9393"],
                "cwd": inst_dir,
            }

        # Last resort: try the venv if present
        venv_python = os.path.join(inst_dir, "venv", "Scripts", "python.exe")
        if os.path.exists(venv_python):
            return {
                "cmd": [venv_python, "-m", "uvicorn", "nexroll_backend.main:app", "--host", "0.0.0.0", "--port", "9393"],
                "cwd": inst_dir,
            }

        # If nothing found, return None
        return None

    def _get_log_dir(self) -> str:
        base = os.environ.get("PROGRAMDATA") or os.environ.get("ALLUSERSPROFILE") or self._get_install_dir()
        return os.path.join(base, "NeXroll", "logs")

    def _log(self, level: str, msg: str):
        # Write to Windows Event Log and file
        text = f"NeXrollService: {msg}"
        try:
            if level.lower() == "error":
                servicemanager.LogErrorMsg(text)
            else:
                servicemanager.LogInfoMsg(text)
        except Exception:
            pass

        try:
            log_path = os.path.join(self.log_dir, "service.log")
            with open(log_path, "a", encoding="utf-8") as f:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{ts}] [{level.upper()}] {msg}\n")
        except Exception:
            pass

    def _is_port_open(self, host: str, port: int, timeout: float = 1.5) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception:
            return False

    def _wait_for_health(self, timeout: int = 60) -> bool:
        """Wait until the backend reports healthy or port 9393 is open."""
        start = time.time()
        last_log = 0.0
        url = "http://127.0.0.1:9393/health"

        while not self.stopping and (time.time() - start) < timeout:
            # Try HTTP health
            try:
                req = Request(url, headers={"User-Agent": "NeXrollService/1.0"})
                with urlopen(req, timeout=2) as resp:
                    if getattr(resp, "status", 200) == 200:
                        return True
            except (URLError, HTTPError, TimeoutError, Exception):
                pass

            # Fallback to port check
            if self._is_port_open("127.0.0.1", 9393, timeout=1.0):
                return True

            # Periodically tell SCM we're still starting
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            # Log every 5 seconds while waiting
            if time.time() - last_log > 5.0:
                self._log("info", "Waiting for backend health on http://127.0.0.1:9393/health ...")
                last_log = time.time()

            # Wait or break if stop requested
            rc = win32event.WaitForSingleObject(self.hWaitStop, 1000)
            if rc == win32event.WAIT_OBJECT_0:
                break

        return False

    def _start_backend(self):
        launch = self._build_launch_command()
        if not launch:
            self._log("error", "No suitable runtime found to start NeXroll (missing NeXroll.exe and Python).")
            return None

        creationflags = 0
        try:
            # On Windows, hide console window for background service
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW
        except Exception:
            pass

        try:
            proc = subprocess.Popen(
                launch["cmd"],
                cwd=launch["cwd"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                creationflags=creationflags,
            )
            self._log("info", f"Started backend with PID {proc.pid} (cmd: {' '.join(launch['cmd'])})")
            return proc
        except Exception as e:
            self._log("error", f"Failed to start backend: {e}")
            return None

    def SvcDoRun(self):
        self._log("info", "Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        healthy = False
        attempts = 0
        max_attempts = 2

        while attempts < max_attempts and not self.stopping:
            if attempts > 0:
                self._log("info", f"Retrying backend start (attempt {attempts + 1}/{max_attempts})...")
                time.sleep(2)

            self.proc = self._start_backend()
            if not self.proc:
                break

            # Keep START_PENDING while probing readiness
            self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
            healthy = self._wait_for_health(timeout=45)

            if healthy:
                break

            # Not healthy, terminate this attempt and try again
            self._log("error", "Backend failed readiness probe. Restarting...")
            self._terminate_backend()
            attempts += 1

        # Move to RUNNING to avoid SCM timeout; continue monitoring even if unhealthy
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        if healthy:
            self._log("info", "Service running (backend healthy).")
        else:
            self._log("error", "Service running but backend did not become healthy; will monitor/restart if needed.")

        # Main loop: wait for stop event, monitor child process
        try:
            while True:
                # Wait for stop signal for up to 2 seconds
                rc = win32event.WaitForSingleObject(self.hWaitStop, 2000)
                # If stop event is signaled, break
                if rc == win32event.WAIT_OBJECT_0:
                    break

                # If child exited unexpectedly while not stopping, attempt a restart
                if self.proc and self.proc.poll() is not None and not self.stopping:
                    exit_code = self.proc.returncode
                    self._log("error", f"Backend exited unexpectedly with code {exit_code}. Attempting restart...")
                    time.sleep(2)
                    self.proc = self._start_backend()
                    if not self.proc:
                        self._log("error", "Restart failed; stopping service loop.")
                        break

        finally:
            # Ensure backend is stopped on service exit
            self._terminate_backend()
            self._log("info", "Service stopped.")
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def _terminate_backend(self):
        if not self.proc:
            return
        try:
            # Try graceful termination
            self.proc.terminate()
        except Exception:
            pass

        # Wait briefly
        try:
            self.proc.wait(timeout=10)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        finally:
            self.proc = None

    def SvcStop(self):
        self._log("info", "Stop requested.")
        self.stopping = True
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self._terminate_backend()


if __name__ == "__main__":
    # This allows standard pywin32 service commands:
    # windows_service.exe install
    # windows_service.exe start
    # windows_service.exe stop
    # windows_service.exe remove
    win32serviceutil.HandleCommandLine(NeXrollService)