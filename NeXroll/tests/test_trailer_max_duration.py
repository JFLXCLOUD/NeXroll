"""A trailer over Max Trailer Duration must be reported as too long.

yt-dlp's duration match_filter rejects a video without raising: extract_info
returns the info dict and writes nothing. NeX-Up read that as "success but file
not found", retried all six YouTube strategies, and, because the cookies
strategy was among the empty results, reported YOUTUBE_BOT_BLOCK and told the
user to fix their cookies. The Upcoming tab's download button passes no limit,
so it worked every time, which made the sync look broken.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yt_dlp

from backend import nexup_potoken
from backend.radarr_connector import TrailerDownloader

URL = "https://www.youtube.com/watch?v=OFaJzL83y0Q"


class UsableProvider:
    def ensure_running(self):
        return {"usable": True}

    def status(self):
        return {"usable": True}


def video(duration):
    # Unreachable media URL: if the filter ever let this through, the test
    # would fail on the download instead of silently passing.
    return {"id": "OFaJzL83y0Q", "title": "Hope", "duration": duration, "ext": "mp4",
            "url": "http://127.0.0.1:9/hope.mp4", "extractor": "youtube",
            "extractor_key": "Youtube", "webpage_url": URL, "_type": "video"}


class MaxDurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        storage = Path(self.tmp.name)
        # The reporter had a cookies file, which is what added the strategy
        # whose empty result was misread as a sign-in failure.
        (storage / "youtube_cookies.txt").write_text("# Netscape HTTP Cookie File\n")
        self.storage = str(storage)
        self.calls = []
        for p in (patch.object(nexup_potoken, "get_manager", return_value=UsableProvider()),
                  patch.object(TrailerDownloader, "get_cookie_browser", return_value=None),
                  patch("asyncio.sleep", self._no_sleep)):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.tmp.cleanup()

    @staticmethod
    async def _no_sleep(*args, **kwargs):
        return None

    def download(self, max_duration, extract):
        def fake_extract(ydl, url, download=True, **kwargs):
            self.calls.append(ydl.params.get("cookiefile"))
            return extract(ydl, download)

        with patch.object(yt_dlp.YoutubeDL, "extract_info", fake_extract):
            downloader = TrailerDownloader(self.storage, "1080", max_duration=max_duration)
            return asyncio.run(downloader.download_trailer(URL, "Hope", 1058424, only_provided_url=True))

    def test_trailer_over_the_limit_is_too_long_not_a_bot_block(self):
        # The real yt-dlp pipeline, so its match_filter makes the decision.
        result = self.download(90, lambda ydl, dl: ydl.process_ie_result(video(151), download=dl))

        self.assertEqual(result["error"], "TOO_LONG")
        self.assertIn("2:31", result["message"])
        self.assertIn("1:30", result["message"])
        # Every client sees the same length, so one attempt is enough.
        self.assertEqual(len(self.calls), 1)

    def test_empty_cookie_result_is_not_called_a_sign_in_failure(self):
        # No limit, and yt-dlp reports success without a file for some other
        # reason: that says nothing about the cookies.
        result = self.download(0, lambda ydl, dl: video(60))

        self.assertIn(str(Path(self.storage) / "youtube_cookies.txt"), self.calls)
        self.assertNotEqual(result["error"], "YOUTUBE_BOT_BLOCK")
        self.assertEqual(result["error"], "DOWNLOAD_FAILED")


if __name__ == "__main__":
    unittest.main()
