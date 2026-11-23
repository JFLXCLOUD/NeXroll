"""YouTube's age gate is not a bot block.

YouTube answers "Sign in to confirm your age" for an age-restricted video and
"Sign in to confirm you're not a bot" when it walls off a client. The
classifier looked for the bot wall first, so every age-restricted trailer was
reported as a bot block: on production (November 2026) the Library Trailers
sync logged "YouTube bot detection" five times for Evil Dead II, and the NeX-Up
Sync button would have told the user to re-export cookies and written an ERROR
event. Every trailer path uses TrailerDownloader, so the fix covers them all.
"""
import ast
import asyncio
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import yt_dlp

from backend import nexup_potoken
from backend.radarr_connector import TrailerDownloader, classify_ytdlp_error

# Copied from production's app.log (November 18, 2026), cut at 300 characters
# as _download_with_ytdlp keeps it.
AGE_GATE = ("ERROR: [youtube] s7WNgzilRBw: Sign in to confirm your age. This video may be inappropriate "
            "for some users. Use --cookies-from-browser or --cookies for the authentication. See  "
            "https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-pass-cookies-to-yt-dlp  for how to "
            "manually pass cookies. Also see  https")
BOT_WALL = ("ERROR: [youtube] abc123def45: Sign in to confirm you’re not a bot. Use --cookies-from-browser "
            "or --cookies for the authentication. See  https://github.com/yt-dlp/yt-dlp/wiki/FAQ#how-do-i-"
            "pass-cookies-to-yt-dlp  for how to manually pass cookies.")
RADARR_URL = "https://www.youtube.com/watch?v=s7WNgzilRBw"


@pytest.mark.parametrize("message", [
    AGE_GATE,
    "ERROR: [youtube] x: This video is age-restricted and only available on YouTube.",
    "ERROR: [youtube] x: Age restricted video. Sign in to view it.",
])
def test_the_age_gate_is_age_restricted(message):
    assert classify_ytdlp_error(message)["category"] == "age_restricted"


@pytest.mark.parametrize("message", [
    BOT_WALL,
    BOT_WALL.replace("’", "'"),
    "ERROR: [youtube] x: Sign in to confirm you're not a bot. This helps protect our community. Learn more on the help page.",
])
def test_the_bot_wall_is_still_a_sign_in_problem(message):
    assert classify_ytdlp_error(message)["category"] == "auth"


@pytest.mark.parametrize("message,category", [
    ("ERROR: [youtube] x: Video unavailable. This video is private", "video_unavailable"),
    ("ERROR: [youtube] x: HTTP Error 429: Too Many Requests", "rate_limited"),
    ("ERROR: [youtube] x: Requested format is not available", "reachable"),
    # "page" and "restricted" without the word "age": the old loose check
    # ('age' anywhere plus 'restrict') would have called this age-restricted.
    ("ERROR: Unable to download webpage: restricted network", "other"),
])
def test_other_failures_keep_their_categories(message, category):
    assert classify_ytdlp_error(message)["category"] == category


class AgeGatedYoutubeDL:
    def __init__(self, opts):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def extract_info(self, url, download=True):
        raise yt_dlp.utils.DownloadError(AGE_GATE)


def test_the_download_logs_an_age_gate_as_one(tmp_path, caplog):
    downloader = TrailerDownloader(str(tmp_path), "1080")
    with patch.object(yt_dlp, "YoutubeDL", AgeGatedYoutubeDL), \
            caplog.at_level(logging.WARNING, logger="backend.radarr_connector"):
        result = asyncio.run(downloader._download_with_ytdlp(
            RADARR_URL, str(tmp_path / "Evil_Dead_II_765_trailer.%(ext)s"), "Evil Dead II", 765, [], 0, tmp_path))
    assert result["error"] == "age_restricted"
    assert "YouTube age restriction" in caplog.text
    assert "bot detection" not in caplog.text


class FakeProvider:
    def ensure_running(self):
        return {"usable": True}

    def status(self):
        return {"usable": True}


def download(tmp_path, answers, cookies=False):
    """Run download_trailer where strategy N fails with answers[N] (the last repeats)."""
    if cookies:
        (tmp_path / "youtube_cookies.txt").write_text("# Netscape HTTP Cookie File\n")
    tried = []

    async def fake_download(downloader, url, template, title, tmdb_id, args, flags, out):
        tried.append(list(args))
        return {"error": "download_error", "message": answers[min(len(tried), len(answers)) - 1]}

    async def no_sleep(*args, **kwargs):
        return None

    with patch.object(TrailerDownloader, "_download_with_ytdlp", fake_download), \
            patch.object(TrailerDownloader, "get_cookie_browser", return_value=None), \
            patch.object(nexup_potoken, "get_manager", return_value=FakeProvider()), \
            patch("asyncio.sleep", no_sleep):
        downloader = TrailerDownloader(str(tmp_path), "1080")
        result = asyncio.run(downloader.download_trailer(RADARR_URL, "Evil Dead II", 765, only_provided_url=True))
    return result, tried


def test_an_age_restricted_trailer_is_reported_as_one(tmp_path):
    result, tried = download(tmp_path, [AGE_GATE])
    assert len(tried) > 1
    assert result["error"] == "AGE_RESTRICTED"
    assert "sign in for age-restricted trailers" in result["message"]


def test_the_age_gate_wins_over_a_bot_wall_from_another_client(tmp_path):
    result, _ = download(tmp_path, [BOT_WALL, AGE_GATE])
    assert result["error"] == "AGE_RESTRICTED"


def test_cookies_that_still_hit_the_age_gate_are_called_out(tmp_path):
    result, tried = download(tmp_path, [AGE_GATE], cookies=True)
    assert any("--cookies" in args for args in tried)
    assert result["error"] == "AGE_RESTRICTED"
    assert "still asked to sign in with your cookies" in result["message"]


def test_a_real_bot_wall_is_still_a_bot_block(tmp_path):
    result, _ = download(tmp_path, [BOT_WALL])
    assert result["error"] == "YOUTUBE_BOT_BLOCK"


def test_the_sync_button_gives_an_age_gate_its_own_message():
    """sync_nexup: no "re-export cookies" flag and no ERROR event for one video's age gate."""
    path = Path(__file__).resolve().parents[1] / "backend" / "main.py"
    text = path.read_text(encoding="utf-8")
    node = next(n for n in ast.parse(text).body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == "sync_nexup")
    source = ast.get_source_segment(text, node)
    start = source.index("elif error_code == 'AGE_RESTRICTED':")
    branch = source[start:source.index("elif ", start + 10)]
    assert "cookie_error" not in branch and "log_event" not in branch
    assert "age-restricted" in branch
