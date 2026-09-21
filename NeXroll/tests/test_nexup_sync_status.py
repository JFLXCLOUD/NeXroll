"""NeX-Up auto-sync must record its downloads as 'downloaded'.

Regression cover for issue #39: the scheduler's Radarr/Sonarr auto-sync built
its trailer rows without a status, so they sat at the model default 'pending'
and eligible_nexup_trailers() never saw them. The files were on disk and
playable, but no trailer block would pick one, so a library synced only by the
scheduler had an empty trailer pool.
"""

import asyncio
import datetime
import os
import tempfile
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend import models
from backend import scheduler as scheduler_module


class FakeRadarrConnector:
    """Stands in for Radarr: one upcoming movie, already carrying a trailer."""

    def __init__(self, *args, **kwargs):
        pass

    async def get_all_movies_raw(self):
        return [{"id": 41, "hasFile": False}]

    def parse_upcoming_from_raw(self, all_movies, days_ahead):
        return [{
            "radarr_id": 41,
            "tmdb_id": 603,
            "imdb_id": "tt0133093",
            "title": "The Upcoming One",
            "year": 2026,
            "overview": "A movie that has not come out yet.",
            "status": "announced",
            "release_date": "2026-12-01",
            "release_type": "digital",
            "trailer_url": "https://www.youtube.com/watch?v=abc123",
            "poster_url": "https://images.example/poster.jpg",
            "fanart_url": "https://images.example/fanart.jpg",
            "monitored": True,
        }]


class FakeSonarrConnector:
    def __init__(self, *args, **kwargs):
        pass

    async def get_all_series(self):
        return []

    async def get_upcoming_shows(self, days_ahead=90):
        return [{
            "sonarr_id": 7,
            "tvdb_id": 121361,
            "imdb_id": "tt0944947",
            "title": "The Upcoming Season",
            "year": 2026,
            "overview": "A season that has not aired yet.",
            "network": "HBO",
            "release_date": "2026-11-05",
            "release_type": "new_season",
            "season_number": 4,
            "poster_url": "https://images.example/show.jpg",
            "fanart_url": "https://images.example/show-fanart.jpg",
            "monitored": True,
            # The scheduler's Sonarr path filters on this key. get_upcoming_shows
            # does not populate it in production, which is a separate defect;
            # supplying it here is what lets this test reach the insert at all.
            "trailer_url": "https://www.youtube.com/watch?v=def456",
        }]


class FakeDownloader:
    """Writes a real file so the on-disk checks are exercised, not mocked."""

    last_path = None

    def __init__(self, storage_path, quality, max_duration=0):
        self.storage_path = storage_path

    async def download_trailer(self, url, title, tmdb_id=None, tvdb_id=None, year=None):
        path = os.path.join(self.storage_path, f"{title}.mp4")
        with open(path, "wb") as f:
            f.write(b"trailer bytes")
        FakeDownloader.last_path = path
        return {"path": path, "size_mb": 12.5, "duration": 145, "resolution": "1080p"}


class AutoSyncStatusTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()
        with self.Session() as db:
            db.add(models.Setting(nexup_storage_path=self.temp_dir.name,
                                  nexup_radarr_url="http://radarr.test",
                                  nexup_radarr_api_key="key",
                                  nexup_sonarr_url="http://sonarr.test",
                                  nexup_sonarr_api_key="key",
                                  nexup_download_delay=0))
            db.commit()

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def run_radarr_sync(self, db):
        setting = db.query(models.Setting).first()
        sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)
        with patch("backend.radarr_connector.RadarrConnector", FakeRadarrConnector), \
             patch("backend.radarr_connector.TrailerDownloader", FakeDownloader):
            asyncio.run(sched._sync_radarr_trailers(db, setting))

    def run_sonarr_sync(self, db):
        setting = db.query(models.Setting).first()
        sched = scheduler_module.Scheduler.__new__(scheduler_module.Scheduler)
        with patch("backend.sonarr_connector.SonarrConnector", FakeSonarrConnector), \
             patch("backend.radarr_connector.TrailerDownloader", FakeDownloader):
            asyncio.run(sched._sync_sonarr_trailers(db, setting))

    def test_radarr_auto_sync_records_the_download_as_downloaded(self):
        with self.Session() as db:
            self.run_radarr_sync(db)
            trailer = db.query(models.ComingSoonTrailer).one()
            self.assertEqual(trailer.status, "downloaded")
            self.assertEqual(trailer.resolution, "1080p")

    def test_radarr_auto_synced_trailer_is_eligible_for_a_block(self):
        """The actual symptom in issue #39: the pool came back empty."""
        with self.Session() as db:
            self.run_radarr_sync(db)
            eligible = scheduler_module.eligible_nexup_trailers(db, "movies")
            self.assertEqual([t.title for t in eligible], ["The Upcoming One"])

    def test_radarr_auto_sync_keeps_the_artwork_the_list_slide_draws(self):
        with self.Session() as db:
            self.run_radarr_sync(db)
            trailer = db.query(models.ComingSoonTrailer).one()
            self.assertEqual(trailer.poster_url, "https://images.example/poster.jpg")
            self.assertEqual(trailer.fanart_url, "https://images.example/fanart.jpg")
            self.assertEqual(trailer.imdb_id, "tt0133093")
            self.assertEqual(trailer.release_type, "digital")

    def test_radarr_auto_sync_does_not_store_the_radarr_status(self):
        """The upcoming dict has its own 'status' ('announced'); it is not ours."""
        with self.Session() as db:
            self.run_radarr_sync(db)
            self.assertEqual(db.query(models.ComingSoonTrailer).one().status, "downloaded")

    def test_sonarr_auto_sync_records_the_download_as_downloaded(self):
        with self.Session() as db:
            self.run_sonarr_sync(db)
            trailer = db.query(models.ComingSoonTVTrailer).one()
            self.assertEqual(trailer.status, "downloaded")
            self.assertEqual(trailer.season_number, 4)
            self.assertEqual(trailer.network, "HBO")
            self.assertEqual(
                [t.title for t in scheduler_module.eligible_nexup_trailers(db, "tv")],
                ["The Upcoming Season"],
            )


class ReconcileStatusTests(unittest.TestCase):
    """Existing databases still carry rows the old auto-sync left pending."""

    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.engine.dispose()
        self.temp_dir.cleanup()

    def media(self, name):
        path = os.path.join(self.temp_dir.name, name)
        with open(path, "wb") as f:
            f.write(b"trailer bytes")
        return path

    def test_a_pending_row_with_a_real_file_becomes_downloaded(self):
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(
                title="Stranded", status="pending", is_enabled=True,
                local_path=self.media("stranded.mp4"),
                downloaded_at=datetime.datetime.utcnow()))
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 1)
            db.commit()
            self.assertEqual([t.title for t in scheduler_module.eligible_nexup_trailers(db)],
                             ["Stranded"])

    def test_tv_rows_are_repaired_too(self):
        with self.Session() as db:
            db.add(models.ComingSoonTVTrailer(
                title="Stranded Show", status="pending", is_enabled=True,
                local_path=self.media("stranded-show.mp4"),
                downloaded_at=datetime.datetime.utcnow()))
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 1)
            db.commit()
            self.assertEqual(db.query(models.ComingSoonTVTrailer).one().status, "downloaded")

    def test_a_row_whose_file_is_gone_stays_pending(self):
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(
                title="Vanished", status="pending", is_enabled=True,
                local_path=os.path.join(self.temp_dir.name, "not-there.mp4"),
                downloaded_at=datetime.datetime.utcnow()))
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 0)
            self.assertEqual(db.query(models.ComingSoonTrailer).one().status, "pending")

    def test_an_in_flight_download_is_left_alone(self):
        """'downloading' means yt-dlp may still be writing; not ours to promote."""
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(
                title="In Flight", status="downloading", is_enabled=True,
                local_path=self.media("in-flight.mp4"),
                downloaded_at=datetime.datetime.utcnow()))
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 0)
            self.assertEqual(db.query(models.ComingSoonTrailer).one().status, "downloading")

    def test_a_row_that_never_downloaded_stays_pending(self):
        """No downloaded_at: the record was created before any download ran."""
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(
                title="Queued", status="pending", is_enabled=True,
                local_path=self.media("queued.mp4")))
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 0)

    def test_an_errored_row_is_not_resurrected(self):
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(
                title="Failed", status="error", is_enabled=True,
                local_path=self.media("failed.mp4"),
                downloaded_at=datetime.datetime.utcnow()))
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 0)

    def test_running_twice_repairs_nothing_the_second_time(self):
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(
                title="Stranded", status="pending", is_enabled=True,
                local_path=self.media("stranded.mp4"),
                downloaded_at=datetime.datetime.utcnow()))
            db.commit()
            scheduler_module.reconcile_nexup_trailer_status(db)
            db.commit()
            self.assertEqual(scheduler_module.reconcile_nexup_trailer_status(db), 0)


if __name__ == "__main__":
    unittest.main()
