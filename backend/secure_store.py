import os
import sys
import json
import base64
from typing import Optional, Tuple

# Public API:
# - has_secret(name) -> bool
# - get_secret(name) -> Optional[str]
# - set_secret(name, value) -> bool
# - delete_secret(name) -> bool
# - provider_info() -> Tuple[str, str] (provider_key, human_readable)


# ----------------------------
# Utilities and path resolution
# ----------------------------

def _program_data_root() -> str:
    r"""
    Returns a writable base directory for NeXroll app data.
    Prefers ProgramData\NeXroll or LOCALAPPDATA/APPDATA\NeXroll on Windows.
    Falls back to current working directory otherwise.
    """
    try:
        if sys.platform.startswith("win"):
            pd = os.environ.get("ProgramData")
            if pd:
                p = os.path.join(pd, "NeXroll")
                try:
                    os.makedirs(p, exist_ok=True)
                except Exception:
                    pass
                return p
            la = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") or os.path.expanduser("~")
            p = os.path.join(la, "NeXroll")
            try:
                os.makedirs(p, exist_ok=True)
            except Exception:
                pass
            return p
    except Exception:
        pass
    # Non-Windows or last resort
    try:
        p = os.path.join(os.getcwd(), "data")
        os.makedirs(p, exist_ok=True)
        return p
    except Exception:
        return os.getcwd()


def _secrets_file_path() -> str:
    """
    Path to DPAPI-encrypted secret store (JSON with base64 blobs).
    """
    return os.path.join(_program_data_root(), "secrets.json")


def _atomic_write(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass
    os.replace(tmp, path)


def _is_writable_dir(path: str) -> bool:
    try:
        os.makedirs(path, exist_ok=True)
        test = os.path.join(path, f".nx_writetest_{os.getpid()}.tmp")
        with open(test, "w", encoding="utf-8") as f:
            f.write("ok")
        try:
            os.remove(test)
        except Exception:
            pass
        return True
    except Exception:
        return False


# ----------------------------
# Provider 1: Windows Credential Manager (preferred on Windows)
# ----------------------------

_WIN_CRED_AVAILABLE = False
try:
    if sys.platform.startswith("win"):
        import win32cred  # type: ignore
        _WIN_CRED_AVAILABLE = True
except Exception:
    _WIN_CRED_AVAILABLE = False


def _cred_target(name: str) -> str:
    # Scope credentials under a common namespace
    return f"NeXroll/{name}"


def _cm_has(name: str) -> bool:
    if not _WIN_CRED_AVAILABLE:
        return False
    try:
        win32cred.CredRead(_cred_target(name), win32cred.CRED_TYPE_GENERIC, 0)
        return True
    except Exception:
        return False


def _cm_get(name: str) -> Optional[str]:
    if not _WIN_CRED_AVAILABLE:
        return None
    try:
        cred = win32cred.CredRead(_cred_target(name), win32cred.CRED_TYPE_GENERIC, 0)
        blob = cred.get("CredentialBlob", b"")
        try:
            return blob.decode("utf-8")
        except Exception:
            return None
    except Exception:
        return None


def _cm_set(name: str, value: str) -> bool:
    if not _WIN_CRED_AVAILABLE:
        return False
    try:
        blob = value.encode("utf-8")
        cred = {
            "Type": win32cred.CRED_TYPE_GENERIC,
            "TargetName": _cred_target(name),
            "UserName": "",  # not used
            "CredentialBlob": blob,
            "Comment": "NeXroll secret",
            "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        }
        win32cred.CredWrite(cred, 0)
        return True
    except Exception:
        return False


def _cm_delete(name: str) -> bool:
    if not _WIN_CRED_AVAILABLE:
        return False
    try:
        win32cred.CredDelete(_cred_target(name), win32cred.CRED_TYPE_GENERIC, 0)
        return True
    except Exception:
        return False


# ----------------------------
# Provider 2: DPAPI-encrypted file store (Windows fallback)
# ----------------------------

_DPAPI_AVAILABLE = False
if sys.platform.startswith("win"):
    try:
        import ctypes
        from ctypes import wintypes

        # DPAPI flags
        CRYPTPROTECT_UI_FORBIDDEN = 0x01
        CRYPTPROTECT_LOCAL_MACHINE = 0x04  # allow decryption under LocalSystem and other accounts on this machine

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD),
                        ("pbData", ctypes.POINTER(ctypes.c_byte))]

        _crypt32 = ctypes.windll.crypt32
        _kernel32 = ctypes.windll.kernel32

        def _dpapi_protect(plain: bytes) -> bytes:
            in_blob = DATA_BLOB()
            out_blob = DATA_BLOB()

            in_blob.cbData = len(plain)
            in_blob.pbData = ctypes.cast(ctypes.create_string_buffer(plain), ctypes.POINTER(ctypes.c_byte))

            # Use LocalMachine scope so services and different user contexts on the same machine can decrypt
            if not _crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE,
                ctypes.byref(out_blob)
            ):
                raise ctypes.WinError()

            try:
                data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                return data
            finally:
                _kernel32.LocalFree(out_blob.pbData)

        def _dpapi_unprotect(cipher: bytes) -> bytes:
            in_blob = DATA_BLOB()
            out_blob = DATA_BLOB()

            in_blob.cbData = len(cipher)
            in_blob.pbData = ctypes.cast(ctypes.create_string_buffer(cipher), ctypes.POINTER(ctypes.c_byte))

            if not _crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                0x01,  # CRYPTPROTECT_UI_FORBIDDEN
                ctypes.byref(out_blob)
            ):
                raise ctypes.WinError()

            try:
                data = ctypes.string_at(out_blob.pbData, out_blob.cbData)
                return data
            finally:
                _kernel32.LocalFree(out_blob.pbData)

        _DPAPI_AVAILABLE = True
    except Exception:
        _DPAPI_AVAILABLE = False


