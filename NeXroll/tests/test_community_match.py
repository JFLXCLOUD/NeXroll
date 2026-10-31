"""Matching local prerolls to the Community index (backend/community_match.py).

Replayed on JB's production library (October 30), the old title-only
matchers linked "Carrie_7340_trailer" to "Car", "20thCenturyFox-Flute" to
"Fox", "Waldo The Movie_x264" (130 s) to "The Core - PLEX 2 x264" (54 s) and
"HBOPLEX" (6 s) to "HBO (1983) Plex v2" (81 s). The cases below are those
files, with the index entries they met.
"""

import ast
import copy
import os
import threading
import time
from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import community_match as cm
from backend import models
from tests.test_trailer_filters import main_ast

HEX = "06c352c2c3b046dfb04896434e035064"


def entry(path, size=None, category=None):
    return {"id": path, "path": path, "url": "https://prerolls.uk" + path, "title": "Stored Title",
            "size_bytes": size, "category": category or path.split("/")[1]}


INDEX = [
    entry(f"/Community/_Plex/Pulp%20Fiction/{HEX}.Pulp_Fiction_We_Happy_Plex_Pre-roll.mp4", 31_000_001),
    entry("/Archives/TypicalNerds%20Personal%20Archive/Plex-Old/Fall/Fox.mp4", 1_000_002),
    entry("/Archives/TypicalNerds%20Personal%20Archive/Plex-2022/General/Car.mp4", 1_000_003),
    entry("/Community/_Plex/RaT%20FBI%20Scene%20Pre-roll%20-%20JBrns/The_Core_-_PLEX_2_x264.mp4", 17_979_281),
    entry("/Holidays/St.%20Patrick%20-%20AwesomeAustn/St.%20Patrick_s%20Day%20Universal.mp4", 1_000_005),
    entry(f"/Archives/prerolls.video/p5/{HEX}.stpatrickplex.mp4", 1_000_006),
    entry("/Seasons/Nature%20-%20AwesomeAustn/Day/1080p/Nature%20Day%20Plex_1080p.mp4", 1_000_007),
    entry("/Seasons/Nature%20-%20AwesomeAustn/Day/2160p/Nature%20Day%20Plex_4K.mp4", 1_000_008),
    entry("/Seasons/Fall/Maple%20Leaves%20-%20AwesomeAustn/Maple%20Leaves%20Plex.mp4", 1_000_009),
    entry("/Seasons/Fall/Maple%20Leaves%20-%20AwesomeAustn/Maple%20Leaves%20Jellyfin.mp4", 1_000_010),
    entry("/Community/Light%20Speed%20Pre-roll%20-%20preroller/1080p/Light%20Speed%20Plex%20Pre-roll.mp4", 1_000_011),
    entry("/Holidays/Christmas/_Plex/Grinchmas%20-%20HeliumNewb/Grinchmas%20-%20Plex.mp4", 1_000_012),
    entry("/Holidays/Christmas/_Jellyfin/Grinchmas%20-%20HeliumNewb/Grinchmas%20-%20Jellyfin.mp4", 1_000_013),
    entry("/Holidays/Halloween/Ghost%20Light%20-%20Ann/Ghost%20Light.mp4", 1_000_014),
    entry("/Community/Ghost%20Light%20-%20Bob/Ghost%20Light.mp4", 1_000_015),
    entry("/Archives/prerolls.video/preroller/_Emby/HBO_Emby_Pre-roll.mp4", 1_000_016),
    entry("/Holidays/Halloween/Halloween%20Moon%20-%20AwesomeAustn/Halloween%20Moon%20Plex.mp4", 5_555_555),
    entry("/Archives/TypicalNerds%20Personal%20Archive/Plex-2022/Halloween/Halloween-Moon.mp4", 5_555_555),
    entry("/Archives/TypicalNerds%20Personal%20Archive/Plex-2022/General/Epic-Blockbuster.mp4", 1_000_019),
    entry("/Community/Epic%20Blockbuster%20Pre-roll%20-%20preroller/Epic%20Blockbuster%20Plex%20Pre-roll.mp4", 1_000_020),
    entry("/Holidays/Halloween/Pumpkin%20Patch%20-%20JBrns/Charlie%20Brown%20Pumpkin%20Patch%20-%20Emby.mp4", 1_000_021),
    entry("/Holidays/Halloween/Pumpkin%20Patch%20-%20JBrns/Charlie%20Brown%20Pumpkin%20Patch%20-%20Plex.mp4", 1_000_022),
]
LENGTHS = {
    INDEX[0]["path"]: 20.0, INDEX[1]["path"]: 7.37, INDEX[2]["path"]: 9.56, INDEX[3]["path"]: 53.98,
    INDEX[4]["path"]: 11.73, INDEX[5]["path"]: 8.6, INDEX[6]["path"]: 9.02, INDEX[7]["path"]: 9.02,
    INDEX[8]["path"]: 10.0, INDEX[9]["path"]: 10.0, INDEX[10]["path"]: 6.4,
    INDEX[16]["path"]: 12.0, INDEX[17]["path"]: 12.0, INDEX[18]["path"]: 10.0, INDEX[19]["path"]: 10.02,
    INDEX[20]["path"]: 15.0, INDEX[21]["path"]: 15.05,
    # Grinchmas, Ghost Light and HBO have no length read yet.
}
MATCHER = cm.Matcher(INDEX, LENGTHS)


