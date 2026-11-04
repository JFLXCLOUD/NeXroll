"""Changing NeXroll's timezone works out every schedule's next run again.

Issue #50: an install left on the default UTC ran a Central-time user's
schedules six hours early. Next runs are wall-clock times on NeXroll's clock,
so after the timezone changes the stored ones belong to the old clock; the
Dashboard's "Up next" and the Schedules page showed them until each schedule
next fired. PUT /settings/timezone now recalculates them.
"""

import ast
import types
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.testclient import TestClient


class FakeDb:
    def __init__(self, setting, schedules):
        self.setting, self.schedules, self.commits = setting, schedules, 0

    def query(self, model):
        rows = self.schedules if model == "Schedule" else [self.setting]
        return types.SimpleNamespace(first=lambda: rows[0] if rows else None, all=lambda: list(rows))

    def add(self, row):
        self.setting = row

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def client_for(db, calculated, logged, ticks=None):
    app = FastAPI()

    def get_db():
        yield db

    env = dict(app=app, Request=Request, Depends=Depends, HTTPException=HTTPException, Session=object,
               get_db=get_db, models=types.SimpleNamespace(Setting="Setting", Schedule="Schedule"),
               scheduler=types.SimpleNamespace(trigger_immediate_check=lambda: (ticks if ticks is not None else []).append(1)),
               _file_log=lambda message, **k: logged.append(message), log_event=lambda *a, **k: None)
    tree = ast.parse((Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name == "set_timezone"]
    assert len(nodes) == 1
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<set_timezone>", "exec"), env)
    # Stands in for main._refresh_schedule_next_run (normalize + scheduler).
    env["_refresh_schedule_next_run"] = lambda schedule: (
        calculated.append(schedule.id), setattr(schedule, "next_run", f"next-{schedule.id}"))
    return TestClient(app)


def test_a_new_timezone_recalculates_every_next_run():
    setting = types.SimpleNamespace(timezone="UTC")
    schedules = [types.SimpleNamespace(id=1, next_run="old"), types.SimpleNamespace(id=2, next_run="old")]
    db, calculated, logged, ticks = FakeDb(setting, schedules), [], [], []
    reply = client_for(db, calculated, logged, ticks).put("/settings/timezone", json={"timezone": "America/Chicago"})
    assert reply.status_code == 200 and setting.timezone == "America/Chicago"
    assert calculated == [1, 2] and [s.next_run for s in schedules] == ["next-1", "next-2"]
    assert db.commits == 2  # the zone first, so the calculation reads it
    assert logged == ["Timezone changed from UTC to America/Chicago; schedule next runs recalculated"]
    assert ticks == [1]  # the winner on the new clock takes over now


def test_saving_the_same_timezone_changes_nothing():
    setting = types.SimpleNamespace(timezone="America/Chicago")
    db, calculated, logged, ticks = FakeDb(setting, [types.SimpleNamespace(id=1, next_run="old")]), [], [], []
    client = client_for(db, calculated, logged, ticks)
    assert client.put("/settings/timezone", json={"timezone": "America/Chicago"}).status_code == 200
    assert calculated == [] and logged == [] and ticks == []
    assert client.put("/settings/timezone", json={"timezone": "Mars/Olympus"}).status_code == 400
