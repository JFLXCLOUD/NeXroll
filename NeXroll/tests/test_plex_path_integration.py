import json
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

import backend.models as models
from backend import health_summary, path_mapping, plex_visibility as pv
from backend.plex_connector import PlexConnector
from tests.test_plex_visibility import FakePlex, TREE
from tests.test_trailer_filters import db, route  # noqa: F401  (db is a fixture)


@pytest.fixture(autouse=True)
def fresh_state():
    pv.reset_state()
    yield
    pv.reset_state()


def connector():
    c = PlexConnector("http://plex:32400", "secret")
    c._try_set_preroll_value = Mock(return_value=True)
    return c


# -- the gate inside PlexConnector.set_preroll ---------------------------------

def test_withheld_value_is_never_written():
    c = connector()
    gate = pv.GateResult("withheld", "/x/a.mp4", [{"path": "/x/a.mp4", "status": pv.MISSING, "reason": "no"}], "none")
    with patch.object(pv, "gate_preroll_value", return_value=gate):
        assert c.set_preroll("/x/a.mp4") is False
    c._try_set_preroll_value.assert_not_called()
    assert c.visibility_summary()["action"] == "withheld"


def test_filtered_value_is_what_gets_written():
    c = connector()
    gate = pv.GateResult("filtered", "/x/a.mp4", [], "some")
    with patch.object(pv, "gate_preroll_value", return_value=gate):
        assert c.set_preroll("/x/a.mp4;/x/gone.mp4") is True
    c._try_set_preroll_value.assert_called_once_with("/x/a.mp4")


def test_a_failing_check_writes_the_value_unchanged():
    c = connector()
    with patch.object(pv, "gate_preroll_value", side_effect=RuntimeError("boom")):
        assert c.set_preroll("/x/a.mp4;/x/b.mp4") is True
    c._try_set_preroll_value.assert_called_once_with("/x/a.mp4;/x/b.mp4")


def test_clearing_prerolls_is_not_checked():
    c = connector()
    with patch.object(pv, "gate_preroll_value") as gate:
        c.set_preroll("")
    gate.assert_not_called()


def test_end_to_end_against_a_fake_plex():
    c = connector()
    fake = FakePlex(TREE)
    value = "/data/Prerolls/BTTJFLX.mp4;/data/prerolls/BTTJFLX.mp4"
    with patch.object(pv.requests, "get", side_effect=fake.get), patch.object(pv.time, "sleep"):
        assert c.set_preroll(value) is True
    c._try_set_preroll_value.assert_called_once_with("/data/Prerolls/BTTJFLX.mp4")
    assert pv.last_report()["missing_count"] == 1


# -- the health row -------------------------------------------------------------

@pytest.mark.parametrize("report,status", [
    (None, health_summary.UNKNOWN),
    ({"action": "unverified"}, health_summary.UNKNOWN),
    ({"action": "ok", "total": 3, "missing_count": 0}, health_summary.OK),
    ({"action": "filtered", "total": 3, "missing_count": 1, "missing": [{"path": "/p", "reason": "r"}]}, health_summary.WARN),
    ({"action": "withheld", "total": 2, "missing_count": 2, "missing": [{"path": "/p", "reason": "r"}]}, health_summary.ERROR),
])
def test_plex_paths_health_row(report, status):
    check = health_summary.plex_paths_check(report)
    assert check["key"] == "plex_paths" and check["status"] == status


def test_an_unchecked_plex_costs_nothing():
    checks = [health_summary.plex_paths_check(None)]
    assert health_summary.score_checks(checks) == 100


def test_a_withheld_apply_names_the_first_missing_file():
    check = health_summary.plex_paths_check({"action": "withheld", "total": 1, "missing_count": 1,
                                             "missing": [{"path": "/data/prerolls/x.mp4", "reason": "Plex has no folder /data/prerolls."}]})
    assert "/data/prerolls/x.mp4" in check["detail"] and check["value"] == "0 of 1 visible"


# -- routes ---------------------------------------------------------------------

def sequence_apply(plex, paths):
    fn = route("apply_sequence_to_server", HTTPException=HTTPException, path_mapping=path_mapping,
               PlexConnector=Mock(return_value=plex), _file_log=lambda *a, **k: None, log_event=lambda *a, **k: None)
    fn.__globals__["resolve_sequence_paths"] = lambda *a, **k: list(paths)
    fn.__globals__["playback_context"] = lambda *a, **k: None
    return fn

