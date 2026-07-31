from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .constants import REDIRECT_URI
from .errors import CredentialError


_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class Credentials:
    client_id: str
    client_secret: str
    refresh_token: str
    user_agent: str
    redirect_uri: str = REDIRECT_URI

    def require_client(self) -> None:
        missing = [
            name
            for name, value in (
                ("REDDIT_CLIENT_ID", self.client_id),
                ("REDDIT_CLIENT_SECRET", self.client_secret),
                ("REDDIT_USER_AGENT", self.user_agent),
            )
            if not value
        ]
        if missing:
            raise CredentialError(
                "Missing OAuth configuration: " + ", ".join(missing) + "."
            )
        _validate_user_agent(self.user_agent)
        if self.redirect_uri != REDIRECT_URI:
            raise CredentialError(
                f"REDDIT_REDIRECT_URI must be exactly {REDIRECT_URI!r}."
            )

    def require_authorized(self) -> None:
        self.require_client()
        if not self.refresh_token:
            raise CredentialError(
                "REDDIT_REFRESH_TOKEN is missing. Run `python manage.py authorize` first."
            )


def _strip_env_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _fallback_dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if _ENV_KEY_RE.fullmatch(key):
            values[key] = _strip_env_value(value)
    return values


def read_environment(path: Path, environ: Mapping[str, str] | None = None) -> Credentials:
    path = Path(path)
    try:
        from dotenv import dotenv_values

        file_values = {
            key: "" if value is None else str(value)
            for key, value in dotenv_values(path).items()
        }
    except ImportError:
        file_values = _fallback_dotenv_values(path)

    source = dict(file_values)
    source.update(dict(os.environ if environ is None else environ))
    return Credentials(
        client_id=source.get("REDDIT_CLIENT_ID", "").strip(),
        client_secret=source.get("REDDIT_CLIENT_SECRET", "").strip(),
        refresh_token=source.get("REDDIT_REFRESH_TOKEN", "").strip(),
        user_agent=source.get("REDDIT_USER_AGENT", "").strip(),
        redirect_uri=source.get("REDDIT_REDIRECT_URI", REDIRECT_URI).strip()
        or REDIRECT_URI,
    )


def _validate_user_agent(user_agent: str) -> None:
    lowered = user_agent.casefold()
    placeholders = ("your_username", "your-user", "change-me", "example")
    if any(value in lowered for value in placeholders):
        raise CredentialError("REDDIT_USER_AGENT still contains a placeholder.")
    if "/u/" not in lowered or ":" not in user_agent:
        raise CredentialError(
            "REDDIT_USER_AGENT must be descriptive, versioned, and include `(by /u/name)`."
        )


def write_env_secret(path: Path, key: str, value: str) -> None:
    """Atomically add or replace one secret without logging it."""
    path = Path(path)
    if not _ENV_KEY_RE.fullmatch(key):
        raise CredentialError("Invalid environment variable name.")
    if not value or "\n" in value or "\r" in value:
        raise CredentialError(f"Refusing to write an invalid {key} value.")

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = f"{key}={value}"
    output: list[str] = []
    replaced = False
    for line in lines:
        candidate = line.split("=", 1)[0].strip() if "=" in line else ""
        if candidate == key:
            if not replaced:
                output.append(replacement)
                replaced = True
            continue
        output.append(line)
    if not replaced:
        if output and output[-1]:
            output.append("")
        output.append(replacement)

    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
        newline="\n",
    )
    temporary_path = Path(handle.name)
    try:
        with handle:
            handle.write("\n".join(output) + "\n")
        try:
            os.chmod(temporary_path, 0o600)
        except OSError:
            pass
        os.replace(temporary_path, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
