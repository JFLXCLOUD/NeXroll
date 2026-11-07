"""Trailer files are not deleted while Plex's preroll list still has them.

Plex reads the next entry of CinemaTrailersPrerollID as it plays, so a
trailer file deleted while its path is in that list fails to play. Retention
already kept such files; the cleanup when a movie arrives, both syncs, Sonarr
expiry, Library Trailers rotation and the delete buttons did not (user
report, November 6). Each now deletes the rows, keeps a file Plex's list
holds, has the scheduler rewrite the list, and deletes the file once Plex has
the new one.
"""

import datetime
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.models as models
import backend.scheduler as scheduler_module
from backend import library_trailers, retired_files

START = datetime.datetime(2026, 11, 6, 19, 0)
TICK = datetime.timedelta(seconds=60)


class FakePlex:
    writes = []
    current = ""

    def __init__(self, url=None, token=None, *args, **kwargs):
        self.url, self.token = url, token
        self.headers = {"X-Plex-Token": token or ""}
        self._verify = True

    def get_server_info(self):
        return {"platform": "windows" if os.name == "nt" else "linux"}

    def set_preroll(self, value):
        FakePlex.writes.append(value)
        FakePlex.current = value
        return True

    def get_preroll(self):
        return FakePlex.current


class RetiredFileUnitTests(unittest.TestCase):
    def setUp(self):
        retired_files.reset()
        retired_files.configure(None)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(retired_files.reset)

    def file(self, name):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as handle:
            handle.write(b"x")
        return path

    def setting(self, path_mappings=None):
        return SimpleNamespace(plex_url="http://plex.test", plex_token="t", path_mappings=path_mappings)

    def test_without_plex_nothing_is_in_its_list(self):
        self.assertEqual(retired_files.in_plex_list(["/x.mp4"], SimpleNamespace(plex_url=None)), set())

    def test_an_unreachable_plex_is_unknown(self):
        self.assertIsNone(retired_files.in_plex_list(["/x.mp4"], self.setting(), reader=lambda s: None))

    def test_paths_are_compared_as_plex_sees_them(self):
        local = os.path.join(self.tmp.name, "nexup", "Dune Part Three.mp4")
        mappings = json.dumps([{"local": self.tmp.name, "plex": "/data/prerolls"}])
        setting = self.setting(path_mappings=mappings)
        value = "/data/prerolls/nexup/Dune Part Three.mp4;/data/prerolls/other.mp4"
        self.assertEqual(retired_files.in_plex_list([local], setting, reader=lambda s: value), {local})
        self.assertEqual(retired_files.in_plex_list([local], setting, reader=lambda s: "/data/prerolls/other.mp4"),
                         set())

    def test_a_list_that_cannot_be_split_is_searched_as_text(self):
        # A comma inside a filename: whole entries can't be trusted, so keep.
        path = os.path.join(self.tmp.name, "Hello, Goodbye.mp4")
        value = f"{path};{os.path.join(self.tmp.name, 'Another.mp4')}"
        self.assertEqual(retired_files.in_plex_list([path], self.setting(), reader=lambda s: value), {path})

    def test_retire_deletes_what_plex_does_not_have_and_keeps_the_rest(self):
        gone, held = self.file("gone.mp4"), self.file("held.mp4")
        result = retired_files.retire([gone, held], self.setting(), reader=lambda s: held)
        self.assertEqual((result["deleted"], result["kept"]), ([gone], [held]))
        self.assertFalse(os.path.exists(gone))
        self.assertTrue(os.path.exists(held))
        self.assertEqual(retired_files.pending(), [held])

    def test_retire_keeps_everything_when_plex_cannot_be_asked(self):
        path = self.file("unknown.mp4")
        retired_files.retire([path], self.setting(), reader=lambda s: None)
        self.assertTrue(os.path.exists(path))

    def test_purge_waits_for_plex_to_move_on_and_drops_reused_paths(self):
        held, reused = self.file("held.mp4"), self.file("reused.mp4")
        retired_files.retire([held, reused], self.setting(), reader=lambda s: f"{held};{reused}")
        result = retired_files.purge(self.setting(), lambda paths: {reused}, reader=lambda s: held)
        self.assertEqual((result["held"], result["reused"]), ([held], [reused]))
        self.assertTrue(os.path.exists(reused), "a path the library uses again is never deleted")
        result = retired_files.purge(self.setting(), lambda paths: set(), reader=lambda s: "")
        self.assertEqual(result["deleted"], [held])
        self.assertFalse(os.path.exists(held))
        self.assertEqual(retired_files.pending(), [])

    def test_kept_paths_survive_a_restart(self):
        store = os.path.join(self.tmp.name, "retired_trailers.json")
        retired_files.configure(store)
        held = self.file("held.mp4")
        retired_files.retire([held], self.setting(), reader=lambda s: held)
        retired_files.reset()
        retired_files.configure(store)
        self.assertEqual(retired_files.pending(), [os.path.abspath(held)])
        retired_files.configure(None)