def match(name, size=None, seconds=None, platform=None, matcher=MATCHER):
    return matcher.match([name], size=size, seconds=seconds, platform=platform or cm.local_platform(name))


def ends(result, tail):
    return bool(result["id"]) and result["id"].endswith(tail)


# --- the same file ---------------------------------------------------------

def test_a_renamed_file_is_found_by_its_size():
    result = match("PlexFiction.mp4", size=31_000_001, seconds=20.01)
    assert result["how"] == "file" and result["confidence"] == 100
    assert ends(result, "Pulp_Fiction_We_Happy_Plex_Pre-roll.mp4")
    assert result["title"] == "Pulp Fiction We Happy Plex Pre-roll"


def test_the_same_size_with_a_different_length_is_not_the_same_file():
    result = match("Something Else.mp4", size=31_000_001, seconds=45.0)
    assert result["how"] != "file"


def test_a_file_in_two_folders_links_the_copy_outside_archives():
    result = match("Moon.mp4", size=5_555_555)
    assert result["how"] == "file"
    assert ends(result, "Halloween%20Moon%20Plex.mp4")


# --- titles: whole words, filler ------------------------------------------

def test_a_short_title_inside_a_longer_word_is_not_a_match():
    for name, seconds in (("20thCenturyFox-Flute.mp4", 20.6), ("Carrie Night.mp4", 9.56)):
        result = match(name, seconds=seconds)
        assert result["id"] is None, name
        assert not any(s["title"] in ("Fox", "Car") for s in result["suggestions"]), name


def test_two_filler_words_in_common_are_not_a_match():
    # "The" and "x264" were all "Waldo The Movie_x264" shared with The Core.
    result = match("Waldo The Movie_x264.mp4", seconds=130.08)
    assert result["id"] is None
    assert result["suggestions"] == []


def test_title_words_ignore_platform_preroll_resolution_and_codec():
    assert cm.words("Light Speed Plex Pre-roll 1080p x264") == ("light", "speed")
    assert cm.words("The_Core_-_PLEX_2_x264") == ("core", "2")


def test_joined_words_plurals_and_possessives_compare_equal():
    assert cm.joined("LightSpeed") == cm.joined("Light Speed")
    assert cm.joined("St_patrick_plex") == cm.joined(f"{HEX}.stpatrickplex")
    assert cm.words("Valentines Hearts") == cm.words("Valentine's Hearts")
    assert cm.words("Let_s Go") == cm.words("Let's Go")
    assert cm.words("Christmas Lights") == ("christmas", "light")


# --- lengths ---------------------------------------------------------------

def test_title_and_length_agreeing_links():
    result = match("St. Patrick Day Uni.mp4", seconds=11.71)
    assert result["how"] == "title_length"
    assert ends(result, "St.%20Patrick_s%20Day%20Universal.mp4")


def test_a_platform_word_glued_on_still_links():
    result = match("St_patrick_plex.mp4", seconds=8.58)
    assert result["how"] == "title_length"
    assert ends(result, ".stpatrickplex.mp4")


