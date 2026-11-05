"""Jellyfin/Emby plugins asking for prerolls without an API key.

The key is optional in both plugins, so /plugin/intros answers without one,
even with login on (flagged in a November 2026 security review). Refusing
would quietly stop prerolls on servers whose plugin was set up by hand, so
NeXroll first names those plugins on the Connect page and the health tile
while login is on. These tests cover the tracker, the health check and the
endpoint wiring (main.py functions lifted onto a bare app, main not imported).
"""

import ast
import types
from pathlib import Path
from typing import Optional

import pytest
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.testclient import TestClient

from backend import health_summary, keyless_plugins

DAY = 86400


@pytest.fixture(autouse=True)
def fresh():
    keyless_plugins.reset()
    yield
    keyless_plugins.reset()


# ---------------------------------------------------------------------------
# The tracker
# ---------------------------------------------------------------------------

def test_a_keyless_request_is_listed_once_per_server():
    first = keyless_plugins.note("Jellyfin", "MEDIA-PC", "1.14.2.0", "192.168.1.20", now=1000)
    again = keyless_plugins.note("Jellyfin", "MEDIA-PC", "1.14.2.0", "192.168.1.20", now=1060)
    assert first["server_name"] == "MEDIA-PC" and again is None
    rows = keyless_plugins.current(now=1100)
    assert len(rows) == 1
    row = rows[0]
    assert row["server_type"] == "Jellyfin" and row["plugin_version"] == "1.14.2.0"
    assert row["address"] == "192.168.1.20" and row["requests"] == 2
    assert row["last_seen"].endswith("Z")


def test_rows_are_per_server_type_and_newest_first():
    keyless_plugins.note("jellyfin", "A", "", "10.0.0.1", now=1000)
    keyless_plugins.note("EMBY", "B", "", "10.0.0.2", now=2000)
    assert [r["server_name"] for r in keyless_plugins.current(now=2100)] == ["B", "A"]
    assert [r["server_name"] for r in keyless_plugins.current("Jellyfin", now=2100)] == ["A"]
    assert [r["server_type"] for r in keyless_plugins.current("emby", now=2100)] == ["Emby"]
    assert keyless_plugins.seen("jellyfin", now=2100) and not keyless_plugins.seen("Plex", now=2100)


def test_connecting_with_a_key_takes_the_server_off_the_list():
    keyless_plugins.note("Jellyfin", "MEDIA-PC", "", "192.168.1.20", now=1000)
    keyless_plugins.note("Jellyfin", "OTHER", "", "192.168.1.30", now=1000)
    keyless_plugins.forget("Jellyfin", "media-pc", "192.168.1.20")
    assert [r["server_name"] for r in keyless_plugins.current(now=1100)] == ["OTHER"]


def test_a_plugin_that_sent_no_name_is_told_apart_by_address():
    keyless_plugins.note("Emby", "", "", "192.168.1.40", now=1000)
    keyless_plugins.note("Emby", "", "", "192.168.1.41", now=1000)
    assert len(keyless_plugins.current(now=1100)) == 2
    # Its keyed request names the machine; same address, so it goes.
    keyless_plugins.forget("Emby", "NAS", "192.168.1.40")
    assert [r["address"] for r in keyless_plugins.current(now=1100)] == ["192.168.1.41"]


def test_a_week_without_a_keyless_request_drops_it_and_it_counts_as_new_again():
    keyless_plugins.note("Jellyfin", "MEDIA-PC", "", "", now=1000)
    assert keyless_plugins.current(now=1000 + 7 * DAY - 1)
    assert keyless_plugins.current(now=1000 + 7 * DAY + 1) == []
    keyless_plugins.note("Jellyfin", "MEDIA-PC", "", "", now=1000)
    assert keyless_plugins.note("Jellyfin", "MEDIA-PC", "", "", now=1000 + 8 * DAY) is not None


def test_saving_a_key_into_the_plugin_clears_that_server_type():
    keyless_plugins.note("Jellyfin", "A", "", "", now=1000)
    keyless_plugins.note("Emby", "B", "", "", now=1000)
    keyless_plugins.forget_type("jellyfin")
    assert [r["server_type"] for r in keyless_plugins.current(now=1100)] == ["Emby"]


def test_odd_header_values_are_trimmed():
    keyless_plugins.note(None, "x" * 500, "v" * 100, None, now=1000)
    row = keyless_plugins.current(now=1000)[0]
    assert row["server_type"] == "unknown"
    assert len(row["server_name"]) == 120 and len(row["plugin_version"]) == 40
    assert keyless_plugins.describe(row).startswith("The unknown plugin on xxx")
    assert keyless_plugins.describe({"server_type": "Emby"}) == "The Emby plugin"


# ---------------------------------------------------------------------------
# The health tile
# ---------------------------------------------------------------------------

def _row(name="MEDIA-PC", kind="Jellyfin", address="192.168.1.20"):
    return {"server_type": kind, "server_name": name, "address": address}


def test_the_health_check_only_appears_with_login_on_and_a_keyless_plugin():
    assert health_summary.plugin_keys_check(False, [_row()]) is None
    assert health_summary.plugin_keys_check(True, []) is None
    check = health_summary.plugin_keys_check(True, [_row()])
    assert check["key"] == "plugin_keys" and check["status"] == health_summary.WARN
    assert check["detail"] == ("The Jellyfin plugin on MEDIA-PC connects without an API key; "
                               "give it one on the Connect page")
    assert check["value"] == "1 without a key"