def _dpapi_file_has(name: str) -> bool:
    try:
        fp = _secrets_file_path()
        if not os.path.exists(fp):
            return False
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        return name in data
    except Exception:
        return False


def _dpapi_file_get(name: str) -> Optional[str]:
    if not _DPAPI_AVAILABLE:
        return None
    try:
        fp = _secrets_file_path()
        if not os.path.exists(fp):
            return None
        with open(fp, "r", encoding="utf-8") as f:
            data = json.load(f)
        b64 = data.get(name)
        if not b64:
            return None
        cipher = base64.b64decode(b64)
        plain = _dpapi_unprotect(cipher)
        try:
            return plain.decode("utf-8")
        except Exception:
            return None
    except Exception:
        return None


def _dpapi_file_set(name: str, value: str) -> bool:
    if not _DPAPI_AVAILABLE:
        return False
    try:
        root = _program_data_root()
        if not _is_writable_dir(root):
            return False

        fp = _secrets_file_path()
        store = {}
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    store = json.load(f)
            except Exception:
                store = {}

        cipher = _dpapi_protect(value.encode("utf-8"))
        store[name] = base64.b64encode(cipher).decode("ascii")

        _atomic_write(fp, json.dumps(store, indent=2).encode("utf-8"))
        return True
    except Exception:
        return False


def _dpapi_file_delete(name: str) -> bool:
    if not _DPAPI_AVAILABLE:
        return False
    try:
        fp = _secrets_file_path()
        if not os.path.exists(fp):
            return True
        with open(fp, "r", encoding="utf-8") as f:
            store = json.load(f)
        if name in store:
            del store[name]
            _atomic_write(fp, json.dumps(store, indent=2).encode("utf-8"))
        return True
    except Exception:
        return False


# ----------------------------
# Provider selection and facade
# ----------------------------

def _pick_provider() -> str:
    """
    Returns provider key:
      - "credman" on Windows with Credential Manager available
      - "dpapi_file" on Windows fallback
      - "none" otherwise
    """
    if sys.platform.startswith("win"):
        if _WIN_CRED_AVAILABLE:
            return "credman"
        if _DPAPI_AVAILABLE:
            return "dpapi_file"
    return "none"


def provider_info() -> Tuple[str, str]:
    """
    Report available secure providers. When multiple providers are available,
    we use both for maximum compatibility across user/service contexts.
    """
    available = []
    if sys.platform.startswith("win"):
        if _WIN_CRED_AVAILABLE:
            available.append("credman")
        if _DPAPI_AVAILABLE:
            available.append("dpapi_file")
    key = "/".join(available) if available else "none"
    labels = {
        "credman": "Windows Credential Manager",
        "dpapi_file": "Windows DPAPI-encrypted file",
    }
    if not available:
        human = "No secure provider available"
    elif len(available) == 1:
        human = labels[available[0]]
    else:
        human = " + ".join(labels[k] for k in available)
    return key, human


def has_secret(name: str) -> bool:
    # Check all available providers
    try:
        if _WIN_CRED_AVAILABLE and _cm_has(name):
            return True
    except Exception:
        pass
    try:
        if _DPAPI_AVAILABLE and _dpapi_file_has(name):
            return True
    except Exception:
        pass
    return False


def get_secret(name: str) -> Optional[str]:
    """
    Try all providers in order:
      1) Credential Manager
      2) DPAPI file (machine scope)
    """
    val = None
    try:
        if _WIN_CRED_AVAILABLE:
            val = _cm_get(name)
            if val:
                return val
    except Exception:
        pass
    try:
        if _DPAPI_AVAILABLE:
            val = _dpapi_file_get(name)
            if val:
                return val
    except Exception:
        pass
    return None


def set_secret(name: str, value: str) -> bool:
    """
    Write to all available providers to ensure both user and service contexts can read it.
    Returns True if at least one provider succeeded.
    """
    ok = False
    try:
        if _WIN_CRED_AVAILABLE:
            ok = _cm_set(name, value) or ok
    except Exception:
        pass
    try:
        if _DPAPI_AVAILABLE:
            ok = _dpapi_file_set(name, value) or ok
    except Exception:
        pass
    return ok


def delete_secret(name: str) -> bool:
    """
    Attempt deletion in all providers. Return True if deletion succeeded or item absent.
    """
    ok = False
    try:
        if _WIN_CRED_AVAILABLE:
            ok = _cm_delete(name) or ok
    except Exception:
        pass
    try:
        if _DPAPI_AVAILABLE:
            ok = _dpapi_file_delete(name) or ok
    except Exception:
        pass
    # If neither provider is available, treat as no-op success
    return ok or (not _WIN_CRED_AVAILABLE and not _DPAPI_AVAILABLE)


# ----------------------------
# Convenience for Plex token
# ----------------------------

_PLEX_TOKEN_KEY = "plex_token"


def has_plex_token() -> bool:
    return has_secret(_PLEX_TOKEN_KEY)


def get_plex_token() -> Optional[str]:
    return get_secret(_PLEX_TOKEN_KEY)


def set_plex_token(token: str) -> bool:
    return set_secret(_PLEX_TOKEN_KEY, token)


def delete_plex_token() -> bool:
    return delete_secret(_PLEX_TOKEN_KEY)