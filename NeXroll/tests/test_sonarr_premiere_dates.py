"""Sonarr premieres are dated as Sonarr shows them, and unmonitored ones can be included.

User report on 2.2.9 (Canada/Eastern): Dexter: Resurrection S2 airs Nov 1 at
8 PM in Sonarr but NeXroll listed it on Nov 2. Premieres were dated by
airDateUtc (2026-11-02T01:00:00Z); they now use airDate, the network's own
date (2026-11-01, as on JB's Sonarr 4.0.20). The calendar is asked a day
back, since Sonarr filters it on UTC air times.

Sonarr's calendar also leaves out unmonitored series and episodes unless sent
unmonitored=true (checked on Sonarr 4.0.20), so "Include Unmonitored TV Shows"
never worked for the Coming Soon list or the Upcoming page. NeXroll now asks
for them and filters them itself.
"""

import asyncio
import datetime
from unittest.mock import patch

import httpx

from backend.sonarr_connector import SonarrConnector

TODAY = datetime.datetime.now().date()


def _episode(series_id, title, air_date, air_date_utc, has_file=False, season=2,
             monitored=True, series_monitored=True):
    episode = {
        "seriesId": series_id,
        "seasonNumber": season,
        "episodeNumber": 1,
        "airDateUtc": air_date_utc,
        "hasFile": has_file,
        "monitored": monitored,
        "title": "Episode 1",
        "series": {"id": series_id, "title": title, "monitored": series_monitored, "images": []},
    }
    if air_date is not None:
        episode["airDate"] = air_date
    return episode


def _utc(day, hour):
    return datetime.datetime.combine(day, datetime.time(hour)).isoformat() + "Z"


def _premieres(calendar, recent_days=0):
    calls = []

    async def fake_calendar(self, start_date=None, end_date=None):
        calls.append((start_date, end_date))
        # Like Sonarr: only episodes inside [start, end] by UTC air time.
        return [e for e in calendar
                if start_date.date() <= datetime.datetime.fromisoformat(e["airDateUtc"][:19]).date() <= end_date.date()]

    with patch.object(SonarrConnector, "get_calendar", fake_calendar):
        shows = asyncio.run(SonarrConnector("http://sonarr.invalid", "key").get_upcoming_premieres(90, recent_days=recent_days))
    return shows, calls


def test_an_evening_premiere_keeps_its_own_date():
    # 8 PM Eastern on day 3 is 01:00 UTC on day 4.
    day = TODAY + datetime.timedelta(days=3)
    shows, _ = _premieres([_episode(1, "Evening Show", day.isoformat(), _utc(day + datetime.timedelta(days=1), 1))])
    assert shows[0]["release_date"] == day.isoformat()
    assert shows[0]["days_until_release"] == 3


def test_a_premiere_dated_today_that_was_yesterday_in_utc_is_listed():
    # An early-morning premiere east of UTC (Tokyo 05:00 is 20:00 UTC the day before).
    yesterday = TODAY - datetime.timedelta(days=1)
    shows, calls = _premieres([_episode(2, "Morning Show", TODAY.isoformat(), _utc(yesterday, 20))])
    assert calls[0][0].date() == yesterday
    assert [(s["title"], s["release_date"], s["days_until_release"]) for s in shows] == [
        ("Morning Show", TODAY.isoformat(), 0)]


def test_a_premiere_from_yesterday_still_drops_off_without_a_window():
    yesterday = TODAY - datetime.timedelta(days=1)
    shows, _ = _premieres([_episode(3, "Yesterday", yesterday.isoformat(), _utc(yesterday, 12), has_file=True)])
    assert shows == []


def test_the_available_now_window_counts_from_the_networks_date():
    # Aired 8 PM Eastern seven days ago (UTC: six days ago), downloaded.
    aired = TODAY - datetime.timedelta(days=7)
    calendar = [_episode(4, "Week Old", aired.isoformat(), _utc(aired + datetime.timedelta(days=1), 1), has_file=True)]
    shows, _ = _premieres(calendar, recent_days=7)
    assert [(s["release_date"], s["days_until_release"]) for s in shows] == [(aired.isoformat(), -7)]
    shows, _ = _premieres(calendar, recent_days=6)
    assert shows == []


def test_without_air_date_the_utc_date_is_used():
    day = TODAY + datetime.timedelta(days=5)
    shows, _ = _premieres([_episode(5, "No Local Date", None, _utc(day, 1))])
    assert shows[0]["release_date"] == day.isoformat()


# --- Unmonitored -----------------------------------------------------------

def test_the_calendar_asks_sonarr_for_unmonitored_episodes():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=[])

    real_client = httpx.AsyncClient
    with patch("backend.sonarr_connector.httpx.AsyncClient",
               lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)):
        asyncio.run(SonarrConnector("http://sonarr.invalid", "key").fetch_calendar(
            datetime.datetime(2026, 10, 1), datetime.datetime(2026, 10, 2)))
    assert seen["unmonitored"] == "true"
    assert seen["includeSeries"] == "true"


UNMONITORED = [
    _episode(6, "Monitored", (TODAY + datetime.timedelta(days=2)).isoformat(), _utc(TODAY + datetime.timedelta(days=2), 12)),
    _episode(7, "Unmonitored Season", (TODAY + datetime.timedelta(days=3)).isoformat(),
             _utc(TODAY + datetime.timedelta(days=3), 12), monitored=False),
    _episode(8, "Unmonitored Series", (TODAY + datetime.timedelta(days=4)).isoformat(),
             _utc(TODAY + datetime.timedelta(days=4), 12), series_monitored=False),
]


def test_unmonitored_seasons_and_series_are_left_out_by_default():
    shows = SonarrConnector("http://sonarr.invalid", "key").premieres_from_calendar(UNMONITORED)
    assert [s["title"] for s in shows] == ["Monitored"]


def test_include_unmonitored_lists_them():
    shows = SonarrConnector("http://sonarr.invalid", "key").premieres_from_calendar(UNMONITORED, include_unmonitored=True)
    assert [s["title"] for s in shows] == ["Monitored", "Unmonitored Season", "Unmonitored Series"]
