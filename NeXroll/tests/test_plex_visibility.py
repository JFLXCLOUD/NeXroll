import base64
import urllib.parse
from unittest.mock import Mock, patch

import pytest

from backend import plex_visibility as pv


class FakePlex:
    """Answers /services/browse the way a real server does, from a dict of
    folder -> (subfolder names, file names). Folders not in the dict come back
    empty, which is what Plex returns for a folder it cannot see."""

    def __init__(self, tree, roots=None, platform="Linux", refuse=False, fail=(), libraries=()):
        self.tree = tree
        self.roots = roots if roots is not None else sorted(p for p in tree if p.count("/") == 1 and p != "/")
        self.platform = platform
        self.refuse = refuse
        self.fail = set(fail)
        self.libraries = list(libraries)
        self.requests = []

    def _sep(self, path):
        return "\\" if ("\\" in path or (len(path) > 1 and path[1] == ":")) else "/"

    def _child(self, folder, name):
        sep = self._sep(folder)
        return folder.rstrip("/\\") + sep + name if folder not in ("/",) else "/" + name

    def get(self, url, headers=None, params=None, timeout=None, verify=None, allow_redirects=None):
        path = url.split("http://plex:32400", 1)[1]
        self.requests.append(path)
        res = Mock()
        res.status_code = 401 if self.refuse else 200
        if path == "/":
            res.json.return_value = {"MediaContainer": {"platform": self.platform}}
        elif path == "/library/sections":
            res.json.return_value = {"MediaContainer": {"Directory": [
                {"type": "movie", "Location": [{"path": loc}]} for loc in self.libraries]}}
        elif path == "/services/browse":
            res.json.return_value = {"MediaContainer": {"Path": [{"path": r, "title": r} for r in self.roots]}}
        else:
            folder = base64.b64decode(urllib.parse.unquote(path.rsplit("/", 1)[1])).decode("utf-8")
            if folder in self.fail:
                res.status_code = 500
            dirs, files = self.tree.get(folder, ([], []))
            res.json.return_value = {"MediaContainer": {
                "Path": [{"title": d, "path": self._child(folder, d)} for d in dirs],
                "File": [{"title": f, "path": self._child(folder, f)} for f in files],
            }}
        return res


TREE = {
    "/": (["data", "Volumes"], []),
    "/data": (["MEDIA", "Prerolls"], []),
    "/data/MEDIA": (["Movies"], []),
    "/data/MEDIA/Movies": (["Alien (1979)"], []),
    "/data/Prerolls": (["Halloween", "Fake Trailers"], ["BTTJFLX.mp4", "Dem_JFLX.mp4"]),
    "/data/Prerolls/Halloween": ([], ["plexpreroll-EvilDead2.m4v", "Cafe\u0301.mp4"]),
    "/data/Prerolls/Fake Trailers": ([], ["20thCenturyFox-Flute.mp4"]),
    "/Volumes": (["Plex"], []),
    # /Volumes/Plex exists but lists as empty: the macOS permission case.
}


@pytest.fixture(autouse=True)
def fresh_state():
    pv.reset_state()
    yield
    pv.reset_state()


def files_for(fake, **kw):
    return pv.PlexFiles("http://plex:32400", "secret", **kw)


def run(fake, fn):
    with patch.object(pv.requests, "get", side_effect=fake.get):
        return fn()


def test_a_file_plex_lists_is_visible():
    fake = FakePlex(TREE)
    f = files_for(fake)
    assert run(fake, lambda: f.status("/data/Prerolls/Halloween/plexpreroll-EvilDead2.m4v"))[0] == pv.VISIBLE


def test_decomposed_accents_and_case_still_match():
    fake = FakePlex(TREE)
    f = files_for(fake)
    assert run(fake, lambda: f.status("/data/Prerolls/Halloween/Caf\u00e9.mp4"))[0] == pv.VISIBLE
    assert run(fake, lambda: f.status("/data/Prerolls/halloween/PLEXPREROLL-EVILDEAD2.M4V"))[0] in (pv.VISIBLE, pv.MISSING)


def test_a_file_absent_from_a_listed_folder_is_missing():
    fake = FakePlex(TREE)
    state, reason = run(fake, lambda: files_for(fake).status("/data/Prerolls/Halloween/gone.mp4"))
    assert state == pv.MISSING
    assert "/data/Prerolls/Halloween" in reason


def test_a_docker_only_folder_is_missing_when_its_parent_is_listed():
    fake = FakePlex(TREE)
    state, reason = run(fake, lambda: files_for(fake).status("/data/nexroll/Halloween/x.mp4"))
    assert state == pv.MISSING
    assert "no folder /data/nexroll" in reason