def test_a_different_length_is_never_linked_and_shows_low():
    # JB's own 4.9 s cut of the 6.4 s Light Speed.
    result = match("LightSpeed.mp4", seconds=4.94)
    assert result["id"] is None
    cut = next(s for s in result["suggestions"] if s["title"] == "Light Speed Plex Pre-roll")
    assert cut["reason"] == "title, different length"
    assert cut["confidence"] < 40
    assert (cut["seconds"], cut["local_seconds"]) == (6.4, 4.94)


def test_lengths_within_a_second_agree():
    assert cm.lengths_agree(22.12, 22.14) is True
    assert cm.lengths_agree(8.34, 8.02) is True
    assert cm.lengths_agree(18.63, 17.05) is False
    assert cm.lengths_agree(None, 12.0) is None


def test_the_full_name_picks_the_version():
    result = match("Nature Day Plex 4K.mp4", seconds=9.0)
    assert ends(result, "Nature%20Day%20Plex_4K.mp4")
    result = match("Nature Day Plex 1080p.mp4", seconds=9.0)
    assert ends(result, "Nature%20Day%20Plex_1080p.mp4")
    result = match("Maple Leaves Jellyfin.mp4", seconds=10.0)
    assert ends(result, "Maple%20Leaves%20Jellyfin.mp4")


def test_an_equal_match_outside_archives_wins():
    result = match("EpicBlockbusterPlex.mp4", seconds=10.0)
    assert ends(result, "Epic%20Blockbuster%20Plex%20Pre-roll.mp4")


def test_the_platform_from_the_path_picks_the_version():
    result = MATCHER.match(["Maple Leaves.mp4"], seconds=10.0, platform="jellyfin")
    assert ends(result, "Maple%20Leaves%20Jellyfin.mp4")
    assert cm.local_platform("Maple Leaves.mp4", None, "/data/prerolls/Jellyfin/Fall/Maple Leaves.mp4") == "jellyfin"


# --- no length to compare --------------------------------------------------

def test_an_exact_title_naming_one_preroll_links_without_a_length():
    result = match("Grinchmas.mp4")  # Plex and Jellyfin versions of one preroll
    assert result["how"] == "title"
    assert "Grinchmas" in result["id"]


def test_an_exact_title_shared_by_two_prerolls_is_only_suggested():
    result = match("Ghost Light.mp4")
    assert result["id"] is None
    top_two = [s["id"].split("/")[-2] for s in result["suggestions"][:2]]
    assert sorted(top_two) == ["Ghost%20Light%20-%20Ann", "Ghost%20Light%20-%20Bob"]


def test_a_short_exact_title_is_only_suggested():
    result = match("HBOPLEX.mp4")
    assert result["id"] is None
    assert result["suggestions"][0]["title"] == "HBO Emby Pre-roll"
    assert result["suggestions"][0]["confidence"] < 70


def test_the_length_is_measured_once_and_only_when_a_candidate_has_one():
    calls = []

    def measure():
        calls.append(1)
        return 11.72

    assert match("Nothing Like Anything.mp4", seconds=measure)["id"] is None
    assert calls == []
    assert match("Grinchmas.mp4", seconds=measure)["how"] == "title"  # no index length to compare
    assert calls == []
    assert match("PlexFiction.mp4", size=31_000_001, seconds=measure)["how"] == "file"
    assert calls == []
    assert match("St. Patrick Day Uni.mp4", seconds=measure)["how"] == "title_length"
    assert calls == [1]


def test_copies_are_suggested_once():
    result = match("Halloween Moon Night.mp4")
    sizes = [s["id"] for s in result["suggestions"] if "Moon" in s["id"]]
    assert len(sizes) == 1


# --- NeXroll's own files ---------------------------------------------------

@pytest.mark.parametrize("path", [
    "/data/prerolls/NeXup/library/movies/Carrie_7340_trailer.mp4",
    "/data/nexup_trailers/tv/Phony_tvdb123456_trailer.mp4",
    "/data/nexup_trailers/movies/Weapons_1078605_trailer.f137.mp4",
    "/data/nexup_trailers/dynamic_prerolls/coming_soon_grid.mp4",
    "/data/prerolls/NeXup/dynamic_prerolls/custom_text_aurora_drift_preroll.mp4",
    r"C:\ProgramData\NeXroll\NeXup\dynamic_prerolls\assets\theme_backdrop_aurora_drift.webm",
])
def test_nexroll_made_files_are_recognised(path):
    assert cm.is_nexroll_file(path)


