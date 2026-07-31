from __future__ import annotations

import hmac
import secrets
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlsplit

from .constants import CALLBACK_HOST, CALLBACK_PORT, OAUTH_SCOPES
from .environment import Credentials, read_environment, write_env_secret
from .errors import AuthorizationError, DependencyError


@dataclass(frozen=True)
class AuthorizationResult:
    username: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class CallbackResult:
    code: str
    state: str
    error: str


class _CallbackServer(HTTPServer):
    callback: CallbackResult | None = None


class _CallbackHandler(BaseHTTPRequestHandler):
    server: _CallbackServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
        self.server.callback = CallbackResult(
            code=query.get("code", [""])[0],
            state=query.get("state", [""])[0],
            error=query.get("error", [""])[0],
        )
        if self.server.callback.error:
            status = 400
            message = "Reddit authorization was declined. You can close this tab."
        else:
            status = 200
            message = "NeXroll authorization received. You can close this tab."
        body = (
            "<!doctype html><html><head><meta charset='utf-8'>"
            "<title>NeXroll authorization</title></head>"
            f"<body><p>{message}</p></body></html>"
        ).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, _format: str, *_args: object) -> None:
        return


def validate_callback(callback: CallbackResult | None, expected_state: str) -> str:
    if callback is None:
        raise AuthorizationError("Timed out waiting for Reddit authorization.")
    if callback.error:
        raise AuthorizationError("Reddit authorization was declined.")
    if not callback.state or not hmac.compare_digest(callback.state, expected_state):
        raise AuthorizationError("OAuth state mismatch; no credentials were stored.")
    if not callback.code:
        raise AuthorizationError("Reddit did not return an authorization code.")
    return callback.code


def _load_praw():
    try:
        import praw
    except ImportError as exc:
        raise DependencyError(
            "PRAW is not installed. Run `python -m pip install -r requirements.txt` "
            "from community/reddit."
        ) from exc
    return praw


def authorize(
    env_path: Path,
    *,
    open_browser: bool = True,
    timeout_seconds: int = 300,
    announce_url: Callable[[str], None] = print,
) -> AuthorizationResult:
    credentials: Credentials = read_environment(env_path)
    credentials.require_client()
    praw = _load_praw()
    reddit = praw.Reddit(
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
        redirect_uri=credentials.redirect_uri,
        user_agent=credentials.user_agent,
        check_for_async=False,
    )

    try:
        server = _CallbackServer((CALLBACK_HOST, CALLBACK_PORT), _CallbackHandler)
    except OSError as exc:
        raise AuthorizationError(
            f"Could not listen on localhost:{CALLBACK_PORT}; stop the process using that port."
        ) from exc
    with server:
        state = secrets.token_urlsafe(32)
        authorization_url = reddit.auth.url(
            scopes=list(OAUTH_SCOPES), state=state, duration="permanent"
        )
        announce_url(
            "Authorize the NeXroll community manager in your browser:\n"
            f"{authorization_url}"
        )
        if open_browser:
            webbrowser.open(authorization_url, new=2)
        server.timeout = max(1, timeout_seconds)
        server.handle_request()
        code = validate_callback(server.callback, state)

    refresh_token = reddit.auth.authorize(code)
    if not refresh_token:
        raise AuthorizationError(
            "Reddit did not return a refresh token. Revoke the grant and authorize again."
        )
    granted = set(reddit.auth.scopes())
    missing = set(OAUTH_SCOPES) - granted
    if missing:
        raise AuthorizationError(
            "Reddit did not grant every required scope: " + ", ".join(sorted(missing))
        )
    username = str(reddit.user.me() or "")
    if not username:
        raise AuthorizationError("Authorized Reddit identity could not be verified.")

    write_env_secret(Path(env_path), "REDDIT_REFRESH_TOKEN", refresh_token)
    return AuthorizationResult(username=username, scopes=tuple(sorted(granted)))
