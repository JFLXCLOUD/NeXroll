import os
import tempfile
import threading
import unittest

from backend.preroll_files import (
    apply_preroll_media_replacement,
    ensure_preroll_category,
    managed_category_suffix,
    move_to_unique_destination,
    open_unique_destination,
    preroll_has_category,
    ReversibleFileTransaction,
    rename_file_case_safe,
    resolve_thumbnail_path,
    thumbnail_path_candidates,
    unique_destination,
    validate_preroll_filename,
    validate_storage_component,
)


class PrerollFileHelpersTests(unittest.TestCase):
    def test_category_assignment_preserves_existing_tags_and_sets_legacy_for_uncategorized(self):
        class Category:
            def __init__(self, category_id):
                self.id = category_id

        class Preroll:
            category_id = None
            categories = []

        preroll = Preroll()
        existing = Category(1)
        added = Category(2)
        preroll.categories = [existing]

        self.assertTrue(ensure_preroll_category(preroll, added))
        self.assertEqual([item.id for item in preroll.categories], [1, 2])
        self.assertIsNone(preroll.category_id)
        self.assertTrue(preroll_has_category(preroll, 2))

        uncategorized = Preroll()
        self.assertTrue(ensure_preroll_category(uncategorized, added))
        self.assertEqual(uncategorized.category_id, 2)
        self.assertEqual([item.id for item in uncategorized.categories], [2])

    def test_category_assignment_backfills_m2m_for_legacy_row_idempotently(self):
        class Category:
            id = 7

        class Preroll:
            category_id = 7
            categories = []

        preroll = Preroll()
        self.assertFalse(ensure_preroll_category(preroll, Category()))
        self.assertEqual([item.id for item in preroll.categories], [7])
        self.assertFalse(ensure_preroll_category(preroll, Category()))

    def test_thumbnail_candidates_handle_docker_prerolls_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prerolls_dir = os.path.join(temp_dir, "prerolls")
            expected = os.path.join(
                prerolls_dir,
                "thumbnails",
                "Default",
                "637_intro.mp4.jpg",
            )

            candidates = thumbnail_path_candidates(
                "prerolls/thumbnails/Default/637_intro.mp4.jpg",
                prerolls_dir,
                prerolls_dir,
            )

            self.assertIn(os.path.abspath(expected), candidates)

    def test_thumbnail_resolver_rejects_non_thumbnail_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prerolls_dir = os.path.join(temp_dir, "prerolls")
            thumbnails_dir = os.path.join(prerolls_dir, "thumbnails")
            thumbnail = os.path.join(thumbnails_dir, "Default", "intro.jpg")
            video = os.path.join(prerolls_dir, "intro.mp4")
            database = os.path.join(temp_dir, "nexroll.db")
            os.makedirs(os.path.dirname(thumbnail), exist_ok=True)
            for path in (thumbnail, video, database):
                with open(path, "wb") as handle:
                    handle.write(b"test")

            resolved = resolve_thumbnail_path(
                "prerolls/thumbnails/Default/intro.jpg",
                prerolls_dir,
                prerolls_dir,
                thumbnails_dir,
            )

            self.assertEqual(resolved, os.path.normcase(os.path.realpath(thumbnail)))
            self.assertIsNone(resolve_thumbnail_path(
                "intro.mp4",
                prerolls_dir,
                prerolls_dir,
                thumbnails_dir,
            ))
            self.assertIsNone(resolve_thumbnail_path(
                "../nexroll.db",
                prerolls_dir,
                prerolls_dir,
                thumbnails_dir,
            ))

    def test_replacement_updates_media_without_changing_identity_or_associations(self):
        category = object()

        class ExistingPreroll:
            id = 42
            category_id = 7
            categories = [category]
            display_name = "Keep this label"
            filename = "old.mp4"
            path = "old/path.mp4"
            tags = None
            description = None
            duration = None
            file_size = 1
            file_hash = "old"
            managed = False

        existing = ExistingPreroll()
        result = apply_preroll_media_replacement(
            existing,
            filename="new.mp4",
            path="new/path.mp4",
            tags='["new"]',
            description="New media",
            duration=12.5,
            file_size=99,
            file_hash="new",
        )

        self.assertIs(result, existing)
        self.assertEqual(existing.id, 42)
        self.assertEqual(existing.category_id, 7)
        self.assertEqual(existing.categories, [category])
        self.assertEqual(existing.display_name, "Keep this label")
        self.assertEqual(existing.filename, "new.mp4")
        self.assertEqual(existing.path, "new/path.mp4")
        self.assertTrue(existing.managed)

    def test_upload_filename_strips_client_paths_from_either_platform(self):
        self.assertEqual(validate_preroll_filename(r"C:\clips\intro.mp4"), "intro.mp4")
        self.assertEqual(validate_preroll_filename("../../clips/intro.mkv"), "intro.mkv")

    def test_upload_filename_rejects_non_video_extension(self):
        with self.assertRaisesRegex(ValueError, "not allowed"):
            validate_preroll_filename("notes.txt")

    def test_upload_filename_rejects_windows_device_and_invalid_names(self):
        for value in ("CON.mp4", "bad:name.mp4", "bad?.mp4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_preroll_filename(value)

    def test_storage_component_rejects_nested_or_parent_paths(self):
        for value in ("../outside", r"..\outside", ".", "..", "Holiday: Special", "CON"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_storage_component(value)

    def test_unique_destination_does_not_overwrite_an_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original = os.path.join(temp_dir, "intro.mp4")
            with open(original, "wb") as handle:
                handle.write(b"original")

            name, path = unique_destination(temp_dir, "intro.mp4")

            self.assertEqual(name, "intro_1.mp4")
            self.assertEqual(path, os.path.join(temp_dir, "intro_1.mp4"))
            with open(original, "rb") as handle:
                self.assertEqual(handle.read(), b"original")

    def test_concurrent_upload_destinations_are_created_exclusively(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            barrier = threading.Barrier(8)
            results = []
            errors = []

            def create_file(index):
                try:
                    barrier.wait()
                    name, path, handle = open_unique_destination(temp_dir, "intro.mp4")
                    with handle:
                        handle.write(str(index).encode("ascii"))
                    results.append((name, path))
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            workers = [threading.Thread(target=create_file, args=(index,)) for index in range(8)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(results), 8)
            self.assertEqual(len({name for name, _ in results}), 8)
            self.assertTrue(all(os.path.getsize(path) > 0 for _, path in results))

    def test_category_move_suffix_cannot_escape_the_preroll_root(self):
        root = os.path.join("C:\\", "nexroll", "prerolls")
        outside = os.path.join("C:\\", "external", "intro.mp4")
        self.assertEqual(managed_category_suffix(outside, root), "intro.mp4")

        nested = os.path.join(root, "Old Category", "Preroll_7", "loading.mp4")
        self.assertEqual(
            managed_category_suffix(nested, root),
            os.path.join("Preroll_7", "loading.mp4"),
        )

    def test_case_only_rename_preserves_media_and_requested_casing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "Intro.MP4")
            destination = os.path.join(temp_dir, "intro.mp4")
            with open(source, "wb") as handle:
                handle.write(b"media")

            rename_file_case_safe(source, destination)

            self.assertEqual(os.listdir(temp_dir), ["intro.mp4"])
            with open(destination, "rb") as handle:
                self.assertEqual(handle.read(), b"media")

    def test_rename_rejects_a_different_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            source = os.path.join(temp_dir, "source.mp4")
            destination = os.path.join(temp_dir, "destination.mp4")
            with open(source, "wb") as handle:
                handle.write(b"source")
            with open(destination, "wb") as handle:
                handle.write(b"destination")

            with self.assertRaises(FileExistsError):
                rename_file_case_safe(source, destination)

            with open(source, "rb") as handle:
                self.assertEqual(handle.read(), b"source")
            with open(destination, "rb") as handle:
                self.assertEqual(handle.read(), b"destination")

    def test_concurrent_category_moves_never_overwrite_each_other(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            destination_dir = os.path.join(temp_dir, "category")
            barrier = threading.Barrier(8)
            results = []
            errors = []

            def move_file(index):
                source_dir = os.path.join(temp_dir, f"source-{index}")
                os.makedirs(source_dir)
                source = os.path.join(source_dir, "intro.mp4")
                with open(source, "wb") as handle:
                    handle.write(str(index).encode("ascii"))
                try:
                    barrier.wait()
                    results.append(move_to_unique_destination(source, destination_dir, "intro.mp4"))
                except Exception as exc:  # pragma: no cover - asserted below
                    errors.append(exc)

            workers = [threading.Thread(target=move_file, args=(index,)) for index in range(8)]
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(results), 8)
            self.assertEqual(len({name for name, _ in results}), 8)
            contents = set()
            for _, path in results:
                with open(path, "rb") as handle:
                    contents.add(handle.read())
            self.assertEqual(contents, {str(index).encode("ascii") for index in range(8)})

    def test_file_transaction_rolls_back_commit_failure_after_combined_mutations(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            original_dir = os.path.join(temp_dir, "original")
            category_dir = os.path.join(temp_dir, "category")
            os.makedirs(original_dir)
            original_video = os.path.join(original_dir, "intro.mp4")
            renamed_video = os.path.join(original_dir, "renamed.mp4")
            original_thumbnail = os.path.join(original_dir, "intro.jpg")
            staged_thumbnail = os.path.join(category_dir, "renamed.jpg")
            with open(original_video, "wb") as handle:
                handle.write(b"video")
            with open(original_thumbnail, "wb") as handle:
                handle.write(b"old thumbnail")

            transaction = ReversibleFileTransaction()
            rename_file_case_safe(original_video, renamed_video)
            transaction.record_move(original_video, renamed_video)
            _, moved_video = move_to_unique_destination(
                renamed_video, category_dir, "renamed.mp4"
            )
            transaction.record_move(renamed_video, moved_video)
            with open(staged_thumbnail, "wb") as handle:
                handle.write(b"new thumbnail")
            transaction.record_new_file(staged_thumbnail)
            transaction.delete_after_commit(original_thumbnail)

            self.assertEqual(transaction.rollback(), [])

            self.assertTrue(os.path.isfile(original_video))
            self.assertFalse(os.path.exists(renamed_video))
            self.assertFalse(os.path.exists(moved_video))
            self.assertFalse(os.path.exists(staged_thumbnail))
            with open(original_thumbnail, "rb") as handle:
                self.assertEqual(handle.read(), b"old thumbnail")

    def test_file_transaction_staged_delete_follows_commit_or_rollback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            restored = os.path.join(temp_dir, "restore.mp4")
            removed = os.path.join(temp_dir, "remove.mp4")
            for path in (restored, removed):
                with open(path, "wb") as handle:
                    handle.write(os.path.basename(path).encode("ascii"))

            rollback_transaction = ReversibleFileTransaction()
            rollback_transaction.stage_delete(restored)
            self.assertFalse(os.path.exists(restored))
            self.assertEqual(rollback_transaction.rollback(), [])
            self.assertTrue(os.path.isfile(restored))

            commit_transaction = ReversibleFileTransaction()
            staged = commit_transaction.stage_delete(removed)
            self.assertTrue(os.path.isfile(staged))
            self.assertEqual(commit_transaction.commit(), [])
            self.assertFalse(os.path.exists(removed))
            self.assertFalse(os.path.exists(staged))

    def test_file_transaction_commit_keeps_new_thumbnail_and_removes_old_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            old_thumbnail = os.path.join(temp_dir, "old.jpg")
            new_thumbnail = os.path.join(temp_dir, "new.jpg")
            with open(old_thumbnail, "wb") as handle:
                handle.write(b"old")
            with open(new_thumbnail, "wb") as handle:
                handle.write(b"new")

            transaction = ReversibleFileTransaction()
            transaction.record_new_file(new_thumbnail)
            transaction.delete_after_commit(old_thumbnail)

            self.assertEqual(transaction.commit(), [])
            self.assertFalse(os.path.exists(old_thumbnail))
            with open(new_thumbnail, "rb") as handle:
                self.assertEqual(handle.read(), b"new")


if __name__ == "__main__":
    unittest.main()
