import json
import os
import sys
from types import SimpleNamespace

import pytest

from backend import path_mapping


def legacy_translate(local_path, mappings, windows):
    """The translation each Plex write path carried before path_mapping,
    copied verbatim from main.py (category apply) with the platform check
    turned into a parameter."""
    try:
        lp = os.path.normpath(local_path)
        best = None
        best_src = None
        best_len = -1
        for m in mappings:
            src = os.path.normpath(str(m.get("local")))
            if windows:
                if lp.lower().startswith(src.lower()) and len(src) > best_len:
                    best, best_src, best_len = m, src, len(src)
            else:
                if lp.startswith(src) and len(src) > best_len:
                    best, best_src, best_len = m, src, len(src)
        if best:
            dst_prefix = str(best.get("plex"))
            rest = lp[len(best_src):].lstrip("\\/")
            if ("/" in dst_prefix) and ("\\" not in dst_prefix):
                return dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
            elif "\\" in dst_prefix:
                return dst_prefix.rstrip("\\") + "\\" + rest.replace("/", "\\")
            return dst_prefix.rstrip("/") + "/" + rest.replace("\\", "/")
    except Exception:
        pass
    return local_path


def local(*parts):
    """A path in this host's own style, as NeXroll stores them."""
    if sys.platform.startswith("win"):
        return "C:\\" + "\\".join(parts)
    return "/" + "/".join(parts)


MAPPINGS = [
    {"local": local("data", "prerolls"), "plex": "/Volumes/Plex/PreRoll"},
    {"local": local("data", "prerolls", "Holiday"), "plex": "\\\\NAS\\Holiday"},
    {"local": local("media"), "plex": "M:"},
    {"local": local("trailers") + os.sep, "plex": "/mnt/user/trailers/"},
]

CASES = [
    local("data", "prerolls", "Halloween", "Evil Dead 2.m4v"),
    local("data", "prerolls", "plexpreroll.mp4"),
    local("data", "prerolls", "Holiday", "Snow.mp4"),
    local("data", "prerolls", "Holiday", "Sub", "Deep.mkv"),
    local("media", "Intro.mp4"),
    local("trailers", "a", "b.mp4"),
    local("elsewhere", "x.mp4"),
    local("data", "prerolls"),
]


@pytest.mark.parametrize("windows", [False, True])
@pytest.mark.parametrize("path", CASES)
def test_matches_every_legacy_translation(path, windows):
    assert path_mapping.translate(path, MAPPINGS, windows=windows) == legacy_translate(path, MAPPINGS, windows)


def test_a_prefix_no_longer_claims_a_longer_folder_name():
    mappings = [{"local": local("data", "pre"), "plex": "/srv/pre"}]
    path = local("data", "prerolls2", "x.mp4")
    assert legacy_translate(path, mappings, False) == "/srv/pre/rolls2/x.mp4"
    assert path_mapping.translate(path, mappings, windows=False) == path
    assert path_mapping.translate_detail(path, mappings, windows=False)["matched"] is False


def test_the_longest_matching_folder_wins():
    out = path_mapping.translate(local("data", "prerolls", "Holiday", "Snow.mp4"), MAPPINGS, windows=False)
    assert out == "\\\\NAS\\Holiday\\Snow.mp4"


def test_windows_hosts_ignore_case_and_others_do_not():
    mappings = [{"local": local("Data", "PreRolls"), "plex": "/p"}]
    path = local("data", "prerolls", "x.mp4")
    assert path_mapping.translate(path, mappings, windows=True) == "/p/x.mp4"
    assert path_mapping.translate(path, mappings, windows=False) == path


def test_a_folder_itself_keeps_the_trailing_separator():
    out = path_mapping.translate(local("data", "prerolls"), MAPPINGS, windows=False)
    assert out == "/Volumes/Plex/PreRoll/"


def test_detail_names_the_mapping_used():
    d = path_mapping.translate_detail(local("media", "Intro.mp4"), MAPPINGS, windows=False)
    assert d["matched"] is True
    assert d["output"] == "M:/Intro.mp4"
    assert d["mapping"]["plex"] == "M:"


@pytest.mark.parametrize("raw,count", [
    (None, 0), ("", 0), ("not json", 0), ("{}", 0),
    (json.dumps([{"local": "/a", "plex": "/b"}, {"local": "", "plex": "/c"}, "junk", {"plex": "/d"}]), 1),
    ([{"local": "/a", "plex": "/b"}], 1),
])
def test_load_mappings_keeps_only_complete_pairs(raw, count):
    assert len(path_mapping.load_mappings(raw)) == count


def test_mappings_from_setting_reads_the_row():
    row = SimpleNamespace(path_mappings=json.dumps([{"local": "/a", "plex": "/b"}]))
    assert path_mapping.mappings_from_setting(row) == [{"local": "/a", "plex": "/b"}]
    assert path_mapping.mappings_from_setting(None) == []


@pytest.mark.parametrize("path,style", [
    ("/data/x.mp4", "posixpath"),
    ("C:\\Prerolls\\x.mp4", "ntpath"),
    ("D:/Prerolls/x.mp4", "ntpath"),
    ("\\\\NAS\\share\\x.mp4", "ntpath"),
    ("relative\\x.mp4", "ntpath"),
    ("", "posixpath"),
])
def test_plex_path_style_is_read_from_the_path(path, style):
    assert path_mapping.plex_path_module(path).__name__ == style
