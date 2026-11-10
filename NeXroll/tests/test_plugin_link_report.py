"""The Connect page's view of a detected Jellyfin/Emby plugin."""
import pytest


@pytest.fixture
def main_module():
    import backend.main as main
    return main


def _db(main):
    return main.SessionLocal()


def test_key_is_masked_and_unknown_key_means_linked_elsewhere(main_module, monkeypatch):
    main = main_module
    monkeypatch.setattr(main, "_plugin_has_checked_in", lambda kind: False)
    db = _db(main)
    try:
        safe, linked = main._plugin_link_report(
            "jellyfin", {"NexrollUrl": "http://other:9393", "ApiKey": "nx_secret_from_another_install"}, db)
    finally:
        db.close()
    assert safe["ApiKey"] == "nx_sec..."
    assert "another_install" not in str(safe)
    assert linked is False


def test_a_key_this_install_issued_is_linked_here(main_module, monkeypatch):
    main = main_module
    monkeypatch.setattr(main, "_plugin_has_checked_in", lambda kind: False)
    db = _db(main)
    try:
        raw = "nx_issued_here_0123456789"
        row = main.models.APIKey(name="plugin-link-test", key_hash=main._hash_api_key(raw),
                                 key_prefix=raw[:8], is_active=True)
        db.add(row)
        db.commit()
        try:
            safe, linked = main._plugin_link_report("emby", {"ApiKey": raw}, db)
        finally:
            db.delete(row)
            db.commit()
    finally:
        db.close()
    assert linked is True
    assert safe["ApiKey"].endswith("...")


def test_no_key_and_never_seen_is_unknown_and_seen_is_here(main_module, monkeypatch):
    main = main_module
    db = _db(main)
    try:
        monkeypatch.setattr(main, "_plugin_has_checked_in", lambda kind: False)
        assert main._plugin_link_report("jellyfin", {"NexrollUrl": "http://x"}, db)[1] is None
        monkeypatch.setattr(main, "_plugin_has_checked_in", lambda kind: True)
        assert main._plugin_link_report("jellyfin", {"ApiKey": "nx_unknown"}, db)[1] is True
    finally:
        db.close()