@pytest.mark.parametrize("path", [
    "/data/prerolls/Trailers/Movie Trailer Intro.mp4",
    "/data/prerolls/Coming Soon Plex.mp4",
    "/data/prerolls/Holiday/Halloween 2023 trailer.mp4",
])
def test_ordinary_prerolls_are_not_nexroll_made(path):
    assert not cm.is_nexroll_file(path)


# --- main.py: endpoints and the startup pass --------------------------------

FUNCTIONS = ("_is_nexroll_made", "_connected_platforms", "_community_match_for", "_local_media_seconds", "auto_match_single_preroll",
             "_match_existing_prerolls", "migrate_legacy_community_prerolls_endpoint", "_find_community_id_for",
             "migrate_legacy_community_prerolls", "_match_job_update", "_match_job_status", "_run_match_job",
             "start_match_existing_prerolls", "get_match_existing_status")
_opened = []


@pytest.fixture(autouse=True)
def _close_databases():
    yield
    while _opened:
        db, engine = _opened.pop()
        db.close()
        engine.dispose()


@pytest.fixture
def env(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'match.db'}")
    models.Base.metadata.create_all(engine)
    make = sessionmaker(bind=engine)
    db = make()
    _opened.append((db, engine))
    probes = []

    def run(cmd, **kwargs):
        probes.append(cmd[-1])
        return type("Result", (), {"stdout": "11.72\n"})()

    nodes = []
    for node in main_ast().body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            node = copy.deepcopy(node)
            node.decorator_list = []
            node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
            nodes.append(node)
    # The job's thread runs at start() so a test sees the finished run.
    threads = SimpleNamespace(Thread=lambda target, args, **kw: SimpleNamespace(start=lambda: target(*args)))
    namespace = dict(
        models=models, os=os, time=time, threading=threads, Optional=Optional, HTTPException=HTTPException,
        community_match=cm, Query=None, Depends=None, Session=object, get_db=None,
        _community_matcher=lambda: MATCHER, _file_log=lambda *a, **k: None, log_event=lambda *a, **k: None,
        _run_subprocess=run, get_ffprobe_cmd=lambda: "ffprobe", _sqlite_has_column=lambda *a: True,
        SessionLocal=make, _match_job_gate=threading.Lock(),
        _match_job={"running": False, "phase": "idle", "rematch": False, "total": 0, "checked": 0, "matched": 0,
                    "needs_review": 0, "skipped": 0, "current": "", "result": None, "error": None, "finished_at": None},
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), "<main-match>", "exec"), namespace)
    namespace.update(db=db, probes=probes, tmp_path=tmp_path, make=make)
    return namespace


def add(env, name, *, duration=None, size=None, description=None, exclude=False, folder="Prerolls", category=None, write=None):
    path = env["tmp_path"] / folder / name
    if write is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(write)
    preroll = models.Preroll(filename=name, path=str(path), duration=duration, file_size=size,
                             description=description, exclude_from_matching=exclude, category=category)
    env["db"].add(preroll)
    env["db"].commit()
    return preroll


def test_bulk_match_links_confident_ones_and_counts_the_rest(env):
    db = env["db"]
    trailers = models.Category(name="NeX-Up Movie Trailers", is_system=True)
    db.add(trailers)
    linked = add(env, "St. Patrick Day Uni.mp4", duration=11.71)
    renamed = add(env, "PlexFiction.mp4", duration=20.0, size=31_000_001)
    cut = add(env, "LightSpeed.mp4", duration=4.94)
    excluded = add(env, "Maple Leaves Plex.mp4", duration=10.0, exclude=True)
    trailer = add(env, "Carrie_7340_trailer.mp4", duration=9.56, folder="NeXup/movies")
    generated = add(env, "Aurora.mp4", duration=8.73, category=trailers)
    nothing = add(env, "Waldo The Movie_x264.mp4", duration=130.08)

    out = env["migrate_legacy_community_prerolls_endpoint"](match_all=True, db=db)

    assert (out["matched"], out["total_scanned"], out["skipped"], out["needs_review"]) == (2, 4, 3, 1)
    assert out["success"] is True
    assert linked.community_preroll_id.endswith("St.%20Patrick_s%20Day%20Universal.mp4")
    assert renamed.community_preroll_id.endswith("Pulp_Fiction_We_Happy_Plex_Pre-roll.mp4")
    for preroll in (cut, excluded, trailer, generated, nothing):
        assert preroll.community_preroll_id is None, preroll.filename
    assert sorted(out["failed_titles"]) == ["LightSpeed.mp4", "Waldo The Movie_x264.mp4"]