def test_a_folder_differing_only_in_case_is_named():
    # Linux Plex has /data/Prerolls; a Docker NeXroll might say /data/prerolls.
    fake = FakePlex(TREE)
    state, reason = run(fake, lambda: files_for(fake).status("/data/prerolls/Halloween/x.mp4"))
    assert state == pv.MISSING
    assert "Plex has /data/Prerolls, not /data/prerolls" in reason
    assert "Letter case" in reason


def test_a_folder_plex_can_see_but_not_read_says_so():
    fake = FakePlex(TREE)
    state, reason = run(fake, lambda: files_for(fake).status("/Volumes/Plex/PreRoll/x.m4v"))
    assert state == pv.MISSING
    assert "cannot read anything in it" in reason and "network volumes" in reason


def test_nothing_listable_up_the_tree_is_unknown_not_missing():
    # A UNC share Plex's browser cannot list at all must not be called missing.
    fake = FakePlex({}, roots=["C:\\"], platform="Windows")
    state, _ = run(fake, lambda: files_for(fake).status("\\\\NAS\\PreRoll\\Halloween\\x.mp4"))
    assert state == pv.UNKNOWN


def test_a_refused_or_failing_check_is_unknown():
    for fake in (FakePlex(TREE, refuse=True), FakePlex(TREE, fail={"/data/Prerolls/Halloween"})):
        state, _ = run(fake, lambda: files_for(fake).status("/data/Prerolls/Halloween/x.mp4"))
        assert state == pv.UNKNOWN


@pytest.mark.parametrize("path", ["C:\\ProgramData\\NeXroll\\Prerolls\\Default\\a.mp4", "\\\\NAS\\PreRoll\\a.mp4"])
def test_a_windows_path_on_a_linux_or_mac_plex_is_missing(path):
    for platform in ("Linux", "MacOSX"):
        fake = FakePlex(TREE, platform=platform)
        state, reason = run(fake, lambda: files_for(fake).status(path))
        assert state == pv.MISSING and f"Plex runs on {platform}" in reason


def test_windows_style_paths_walk_up_to_the_drive():
    tree = {"C:\\": (["Prerolls"], []), "C:\\Prerolls": ([], ["a.mp4"])}
    fake = FakePlex(tree, roots=["C:\\"], platform="Windows")
    f = files_for(fake)
    assert run(fake, lambda: f.status("C:\\Prerolls\\a.mp4"))[0] == pv.VISIBLE
    assert run(fake, lambda: f.status("C:\\Prerolls\\b.mp4"))[0] == pv.MISSING
    assert run(fake, lambda: f.status("C:\\Nope\\b.mp4"))[0] == pv.MISSING


@pytest.mark.parametrize("value,delim,count", [
    ("/a/x.mp4", None, 1),
    ("/a/x.mp4;/a/y.mkv", ";", 2),
    ("/a/x.mp4,/a/y.mkv", ",", 2),
    ("/a/Movie, The.mp4;/a/y.mp4", ";", 2),
    ("", None, 0),
])
def test_split_follows_plex_separators(value, delim, count):
    d, paths = pv.split_preroll_value(value)
    assert d == delim and len(paths) == count


def test_a_comma_inside_a_single_filename_is_not_split():
    assert pv.split_preroll_value("/a/Movie, The.mp4")[1] is None


def test_gate_writes_everything_when_plex_sees_it_all():
    fake = FakePlex(TREE)
    value = "/data/Prerolls/BTTJFLX.mp4;/data/Prerolls/Halloween/plexpreroll-EvilDead2.m4v"
    g = run(fake, lambda: pv.gate_preroll_value(files_for(fake), value, retry_delay=0))
    assert (g.action, g.value) == ("ok", value)


def test_gate_drops_missing_files_and_keeps_order():
    fake = FakePlex(TREE)
    value = "/data/Prerolls/Dem_JFLX.mp4,/data/Prerolls/gone.mp4,/data/Prerolls/BTTJFLX.mp4"
    g = run(fake, lambda: pv.gate_preroll_value(files_for(fake), value, retry_delay=0))
    assert g.action == "filtered"
    assert g.value == "/data/Prerolls/Dem_JFLX.mp4,/data/Prerolls/BTTJFLX.mp4"
    assert pv.last_report()["missing_count"] == 1


