"""Downloaded NeX-Up trailers belong to their trailer category.

JB's production, October 10: a schedule set to the "NeX-Up Movie Trailers"
category applied nothing ("No prerolls found for category_id=33"). Seven
trailers were downloaded, but a full sync never gave them a preroll, and the
category, which every schedule, count and plugin reads, was empty.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models as models
import backend.scheduler as scheduler_module
from backend.scheduler import ensure_trailer_prerolls, prerolls_for_category_query

from tests.test_rotation_cadence import FakePlex, START


class TrailerCategoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        with self.Session() as db:
            movies = models.Category(name="NeX-Up Movie Trailers", is_system=True)
            tv = models.Category(name="NeX-Up TV Trailers", is_system=True)
            db.add_all([movies, tv])
            db.flush()
            db.add(models.Setting(plex_url="http://plex.test", plex_token="token",
                                  nexup_category_id=movies.id, nexup_tv_category_id=tv.id))
            db.commit()
            self.movies_id, self.tv_id = movies.id, tv.id

    def file(self, name):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as handle:
            handle.write(b"x")
        return path

    def add_movie(self, title, *, status="downloaded", enabled=True, exists=True):
        path = self.file(f"{title}.mp4") if exists else os.path.join(self.tmp.name, f"{title}.mp4")
        with self.Session() as db:
            db.add(models.ComingSoonTrailer(radarr_movie_id=abs(hash(title)) % 100000, title=title,
                                            local_path=path, status=status, is_enabled=enabled,
                                            duration_seconds=120, file_size_mb=10))
            db.commit()
        return path

    def test_downloaded_trailers_join_the_movie_trailer_category(self):
        self.add_movie("Alpha")
        self.add_movie("Bravo", enabled=False)
        self.add_movie("Charlie", status="pending")      # older rows: file on disk, status never set
        self.add_movie("Delta", status="downloading")    # still being written
        self.add_movie("Echo", exists=False)             # file gone
        with self.Session() as db:
            self.assertEqual(ensure_trailer_prerolls(db), 3)
            rows = {p.display_name: p for p in db.query(models.Preroll).all()}
            self.assertEqual(set(rows), {"[Trailer] Alpha", "[Trailer] Bravo", "[Trailer] Charlie"})
            self.assertFalse(rows["[Trailer] Bravo"].enabled, "a disabled trailer stays out of picks")
            self.assertEqual([c.id for c in rows["[Trailer] Alpha"].categories], [self.movies_id])
            usable = {p.display_name for p in prerolls_for_category_query(db, self.movies_id).all()}
            self.assertEqual(usable, {"[Trailer] Alpha", "[Trailer] Charlie"})

    def test_it_is_idempotent_and_leaves_existing_prerolls_alone(self):
        path = self.add_movie("Alpha")
        with self.Session() as db:
            db.add(models.Preroll(filename="Alpha.mp4", path=path, display_name="Mine", category_id=None))
            db.commit()
            self.assertEqual(ensure_trailer_prerolls(db), 0)
            self.assertEqual(ensure_trailer_prerolls(db), 0)
            self.assertEqual(db.query(models.Preroll).count(), 1)
            self.assertEqual(db.query(models.Preroll).first().display_name, "Mine")

    def test_tv_trailers_join_the_tv_category(self):
        path = self.file("Show_S2.mp4")
        with self.Session() as db:
            db.add(models.ComingSoonTVTrailer(sonarr_series_id=7, title="Show", season_number=2,
                                              local_path=path, status="downloaded", is_enabled=True))
            db.commit()
            self.assertEqual(ensure_trailer_prerolls(db), 1)
            preroll = db.query(models.Preroll).one()
            self.assertEqual(preroll.category_id, self.tv_id)
            self.assertEqual(preroll.display_name, "[Trailer] Show S2")

    def test_without_a_trailer_category_nothing_is_made(self):
        with self.Session() as db:
            db.query(models.Setting).first().nexup_category_id = None
            db.query(models.Category).filter(models.Category.name == "NeX-Up Movie Trailers").delete()
            db.commit()
        self.add_movie("Alpha")
        with self.Session() as db:
            self.assertEqual(ensure_trailer_prerolls(db), 0)

    def test_a_schedule_on_the_trailer_category_reaches_plex(self):
        self.add_movie("Alpha")
        self.add_movie("Bravo")
        with self.Session() as db:
            ensure_trailer_prerolls(db)
            db.add(models.Schedule(name="Trailers Rand Test", type="daily", start_date=START.replace(hour=0),
                                   category_id=self.movies_id, is_active=True, exclusive=True, priority=5))
            db.commit()
        FakePlex.writes = []
        sched = scheduler_module.Scheduler()
        with patch.object(scheduler_module, "SessionLocal", self.Session), \
                patch.object(scheduler_module, "_localized_now", lambda *a, **k: START), \
                patch.object(scheduler_module, "PlexConnector", FakePlex), \
                patch.object(scheduler_module, "_scheduler_log", MagicMock()), \
                patch.object(scheduler_module, "_scheduler_verbose", MagicMock()), \
                patch.object(sched, "_defer_preroll_write", lambda *a, **k: False):
            sched._check_and_execute_schedules_locked()
        self.assertEqual(len(FakePlex.writes), 1)
        self.assertIn("Alpha.mp4", FakePlex.writes[0])
        self.assertIn("Bravo.mp4", FakePlex.writes[0])

    def test_an_empty_category_says_so_instead_of_blaming_the_servers(self):
        result = scheduler_module.ApplyResult(reason="category 'X' has no enabled prerolls")
        self.assertFalse(result)
        self.assertEqual(result.describe(), "category 'X' has no enabled prerolls")
        self.assertEqual(scheduler_module.ApplyResult().describe(), "no media server configured")


if __name__ == "__main__":
    unittest.main()