def test_sequence_apply_reaches_plex_with_the_token_in_the_secure_store(db):
    """The token column is cleared on connect; requiring it skipped Plex."""
    setting = db.query(models.Setting).first()
    setting.plex_url, setting.plex_token = "http://plex:32400", None
    saved = models.SavedSequence(name="S", blocks=json.dumps([{"type": "fixed", "preroll_id": 1}]))
    db.add(saved)
    db.commit()
    plex = Mock()
    plex.set_preroll.return_value = True
    plex.visibility_summary.return_value = {"action": "ok"}
    fn = sequence_apply(plex, ["/data/Prerolls/a.mp4"])
    out = fn(saved.id, db)
    assert out["applied_to"] == ["plex"]
    plex.set_preroll.assert_called_once_with("/data/Prerolls/a.mp4")


def test_sequence_apply_reports_a_withheld_plex(db):
    setting = db.query(models.Setting).first()
    setting.plex_url = "http://plex:32400"
    saved = models.SavedSequence(name="S", blocks=json.dumps([{"type": "fixed", "preroll_id": 1}]))
    db.add(saved)
    db.commit()
    plex = Mock()
    plex.set_preroll.return_value = False
    plex.visibility_summary.return_value = {"action": "withheld", "message": "Plex cannot see any"}
    fn = sequence_apply(plex, ["/x/a.mp4"])
    with pytest.raises(HTTPException) as err:
        fn(saved.id, db)
    assert err.value.status_code == 409


def folder_env(tmp_path):
    """_plex_path_folders wired up against a temporary preroll folder."""
    prerolls = str(tmp_path / "prerolls")
    raw_known = route("_known_preroll_paths", plex_visibility=pv)
    known = lambda db, root: raw_known(db, root, 400)  # the loader blanks default arguments
    raw_rel = route("_relative_under")
    relative = lambda root, paths, limit=400: raw_rel(root, paths, limit)
    inside = route("_is_inside")
    folders = route("_plex_path_folders", plex_visibility=pv, PREROLLS_DIR=prerolls,
                    _known_preroll_paths=known, _relative_under=relative, _is_inside=inside)
    return prerolls, known, folders


def detect_env(db, tmp_path, fake, sleep=None, marker_writer=None):
    import time as real_time
    prerolls, known, folders = folder_env(tmp_path)
    clock = SimpleNamespace(sleep=sleep or (lambda s: None), monotonic=real_time.monotonic)
    detect_with = route("_detect_with", path_mapping=path_mapping, plex_visibility=pv, time=clock)
    marker = marker_writer or route("_write_location_marker")
    detect_folder = route("_detect_folder", _write_location_marker=marker, _detect_with=detect_with)
    return route("detect_path_mapping", HTTPException=HTTPException, path_mapping=path_mapping,
                 plex_visibility=pv, PREROLLS_DIR=prerolls,
                 _plex_files=lambda db, **k: (None, pv.PlexFiles("http://plex:32400", "secret")),
                 _known_preroll_paths=known, _plex_path_folders=folders, _detect_folder=detect_folder,
                 _detect_with=detect_with, _write_location_marker=marker)


def add_prerolls(db, root, rels):
    for rel in rels:
        p = root.joinpath(*rel.split("/"))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x")
        db.add(models.Preroll(filename=p.name, path=str(p)))
    db.commit()


def test_detect_finds_the_plex_folder_and_proposes_a_mapping(db, tmp_path):
    fake = FakePlex(TREE)
    add_prerolls(db, tmp_path / "prerolls", ["BTTJFLX.mp4", "Halloween/plexpreroll-EvilDead2.m4v"])
    fn = detect_env(db, tmp_path, fake)
    with patch.object(pv.requests, "get", side_effect=fake.get):
        out = fn(None, db)
    assert out["found"] and out["plex_folder"] == "/data/Prerolls"
    assert out["mapping_needed"] and out["suggestion"] == {"local": str(tmp_path / "prerolls"), "plex": "/data/Prerolls"}


