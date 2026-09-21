import asyncio
import datetime
import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import library_trailers as lt
from backend import models
from backend import scheduler as scheduler_module
from backend.sequence_conditions import PlaybackContext

NOW = datetime.datetime(2026, 9, 18, 12, 0)


def movie(mid, title, genres=("Drama",), days_ago=100, has_file=True, trailer="yt", path=None,
          year=2020, cert="PG-13", imdb=7.0, rt=80, lang="English", popularity=10.0, tags=()):
    return {
        "id": mid, "tmdbId": 1000 + mid, "title": title, "year": year, "hasFile": has_file,
        "certification": cert, "originalLanguage": {"name": lang}, "popularity": popularity, "tags": list(tags),
        "ratings": {"imdb": {"value": imdb}, "rottenTomatoes": {"value": rt}, "tmdb": {"value": imdb}},
        "genres": list(genres), "youTubeTrailerId": trailer, "path": path or f"/movies/{title}",
        "movieFile": {"dateAdded": (NOW - datetime.timedelta(days=days_ago)).isoformat() + "Z"},
        "images": [{"coverType": "poster", "remoteUrl": f"http://img/{mid}.jpg"}],
    }


class FakeDownloader:
    """Writes a small file per download into NeXroll's library folder."""

    def __init__(self, folder, size_mb=100.0, fail=()):
        self.folder, self.size_mb, self.fail, self.calls = folder, size_mb, set(fail), []
        os.makedirs(folder, exist_ok=True)

    async def download_trailer(self, url, title, tmdb_id=None, year=None):
        self.calls.append(title)
        if title in self.fail:
            return None
        path = os.path.join(self.folder, f"{title}_{tmdb_id}_trailer.mp4")
        with open(path, "wb") as f:
            f.write(b"x")
        return {"path": path, "size_mb": self.size_mb, "duration": 120}


class LibraryTrailerTestBase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.tmp = tempfile.TemporaryDirectory()
        self.storage = os.path.join(self.tmp.name, "nexup")
        self.movies_root = os.path.join(self.tmp.name, "media")
        os.makedirs(self.storage)
        self.downloader = FakeDownloader(os.path.join(lt.library_dir(self.storage), "movies"))

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.tmp.cleanup()

    def config(self, **overrides):
        config = lt.normalize_config({"enabled": True, **overrides})
        config["path_mappings"] = [{"radarr": "/movies", "local": self.movies_root}]
        return config

    def local_trailer(self, title, name=None):
        folder = os.path.join(self.movies_root, title)
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, name or f"{title}-trailer.mp4")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(b"x")
        return path

    def sync(self, movies, config, now=NOW):
        return asyncio.run(lt.sync_library_trailers(
            self.db, movies, self.storage, config, self.downloader, download_delay=0, now=now))

    def rows(self):
        return {r.title: r for r in self.db.query(models.LibraryTrailer).all()}


