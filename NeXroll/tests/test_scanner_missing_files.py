"""Telling files deleted on purpose from storage that is offline.

A Discord report (Synology): 253 of 879 prerolls deleted from the share were
never cleaned up. More than a quarter of the library missing looked like an
outage, so every scan kept the rows and the dashboard said the storage was
offline. Now a missing file whose folder is still there, with something in it,
counts as deleted; only files whose folder is gone or empty face the threshold.
"""

import ast
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import health_summary, media_server_health
from backend import models
from backend.scanner import reconcile_prerolls


class MissingFileTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = self.temp_dir.name

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def library(self, folders):
        """{folder: count} of registered prerolls, all present on disk."""
        for folder, count in folders.items():
            category = models.Category(name=folder)
            self.db.add(category)
            self.db.flush()
            os.makedirs(os.path.join(self.root, folder), exist_ok=True)
            for i in range(count):
                path = os.path.join(self.root, folder, f"{folder}-{i}.mp4")
                with open(path, "wb") as f:
                    f.write(b"video")
                self.db.add(models.Preroll(filename=os.path.basename(path), path=path, category_id=category.id))
        self.db.commit()

    def delete(self, folder, count):
        for i in range(count):
            os.remove(os.path.join(self.root, folder, f"{folder}-{i}.mp4"))

    def scan(self, **kwargs):
        stats = reconcile_prerolls(self.db, self.root, auto_prune_missing=True, **kwargs)
        self.db.commit()
        return stats

    def test_the_reported_case_is_cleaned_up(self):
        # 253 of 879 deleted from folders that still hold other prerolls.
        self.library({"Intros": 500, "Holiday": 379})
        self.delete("Intros", 150)
        self.delete("Holiday", 103)
        stats = self.scan()
        self.assertEqual(stats["files_on_disk"], 626)
        self.assertEqual(stats["deleted_missing"], 253)
        self.assertEqual(stats["missing_files"], 0)
        self.assertFalse(stats["storage_maybe_offline"])
        self.assertEqual(self.db.query(models.Preroll).count(), 626)

    def test_a_folder_that_is_gone_is_held_back_as_a_possible_outage(self):
        # A share mounted as one category folder drops: the folder vanishes.
        self.library({"Intros": 20, "Holiday": 60})
        shutil.rmtree(os.path.join(self.root, "Holiday"))
        stats = self.scan()
        self.assertEqual(stats["deleted_missing"], 0)
        self.assertEqual(stats["missing_not_pruned"], 60)
        self.assertTrue(stats["storage_maybe_offline"])
        self.assertEqual(self.db.query(models.Preroll).count(), 80)

    def test_an_empty_mount_point_is_held_back_too(self):
        # An unmounted Docker bind or Linux mount shows as an empty folder.
        self.library({"Intros": 20, "Holiday": 60})
        self.delete("Holiday", 60)
        stats = self.scan()
        self.assertEqual(stats["deleted_missing"], 0)
        self.assertTrue(stats["storage_maybe_offline"])

    def test_a_few_files_from_an_emptied_folder_are_still_cleaned_up(self):
        # Within the old threshold (10 files or a quarter), as before.
        self.library({"Intros": 40, "Old": 5})
        self.delete("Old", 5)
        stats = self.scan()
        self.assertEqual(stats["deleted_missing"], 5)
        self.assertFalse(stats["storage_maybe_offline"])

    def test_synology_metadata_left_in_a_folder_counts_as_online(self):
        # DSM leaves an @eaDir folder behind after the videos are deleted.
        self.library({"Intros": 20, "Holiday": 60})
        self.delete("Holiday", 60)
        os.makedirs(os.path.join(self.root, "Holiday", "@eaDir"))
        stats = self.scan()
        self.assertEqual(stats["deleted_missing"], 60)
        self.assertFalse(stats["storage_maybe_offline"])

    def test_deleted_and_unclear_files_are_handled_separately(self):
        self.library({"Intros": 40, "Holiday": 60})
        self.delete("Intros", 30)
        shutil.rmtree(os.path.join(self.root, "Holiday"))
        stats = self.scan()
        self.assertEqual(stats["deleted_missing"], 30)
        self.assertEqual(stats["missing_not_pruned"], 60)
        self.assertTrue(stats["storage_maybe_offline"])
        self.assertEqual(stats["missing_files"], 60)

    def test_nothing_is_removed_when_no_files_are_found(self):
        # Even folders with leftovers in them do not prove the storage is up.
        self.library({"Intros": 30})
        self.delete("Intros", 30)
        os.makedirs(os.path.join(self.root, "Intros", "@eaDir"))
        stats = self.scan()
        self.assertEqual(stats["files_on_disk"], 0)
        self.assertEqual(stats["deleted_missing"], 0)
        self.assertTrue(stats["storage_maybe_offline"])

    def test_remove_missing_rows_still_removes_everything_missing(self):
        self.library({"Intros": 20, "Holiday": 60})
        shutil.rmtree(os.path.join(self.root, "Holiday"))
        stats = reconcile_prerolls(self.db, self.root, delete_missing=True)
        self.assertEqual(stats["deleted_missing"], 60)


def summary_route(scan_stats):
    """main.system_health_summary, run without importing main's workers."""
    tree = ast.parse((Path(__file__).parents[1] / "backend/main.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "system_health_summary")
    node.decorator_list = []
    node.returns = None
    node.args.defaults = []
    for arg in node.args.args:
        arg.annotation = None
    env = dict(health_summary=health_summary, models=SimpleNamespace(Setting=object(), Preroll=object()),
               scheduler=SimpleNamespace(running=True, thread=SimpleNamespace(is_alive=lambda: True)),
               PLUGIN_CLIENTS={}, _LAST_SCAN_STATS=scan_stats, PREROLLS_INDEX_PATH=None)
    exec(compile(ast.Module(body=[node], type_ignores=[]), "<health-route>", "exec"), env)
    db = Mock()
    db.query.return_value.count.return_value = 10
    with patch.object(media_server_health, "check_media_servers", return_value=[]):
        summary = env["system_health_summary"](0, db)
    return next(c for c in summary["checks"] if c["key"] == "storage")


def test_health_says_offline_only_when_no_files_were_found():
    offline = summary_route({"missing_files": 60, "storage_maybe_offline": True, "files_on_disk": 0})
    assert offline["status"] == health_summary.ERROR
    unclear = summary_route({"missing_files": 60, "storage_maybe_offline": True, "files_on_disk": 20})
    assert unclear["status"] == health_summary.WARN
    assert "deleted, or on storage that is offline" in unclear["detail"]


if __name__ == "__main__":
    unittest.main()