def test_bulk_match_without_match_all_takes_community_downloads_only(env):
    download = add(env, "St. Patrick Day Uni.mp4", duration=11.71, description="Downloaded from Community Prerolls")
    other = add(env, "St_patrick_plex.mp4", duration=8.58)
    out = env["migrate_legacy_community_prerolls_endpoint"](match_all=False, db=env["db"])
    assert (out["matched"], out["total_scanned"]) == (1, 1)
    assert download.community_preroll_id and other.community_preroll_id is None


@pytest.mark.parametrize("servers, version", [({"plex_url": "http://plex:32400"}, "Plex"),
                                               ({"emby_url": "http://emby:8096"}, "Emby")])
def test_a_single_server_install_takes_its_version(env, servers, version):
    db = env["db"]
    db.add(models.Setting(**servers))
    preroll = add(env, "Charlie_Brown_Pumpkin_Patch-1080p.mp4", duration=15.02)
    out = env["migrate_legacy_community_prerolls_endpoint"](match_all=True, db=db)
    assert out["matched"] == 1
    assert preroll.community_preroll_id.endswith(f"Charlie%20Brown%20Pumpkin%20Patch%20-%20{version}.mp4")


def test_size_and_length_come_from_the_file_when_the_row_has_none(env):
    preroll = add(env, "St. Patrick Day Uni.mp4", write=b"x" * 10)
    assert env["_community_match_for"](MATCHER, preroll)["how"] == "title_length"
    assert env["probes"] == [preroll.path]


def test_auto_match_links_suggests_and_refuses_nexroll_files(env):
    db = env["db"]
    linked = add(env, "St_patrick_plex.mp4", duration=8.58)
    out = env["auto_match_single_preroll"](preroll_id=linked.id, db=db)
    assert out["matched"] is True and out["match_how"] == "title_length"
    assert out["community_preroll_id"] == linked.community_preroll_id

    cut = add(env, "LightSpeed.mp4", duration=4.94)
    out = env["auto_match_single_preroll"](preroll_id=cut.id, db=db)
    assert out["matched"] is False
    assert "title, different length" in [s["reason"] for s in out["similar_matches"]]
    assert cut.community_preroll_id is None

    trailer = add(env, "Weapons_1078605_trailer.mp4", duration=150.0, folder="nexup_trailers/movies")
    out = env["auto_match_single_preroll"](preroll_id=trailer.id, db=db)
    assert out["excluded"] is True and out["matched"] is False
    assert trailer.community_preroll_id is None


def test_auto_match_of_a_missing_preroll_is_a_404(env):
    with pytest.raises(HTTPException) as raised:
        env["auto_match_single_preroll"](preroll_id=999, db=env["db"])
    assert raised.value.status_code == 404


def test_export_lookup_returns_only_confident_ids(env):
    assert env["_find_community_id_for"](add(env, "St_patrick_plex.mp4", duration=8.58)).endswith(".stpatrickplex.mp4")
    assert env["_find_community_id_for"](add(env, "LightSpeed.mp4", duration=4.94)) is None
    assert env["_find_community_id_for"](add(env, "Waldo The Movie_x264.mp4", duration=130.08)) is None
    assert env["_find_community_id_for"](add(env, "Car_1_trailer.mp4", duration=9.56)) is None


def test_startup_pass_matches_old_community_downloads(env):
    download = add(env, "St. Patrick Day Uni.mp4", duration=11.71, description="Downloaded from Community Prerolls")
    unsure = add(env, "LightSpeed.mp4", duration=4.94, description="Downloaded from Community Prerolls")
    preroll_ids = (download.id, unsure.id)
    env["migrate_legacy_community_prerolls"]()
    check = env["make"]()
    _opened.append((check, check.get_bind()))
    found = {p.id: p.community_preroll_id for p in check.query(models.Preroll).filter(models.Preroll.id.in_(preroll_ids))}
    assert found[download.id].endswith("St.%20Patrick_s%20Day%20Universal.mp4")
    assert found[unsure.id] is None


