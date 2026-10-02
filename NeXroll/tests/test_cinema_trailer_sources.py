import urllib.parse
from unittest.mock import Mock, patch

from backend import plex_connector as pc


class FakePrefs:
    """A Plex /:/prefs endpoint: GET lists the settings, PUT changes one.
    Booleans come back as '1'/'0' the way a real server stores them."""

    def __init__(self, values, reject=()):
        self.values = dict(values)
        self.reject = set(reject)
        self.puts = []

    def get(self, url, headers=None, timeout=None, verify=None):
        settings = "".join(
            f'<Setting id="{sid}" type="{"enum" if sid == "CinemaTrailersType" else "bool"}" value="{value}"/>'
            for sid, value in self.values.items()
        )
        return Mock(status_code=200, content=f"<MediaContainer>{settings}</MediaContainer>".encode())

    def put(self, url, headers=None, timeout=None, verify=None):
        key, _, value = url.split("?", 1)[1].partition("=")
        self.puts.append((key, urllib.parse.unquote(value)))
        if key in self.reject:
            return Mock(status_code=400, text="rejected")
        self.values[key] = "1" if value == "true" else "0" if value == "false" else value
        return Mock(status_code=200, text="")


def run(fake, fn):
    with patch.object(pc.requests, "get", side_effect=fake.get), \
         patch.object(pc.requests, "put", side_effect=fake.put):
        return fn(pc.PlexConnector("http://plex:32400", "secret"))


PLEX_PASS = {
    "CinemaTrailersType": "0",
    "CinemaTrailersFromLibrary": "1",
    "CinemaTrailersFromTheater": "1",
    "CinemaTrailersFromBluRay": "0",
    "CinemaTrailersAlwaysIncludeEnglish": "1",
}


def test_turns_off_only_sources_that_are_on_and_leaves_other_settings():
    fake = FakePrefs(PLEX_PASS)
    result = run(fake, lambda c: c.disable_trailer_sources())
    assert result == {"changed": ["CinemaTrailersFromLibrary", "CinemaTrailersFromTheater"], "failed": []}
    assert [key for key, _ in fake.puts] == ["CinemaTrailersFromLibrary", "CinemaTrailersFromTheater"]
    assert fake.values["CinemaTrailersAlwaysIncludeEnglish"] == "1"
    assert fake.values["CinemaTrailersType"] == "0"
    assert all(fake.values[sid] == "0" for sid in pc.PlexConnector.CINEMA_TRAILER_SOURCE_IDS)


def test_server_without_plex_pass_only_has_the_library_source():
    fake = FakePrefs({"CinemaTrailersType": "0", "CinemaTrailersFromLibrary": "1"})
    assert run(fake, lambda c: c.disable_trailer_sources()) == {"changed": ["CinemaTrailersFromLibrary"], "failed": []}
    assert fake.values["CinemaTrailersFromLibrary"] == "0"


def test_nothing_is_written_when_sources_are_already_off():
    fake = FakePrefs({**PLEX_PASS, "CinemaTrailersFromLibrary": "0", "CinemaTrailersFromTheater": "0"})
    assert run(fake, lambda c: c.disable_trailer_sources()) == {"changed": [], "failed": []}
    assert fake.puts == []


def test_a_rejected_source_is_reported_and_the_rest_still_change():
    fake = FakePrefs(PLEX_PASS, reject={"CinemaTrailersFromTheater"})
    result = run(fake, lambda c: c.disable_trailer_sources())
    assert result == {"changed": ["CinemaTrailersFromLibrary"], "failed": ["CinemaTrailersFromTheater"]}
    assert fake.values["CinemaTrailersFromTheater"] == "1"


def test_unreadable_prefs_return_none():
    fake = FakePrefs({})
    fake.get = lambda *a, **k: Mock(status_code=401, content=b"")
    assert run(fake, lambda c: c.disable_trailer_sources()) is None
    assert fake.puts == []
