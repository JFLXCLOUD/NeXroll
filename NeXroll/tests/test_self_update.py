"""Install update from the web UI (Windows installer builds).

User request: a Windows user whose NeXroll machine is rarely touched wanted to
update from the web UI. NeXroll can't replace its own files, so it backs up the
database, leaves a request (version + port) and starts the "NeXroll Updater"
scheduled task, which runs Releases/NeXrollUpdater.ps1 as SYSTEM. These tests
cover NeXroll's side: when the button is offered, the request it leaves, the
backup, how it reads the script's status, and the endpoint's refusals. The
script itself is checked against a fake GitHub (see the handoff).
"""

import ast
import datetime
import json
import os
import types
from pathlib import Path
from typing import Optional

import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from backend import self_update

UTC = datetime.timezone.utc


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a, b, want", [
    ("2.3.1", "2.3.0", 1),
    ("2.3.0", "2.3.0", 0),
    ("v2.3.0", "2.3.0", 0),
    ("2.10.0", "2.9.9", 1),
    ("2.3.0", "2.3.0-beta.4", 1),
    ("2.3.0-rc.1", "2.3.0-beta.9", 1),
    ("2.3.0-beta.10", "2.3.0-beta.9", 1),
    ("2.2.9", "2.3.0", -1),
])
def test_versions_compare_like_the_update_check(a, b, want):
    assert self_update.compare_versions(a, b) == want


@pytest.mark.parametrize("value, ok", [
    ("2.3.1", True), ("2.3.0-beta.11", True), ("2.3.0-rc1", True),
    ("2.3", False), ("2.3.1; rm", False), ("../2.3.1", False), ("", False),
])
def test_only_plain_version_numbers_are_accepted(value, ok):
    assert bool(self_update.VERSION_RE.match(value)) is ok


# ---------------------------------------------------------------------------
# When Install update is offered
# ---------------------------------------------------------------------------

def test_docker_and_source_installs_are_not_offered_the_button(tmp_path):
    assert self_update.support(in_docker=True)["reason"] == "docker"
    # Tests don't run the installed NeXroll.exe, so there's no install folder.
    assert self_update.support()["reason"] == "not_installer"


def test_an_install_from_before_the_updater_is_told_to_update_by_hand_once(tmp_path):
    info = self_update.support(folder=str(tmp_path), has_task=lambda: True)
    assert info == {"supported": False, "reason": "updater_missing", "message": info["message"]}
    assert "by hand once" in info["message"]
    (tmp_path / "NeXrollUpdater.ps1").write_text("# script")
    assert self_update.support(folder=str(tmp_path), has_task=lambda: False)["reason"] == "updater_missing"
    assert self_update.support(folder=str(tmp_path), has_task=lambda: True)["supported"] is True


# ---------------------------------------------------------------------------
# Reading the script's status
# ---------------------------------------------------------------------------

def write_status(folder, data, bom=True):
    path = folder / "update" / "status.json"
    path.parent.mkdir(exist_ok=True)
    text = data if isinstance(data, str) else json.dumps(data)
    path.write_bytes(("﻿" if bom else "").encode("utf-8") + text.encode("utf-8"))


def ps_time(when):
    # What PowerShell's ToString('o') writes: seven fractional digits.
    return when.strftime("%Y-%m-%dT%H:%M:%S.%f") + "3Z"


def test_status_is_read_as_powershell_writes_it(tmp_path):
    now = datetime.datetime.now(UTC)
    write_status(tmp_path, {"state": "downloading", "message": "Downloading NeXroll 2.3.1",
                            "request_id": "abc123ef", "from_version": "2.3.0", "to_version": "2.3.1",
                            "started_at": ps_time(now), "updated_at": ps_time(now), "extra": "dropped"})
    status = self_update.read_status(str(tmp_path), now=now)
    assert status["state"] == "downloading" and status["to_version"] == "2.3.1"
    assert "extra" not in status
    assert self_update.update_running(str(tmp_path)) is True


