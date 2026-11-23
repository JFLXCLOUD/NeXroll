"""TMDB without a key of the user's own.

NeXroll shipped a shared TMDB key, and TMDB revoked it (401 since at least
October 2026). Installs without their own key still called TMDB with it on
every sync, logged "TMDB API key invalid or expired" and found fewer trailers.
Now TMDB is skipped without a key, a trailer language that needs TMDB says a
key is missing (not that it was rejected), and Test key sends nothing.
"""
import ast
import asyncio
import logging
import types
from pathlib import Path
from typing import Optional
from unittest.mock import patch

import httpx
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from backend import nexup_potoken, radarr_connector, sonarr_connector
from backend.radarr_connector import TMDBTrailerFetcher, TrailerDownloader
from backend.sonarr_connector import TVTrailerFetcher

BACKEND = Path(__file__).resolve().parents[1] / "backend"
RADARR_URL = "https://www.youtube.com/watch?v=radarrEN01"


class Response:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)


class Net:
    """Stands in for httpx.AsyncClient: TMDB answers `tmdb_status`, anything
    else (the Apple Trailers lookup) is offline. Records every request."""

    calls = []
    tmdb_status = 200

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, **kwargs):
        Net.calls.append((url, dict(params or {})))
        if "themoviedb.org" in url:
            return Response(Net.tmdb_status, {"results": []})
        raise httpx.ConnectError("offline")


@pytest.fixture(autouse=True)
def network():
    Net.calls = []
    Net.tmdb_status = 200
    with patch("httpx.AsyncClient", Net):
        yield


def tmdb_calls():
    return [url for url, _ in Net.calls if "themoviedb.org" in url]


def test_no_key_is_built_in_any_more():
    assert not hasattr(radarr_connector, "TMDB_API_KEY")
    assert not hasattr(sonarr_connector, "TMDB_API_KEY")


@pytest.mark.parametrize("key", [None, "", "   "])
def test_movie_lookups_skip_tmdb_without_a_key(key, caplog):
    fetcher = TMDBTrailerFetcher(tmdb_api_key=key)
    assert fetcher.api_key is None and fetcher.tmdb_available is False
    with caplog.at_level(logging.WARNING, logger="backend.radarr_connector"):
        assert asyncio.run(fetcher.get_trailer_sources(603, title="The Matrix")) == []
    assert tmdb_calls() == []
    assert "TMDB" not in caplog.text


def test_the_users_key_is_trimmed_and_used():
    fetcher = TMDBTrailerFetcher(tmdb_api_key="  mine  ")
    assert fetcher.api_key == "mine" and fetcher.tmdb_available is True
    asyncio.run(fetcher.get_trailer_sources(603))
    (url, params), = [(u, p) for u, p in Net.calls if "themoviedb.org" in u]
    assert url.endswith("/movie/603/videos") and params["api_key"] == "mine"


def test_tv_lookups_skip_tmdb_without_a_key():
    fetcher = TVTrailerFetcher()
    assert fetcher.api_key is None and fetcher.tmdb_available is False
    assert asyncio.run(fetcher.get_tv_trailers(tvdb_id=81189)) == []
    assert asyncio.run(fetcher.search_tv_by_tvdb(81189)) is None
    assert tmdb_calls() == []
    assert TVTrailerFetcher(tmdb_api_key=" tv-key ").api_key == "tv-key"


class FakeProvider:
    def ensure_running(self):
        return {"usable": True}

    def status(self):
        return {"usable": True}


def download_in_german(tmp_path, key):
    async def fake_download(*args, **kwargs):
        pytest.fail("nothing should be downloaded")

    with patch.object(TrailerDownloader, "_download_with_ytdlp", fake_download), \
            patch.object(TrailerDownloader, "get_cookie_browser", return_value=None), \
            patch.object(nexup_potoken, "get_manager", return_value=FakeProvider()):
        downloader = TrailerDownloader(str(tmp_path), "1080", tmdb_api_key=key,
                                       language="de-DE", language_fallback="skip")
        return asyncio.run(downloader.download_trailer(RADARR_URL, "Movie", 603))


def test_a_language_without_a_key_says_a_key_is_needed(tmp_path):
    result = download_in_german(tmp_path, None)
    assert result["error"] == "TMDB_KEY_MISSING"
    assert "German" in result["message"] and "needs an API key" in result["message"]
    assert tmdb_calls() == []


def test_a_rejected_key_is_still_reported_as_rejected(tmp_path):
    Net.tmdb_status = 401
    result = download_in_german(tmp_path, "expired")
    assert result["error"] == "TMDB_KEY_REJECTED"
    assert "rejected the API key" in result["message"]
    assert len(tmdb_calls()) == 1


# -- /nexup/tmdb/test-key --------------------------------------------------

def key_client(saved):
    app = FastAPI()
    setting = types.SimpleNamespace(nexup_tmdb_api_key=saved)

    class Db:
        def query(self, _model):
            return self

        def first(self):
            return setting

    def get_db():
        yield Db()

    tree = ast.parse((BACKEND / "main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "test_tmdb_key"]
    assert len(nodes) == 1
    env = dict(app=app, Depends=Depends, Optional=Optional, Session=object, get_db=get_db,
               models=types.SimpleNamespace(Setting=object))
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<main-functions>", "exec"), env)
    return TestClient(app)


@pytest.mark.parametrize("saved", [None, "  "])
def test_test_key_without_any_key_sends_nothing(saved):
    body = key_client(saved).get("/nexup/tmdb/test-key").json()
    assert body == {"valid": False, "using_custom_key": False,
                    "message": "No TMDB API key is set, so NeX-Up skips TMDB's trailer lists."}
    assert tmdb_calls() == []


def test_test_key_checks_the_saved_key():
    body = key_client(" saved ").get("/nexup/tmdb/test-key").json()
    assert body["valid"] is True and body["using_custom_key"] is True
    (url, params), = [(u, p) for u, p in Net.calls if "themoviedb.org" in u]
    assert url.endswith("/authentication") and params["api_key"] == "saved"


def test_test_key_reports_a_rejected_key():
    Net.tmdb_status = 401
    body = key_client(None).get("/nexup/tmdb/test-key", params={"api_key": "typed"}).json()
    assert body["valid"] is False and body["using_custom_key"] is True
    assert Net.calls[0][1]["api_key"] == "typed"