def links(env, *prerolls):
    fresh = env["make"]()
    _opened.append((fresh, fresh.get_bind()))
    ids = [p.id for p in prerolls]
    found = dict(fresh.query(models.Preroll.id, models.Preroll.community_preroll_id).filter(models.Preroll.id.in_(ids)))
    return [found[i] for i in ids]


def test_matching_reports_its_progress(env):
    add(env, "St. Patrick Day Uni.mp4", duration=11.71)
    add(env, "LightSpeed.mp4", duration=4.94)
    add(env, "Weapons_1078605_trailer.mp4", duration=150.0)
    seen = []
    out = env["_match_existing_prerolls"](env["db"], True, report=lambda **fields: seen.append(fields))
    phases = [f["phase"] for f in seen if "phase" in f]
    assert phases[0] == "loading" and phases[-1] == "saving"
    assert phases.count("matching") == 2
    assert {"total": 2, "skipped": 1} in seen
    assert [f["current"] for f in seen if f.get("phase") == "matching"] == ["St. Patrick Day Uni.mp4", "LightSpeed.mp4"]
    assert seen[-1] == {"phase": "saving", "checked": 2, "current": ""}
    assert (out["matched"], out["needs_review"]) == (1, 1)


def test_the_job_runs_matching_and_keeps_the_result(env):
    preroll = add(env, "St_patrick_plex.mp4", duration=8.58)
    started = env["start_match_existing_prerolls"](match_all=True, rematch=False)
    assert started["started"] is True
    status = env["get_match_existing_status"]()
    assert (status["running"], status["phase"], status["total"], status["checked"], status["matched"]) == (False, "done", 1, 1, 1)
    assert status["result"]["matched"] == 1 and status["finished_at"]
    assert links(env, preroll)[0].endswith(".stpatrickplex.mp4")


def test_a_second_run_is_refused_while_one_is_going(env):
    env["_match_job"].update(running=True, phase="matching", total=10, checked=4)
    again = env["start_match_existing_prerolls"](match_all=True, rematch=False)
    assert again["started"] is False and again["checked"] == 4


def test_rematch_keeps_good_links_drops_wrong_ones_and_clears_nexroll_files(env):
    good = add(env, "St_patrick_plex.mp4", duration=8.58)
    good_id = f"/Archives/prerolls.video/p5/{HEX}.stpatrickplex.mp4"  # the same id comes back
    good.community_preroll_id = good_id
    wrong = add(env, "Waldo The Movie_x264.mp4", duration=130.08)
    wrong.community_preroll_id = INDEX[3]["id"]
    trailer = add(env, "Car_1_trailer.mp4", duration=9.56)
    trailer.community_preroll_id = INDEX[2]["id"]
    env["db"].commit()

    env["start_match_existing_prerolls"](match_all=False, rematch=True)

    status = env["get_match_existing_status"]()
    assert status["phase"] == "done" and status["rematch"] is True
    assert (status["result"]["cleared"], status["result"]["matched"], status["result"]["skipped"]) == (3, 1, 1)
    assert links(env, good, wrong, trailer) == [good_id, None, None]


def test_a_rematch_that_cannot_match_leaves_the_links_alone(env):
    linked = add(env, "St_patrick_plex.mp4", duration=8.58)
    linked.community_preroll_id = INDEX[5]["id"]
    env["db"].commit()
    env["_community_matcher"] = lambda: None  # no index
    env["start_match_existing_prerolls"](match_all=True, rematch=True)
    status = env["get_match_existing_status"]()
    assert status["phase"] == "done" and status["result"]["success"] is False
    assert links(env, linked) == [INDEX[5]["id"]]


def test_the_startup_pass_starts_with_the_app_not_at_import():
    tree = main_ast()
    module_calls = [n for n in tree.body if isinstance(n, ast.Expr) and "migrate_legacy_community_prerolls" in ast.unparse(n)]
    assert module_calls == []
    startup = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "startup_event")
    assert "target=migrate_legacy_community_prerolls" in ast.unparse(startup)
