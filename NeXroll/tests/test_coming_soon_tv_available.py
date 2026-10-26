"""TV shows must be able to show "Available Now!" on the Coming Soon list.

User report on 2.2.8: a downloaded show never showed "Available Now!". The
list asked Sonarr only for premieres from today onward, and a premiere is only
downloaded after it airs, so a show was already off the list by the time it
could be available. get_upcoming_premieres(recent_days=N) now also returns
premieres from the last N days that Sonarr has downloaded; the Coming Soon
list, its preview and the Upcoming page pass the Available Now window, and the
TV trailer sync keeps looking forward only.
"""

import ast
import asyncio
import datetime
from pathlib import Path
from unittest.mock import patch

from backend.sonarr_connector import SonarrConnector

TODAY = datetime.datetime.now().date()


def _episode(series_id, title, season, offset, has_file, episode=1):
    # Noon UTC keeps the UTC air date on the same calendar day as TODAY.
    aired = datetime.datetime.combine(TODAY + datetime.timedelta(days=offset), datetime.time(12))
    return {
        "seriesId": series_id,
        "seasonNumber": season,
        "episodeNumber": episode,
        "airDate": aired.date().isoformat(),
        "airDateUtc": aired.isoformat() + "Z",
        "hasFile": has_file,
        "title": f"Episode {episode}",
        "series": {"id": series_id, "title": title, "monitored": True, "images": []},
    }


CALENDAR = [
    _episode(1, "Aired Long Ago", 2, -12, True),
    _episode(2, "Outside The Window", 1, -8, True),
    _episode(3, "Downloaded Four Days Ago", 1, -4, True),
    _episode(4, "Aired Not Downloaded", 3, -2, False),
    _episode(5, "Second Episode Only", 2, -1, True, episode=2),
    _episode(6, "Special", 0, -1, True),
    _episode(7, "Premieres Today", 1, 0, False),
    _episode(8, "Premieres Next Week", 4, 7, False),
]


def _premieres(recent_days=None, calendar=CALENDAR):
    calls = []

    async def fake_calendar(self, start_date=None, end_date=None):
        calls.append((start_date, end_date))
        # Like Sonarr: only episodes inside [start, end] by date.
        return [e for e in calendar
                if start_date.date() <= datetime.date.fromisoformat(e["airDate"]) <= end_date.date()]

    connector = SonarrConnector("http://sonarr.invalid", "key")
    kwargs = {} if recent_days is None else {"recent_days": recent_days}
    with patch.object(SonarrConnector, "get_calendar", fake_calendar):
        shows = asyncio.run(connector.get_upcoming_premieres(90, **kwargs))
    return shows, calls


def _titles(shows):
    return [s["title"] for s in shows]


def test_without_a_window_only_today_onward_is_returned():
    shows, calls = _premieres()
    assert _titles(shows) == ["Premieres Today", "Premieres Next Week"]
    assert calls[0][0].date() == TODAY


def test_downloaded_premiere_inside_the_window_is_returned_as_available():
    shows, _ = _premieres(recent_days=7)
    assert "Downloaded Four Days Ago" in _titles(shows)
    show = next(s for s in shows if s["title"] == "Downloaded Four Days Ago")
    assert show["has_file"] is True
    assert show["days_until_release"] == -4
    assert show["release_date"] == (TODAY - datetime.timedelta(days=4)).isoformat()


def test_window_lists_recent_downloads_first_then_upcoming():
    shows, _ = _premieres(recent_days=7)
    assert _titles(shows) == ["Downloaded Four Days Ago", "Premieres Today", "Premieres Next Week"]


def test_aired_premiere_that_is_not_downloaded_is_left_out():
    shows, _ = _premieres(recent_days=7)
    assert "Aired Not Downloaded" not in _titles(shows)


def test_downloaded_premiere_older_than_the_window_is_left_out():
    shows, calls = _premieres(recent_days=7)
    # The calendar is asked one extra day back, so this one comes back from
    # Sonarr and has to be dropped here.
    assert calls[0][0].date() == TODAY - datetime.timedelta(days=8)
    assert "Outside The Window" not in _titles(shows)
    assert "Aired Long Ago" not in _titles(shows)


def test_window_edges():
    shows, _ = _premieres(recent_days=4)
    assert "Downloaded Four Days Ago" in _titles(shows)
    shows, _ = _premieres(recent_days=3)
    assert "Downloaded Four Days Ago" not in _titles(shows)


def test_widest_window_reaches_thirty_days():
    calendar = [_episode(9, "Thirty Days Ago", 1, -30, True), _episode(10, "Thirty One Days Ago", 1, -31, True)]
    shows, _ = _premieres(recent_days=30, calendar=calendar)
    assert _titles(shows) == ["Thirty Days Ago"]


def test_later_episodes_and_specials_are_still_not_premieres():
    shows, _ = _premieres(recent_days=7)
    assert "Second Episode Only" not in _titles(shows)
    assert "Special" not in _titles(shows)


def test_a_series_can_have_an_available_season_and_an_upcoming_one():
    calendar = [_episode(11, "Two Seasons", 2, -3, True), _episode(11, "Two Seasons", 3, 20, False)]
    shows, _ = _premieres(recent_days=7, calendar=calendar)
    assert [(s["title"], s["season_number"], s["has_file"]) for s in shows] == [
        ("Two Seasons", 2, True), ("Two Seasons", 3, False)]


def test_unmonitored_series_stay_out_of_the_window_too():
    episode = _episode(12, "Unmonitored", 1, -2, True)
    episode["series"]["monitored"] = False
    shows, _ = _premieres(recent_days=7, calendar=[episode])
    assert shows == []


def test_bad_window_values_mean_no_window():
    for value in (0, None, -5):
        shows, calls = _premieres(recent_days=value)
        assert _titles(shows) == ["Premieres Today", "Premieres Next Week"]
        assert calls[0][0].date() == TODAY


# --- Who passes the window -------------------------------------------------

def _premiere_calls():
    tree = ast.parse((Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8"))
    found = {}
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(fn):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get_upcoming_premieres"):
                window = next((k.value for k in node.keywords if k.arg == "recent_days"), None)
                found.setdefault(fn.name, []).append(ast.unparse(window) if window is not None else None)
    return found


def test_coming_soon_list_and_upcoming_page_pass_the_available_now_window():
    calls = _premiere_calls()
    for name in ("generate_coming_soon_list", "_auto_regenerate_coming_soon_list",
                 "preview_coming_soon_list", "get_upcoming_shows"):
        assert calls.get(name) == ["available_days"], name


def test_tv_trailer_sync_does_not_fetch_shows_that_already_aired():
    assert _premiere_calls().get("sync_sonarr_trailers") == [None]