class SelectionTests(LibraryTrailerTestBase):
    def test_only_movies_in_the_library_are_considered(self):
        config = self.config()
        self.assertTrue(lt.movie_matches(movie(1, "A"), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", has_file=False), config, NOW))

    def test_genre_and_recently_added_filters(self):
        config = self.config(genres=["horror"], recent_days=30)
        self.assertTrue(lt.movie_matches(movie(1, "A", genres=["Horror"], days_ago=5), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", genres=["Horror"], days_ago=60), config, NOW))
        self.assertFalse(lt.movie_matches(movie(3, "C", genres=["Comedy"], days_ago=5), config, NOW))

    def test_no_genres_chosen_means_any_genre(self):
        self.assertTrue(lt.movie_matches(movie(1, "A"), self.config(genres=[]), NOW))

    def test_settings_saved_as_all_movies_ignore_a_leftover_genre_list(self):
        config = lt.normalize_config({"enabled": True, "include": "all", "genres": ["Horror"]})
        self.assertEqual(config["genres"], [])
        self.assertNotIn("include", config)

    def test_excluded_genres_win(self):
        config = self.config(genres=["Horror"], exclude_genres=["Comedy"])
        self.assertTrue(lt.movie_matches(movie(1, "A", genres=["Horror"]), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", genres=["Horror", "Comedy"]), config, NOW))

    def test_age_ratings_treat_blank_and_nr_as_unrated(self):
        config = self.config(certifications=["G", "PG", "Unrated"])
        self.assertTrue(lt.movie_matches(movie(1, "A", cert="PG"), config, NOW))
        self.assertTrue(lt.movie_matches(movie(2, "B", cert="NR"), config, NOW))
        self.assertTrue(lt.movie_matches(movie(3, "C", cert=""), config, NOW))
        self.assertFalse(lt.movie_matches(movie(4, "D", cert="R"), config, NOW))

    def test_year_range(self):
        config = self.config(year_from=1980, year_to=1989)
        self.assertTrue(lt.movie_matches(movie(1, "A", year=1985), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", year=1979), config, NOW))
        self.assertFalse(lt.movie_matches(movie(3, "C", year=1990), config, NOW))

    def test_minimum_scores(self):
        config = self.config(min_imdb=7.5, min_rt=85)
        self.assertTrue(lt.movie_matches(movie(1, "A", imdb=8.1, rt=90), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", imdb=7.0, rt=95), config, NOW))
        self.assertFalse(lt.movie_matches(movie(3, "C", imdb=8.0, rt=60), config, NOW))
        unscored = movie(4, "D")
        unscored["ratings"] = {}
        self.assertFalse(lt.movie_matches(unscored, config, NOW))

    def test_language_and_tags(self):
        config = self.config(languages=["japanese"], tags=[3])
        self.assertTrue(lt.movie_matches(movie(1, "A", lang="Japanese", tags=[3, 5]), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", lang="English", tags=[3]), config, NOW))
        self.assertFalse(lt.movie_matches(movie(3, "C", lang="Japanese", tags=[5]), config, NOW))

    def test_always_and_never_override_the_filters(self):
        config = self.config(genres=["Horror"], always_include=[2], never_include=[1])
        self.assertFalse(lt.movie_matches(movie(1, "A", genres=["Horror"]), config, NOW))
        self.assertTrue(lt.movie_matches(movie(2, "B", genres=["Comedy"]), config, NOW))
        # Always-include still needs the movie to be in the library.
        self.assertFalse(lt.movie_matches(movie(2, "B", has_file=False), config, NOW))

    def test_a_movie_cannot_be_both_always_and_never(self):
        config = lt.normalize_config({"always_include": [1, 2], "never_include": [2]})
        self.assertEqual(config["always_include"], [1])

    def test_priority_orders_candidates_with_always_include_first(self):
        movies = [movie(1, "Old", days_ago=300, imdb=9.0, popularity=5),
                  movie(2, "New", days_ago=1, imdb=6.0, popularity=50),
                  movie(3, "Pinned", days_ago=500, imdb=5.0, popularity=1)]
        order = lambda **kw: [m["title"] for m in lt.order_candidates(movies, self.config(always_include=[3], **kw))]
        self.assertEqual(order(priority="newest"), ["Pinned", "New", "Old"])
        self.assertEqual(order(priority="rating"), ["Pinned", "Old", "New"])
        self.assertEqual(order(priority="popular"), ["Pinned", "New", "Old"])
        self.assertEqual(order(priority="random")[0], "Pinned")

    def test_facets_count_what_the_library_offers(self):
        f = lt.facets([movie(1, "A", cert="R", lang="English", year=1990), movie(2, "B", cert="", lang="French", year=2010),
                       movie(3, "C", cert="R", has_file=False)])
        self.assertEqual(f["certifications"], [{"name": "R", "count": 1}, {"name": "Unrated", "count": 1}])
        self.assertEqual([l["name"] for l in f["languages"]], ["English", "French"])
        self.assertEqual((f["year_min"], f["year_max"]), (1990, 2010))

    def test_library_genres_count_movies(self):
        genres = lt.library_genres([movie(1, "A", ["Horror", "Drama"]), movie(2, "B", ["horror"]),
                                    movie(3, "C", ["Comedy"], has_file=False)])
        self.assertEqual(genres, [{"name": "Drama", "count": 1}, {"name": "Horror", "count": 2}])


class AddedDateTests(LibraryTrailerTestBase):
    def test_radarrs_added_date_wins_over_a_reimported_file(self):
        # A rename or upgrade resets the file's dateAdded; the movie has been
        # in the library for years.
        old = movie(1, "Old", days_ago=0)
        old["added"] = "2019-05-01T10:00:00Z"
        self.assertEqual(lt.movie_added(old), datetime.datetime(2019, 5, 1, 10, 0))
        new = movie(2, "New", days_ago=400)
        new["added"] = (NOW - datetime.timedelta(days=2)).isoformat() + "Z"
        order = [m["title"] for m in lt.order_candidates([old, new], self.config(priority="newest"))]
        self.assertEqual(order, ["New", "Old"])
        self.assertFalse(lt.movie_matches(old, self.config(recent_days=30), NOW))

    def test_file_date_is_only_a_fallback(self):
        m = movie(1, "A", days_ago=3)
        m.pop("added", None)
        self.assertEqual(lt.movie_added(m), NOW - datetime.timedelta(days=3))


class AutoRefreshTests(unittest.TestCase):
    """Library Trailers rides along with NeX-Up's automatic refresh."""

    def run_refresh(self, config):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, MagicMock, patch
        import json as _json
        setting = SimpleNamespace(library_trailers_config=_json.dumps(config))
        with patch.object(lt, "run_sync", new=AsyncMock(return_value={"downloaded": 1})) as run_sync, \
                patch.object(scheduler_module, "SessionLocal", MagicMock()):
            asyncio.run(scheduler_module.Scheduler()._do_nexup_async_work(
                MagicMock(), setting, False, None, None, False, None, None, None))
        return run_sync

    def test_runs_when_library_trailers_is_on(self):
        self.assertEqual(self.run_refresh({"enabled": True}).await_count, 1)

    def test_skipped_when_library_trailers_is_off(self):
        self.assertEqual(self.run_refresh({"enabled": False}).await_count, 0)


class HandPickTests(LibraryTrailerTestBase):
    def test_only_picked_movies_match_and_filters_are_ignored(self):
        config = self.config(mode="picked", picked=[2], genres=["Horror"], never_include=[2])
        self.assertTrue(lt.movie_matches(movie(2, "B", genres=["Comedy"]), config, NOW))
        self.assertFalse(lt.movie_matches(movie(1, "A", genres=["Horror"]), config, NOW))
        self.assertFalse(lt.movie_matches(movie(2, "B", has_file=False), config, NOW))

    def test_picks_and_filters_are_kept_apart(self):
        config = lt.normalize_config({"mode": "picked", "picked": [3, "4", 3], "genres": ["Horror"]})
        self.assertEqual(config["picked"], [3, 4])
        self.assertEqual(config["genres"], ["Horror"])
        self.assertEqual(lt.normalize_config({"mode": "nonsense"})["mode"], "filters")

    def test_hand_picked_downloads_never_rotate_out(self):
        movies = [movie(i, f"M{i}", days_ago=100 + i) for i in range(1, 7)]
        self.sync(movies, self.config(mode="picked", picked=[1, 2, 3, 4], max_downloads=2))
        first = set(self.rows())
        self.assertEqual(len(first), 2)
        self.sync(movies, self.config(mode="picked", picked=[1, 2, 3, 4], max_downloads=2),
                  now=NOW + datetime.timedelta(days=30))
        self.assertEqual(set(self.rows()), first)

    def test_unpicking_keeps_the_trailer_outside_the_selection(self):
        movies = [movie(1, "A"), movie(2, "B")]
        self.sync(movies, self.config(mode="picked", picked=[1, 2]))
        self.sync(movies, self.config(mode="picked", picked=[2]))
        rows = self.rows()
        self.assertIs(rows["A"].in_selection, False)
        self.assertIs(rows["B"].in_selection, True)
        self.assertTrue(os.path.exists(rows["A"].local_path))

    def test_list_posters_use_a_small_size(self):
        m = movie(1, "A")
        m["images"] = [{"coverType": "poster", "remoteUrl": "https://image.tmdb.org/t/p/original/x.jpg"}]
        self.assertEqual(lt.movie_summary(m)["poster_url"], "https://image.tmdb.org/t/p/w185/x.jpg")


class LocalTrailerTests(LibraryTrailerTestBase):
    def test_finds_named_trailers_and_trailer_folders(self):
        a = self.local_trailer("A")
        b = self.local_trailer("B", os.path.join("Trailers", "teaser.mkv"))
        self.assertEqual(lt.find_local_trailer(os.path.dirname(a)), a)
        self.assertEqual(lt.find_local_trailer(os.path.join(self.movies_root, "B")), b)
        os.makedirs(os.path.join(self.movies_root, "C"))
        self.assertIsNone(lt.find_local_trailer(os.path.join(self.movies_root, "C")))

    def test_path_mapping_translates_radarr_folders(self):
        maps = [{"radarr": "/movies", "local": self.movies_root}]
        self.assertEqual(lt.map_radarr_path("/movies/Alien (1979)", maps), os.path.join(self.movies_root, "Alien (1979)"))
        self.assertEqual(lt.map_radarr_path("/other/X", maps), "/other/X")

    def test_local_trailers_are_used_instead_of_downloading(self):
        path = self.local_trailer("A")
        result = self.sync([movie(1, "A")], self.config())
        row = self.rows()["A"]
        self.assertEqual((row.source, row.status, row.local_path), ("local", "available", path))
        self.assertEqual(self.downloader.calls, [])
        self.assertEqual(result["local_found"], 1)

    def test_local_files_are_never_deleted(self):
        path = self.local_trailer("A")
        self.sync([movie(1, "A", genres=["Horror"])], self.config())
        # The movie stops matching: the trailer is kept, marked outside.
        self.sync([movie(1, "A", genres=["Horror"])], self.config(genres=["Comedy"]))
        self.assertIs(self.rows()["A"].in_selection, False)
        # The movie leaves the library: the row goes, the user's file stays.
        self.sync([movie(1, "A", genres=["Horror"], has_file=False)], self.config())
        self.assertNotIn("A", self.rows())
        self.assertTrue(os.path.exists(path))

    def test_local_trailers_do_not_count_toward_limits(self):
        for title in ("A", "B", "C"):
            self.local_trailer(title)
        self.sync([movie(1, "A"), movie(2, "B"), movie(3, "C")], self.config(max_downloads=1))
        self.assertEqual(sorted(self.rows()), ["A", "B", "C"])


class DownloadTests(LibraryTrailerTestBase):
    def test_progress_reports_stages_counts_and_an_activity_feed(self):
        self.local_trailer("A")
        progress = {}
        asyncio.run(lt.sync_library_trailers(self.db, [movie(1, "A"), movie(2, "B")], self.storage, self.config(),
                                             self.downloader, progress=progress, download_delay=0, now=NOW))
        self.assertEqual(progress["stage"], "done")
        self.assertEqual((progress["to_download"], progress["download_done"]), (1, 1))
        self.assertEqual([(e["kind"], e["title"]) for e in progress["log"]], [("downloaded", "B"), ("found", "A")])
        self.assertEqual(progress["counts"]["downloaded"], 1)

    def test_downloads_follow_the_chosen_priority(self):
        movies = [movie(1, "Low", imdb=5.0), movie(2, "High", imdb=9.0), movie(3, "Mid", imdb=7.0)]
        self.sync(movies, self.config(max_downloads=2, priority="rating"))
        self.assertEqual(self.downloader.calls, ["High", "Mid"])

    def test_downloads_newest_first_up_to_the_count_limit(self):
        movies = [movie(1, "Old", days_ago=300), movie(2, "New", days_ago=2), movie(3, "Mid", days_ago=10)]
        self.sync(movies, self.config(max_downloads=2))
        self.assertEqual(self.downloader.calls, ["New", "Mid"])
        self.assertTrue(all(r.source == "download" for r in self.rows().values()))

    def test_size_limit_stops_downloads(self):
        self.downloader.size_mb = 600
        self.sync([movie(i, f"M{i}", days_ago=i) for i in range(1, 6)], self.config(max_downloads=50, max_gb=1.0))
        self.assertEqual(len(self.downloader.calls), 2)  # 1.2 GB after two; stops there

    def test_downloads_go_only_into_the_library_folder(self):
        self.sync([movie(1, "A")], self.config())
        path = self.rows()["A"].local_path
        self.assertTrue(os.path.abspath(path).startswith(os.path.abspath(lt.library_dir(self.storage))))

    def test_changing_filters_keeps_existing_downloads(self):
        self.sync([movie(1, "A", ["Horror"]), movie(2, "B", ["Comedy"])], self.config())
        old = self.rows()["A"].local_path
        self.sync([movie(1, "A", ["Horror"]), movie(2, "B", ["Comedy"])], self.config(genres=["Comedy"]))
        rows = self.rows()
        self.assertEqual(sorted(rows), ["A", "B"])
        self.assertIs(rows["A"].in_selection, False)
        self.assertIs(rows["B"].in_selection, True)
        self.assertTrue(os.path.exists(old))
        # Kept trailers still play.
        played = scheduler_module.resolve_library_trailer_block({"type": "library_trailers", "count": 5}, self.db)
        self.assertEqual(sorted(r.title for r in played), ["A", "B"])

    def test_trailers_outside_the_filters_make_room_first(self):
        crime = [movie(i, f"Crime{i}", ["Crime"], days_ago=50 + i) for i in range(1, 4)]
        family = [movie(10 + i, f"Family{i}", ["Family"], days_ago=5 + i) for i in range(1, 3)]
        self.sync(crime + family, self.config(genres=["Crime"], max_downloads=3))
        self.assertEqual(sorted(self.rows()), ["Crime1", "Crime2", "Crime3"])
        self.downloader.calls.clear()
        # Two new matches need room: two outside trailers give way, no more.
        self.sync(crime + family, self.config(genres=["Family"], max_downloads=3), now=NOW + datetime.timedelta(days=1))
        rows = self.rows()
        self.assertEqual(sorted(self.downloader.calls), ["Family1", "Family2"])
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(1 for r in rows.values() if r.in_selection is False), 1)

    def test_a_movie_leaving_the_library_removes_its_download(self):
        self.sync([movie(1, "A")], self.config())
        path = self.rows()["A"].local_path
        self.sync([movie(1, "A", has_file=False)], self.config())
        self.assertEqual(self.rows(), {})
        self.assertFalse(os.path.exists(path))

    def test_a_local_trailer_replaces_a_download(self):
        self.sync([movie(1, "A")], self.config())
        downloaded = self.rows()["A"].local_path
        self.local_trailer("A")
        self.sync([movie(1, "A")], self.config())
        self.assertEqual(self.rows()["A"].source, "local")
        self.assertFalse(os.path.exists(downloaded))

    def test_failed_downloads_wait_before_retrying(self):
        self.downloader.fail = {"A"}
        self.sync([movie(1, "A")], self.config())
        self.assertEqual(self.rows()["A"].status, "error")
        self.sync([movie(1, "A")], self.config(), now=NOW + datetime.timedelta(days=1))
        self.assertEqual(self.downloader.calls, ["A"])  # not retried yet
        self.downloader.fail = set()
        self.sync([movie(1, "A")], self.config(), now=NOW + datetime.timedelta(days=4))
        self.assertEqual(self.rows()["A"].status, "available")

    def test_full_library_rotates_a_few_old_downloads(self):
        movies = [movie(i, f"M{i}", days_ago=100 + i) for i in range(1, 11)]
        self.sync(movies, self.config(max_downloads=4))
        first = set(self.rows())
        # Too soon: nothing rotates in the first week.
        self.sync(movies, self.config(max_downloads=4), now=NOW + datetime.timedelta(days=2))
        self.assertEqual(set(self.rows()), first)
        self.sync(movies, self.config(max_downloads=4), now=NOW + datetime.timedelta(days=8))
        after = set(self.rows())
        self.assertEqual(len(after), 4)
        self.assertEqual(len(after - first), lt.ROTATE_PER_SYNC)

    def test_turning_downloads_off_keeps_existing_downloads(self):
        self.sync([movie(1, "A")], self.config())
        path = self.rows()["A"].local_path
        self.sync([movie(1, "A")], self.config(download=False))
        self.assertEqual(list(self.rows()), ["A"])
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.downloader.calls, ["A"])  # nothing new fetched

    def test_a_download_outside_the_library_folder_is_never_deleted(self):
        outside = os.path.join(self.tmp.name, "precious.mp4")
        with open(outside, "wb") as f:
            f.write(b"x")
        row = models.LibraryTrailer(radarr_movie_id=9, title="X", source="download", status="available", local_path=outside)
        self.db.add(row)
        self.db.commit()
        lt.remove_row(self.db, row, self.storage)
        self.db.commit()
        self.assertTrue(os.path.exists(outside))


class PlaybackTests(LibraryTrailerTestBase):
    def setUp(self):
        super().setUp()
        self.sync([movie(1, "Alien", ["Horror", "Science Fiction"]), movie(2, "Airplane", ["Comedy"]),
                   movie(3, "Scream", ["Horror"])], self.config())

    def titles(self, block, context=None):
        return sorted(r.title for r in scheduler_module.resolve_library_trailer_block(block, self.db, context=context))

    def test_genre_filter_on_the_block(self):
        self.assertEqual(self.titles({"type": "library_trailers", "count": 5, "genres": ["horror"]}), ["Alien", "Scream"])

    def test_match_playing_prefers_the_same_genre(self):
        ctx = PlaybackContext(now=NOW, genre_lookup=lambda: ["Comedy"])
        self.assertEqual(self.titles({"type": "library_trailers", "count": 5, "match_playing": True}, ctx), ["Airplane"])

    def test_match_playing_falls_back_when_genre_unknown(self):
        ctx = PlaybackContext(now=NOW, genre_lookup=lambda: None)  # Plex
        self.assertEqual(len(self.titles({"type": "library_trailers", "count": 5, "match_playing": True}, ctx)), 3)

    def test_never_plays_the_trailer_of_the_movie_about_to_play(self):
        ctx = PlaybackContext(now=NOW, genre_lookup=lambda: ["Horror"], tmdb_lookup=lambda: "1001")
        self.assertEqual(self.titles({"type": "library_trailers", "count": 5, "match_playing": True}, ctx), ["Scream"])

    def test_disabled_trailers_do_not_play(self):
        row = self.rows()["Scream"]
        row.is_enabled = False
        self.db.commit()
        self.assertEqual(self.titles({"type": "library_trailers", "count": 5, "genres": ["Horror"]}), ["Alien"])

    def test_resolver_returns_paths(self):
        paths = scheduler_module.resolve_sequence_paths(
            [{"type": "library_trailers", "count": 1, "mode": "newest"}], self.db, ("test",))
        self.assertEqual(len(paths), 1)
        self.assertTrue(os.path.exists(paths[0]))


class ConfigTests(unittest.TestCase):
    def test_normalize_clamps_and_dedupes(self):
        config = lt.normalize_config({"genres": ["Horror", "horror", " "], "max_downloads": 9999,
                                      "max_gb": -1, "path_mappings": [{"radarr": "/m", "local": ""}]})
        self.assertEqual(config["genres"], ["Horror"])
        self.assertEqual(config["max_downloads"], 500)
        self.assertEqual(config["max_gb"], 0.0)
        self.assertEqual(config["path_mappings"], [])
        self.assertFalse(config["enabled"])


if __name__ == "__main__":
    unittest.main()
