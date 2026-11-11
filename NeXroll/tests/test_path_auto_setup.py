"""POST /settings/path-mappings/auto-setup: find the folders and save what is confirmed."""
import json

import pytest


@pytest.fixture
def main_module():
    import backend.main as main
    return main


def _run(main, monkeypatch, report, existing):
    monkeypatch.setattr(main, "detect_path_mapping", lambda req, db: report)
    monkeypatch.setattr(main.scheduler, "request_plex_refresh", lambda *a, **k: None)
    db = main.SessionLocal()
    try:
        setting = db.query(main.models.Setting).first()
        if not setting:
            setting = main.models.Setting()
            db.add(setting)
        before = setting.path_mappings
        setting.path_mappings = json.dumps(existing)
        db.commit()
        try:
            out = main.auto_setup_path_mappings(db)
            db.refresh(setting)
            return out, json.loads(setting.path_mappings or "[]")
        finally:
            setting.path_mappings = before
            db.commit()
    finally:
        db.close()


def test_confirmed_mappings_are_saved_and_others_kept(main_module, monkeypatch):
    found = {"local": "/data/prerolls", "plex": "/mnt/media/prerolls"}
    report = {"folders": [{"label": "Prerolls", "found": True, "mapping_needed": True, "suggestion": found}],
              "suggestions": [found]}
    existing = [{"local": "/data/prerolls/", "plex": "/wrong"}, {"local": "/data/other", "plex": "/mnt/other"}]
    out, stored = _run(main_module, monkeypatch, report, existing)
    assert out["saved"] == [found] and out["working"] is True and out["not_found"] == []
    # The stale rule for the same folder is replaced; the unrelated one stays.
    # (The save normalises the NeXroll side for the host, so compare with forward slashes.)
    by_folder = {m["local"].replace(chr(92), "/").rstrip("/"): m["plex"] for m in stored}
    assert by_folder == {"/data/other": "/mnt/other", "/data/prerolls": "/mnt/media/prerolls"}


def test_nothing_needed_changes_nothing(main_module, monkeypatch):
    report = {"folders": [{"label": "Prerolls", "found": True, "already_working": True}], "suggestions": []}
    existing = [{"local": "/data/prerolls", "plex": "/mnt/media/prerolls"}]
    out, stored = _run(main_module, monkeypatch, report, existing)
    assert out["saved"] == [] and out["working"] is True
    assert [m["plex"] for m in stored] == ["/mnt/media/prerolls"]


def test_a_folder_that_was_not_found_is_reported_not_guessed(main_module, monkeypatch):
    report = {"folders": [{"label": "Prerolls", "found": False, "reason": "not there"}], "suggestions": []}
    out, stored = _run(main_module, monkeypatch, report, [])
    assert out["saved"] == [] and out["working"] is False and out["not_found"] == ["Prerolls"]
    assert stored == []
