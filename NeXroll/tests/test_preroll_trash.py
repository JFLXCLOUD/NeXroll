import os
import tempfile
import time
import unittest

from backend import preroll_trash
from backend.preroll_trash import (
    TRASH_DIR_NAME,
    discard_entry_dir,
    find_entry,
    list_trash,
    move_to_trash,
    purge_trash,
    resolve_trash_root,
    restore_entry,
)


class PrerollTrashTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = self.temp_dir.name
        self.prerolls_dir = os.path.join(self.data_dir, "prerolls")
        os.makedirs(self.prerolls_dir)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_video(self, *parts, content=b"video"):
        path = os.path.join(self.prerolls_dir, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)
        return path

    def test_trash_root_sits_beside_library_files_and_falls_back_for_outside_files(self):
        inside = os.path.join(self.prerolls_dir, "AI", "intro.mp4")
        outside = os.path.join(self.data_dir, "elsewhere", "intro.mp4")

        self.assertEqual(
            resolve_trash_root(inside, self.prerolls_dir, self.data_dir),
            os.path.join(self.prerolls_dir, TRASH_DIR_NAME),
        )
        self.assertEqual(
            resolve_trash_root(outside, self.prerolls_dir, self.data_dir),
            os.path.join(self.data_dir, TRASH_DIR_NAME),
        )

    def test_move_to_trash_preserves_contents_and_records_origin(self):
        path = self._write_video("AI", "intro.mp4", content=b"payload-bytes")

        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)

        self.assertIsNotNone(manifest)
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.isfile(manifest["trashed_path"]))
        self.assertEqual(manifest["original_path"], os.path.abspath(path))
        self.assertEqual(manifest["filename"], "intro.mp4")
        with open(manifest["trashed_path"], "rb") as handle:
            self.assertEqual(handle.read(), b"payload-bytes")

    def test_move_to_trash_returns_none_for_missing_file(self):
        missing = os.path.join(self.prerolls_dir, "gone.mp4")
        self.assertIsNone(move_to_trash(missing, self.prerolls_dir, self.data_dir))

    def test_same_named_files_from_different_categories_do_not_collide(self):
        first = self._write_video("AI", "intro.mp4", content=b"first")
        second = self._write_video("Holiday", "intro.mp4", content=b"second")

        move_to_trash(first, self.prerolls_dir, self.data_dir)
        move_to_trash(second, self.prerolls_dir, self.data_dir)

        entries = list_trash(self.prerolls_dir, self.data_dir)
        self.assertEqual(len(entries), 2)
        payloads = set()
        for entry in entries:
            with open(entry["trashed_path"], "rb") as handle:
                payloads.add(handle.read())
        self.assertEqual(payloads, {b"first", b"second"})

    def test_restore_returns_file_to_its_original_path(self):
        path = self._write_video("AI", "intro.mp4", content=b"payload")
        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)

        restored = restore_entry(manifest["entry_id"], self.prerolls_dir, self.data_dir)

        self.assertEqual(restored["restored_to"], os.path.abspath(path))
        self.assertTrue(os.path.isfile(path))
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), b"payload")
        self.assertEqual(list_trash(self.prerolls_dir, self.data_dir), [])

    def test_restore_refuses_to_overwrite_a_file_that_reappeared(self):
        path = self._write_video("AI", "intro.mp4", content=b"old")
        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)
        self._write_video("AI", "intro.mp4", content=b"new")

        with self.assertRaises(ValueError):
            restore_entry(manifest["entry_id"], self.prerolls_dir, self.data_dir)

        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), b"new")
        self.assertTrue(os.path.isfile(manifest["trashed_path"]))

    def test_entry_ids_containing_separators_are_rejected(self):
        for entry_id in ("../escape", "..\\escape", "a/b", "a\\b", "..", ""):
            with self.subTest(entry_id=entry_id):
                self.assertIsNone(find_entry(entry_id, self.prerolls_dir, self.data_dir))

    def test_entry_without_a_manifest_is_still_listed_and_purgeable(self):
        path = self._write_video("AI", "intro.mp4")
        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)
        os.remove(os.path.join(os.path.dirname(manifest["trashed_path"]), "manifest.json"))

        entries = list_trash(self.prerolls_dir, self.data_dir)
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0]["restorable"])
        self.assertEqual(purge_trash(self.prerolls_dir, self.data_dir)["removed"], 1)

    def test_purge_keeps_fresh_entries_and_removes_expired_ones(self):
        path = self._write_video("AI", "intro.mp4")
        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)
        entry_dir = os.path.dirname(manifest["trashed_path"])

        self.assertEqual(
            purge_trash(self.prerolls_dir, self.data_dir, older_than_days=30)["removed"], 0
        )
        self.assertTrue(os.path.isdir(entry_dir))

        expired = time.time() - (31 * 86400)
        os.utime(entry_dir, (expired, expired))

        self.assertEqual(
            purge_trash(self.prerolls_dir, self.data_dir, older_than_days=30)["removed"], 1
        )
        self.assertFalse(os.path.isdir(entry_dir))

    def test_zero_retention_disables_expiry_purge(self):
        path = self._write_video("AI", "intro.mp4")
        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)

        self.assertEqual(
            purge_trash(self.prerolls_dir, self.data_dir, older_than_days=0)["removed"], 0
        )
        self.assertTrue(os.path.isfile(manifest["trashed_path"]))

    def test_retention_days_reads_env_override_and_ignores_garbage(self):
        original = os.environ.get("NEXROLL_TRASH_RETENTION_DAYS")
        try:
            os.environ["NEXROLL_TRASH_RETENTION_DAYS"] = "7"
            self.assertEqual(preroll_trash.retention_days(), 7)
            os.environ["NEXROLL_TRASH_RETENTION_DAYS"] = "not-a-number"
            self.assertEqual(preroll_trash.retention_days(), preroll_trash.DEFAULT_RETENTION_DAYS)
            os.environ.pop("NEXROLL_TRASH_RETENTION_DAYS")
            self.assertEqual(preroll_trash.retention_days(), preroll_trash.DEFAULT_RETENTION_DAYS)
        finally:
            if original is None:
                os.environ.pop("NEXROLL_TRASH_RETENTION_DAYS", None)
            else:
                os.environ["NEXROLL_TRASH_RETENTION_DAYS"] = original

    def test_discard_entry_dir_cleans_up_after_a_rollback_and_ignores_foreign_paths(self):
        path = self._write_video("AI", "intro.mp4")
        manifest = move_to_trash(path, self.prerolls_dir, self.data_dir)
        entry_dir = os.path.dirname(manifest["trashed_path"])

        # A rollback moves the file back out, leaving the entry folder behind.
        os.replace(manifest["trashed_path"], path)
        discard_entry_dir(manifest)
        self.assertFalse(os.path.isdir(entry_dir))

        # A path that is not inside a trash root must be left untouched.
        outside = self._write_video("Holiday", "keep.mp4")
        discard_entry_dir({"trashed_path": outside})
        self.assertTrue(os.path.isfile(outside))


if __name__ == "__main__":
    unittest.main()
