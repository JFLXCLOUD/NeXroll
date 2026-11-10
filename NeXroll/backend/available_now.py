"""The "Available Now!" window for titles Radarr or Sonarr has downloaded.

Days visible (``nexup_coming_soon_available_days``) is counted on two clocks:

- Coming Soon lists and the Upcoming pages count from the release date. A
  title downloaded before it is out stays "Available Now!" until its release
  date plus Days visible; one downloaded later drops off at the same point.
- A NeX-Up trailer counts from ``available_at``: the first sync that saw its
  movie (or season) downloaded. The trailer keeps playing for Days visible
  days after the title arrives, then the sync removes it.

``downloaded_at`` on a trailer row is when the *trailer* was downloaded, often
weeks before the movie, so it can't start either window. Counting from it made
a movie vanish from the Upcoming page the moment Radarr got it, and made every
sync delete its trailer straight away (user report, November 2026: The Odyssey
downloaded before its digital release).
"""
import datetime
from typing import Iterable, List, Optional


def days_visible(setting) -> int:
    """The saved Days visible setting (1-30; the settings endpoint clamps it)."""
    try:
        return int(getattr(setting, "nexup_coming_soon_available_days", 1) or 1)
    except (TypeError, ValueError):
        return 1


def as_date(value) -> Optional[datetime.date]:
    """A stored or reported date (date, datetime or ISO text) as a date."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    try:
        return datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def release_window_passed(release_date, available_days: int, today: Optional[datetime.date] = None) -> bool:
    """True once a downloaded title's release date is more than Days visible
    days ago: the Coming Soon list's rule. A future release date never passes,
    and neither does a missing or unreadable one (the list keeps those)."""
    released = as_date(release_date)
    if released is None:
        return False
    return ((today or datetime.date.today()) - released).days > available_days


def track_arrival(trailer, downloaded: bool, now: datetime.datetime, clear: bool = True) -> bool:
    """Start a trailer's window the first time its title is downloaded, and
    clear it when Radarr/Sonarr reports the title without a file again (a
    deleted copy), so a later download starts a fresh window. Only call this
    for titles a server actually reported: one that couldn't be read says
    nothing. Pass clear=False when any server couldn't be read: the copy with
    the file may be on that one, and clearing would restart the window once it
    is back. True when the window starts now."""
    if downloaded:
        if trailer.available_at is None:
            trailer.available_at = now
            return True
        return False
    if clear and trailer.available_at is not None:
        trailer.available_at = None
    return False


def trailer_window_passed(trailer, available_days: int, now: datetime.datetime) -> bool:
    """True once the title has been downloaded for more than Days visible days."""
    arrived = trailer.available_at
    return arrived is not None and (now - arrived).days > available_days


def trailer_removal_date(available_at, available_days: int) -> Optional[datetime.datetime]:
    """The first moment a sync removes the trailer of a title that arrived at
    ``available_at``; None while the title isn't downloaded."""
    if available_at is None:
        return None
    return available_at + datetime.timedelta(days=available_days + 1)


def movie_trailers_past_window(trailers: Iterable, reported_ids, downloaded_ids, available_days: int,
                               now: datetime.datetime, on_arrival=None, complete: bool = True) -> List:
    """For a movie sync: note arrivals on every trailer whose movie a Radarr
    reported, and return the trailers whose movie has now been downloaded for
    longer than Days visible. Movies on a Radarr that couldn't be read are not
    in ``reported_ids`` and are left as they are; with complete=False (some
    Radarr failed) an arrival is never cleared, since another server reporting
    the movie without a file doesn't mean the failed one lost it. The caller
    commits and removes the returned trailers."""
    past = []
    for trailer in trailers:
        if trailer.radarr_movie_id not in reported_ids:
            continue
        downloaded = trailer.radarr_movie_id in downloaded_ids
        if track_arrival(trailer, downloaded, now, clear=complete) and on_arrival is not None:
            on_arrival(trailer)
        if downloaded and trailer_window_passed(trailer, available_days, now):
            past.append(trailer)
    return past