def test_detect_recognises_a_mapping_that_already_works(db, tmp_path):
    fake = FakePlex(TREE)
    local = tmp_path / "prerolls"
    add_prerolls(db, local, ["BTTJFLX.mp4", "Halloween/plexpreroll-EvilDead2.m4v"])
    db.query(models.Setting).first().path_mappings = json.dumps([{"local": str(local), "plex": "/data/Prerolls"}])
    db.commit()
    fn = detect_env(db, tmp_path, fake)
    with patch.object(pv.requests, "get", side_effect=fake.get):
        out = fn(None, db)
    assert out["found"] and out["already_working"] and not out["mapping_needed"]


MARKER = "NeXroll-location-check-abcd1234.txt"


def test_an_empty_folder_is_found_with_a_temporary_marker(db, tmp_path, monkeypatch):
    """A fresh install has no prerolls to look for; a marker file stands in."""
    import secrets
    monkeypatch.setattr(secrets, "token_hex", lambda n: "abcd1234")
    tree = dict(TREE)
    dirs, names = tree["/data/Prerolls"]
    tree["/data/Prerolls"] = (dirs, names + [MARKER])
    fake = FakePlex(tree)
    (tmp_path / "prerolls").mkdir()
    fn = detect_env(db, tmp_path, fake)
    with patch.object(pv.requests, "get", side_effect=fake.get):
        out = fn(None, db)
    assert out["found"] and out["used_marker"] and out["plex_folder"] == "/data/Prerolls"
    assert not (tmp_path / "prerolls" / MARKER).exists(), "the marker must be removed"


def test_a_marker_plex_never_sees_is_retried_once_and_removed(db, tmp_path, monkeypatch):
    import secrets
    monkeypatch.setattr(secrets, "token_hex", lambda n: "abcd1234")
    slept = []
    (tmp_path / "prerolls").mkdir()
    fn = detect_env(db, tmp_path, FakePlex(TREE), sleep=slept.append)
    with patch.object(pv.requests, "get", side_effect=FakePlex(TREE).get):
        out = fn(None, db)
    assert not out["found"] and slept == [6]
    assert not (tmp_path / "prerolls" / MARKER).exists()


def test_an_unwritable_empty_folder_explains_itself(db, tmp_path):
    fn = detect_env(db, tmp_path, FakePlex(TREE), marker_writer=lambda folder: None)
    out = fn(None, db)
    assert not out["found"] and "could not write" in out["reason"]


def test_browse_root_hides_device_files(db):
    fake = FakePlex(TREE, roots=["/", "/dev/null", "/data/Prerolls", "/var/lib/plexmediaserver"])
    files = pv.PlexFiles("http://plex:32400", "secret")
    fn = route("plex_browse", HTTPException=HTTPException, path_mapping=path_mapping, plex_visibility=pv,
               _plex_files=lambda db, **k: (None, files))
    with patch.object(pv.requests, "get", side_effect=fake.get):
        root = fn("", db)
        inside = fn("/data/Prerolls", db)
    assert [d["path"] for d in root["dirs"]] == ["/", "/data/Prerolls"]
    assert inside["parent"] == "/data" and inside["video_count"] == 2
    assert {d["name"] for d in inside["dirs"]} == {"Halloween", "Fake Trailers"}


# -- every folder NeXroll hands Plex files from ------------------------------------

def trailer_file(root, *parts):
    p = root.joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x")
    return str(p)


def test_only_the_preroll_folder_by_default(db, tmp_path):
    _, _, folders = folder_env(tmp_path)
    out = folders(db)
    assert [f["kind"] for f in out] == ["prerolls"]


def test_nexup_storage_inside_the_preroll_folder_needs_nothing_more(db, tmp_path):
    _, _, folders = folder_env(tmp_path)
    db.query(models.Setting).first().nexup_storage_path = str(tmp_path / "prerolls" / "NeXup")
    db.commit()
    assert [f["kind"] for f in folders(db)] == ["prerolls"]