def test_several_keyless_plugins_are_counted_and_cost_little():
    check = health_summary.plugin_keys_check(True, [_row(), _row("NAS", "Emby")])
    assert check["detail"].startswith("2 plugins connect without an API key")
    summary = health_summary.build_summary([check])
    assert summary["status"] == "attention" and summary["score"] == 95


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

def load_main_functions(names, env):
    tree = ast.parse((Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<main-functions>", "exec"), env)
    return env


class FakeDb:
    def __init__(self, setting):
        self.setting = setting

    def query(self, _model):
        return self

    def first(self):
        return self.setting


class Key:
    id = 7
    name = "Jellyfin Plugin (Auto)"


def plugin_app(login_on=True):
    app = FastAPI()
    db = FakeDb(types.SimpleNamespace(auth_enabled=login_on))
    logs = []
    clients = {}

    def get_db():
        yield db

    env = dict(
        app=app, Request=Request, Depends=Depends, Query=Query, Optional=Optional,
        HTTPException=HTTPException, Session=object, get_db=get_db,
        models=types.SimpleNamespace(Setting=object), keyless_plugins=keyless_plugins,
        validate_api_key=lambda value, perm, db: Key() if value == "good" else None,
        PLUGIN_CLIENTS=clients, utcnow=lambda: types.SimpleNamespace(isoformat=lambda: "2026-11-05T00:00:00"),
        self_update=types.SimpleNamespace(note_playback=lambda: None),
        _resolve_current_intros=lambda db, **kw: {"paths": ["/p/a.mp4"], "mode": "shuffle"},
        _plugin_play_list=lambda setting, paths, mode, rotation: paths,
        _build_stream_url=lambda base, path: f"{base}/plugin/stream?x",
        _file_version=lambda path: "1-1",
        log_event=lambda level, cat, msg, **kw: logs.append((level, msg)),
        os=__import__("os"),
    )
    load_main_functions({"plugin_get_intros"}, env)
    return TestClient(app), logs, clients


HEADERS = {"X-Plugin-Server-Type": "Jellyfin", "X-Plugin-Server-Name": "MEDIA-PC",
           "X-Plugin-Server-Version": "1.14.2.0"}


def test_a_keyless_plugin_still_gets_its_prerolls_and_is_logged_once():
    client, logs, _ = plugin_app(login_on=True)
    for _ in range(3):
        assert client.get("/plugin/intros", headers=HEADERS).json()["TotalRecordCount"] == 1
    rows = keyless_plugins.current()
    assert len(rows) == 1 and rows[0]["requests"] == 3 and rows[0]["server_name"] == "MEDIA-PC"
    warnings = [m for level, m in logs if level == "WARNING"]
    assert warnings == ["The Jellyfin plugin on MEDIA-PC asks for prerolls without an API key "
                        "while login is on. Give it a key on the Connect page."]


def test_with_login_off_it_is_listed_but_not_logged():
    client, logs, _ = plugin_app(login_on=False)
    client.get("/plugin/intros", headers=HEADERS)
    assert keyless_plugins.current() and not [m for level, m in logs if level == "WARNING"]


def test_the_same_plugin_with_a_key_comes_off_the_list():
    client, _, clients = plugin_app()
    client.get("/plugin/intros", headers=HEADERS)
    assert client.get("/plugin/intros", headers={**HEADERS, "X-Api-Key": "good"}).status_code == 200
    assert keyless_plugins.current() == []
    assert clients["Jellyfin Plugin (Auto)"]["server_name"] == "MEDIA-PC"


def test_a_wrong_key_is_still_refused_and_changes_nothing():
    client, _, _ = plugin_app()
    client.get("/plugin/intros", headers=HEADERS)
    assert client.get("/plugin/intros", headers={**HEADERS, "X-Api-Key": "bad"}).status_code == 401
    assert len(keyless_plugins.current()) == 1


def test_the_status_endpoints_report_keyless_plugins_of_their_type():
    app = FastAPI()

    def get_db():
        yield None

    env = dict(app=app, Depends=Depends, Session=object, get_db=get_db, keyless_plugins=keyless_plugins,
               _jellyfin_connection_status=lambda db: {"connected": False},
               _emby_connection_status=lambda db: {"connected": True, "connection_type": "direct"})
    load_main_functions({"get_jellyfin_status", "get_emby_status"}, env)
    keyless_plugins.note("Jellyfin", "MEDIA-PC", "", "")
    client = TestClient(app)
    jellyfin = client.get("/jellyfin/status").json()
    emby = client.get("/emby/status").json()
    assert jellyfin["connected"] is False and jellyfin["keyless_plugins"][0]["server_name"] == "MEDIA-PC"
    assert emby["connection_type"] == "direct" and emby["keyless_plugins"] == []


def test_a_working_keyless_plugin_counts_as_checked_in():
    # The plugin URL repair leaves a plugin that has checked in alone.
    env = load_main_functions({"_plugin_has_checked_in"},
                              dict(PLUGIN_CLIENTS={}, keyless_plugins=keyless_plugins))
    checked_in = env["_plugin_has_checked_in"]
    assert checked_in("jellyfin") is False
    keyless_plugins.note("Jellyfin", "MEDIA-PC", "", "")
    assert checked_in("jellyfin") is True and checked_in("emby") is False