def test_gate_withholds_when_nothing_is_visible():
    fake = FakePlex(TREE)
    value = "/data/prerolls/a.mp4;/data/prerolls/b.mp4"
    g = run(fake, lambda: pv.gate_preroll_value(files_for(fake), value, retry_delay=0))
    assert g.action == "withheld"
    assert "left Plex's current prerolls in place" in g.message


def test_gate_keeps_unknown_files():
    fake = FakePlex(TREE, fail={"/data/Prerolls/Halloween"})
    value = "/data/Prerolls/Halloween/a.mp4;/data/Prerolls/gone.mp4"
    g = run(fake, lambda: pv.gate_preroll_value(files_for(fake), value, retry_delay=0))
    assert g.action == "filtered" and g.value == "/data/Prerolls/Halloween/a.mp4"


def test_gate_writes_unchanged_when_nothing_could_be_checked():
    fake = FakePlex(TREE, refuse=True)
    g = run(fake, lambda: pv.gate_preroll_value(files_for(fake), "/x/a.mp4;/x/b.mp4", retry_delay=0))
    assert (g.action, g.value) == ("unverified", "/x/a.mp4;/x/b.mp4")


def test_gate_rechecks_missing_files_once(monkeypatch):
    tree = dict(TREE)
    fake = FakePlex(tree)
    slept = []

    def appear(seconds):
        slept.append(seconds)
        tree["/data/Prerolls/Halloween"] = ([], ["new.mp4"])

    monkeypatch.setattr(pv.time, "sleep", appear)
    g = run(fake, lambda: pv.gate_preroll_value(files_for(fake), "/data/Prerolls/Halloween/new.mp4", retry_delay=2))
    assert slept == [2] and g.action == "ok"


def test_gate_can_be_turned_off(monkeypatch):
    monkeypatch.setenv("NEXROLL_PLEX_PATH_CHECK", "0")
    g = pv.gate_preroll_value(Mock(), "/x/a.mp4")
    assert (g.action, g.value) == ("skipped", "/x/a.mp4")


def test_listings_are_cached_but_a_miss_is_asked_again():
    fake = FakePlex(TREE)
    f = files_for(fake)
    run(fake, lambda: f.status("/data/Prerolls/BTTJFLX.mp4"))
    run(fake, lambda: f.status("/data/Prerolls/Dem_JFLX.mp4"))
    assert fake.requests.count(fake.requests[0]) == 1
    run(fake, lambda: f.status("/data/Prerolls/gone.mp4"))
    assert fake.requests.count(fake.requests[0]) == 2


def test_budget_exhaustion_is_unknown():
    fake = FakePlex(TREE)
    f = files_for(fake, max_calls=0)
    assert run(fake, lambda: f.status("/data/Prerolls/BTTJFLX.mp4"))[0] == pv.UNKNOWN


def test_find_folder_locates_prerolls_by_content():
    fake = FakePlex(TREE)
    known = ["BTTJFLX.mp4", "Halloween/plexpreroll-EvilDead2.m4v", "Fake Trailers/20thCenturyFox-Flute.mp4"]
    res = run(fake, lambda: pv.find_folder(files_for(fake), known, "prerolls", ["/data/MEDIA/Movies"]))
    assert res["found"] and res["plex_path"] == "/data/Prerolls"


def test_find_folder_refuses_a_folder_that_only_shares_filenames():
    fake = FakePlex(TREE)
    known = ["Default/BTTJFLX.mp4", "Default/Dem_JFLX.mp4"]
    res = run(fake, lambda: pv.find_folder(files_for(fake), known))
    assert not res["found"]


def test_find_folder_explains_a_refusal():
    fake = FakePlex(TREE, refuse=True)
    res = run(fake, lambda: pv.find_folder(files_for(fake), ["a.mp4"]))
    assert not res["found"] and "owner" in res["reason"]


def test_find_folder_needs_something_to_look_for():
    assert not pv.find_folder(Mock(), [])["found"]


@pytest.mark.parametrize("path,parent,name", [
    ("/data/Prerolls/a.mp4", "/data/Prerolls", "a.mp4"),
    ("/data", "/", "data"),
    ("C:\\Prerolls\\x.mp4", "C:\\Prerolls", "x.mp4"),
    ("C:\\Prerolls", "C:\\", "Prerolls"),
    ("\\\\NAS\\share\\dir\\x.mp4", "\\\\NAS\\share\\dir", "x.mp4"),
    ("\\\\NAS\\share\\dir", "\\\\NAS\\share\\", "dir"),
])
def test_parent_of_each_path_style(path, parent, name):
    assert pv.PlexFiles("http://plex", "t")._parent(path) == (parent, name)