def test_no_status_or_a_damaged_one_reads_as_none(tmp_path):
    assert self_update.read_status(str(tmp_path)) is None
    write_status(tmp_path, "{not json")
    assert self_update.read_status(str(tmp_path)) is None
    write_status(tmp_path, {"state": "rm -rf"})
    assert self_update.read_status(str(tmp_path)) is None
    write_status(tmp_path, {"state": "done", "message": "x" * (70 * 1024)})
    assert self_update.read_status(str(tmp_path)) is None


def test_an_updater_that_died_mid_update_reads_as_failed(tmp_path):
    then = datetime.datetime.now(UTC) - datetime.timedelta(hours=2)
    write_status(tmp_path, {"state": "installing", "updated_at": ps_time(then)})
    status = self_update.read_status(str(tmp_path))
    assert status["state"] == "failed" and "update.log" in status["message"]
    assert self_update.update_running(str(tmp_path)) is False


# ---------------------------------------------------------------------------
# Starting an update
# ---------------------------------------------------------------------------

def test_the_database_is_backed_up_first_and_only_the_newest_three_are_kept(tmp_path):
    db = tmp_path / "nexroll.db"
    db.write_bytes(b"live")
    made = []

    def snapshot(path):
        copy = tmp_path / f"snap{len(made)}.tmp"
        copy.write_bytes(Path(path).read_bytes())
        made.append(copy)
        return str(copy)

    backups = []
    for i in range(5):
        target = self_update.backup_database(str(db), f"2.3.{i + 1}", snapshot)
        os.utime(target, (1000 + i, 1000 + i))
        backups.append(Path(target))
    folder = tmp_path / "update-backups"
    assert sorted(p.name for p in folder.iterdir()) == sorted(p.name for p in backups[2:])
    assert backups[-1].read_bytes() == b"live" and backups[-1].name.startswith("nexroll-before-2.3.5-")
    assert not any(p.exists() for p in made)


def test_no_update_starts_without_a_backup(tmp_path):
    with pytest.raises(self_update.UpdateError, match="back up the database"):
        self_update.backup_database(str(tmp_path / "nexroll.db"), "2.3.1", lambda p: None)


def test_the_request_names_version_and_port_and_the_task_is_started(tmp_path):
    calls = []

    def run(args):
        calls.append(args)
        return types.SimpleNamespace(returncode=0, stdout="SUCCESS", stderr="")

    path = tmp_path / "NeXroll" / "update-request.json"
    request_id = self_update.start_update("2.3.1", 9494, path=str(path), run=run)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["version"] == "2.3.1" and data["port"] == 9494 and data["request_id"] == request_id
    assert calls == [["schtasks", "/Run", "/TN", "NeXroll Updater"]]


def test_a_task_windows_refuses_to_start_is_reported(tmp_path):
    def refused(args):
        return types.SimpleNamespace(returncode=1, stdout="", stderr="ERROR: Access is denied.")

    with pytest.raises(self_update.UpdateError, match="Access is denied"):
        self_update.start_update("2.3.1", 9393, path=str(tmp_path / "r.json"), run=refused)


# ---------------------------------------------------------------------------
# The endpoints
# ---------------------------------------------------------------------------

ROUTES = {"update_install_info", "update_install", "_start_self_update"}