class Harness(unittest.TestCase):
    def setUp(self):
        FakePlex.writes, FakePlex.current = [], ""
        retired_files.reset()
        retired_files.configure(None)
        self.addCleanup(retired_files.reset)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        self.addCleanup(self.engine.dispose)
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.clock = [START]
        self.defer = [False]
        with self.Session() as db:
            self.trailers = models.Category(name="NeX-Up Movie Trailers", is_system=True)
            other = models.Category(name="Christmas")
            db.add_all([self.trailers, other])
            db.flush()
            self.trailer_cat, self.other_cat = self.trailers.id, other.id
            self.paths = {}
            for i, title in enumerate(["Dune Part Three", "Avengers Doomsday", "Toy Story 5"]):
                path = self.file(f"{title}.mp4")
                self.paths[title] = path
                db.add(models.ComingSoonTrailer(radarr_movie_id=i + 1, title=title, local_path=path,
                                                status="downloaded", is_enabled=True,
                                                downloaded_at=datetime.datetime(2026, 11, 1)))
                db.add(models.Preroll(filename=os.path.basename(path), path=path,
                                      category_id=self.trailer_cat, enabled=True, managed=True))
            for i in range(2):
                db.add(models.Preroll(filename=f"xmas{i}.mp4", path=self.file(f"xmas{i}.mp4"),
                                      category_id=self.other_cat, enabled=True))
            db.add(models.Setting(plex_url="http://plex.test", plex_token="token", timezone="UTC"))
            db.commit()
        self.scheduler = scheduler_module.Scheduler()
        self.log = MagicMock()
        patches = [
            patch.object(scheduler_module, "SessionLocal", self.Session),
            patch.object(scheduler_module, "_localized_now", lambda *a, **k: self.clock[0]),
            patch.object(scheduler_module, "PlexConnector", FakePlex),
            patch.object(scheduler_module, "_scheduler_log", self.log),
            patch.object(scheduler_module, "_scheduler_verbose", MagicMock()),
            patch.object(scheduler_module, "scheduler", self.scheduler),
            patch.object(self.scheduler, "_defer_preroll_write", lambda *a, **k: self.defer[0]),
            patch.object(retired_files, "read_plex_list", lambda setting: FakePlex.current),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def file(self, name):
        path = os.path.join(self.tmp.name, name)
        with open(path, "wb") as handle:
            handle.write(b"x")
        return path

    def schedule(self, name, **fields):
        with self.Session() as db:
            row = models.Schedule(name=name, type="daily", start_date=START - datetime.timedelta(days=5),
                                  is_active=True, **fields)
            db.add(row)
            db.commit()
            return row.id

    def tick(self, minutes=0):
        for _ in range(minutes + 1):
            self.scheduler._check_and_execute_schedules_locked()
            self.clock[0] += TICK

    def remove_trailer(self, title):
        """What every cleanup now does: rows first, then retire the file."""
        path = self.paths[title]
        with self.Session() as db:
            scheduler_module.drop_trailer_prerolls(db, path)
            db.query(models.ComingSoonTrailer).filter(models.ComingSoonTrailer.local_path == path).delete()
            db.commit()
        return self.scheduler.retire_trailer_files([path], "arrived"), path


class SchedulerTests(Harness):
    def test_a_trailer_in_plex_s_list_is_kept_until_plex_has_a_new_list(self):
        self.schedule("Trailers", category_id=self.trailer_cat)
        self.tick()
        self.assertIn(self.paths["Dune Part Three"], FakePlex.current)

        result, path = self.remove_trailer("Dune Part Three")
        self.assertEqual(result["kept"], [path])
        self.assertTrue(os.path.exists(path), "Plex could still reach for it")

        self.tick()
        self.assertNotIn(path, FakePlex.current, "the list was rewritten without it")
        self.assertIn(self.paths["Toy Story 5"], FakePlex.current)
        self.assertTrue(os.path.exists(path))
        self.scheduler._purge_retired_files()
        self.assertFalse(os.path.exists(path))
        self.assertEqual(retired_files.pending(), [])

    def test_a_held_rewrite_keeps_the_file_until_playback_lets_it_through(self):
        self.schedule("Trailers", category_id=self.trailer_cat)
        self.tick()
        _, path = self.remove_trailer("Dune Part Three")
        self.defer[0] = True
        self.scheduler._deferred_write_since = START
        self.tick(3)
        self.scheduler._purge_retired_files()
        self.assertTrue(os.path.exists(path))
        self.defer[0] = False
        self.scheduler._deferred_write_since = None
        self.tick()
        self.scheduler._purge_retired_files()
        self.assertFalse(os.path.exists(path))

    def test_a_trailer_plex_does_not_have_goes_at_once(self):
        self.schedule("Christmas", category_id=self.other_cat)
        self.tick()
        result, path = self.remove_trailer("Dune Part Three")
        self.assertEqual(result["deleted"], [path])
        self.assertFalse(os.path.exists(path))
        self.assertEqual(len(FakePlex.writes), 1, "no rewrite needed")

    def test_a_sequence_is_rewritten_without_the_trailer(self):
        self.schedule("Movie night", sequence=json.dumps([{"type": "random", "category_id": self.trailer_cat,
                                                            "count": 3}]))
        self.tick()
        _, path = self.remove_trailer("Avengers Doomsday")
        self.tick()
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertNotIn(path, FakePlex.current)

    def test_filler_is_rewritten_without_the_trailer(self):
        with self.Session() as db:
            setting = db.query(models.Setting).first()
            setting.filler_enabled, setting.filler_type = True, "category"
            setting.filler_category_id = self.trailer_cat
            db.commit()
        self.tick()
        _, path = self.remove_trailer("Toy Story 5")
        self.tick()
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertNotIn(path, FakePlex.current)

    def test_a_blend_rewrites_its_current_pick(self):
        self.schedule("Trailers", category_id=self.trailer_cat, blend_enabled=True)
        self.schedule("Christmas", category_id=self.other_cat, blend_enabled=True)
        with patch.object(scheduler_module.random, "choice", lambda items: items[0]):
            self.tick()
            _, path = self.remove_trailer("Dune Part Three")
            self.tick()
        self.assertEqual(len(FakePlex.writes), 2)
        self.assertNotIn(path, FakePlex.current)

    def test_retention_now_removes_the_rows_and_keeps_only_the_file(self):
        # Retention used to skip a trailer in Plex's list entirely, so its row
        # stayed and a rotation could pick it again.
        self.schedule("Trailers", category_id=self.trailer_cat)
        self.tick()
        with self.Session() as db:
            db.query(models.Setting).first().nexup_trailer_retention_days = 3
            db.commit()
        self.scheduler._maybe_cleanup_trailers()
        with self.Session() as db:
            self.assertEqual(db.query(models.ComingSoonTrailer).count(), 0)
            self.assertEqual(db.query(models.Preroll).filter(models.Preroll.category_id == self.trailer_cat).count(), 0)
        self.assertTrue(all(os.path.exists(p) for p in self.paths.values()))
        self.assertEqual(len(retired_files.pending()), 3)

    def test_kept_files_from_before_a_restart_are_rewritten_out_and_deleted(self):
        self.schedule("Trailers", category_id=self.trailer_cat)
        self.tick()
        _, path = self.remove_trailer("Dune Part Three")
        # Restart: a new scheduler that knows nothing about the request.
        self.scheduler._plex_pending = None
        self.scheduler._refresh_requested_at = None
        self.scheduler._purge_retired_files()
        self.assertTrue(os.path.exists(path))
        self.tick()
        self.scheduler._purge_retired_files()
        self.assertFalse(os.path.exists(path))

    def test_library_trailers_rotation_keeps_a_file_plex_is_playing(self):
        storage = os.path.join(self.tmp.name, "nexup")
        os.makedirs(library_trailers.library_dir(storage))
        path = os.path.join(library_trailers.library_dir(storage), "Heat.mp4")
        with open(path, "wb") as handle:
            handle.write(b"x")
        FakePlex.current = path
        with self.Session() as db:
            row = models.LibraryTrailer(radarr_movie_id=9, title="Heat", source="download", status="available",
                                        local_path=path)
            db.add(row)
            db.commit()
            library_trailers.remove_row(db, row, storage)
            db.commit()
            self.assertEqual(db.query(models.LibraryTrailer).count(), 0)
        self.assertTrue(os.path.exists(path))
        FakePlex.current = ""
        self.scheduler._purge_retired_files()
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()
