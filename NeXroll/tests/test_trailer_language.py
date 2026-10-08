"""NeX-Up Trailer language: TMDB lookups, source order and the skip fallback.

Radarr's trailer link is TMDB's English trailer, and TMDB's /videos without a
language returns English videos only, so before this setting a French household
could only ever get English trailers.
"""

import asyncio
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend import nexup_potoken, trailer_language
from backend.radarr_connector import TMDBTrailerFetcher, TrailerDownloader

RADARR_URL = "https://www.youtube.com/watch?v=radarrEN01"


def video(key, language, region, name="Trailer", official=True, site="YouTube"):
    return {"key": key, "site": site, "type": "Trailer", "name": name, "official": official,
            "size": 1080, "iso_639_1": language, "iso_3166_1": region}


class FakeResponse:
    def __init__(self, results):
        self.status_code = 200
        self._results = results

    def json(self):
        return {"results": self._results}

    def raise_for_status(self):
        return None


class FakeClient:
    """Stands in for httpx.AsyncClient and records the TMDB query."""

    calls = []
    results = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None):
        FakeClient.calls.append((url, dict(params or {})))
        return FakeResponse(FakeClient.results)


class LanguageHelperTests(unittest.TestCase):
    def test_unknown_or_missing_languages_mean_english(self):
        for value in (None, "", "xx-YY", "klingon"):
            self.assertEqual(trailer_language.normalize_language(value), "en")
        self.assertEqual(trailer_language.normalize_language("fr-ca"), "fr-CA")
        self.assertEqual(trailer_language.normalize_language("de-DE"), "de-DE")

    def test_fallback_is_english_unless_skip(self):
        self.assertEqual(trailer_language.normalize_fallback(None), "english")
        self.assertEqual(trailer_language.normalize_fallback("SKIP"), "skip")
        self.assertEqual(trailer_language.normalize_fallback("anything"), "english")

    def test_english_sends_no_tmdb_language_parameters(self):
        self.assertEqual(trailer_language.tmdb_video_params("en"), {})

    def test_other_languages_ask_for_their_videos_plus_english(self):
        self.assertEqual(trailer_language.tmdb_video_params("es-MX"),
                         {"language": "es-MX", "include_video_language": "es,en,null"})

    def test_rank_prefers_the_region_then_the_language(self):
        rank = trailer_language.language_rank
        self.assertEqual(rank("fr-CA", "fr", "CA"), trailer_language.RANK_EXACT)
        self.assertEqual(rank("fr-CA", "fr", "FR"), trailer_language.RANK_LANGUAGE)
        self.assertEqual(rank("fr-CA", "fr", None), trailer_language.RANK_LANGUAGE)
        self.assertEqual(rank("fr-CA", "en", "US"), trailer_language.RANK_OTHER)
        self.assertEqual(rank("fr-CA", None, None), trailer_language.RANK_OTHER)

    def test_tag_labels(self):
        self.assertEqual(trailer_language.tag_label("fr", "CA"), "French (Canada)")
        self.assertEqual(trailer_language.tag_label("de", "AT"), "German (AT)")
        self.assertEqual(trailer_language.tag_label("es", None), "Spanish")
        self.assertEqual(trailer_language.tag_label("tr", "TR"), "tr")
        self.assertIsNone(trailer_language.tag_label(None, "US"))

    def test_search_query_keeps_the_english_wording(self):
        self.assertEqual(trailer_language.search_query("en", "Dune", 2024), "Dune 2024 official trailer")
        self.assertEqual(trailer_language.search_query("de-DE", "Dune", None), "Dune Trailer Deutsch")

    def test_downloader_options_come_from_the_settings(self):
        setting = SimpleNamespace(nexup_trailer_language="it-IT", nexup_trailer_language_fallback="skip",
                                  nexup_tmdb_api_key=" abc123 ")
        self.assertEqual(trailer_language.downloader_options(setting),
                         {"language": "it-IT", "language_fallback": "skip", "tmdb_api_key": "abc123"})
        self.assertEqual(trailer_language.downloader_options(SimpleNamespace()),
                         {"language": "en", "language_fallback": "english", "tmdb_api_key": None})

    def test_every_language_has_search_words(self):
        self.assertEqual(set(trailer_language.SEARCH_TERMS), set(trailer_language.LANGUAGES))


class TmdbLookupTests(unittest.TestCase):
    def setUp(self):
        FakeClient.calls = []
        patcher = patch("backend.radarr_connector.httpx.AsyncClient", FakeClient)
        patcher.start()
        self.addCleanup(patcher.stop)

    def sources(self, language, results):
        FakeClient.results = results
        return asyncio.run(TMDBTrailerFetcher().get_trailer_sources(603, language=language))

    def test_english_lookup_is_unchanged(self):
        self.sources("en", [video("en1", "en", "US")])
        (url, params), = FakeClient.calls
        self.assertTrue(url.endswith("/movie/603/videos"))
        self.assertNotIn("language", params)
        self.assertNotIn("include_video_language", params)

    def test_a_language_is_requested_and_sorted_first(self):
        found = self.sources("fr-FR", [
            video("en1", "en", "US"),
            video("frca", "fr", "CA"),
            video("frfr", "fr", "FR", official=False),
        ])
        params = FakeClient.calls[0][1]
        self.assertEqual(params["language"], "fr-FR")
        self.assertEqual(params["include_video_language"], "fr,en,null")
        self.assertEqual([s["key"] for s in found], ["frfr", "frca", "en1"])
        self.assertEqual(found[0]["language"], "fr")
        self.assertEqual(found[0]["region"], "FR")