def load_main_functions(names, env):
    """The named main.py functions, run in ``env``, without importing main."""
    tree = ast.parse((Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<main-functions>", "exec"), env)
    return env


def route_client(env_overrides, routes=ROUTES, setting=None):
    """The named main.py functions on a bare app."""
    app = FastAPI()
    app.version = "2.3.0"
    db = FakeDb(setting)

    def get_db():
        yield db

    env = dict(app=app, self_update=self_update, Request=Request, Depends=Depends,
               HTTPException=HTTPException, Session=object, get_db=get_db, os=os,
               models=types.SimpleNamespace(Setting=object),
               get_current_user_optional=lambda request, db: None,
               _check_auth_enabled=lambda db: False, _is_local_request=lambda request: False,
               _is_running_in_docker=lambda: False, DB_PATH="unused.db",
               _snapshot_sqlite=lambda path: None, _file_log=lambda *a, **k: None,
               log_event=lambda *a, **k: None)
    env.update(env_overrides)
    load_main_functions(routes, env)
    return TestClient(app)


class FakeDb:
    """db.query(models.Setting).first() and commit(), for one settings row."""

    def __init__(self, setting):
        self.setting = setting
        self.commits = 0

    def query(self, model):
        return self

    def first(self):
        return self.setting

    def commit(self):
        self.commits += 1

    def close(self):
        pass


@pytest.fixture
def supported(monkeypatch):
    started = []
    monkeypatch.setattr(self_update, "support", lambda in_docker=False: {"supported": True, "reason": None, "message": None})
    monkeypatch.setattr(self_update, "read_status", lambda: None)
    monkeypatch.setattr(self_update, "update_running", lambda: False)
    monkeypatch.setattr(self_update, "backup_database", lambda db, version, snap: f"before-{version}.db")
    monkeypatch.setattr(self_update, "start_update", lambda version, port: started.append((version, port)) or "rid")
    return started


def test_install_starts_the_update_for_a_newer_version(supported):
    client = route_client({})
    reply = client.post("/update/install", json={"version": "v2.3.1"})
    assert reply.status_code == 200
    assert reply.json() == {"started": True, "request_id": "rid", "version": "2.3.1", "backup": "before-2.3.1.db"}
    assert supported == [("2.3.1", 9393)]
    info = client.get("/update/install").json()
    assert info["supported"] is True and info["current_version"] == "2.3.0"


@pytest.mark.parametrize("body, code", [
    ({}, 400), ({"version": "2.3"}, 400), ({"version": "2.3.0"}, 400), ({"version": "2.2.9"}, 400),
])
def test_install_refuses_anything_but_a_newer_version(supported, body, code):
    assert route_client({}).post("/update/install", json=body).status_code == code
    assert supported == []


def test_install_refuses_while_an_update_runs_or_where_it_cannot_work(supported, monkeypatch):
    monkeypatch.setattr(self_update, "update_running", lambda: True)
    reply = route_client({}).post("/update/install", json={"version": "2.3.1"})
    assert reply.status_code == 409 and "already running" in reply.json()["detail"]
    monkeypatch.setattr(self_update, "support", lambda in_docker=False: {"supported": False, "reason": "docker", "message": "Docker"})
    assert route_client({}).post("/update/install", json={"version": "2.3.1"}).status_code == 409
    assert supported == []


def test_with_login_on_only_an_admin_or_this_machine_may_install(supported):
    viewer = types.SimpleNamespace(role="viewer", username="v")
    admin = types.SimpleNamespace(role="admin", username="a")
    login_on = {"_check_auth_enabled": lambda db: True}
    as_viewer = route_client({**login_on, "get_current_user_optional": lambda r, db: viewer})
    assert as_viewer.post("/update/install", json={"version": "2.3.1"}).status_code == 403
    as_admin = route_client({**login_on, "get_current_user_optional": lambda r, db: admin})
    assert as_admin.post("/update/install", json={"version": "2.3.1"}).status_code == 200
    local = route_client({**login_on, "_is_local_request": lambda r: True})
    assert local.post("/update/install", json={"version": "2.3.1"}).status_code == 200
    assert len(supported) == 2


# ---------------------------------------------------------------------------
# Automatic updates
# ---------------------------------------------------------------------------

NOW = datetime.datetime(2026, 11, 10, 9, 30, tzinfo=UTC)


def release(version="2.3.1", days_old=5, **extra):
    published = (NOW - datetime.timedelta(days=days_old)).strftime("%Y-%m-%dT%H:%M:%SZ")
    data = {"tag_name": f"v{version}", "draft": False, "prerelease": False, "published_at": published,
            "assets": [{"name": "NeXroll.Jellyfin-1.14.2.0.zip"}, {"name": f"NeXroll_Installer_v{version}.exe"}]}
    data.update(extra)
    return data


def test_auto_settings_are_kept_in_range():
    assert [self_update.auto_hour(v) for v in (0, 23, "7", 24, -1, None, "x")] == [0, 23, 7, 4, 4, 4, 4]
    assert [self_update.auto_delay_days(v) for v in (0, 3, "7", 99, -2, None)] == [0, 3, 7, 30, 0, 3]


@pytest.mark.parametrize("data, current, delay, last, want, why", [
    (release(), "2.3.0", 3, None, "2.3.1", "due"),
    (release(days_old=1), "2.3.0", 3, None, None, "waits until 2026-11-12"),
    (release(days_old=0), "2.3.0", 0, None, "2.3.1", "due"),
    (release(), "2.3.1", 3, None, None, "is the latest"),
    (release(), "2.4.0", 3, None, None, "is the latest"),
    (release(prerelease=True), "2.3.0", 3, None, None, "no stable release"),
    (release(draft=True), "2.3.0", 3, None, None, "no stable release"),
    (release(assets=[{"name": "NeXroll.Jellyfin-1.14.2.0.zip"}]), "2.3.0", 3, None, None, "no Windows installer"),
    (release(published_at=None), "2.3.0", 3, None, None, "no publish date"),
    (release(), "2.3.0", 3, "2.3.1|2026-11-10T04:05:00+00:00", None, "trying again tomorrow"),
    (release(), "2.3.0", 3, "2.3.1|2026-11-09T04:05:00+00:00", "2.3.1", "due"),
    (release(), "2.3.0", 3, "2.3.0|2026-11-10T04:05:00+00:00", "2.3.1", "due"),
    (None, "2.3.0", 3, None, None, "no stable release"),
])
def test_auto_candidate(data, current, delay, last, want, why):
    version, reason = self_update.auto_candidate(data, current, delay, last, NOW)
    assert version == want
    assert why in reason


def test_a_plugin_playback_holds_automatic_updates_for_an_hour(monkeypatch):
    monkeypatch.setattr(self_update, "_last_playback", 0.0)
    assert self_update.recent_playback(now=10_000) is False
    self_update.note_playback(now=10_000)
    assert self_update.recent_playback(now=10_000 + 3599) is True
    assert self_update.recent_playback(now=10_000 + 3600) is False


def auto_setting(**extra):
    values = dict(update_auto_install=True, update_auto_hour=4, update_auto_delay_days=3,
                  update_auto_last_attempt=None, plex_url=None, plex_token=None)
    values.update(extra)
    return types.SimpleNamespace(**values)


def run_tick(monkeypatch, setting, hour=4, latest=None, plex_playing=None, playback=False, supported=True):
    db = FakeDb(setting)
    started, logged, fetched = [], [], []
    monkeypatch.setattr(self_update, "support", lambda in_docker=False: {"supported": supported})
    monkeypatch.setattr(self_update, "update_running", lambda: False)
    monkeypatch.setattr(self_update, "recent_playback", lambda: playback)
    monkeypatch.setattr(self_update, "fetch_latest_release", lambda: fetched.append(1) or (latest or release()))
    env = load_main_functions({"_auto_update_tick", "_auto_update_note"}, dict(
        datetime=datetime, Optional=Optional, self_update=self_update,
        SessionLocal=lambda: db, models=types.SimpleNamespace(Setting=object),
        app=types.SimpleNamespace(version="2.3.0"), _is_running_in_docker=lambda: False,
        _localized_now=lambda db: datetime.datetime(2026, 11, 10, hour, 30),
        _plex_playing_count=lambda s: plex_playing,
        _start_self_update=lambda version, why: started.append((version, why)),
        _file_log=lambda message, **k: logged.append(message), _auto_update_last_note=""))
    result = env["_auto_update_tick"](now_utc=NOW)
    return result, started, logged, fetched, db


def test_automatic_update_installs_a_due_release_in_its_hour(monkeypatch):
    setting = auto_setting()
    result, started, logged, fetched, db = run_tick(monkeypatch, setting)
    assert result == "2.3.1" and started == [("2.3.1", "automatic update")]
    assert setting.update_auto_last_attempt.startswith("2.3.1|2026-11-10T09:30")
    assert db.commits == 1


def test_automatic_update_stays_quiet_when_off_or_outside_its_hour(monkeypatch):
    for setting, hour in ((auto_setting(update_auto_install=False), 4), (auto_setting(), 5), (auto_setting(update_auto_hour=23), 4)):
        result, started, logged, fetched, db = run_tick(monkeypatch, setting, hour=hour)
        assert result is None and started == [] and fetched == [] and logged == []


def test_automatic_update_waits_while_something_plays(monkeypatch):
    plex = auto_setting(plex_url="http://plex:32400", plex_token="t")
    result, started, logged, _, _ = run_tick(monkeypatch, plex, plex_playing=1)
    assert result is None and started == [] and "Plex is playing" in logged[0]
    assert plex.update_auto_last_attempt is None  # tried again on the next check
    result, started, logged, _, _ = run_tick(monkeypatch, auto_setting(), playback=True)
    assert result is None and started == [] and "Jellyfin/Emby playback" in logged[0]
    # Plex can't be asked (None) or plays nothing (0): go ahead.
    assert run_tick(monkeypatch, auto_setting(), plex_playing=0)[0] == "2.3.1"


def test_automatic_update_tries_a_version_once_a_day(monkeypatch):
    setting = auto_setting(update_auto_last_attempt="2.3.1|2026-11-10T04:05:00+00:00")
    result, started, logged, _, _ = run_tick(monkeypatch, setting)
    assert result is None and started == [] and "trying again tomorrow" in logged[0]


def test_automatic_update_needs_the_updater(monkeypatch):
    result, started, _, fetched, _ = run_tick(monkeypatch, auto_setting(), supported=False)
    assert result is None and started == [] and fetched == []


def test_settings_save_the_automatic_update_choices_and_keep_them_in_range():
    setting = types.SimpleNamespace(update_check_interval="daily", update_include_prerelease=False,
                                    update_last_check=None, update_dismissed_version=None,
                                    update_auto_install=False, update_auto_hour=None, update_auto_delay_days=None)
    routes = {"update_get_settings", "update_settings", "_auto_update_settings"}
    client = route_client({}, routes=routes, setting=setting)
    assert client.get("/update/settings").json()["auto_hour"] == 4
    saved = client.put("/update/settings", json={"auto_install": True, "auto_hour": 26, "auto_delay_days": 45}).json()
    assert (saved["auto_install"], saved["auto_hour"], saved["auto_delay_days"]) == (True, 4, 30)
    assert (setting.update_auto_install, setting.update_auto_delay_days) == (True, 30)


def test_with_login_on_only_an_admin_turns_on_automatic_updates():
    setting = types.SimpleNamespace(update_check_interval="daily", update_include_prerelease=False,
                                    update_dismissed_version=None, update_auto_install=False,
                                    update_auto_hour=4, update_auto_delay_days=3)
    routes = {"update_settings", "_auto_update_settings"}
    viewer = types.SimpleNamespace(role="viewer", username="v")
    env = {"_check_auth_enabled": lambda db: True, "get_current_user_optional": lambda r, db: viewer}
    client = route_client(env, routes=routes, setting=setting)
    assert client.put("/update/settings", json={"auto_install": True}).status_code == 403
    assert setting.update_auto_install is False
    # The rest of the update settings stay open to any signed-in user, as before.
    assert client.put("/update/settings", json={"check_interval": "weekly"}).status_code == 200