def test_nexup_storage_elsewhere_is_its_own_folder(db, tmp_path):
    _, _, folders = folder_env(tmp_path)
    storage = tmp_path / "trailers"
    db.query(models.Setting).first().nexup_storage_path = str(storage)
    db.add(models.ComingSoonTrailer(title="Dune", local_path=trailer_file(storage, "movies", "Dune.mp4"), status="downloaded"))
    db.add(models.LibraryTrailer(radarr_movie_id=9, title="Local", source="local", status="available",
                                 local_path=trailer_file(tmp_path, "elsewhere", "Local (2020)", "x-trailer.mp4")))
    db.commit()
    nexup = [f for f in folders(db) if f["kind"] == "nexup"][0]
    assert nexup["local_folder"] == os.path.normpath(str(storage))
    assert nexup["known"] == ["movies/Dune.mp4"]


def test_trailers_beside_movies_group_by_library_folder(db, tmp_path):
    _, _, folders = folder_env(tmp_path)
    movies = tmp_path / "movies"
    for i, parts in enumerate([("Alien (1979)", "Alien-trailer.mp4"), ("Heat (1995)", "Trailers", "Heat.mp4")]):
        db.add(models.LibraryTrailer(radarr_movie_id=i, title=parts[0], source="local", status="available",
                                     local_path=trailer_file(movies, *parts)))
    db.add(models.LibraryTrailer(radarr_movie_id=7, title="Downloaded", source="download", status="available",
                                 local_path=trailer_file(tmp_path, "prerolls", "NeXup", "library", "d.mp4")))
    db.commit()
    library = [f for f in folders(db) if f["kind"] == "library"]
    assert len(library) == 1 and library[0]["local_folder"] == os.path.normpath(str(movies))
    assert sorted(library[0]["known"]) == ["Alien (1979)/Alien-trailer.mp4", "Heat (1995)/Trailers/Heat.mp4"]


MOVIE_TREE = dict(TREE)
MOVIE_TREE.update({
    "/data/MEDIA/Movies": (["Alien (1979)", "Heat (1995)"], []),
    "/data/MEDIA/Movies/Alien (1979)": ([], ["Alien.mkv", "Alien-trailer.mp4"]),
    "/data/MEDIA/Movies/Heat (1995)": (["Trailers"], ["Heat.mkv"]),
    "/data/MEDIA/Movies/Heat (1995)/Trailers": ([], ["Heat.mp4"]),
})


def test_find_it_for_me_covers_the_movie_library_too(db, tmp_path):
    fake = FakePlex(MOVIE_TREE, libraries=["/data/MEDIA/Movies"])
    add_prerolls(db, tmp_path / "prerolls", ["BTTJFLX.mp4", "Halloween/plexpreroll-EvilDead2.m4v"])
    movies = tmp_path / "movies"
    for i, parts in enumerate([("Alien (1979)", "Alien-trailer.mp4"), ("Heat (1995)", "Trailers", "Heat.mp4")]):
        db.add(models.LibraryTrailer(radarr_movie_id=i, title=parts[0], source="local", status="available",
                                     local_path=trailer_file(movies, *parts)))
    db.commit()
    fn = detect_env(db, tmp_path, fake)
    with patch.object(pv.requests, "get", side_effect=fake.get):
        out = fn(None, db)
    kinds = {f["kind"]: f for f in out["folders"]}
    assert kinds["prerolls"]["plex_folder"] == "/data/Prerolls"
    assert kinds["library"]["plex_folder"] == "/data/MEDIA/Movies"
    assert {"local": os.path.normpath(str(movies)), "plex": "/data/MEDIA/Movies"} in out["suggestions"]
    assert len(out["suggestions"]) == 2
    assert out["plex_folder"] == "/data/Prerolls", "top-level fields still describe the preroll folder"


def test_a_movie_library_plex_cannot_see_is_reported_not_guessed(db, tmp_path):
    fake = FakePlex(TREE, libraries=["/data/MEDIA/Movies"])
    add_prerolls(db, tmp_path / "prerolls", ["BTTJFLX.mp4"])
    db.add(models.LibraryTrailer(radarr_movie_id=1, title="Nope", source="local", status="available",
                                 local_path=trailer_file(tmp_path / "movies", "Nope (2022)", "Nope-trailer.mp4")))
    db.commit()
    fn = detect_env(db, tmp_path, fake)
    with patch.object(pv.requests, "get", side_effect=fake.get):
        out = fn(None, db)
    library = [f for f in out["folders"] if f["kind"] == "library"][0]
    assert not library["found"] and library["reason"]
    assert all(s["plex"] != "/data/MEDIA/Movies" for s in out["suggestions"])