class FakeProvider:
    def ensure_running(self):
        return {"usable": True}

    def status(self):
        return {"usable": True}


class DownloaderLanguageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.tried = []
        self.tmdb_sources = []
        self.tmdb_languages = []
        self.tmdb_rejects_key = False

        async def fake_sources(fetcher, tmdb_id, title=None, year=None, language="en"):
            self.tmdb_languages.append(language)
            if self.tmdb_rejects_key:
                fetcher.tmdb_available = False
                return []
            return [dict(s) for s in self.tmdb_sources]

        async def fake_download(downloader, url, *args, **kwargs):
            self.tried.append(url)
            return {"path": f"{self.tmp.name}/trailer.mp4", "size_mb": 10}

        async def no_sleep(*args, **kwargs):
            return None

        for p in (patch.object(TMDBTrailerFetcher, "get_trailer_sources", fake_sources),
                  patch.object(TrailerDownloader, "_download_with_ytdlp", fake_download),
                  patch.object(TrailerDownloader, "get_cookie_browser", return_value=None),
                  patch.object(nexup_potoken, "get_manager", return_value=FakeProvider()),
                  patch("asyncio.sleep", no_sleep)):
            p.start()
            self.addCleanup(p.stop)

    def tmdb(self, key, language, region):
        src = {"source": "youtube", "url": f"https://www.youtube.com/watch?v={key}", "key": key,
               "name": key, "official": True, "size": 1080, "priority": 2,
               "language": language, "region": region}
        src["language_rank"] = 0
        return src

    def download(self, language="en", fallback="english", url=RADARR_URL, only_provided_url=False):
        downloader = TrailerDownloader(self.tmp.name, "1080", language=language, language_fallback=fallback)
        # Rank as the real fetcher would for this language.
        for src in self.tmdb_sources:
            src["language_rank"] = (0 if language == "en" else
                                    trailer_language.language_rank(language, src["language"], src["region"]))
        return asyncio.run(downloader.download_trailer(url, "Movie", 603, only_provided_url=only_provided_url))

    def test_english_still_tries_the_radarr_trailer_first(self):
        self.tmdb_sources = [self.tmdb("en2", "en", "US")]
        result = self.download()
        self.assertEqual(self.tried[0], RADARR_URL)
        self.assertEqual(result["source_url"], RADARR_URL)
        self.assertEqual(self.tmdb_languages, ["en"])

    def test_a_trailer_in_the_language_comes_before_radarrs(self):
        self.tmdb_sources = [self.tmdb("en2", "en", "US"), self.tmdb("de1", "de", "DE")]
        result = self.download("de-DE")
        self.assertEqual(self.tried[0], "https://www.youtube.com/watch?v=de1")
        self.assertEqual(result["source_url"], "https://www.youtube.com/watch?v=de1")
        self.assertEqual(result["language"], "de")

    def test_without_one_the_english_fallback_uses_radarrs(self):
        self.tmdb_sources = [self.tmdb("en2", "en", "US")]
        result = self.download("de-DE")
        self.assertEqual(self.tried[0], RADARR_URL)
        self.assertEqual(result["source_url"], RADARR_URL)

    def test_skip_downloads_nothing_without_one(self):
        self.tmdb_sources = [self.tmdb("en2", "en", "US")]
        result = self.download("de-DE", "skip")
        self.assertEqual(result["error"], "NO_LANGUAGE_MATCH")
        self.assertIn("German", result["message"])
        self.assertEqual(self.tried, [])

    def test_skip_accepts_the_language_from_another_region(self):
        self.tmdb_sources = [self.tmdb("en2", "en", "US"), self.tmdb("frfr", "fr", "FR")]
        result = self.download("fr-CA", "skip")
        self.assertEqual(self.tried, ["https://www.youtube.com/watch?v=frfr"])
        self.assertEqual(result["source_url"], "https://www.youtube.com/watch?v=frfr")

    def test_radarrs_trailer_counts_when_tmdb_tags_it_with_the_language(self):
        self.tmdb_sources = [self.tmdb("radarrEN01", "es", "MX")]
        result = self.download("es-MX", "skip")
        self.assertEqual(self.tried, [RADARR_URL])
        self.assertEqual(result["language"], "es")

    def test_a_rejected_tmdb_key_is_reported_as_such(self):
        self.tmdb_rejects_key = True
        result = self.download("de-DE", "skip")
        self.assertEqual(result["error"], "TMDB_KEY_REJECTED")
        self.assertIn("TMDB API key", result["message"])
        self.assertEqual(self.tried, [])

    def test_a_rejected_tmdb_key_still_falls_back_to_english(self):
        self.tmdb_rejects_key = True
        result = self.download("de-DE", "english")
        self.assertEqual(self.tried[0], RADARR_URL)
        self.assertEqual(result["source_url"], RADARR_URL)

    def test_the_users_tmdb_key_reaches_the_lookup(self):
        downloader = TrailerDownloader(self.tmp.name, "1080", tmdb_api_key="mine")
        self.assertEqual(downloader.tmdb.api_key, "mine")

    def test_a_picked_trailer_ignores_the_language(self):
        self.tmdb_sources = [self.tmdb("de1", "de", "DE")]
        result = self.download("de-DE", "skip", only_provided_url=True)
        self.assertEqual(self.tried, [RADARR_URL])
        self.assertEqual(self.tmdb_languages, [])
        self.assertEqual(result["source_url"], RADARR_URL)


if __name__ == "__main__":
    unittest.main()
