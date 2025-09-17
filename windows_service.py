import os
import sys
import time
import signal
import subprocess
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
            return {
                "cmd": [nexroll_exe],
                "cwd": inst_dir
            }

        # Fall back to Python (system) if available
        python = None
        for cand in ["python", "python3", sys.executable]:
            try:
                completed = subprocess.run([cand, "--version"], capture_output=True)
                if completed.returncode == 0:
                    python = cand
                    break
            except Exception:
                continue

        if python:
            return {
                "cmd": [python, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9393"],
                "cwd": inst_dir
            }

        # Last resort: try the venv if present
        venv_python = os.path.join(inst_dir, "venv", "Scripts", "python.exe")
        if os.path.exists(venv_python):
            return {
                "cmd": [venv_python, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "9393"],
                "cwd": inst_dir
            }

        # If nothing found, return None
        return None

    def _start_backend(self):
        launch = self._build_launch_command()
        if not launch:
            servicemanager.LogErrorMsg("NeXrollService: No suitable runtime found to start NeXroll (missing NeXroll.exe and Python).")
            return None

        creationflags = 0
        try:
            # On Windows, hide console window for background service
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                creationflags |= subprocess.CREATE_NO_WINDOW
        except Exception:
            pass

        env = os.environ.copy()
        # Respect configured PrerollPath from registry via backend code; nothing special here

        try:
            proc = subprocess.Popen(
                launch["cmd"],
                cwd=launch["cwd"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
                creationflags=creationflags
            )
            servicemanager.LogInfoMsg(f"NeXrollService: Started backend with PID {proc.pid}")
            return proc
        except Exception as e:
            servicemanager.LogErrorMsg(f"NeXrollService: Failed to start backend: {e}")
            return None

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("NeXrollService: Service starting...")
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)

        # Start the backend process
        self.proc = self._start_backend()
        if not self.proc:
            # Could not start, report stop
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            return

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        servicemanager.LogInfoMsg("NeXrollService: Service running.")

        # Main loop: wait for stop event, monitor child process
        try:
            while True:
                # Wait for stop signal for up to 2 seconds
                rc = win32event.WaitForSingleObject(self.hWaitStop, 2000)
                # If stop event is signaled, break
                if rc == win32event.WAIT_OBJECT_0:
                    break

                # If child exited unexpectedly while not stopping, attempt a single restart
                if self.proc and self.proc.poll() is not None and not self.stopping:
                    exit_code = self.proc.returncode
                    servicemanager.LogErrorMsg(f"NeXrollService: Backend exited unexpectedly with code {exit_code}. Attempting restart...")
                    time.sleep(2)
                    self.proc = self._start_backend()
                    if not self.proc:
                        break
        finally:
            # Ensure backend is stopped on service exit
            self._terminate_backend()
            servicemanager.LogInfoMsg("NeXrollService: Service stopped.")
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
        self.proc = None

    def SvcStop(self):
        servicemanager.LogInfoMsg("NeXrollService: Stop requested.")
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