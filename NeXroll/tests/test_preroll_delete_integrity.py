import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.preroll_files import ReversibleFileTransaction, apply_preroll_media_replacement
from backend.preroll_trash import discard_entry_dir, list_trash, move_to_trash


class PrerollDeleteIntegrityTests(unittest.TestCase):
    def test_in_place_replacement_preserves_id_and_category_link(self):
        engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)
        db = session_factory()
        try:
            category = models.Category(name="Trailers")
            preroll = models.Preroll(
                filename="old.mp4",
                path="old.mp4",
                display_name="Stable reference",
                categories=[category],
            )
            db.add(preroll)
            db.commit()
            original_id = preroll.id

            apply_preroll_media_replacement(
                preroll,
                filename="new.mp4",
                path="new.mp4",
                tags=None,
                description=None,
                duration=5.0,
                file_size=50,
                file_hash="replacement",
            )
            db.commit()
            db.expire_all()

            replaced = db.query(models.Preroll).filter(
                models.Preroll.id == original_id
            ).one()
            self.assertEqual(replaced.filename, "new.mp4")
            self.assertEqual(replaced.display_name, "Stable reference")
            self.assertEqual([item.id for item in replaced.categories], [category.id])
            self.assertEqual(db.query(models.Preroll).count(), 1)
        finally:
            db.close()
            engine.dispose()

    def test_orm_delete_clears_secondary_links_loaded_or_unloaded(self):
        for load_relationship in (False, True):
            with self.subTest(load_relationship=load_relationship):
                engine = create_engine("sqlite:///:memory:")
                models.Base.metadata.create_all(engine)
                session_factory = sessionmaker(bind=engine)
                db = session_factory()
                try:
                    category = models.Category(name="Trailers")
                    preroll = models.Preroll(
                        filename="intro.mp4",
                        path="intro.mp4",
                        categories=[category],
                    )
                    db.add(preroll)
                    db.commit()
                    preroll_id = preroll.id
                    db.expire_all()

                    preroll = db.query(models.Preroll).filter(
                        models.Preroll.id == preroll_id
                    ).first()
                    if load_relationship:
                        self.assertEqual(len(preroll.categories), 1)

                    db.delete(preroll)
                    db.commit()

                    self.assertIsNone(
                        db.query(models.Preroll).filter(
                            models.Preroll.id == preroll_id
                        ).first()
                    )
                    links = db.execute(models.preroll_categories.select()).all()
                    self.assertEqual(links, [])
                finally:
                    db.close()
                    engine.dispose()


class PrerollDeleteMediaSafetyTests(unittest.TestCase):
    """The delete endpoint's file choreography: trash first, then commit, so a
    database failure can be undone by moving the file straight back."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = self.temp_dir.name
        self.prerolls_dir = os.path.join(self.data_dir, "prerolls")
        os.makedirs(os.path.join(self.prerolls_dir, "AI"))
        self.path = os.path.join(self.prerolls_dir, "AI", "intro.mp4")
        with open(self.path, "wb") as handle:
            handle.write(b"payload")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_rollback_returns_a_trashed_file_to_its_original_path(self):
        transaction = ReversibleFileTransaction()
        manifest = move_to_trash(self.path, self.prerolls_dir, self.data_dir)
        transaction.record_move(self.path, manifest["trashed_path"])
        self.assertFalse(os.path.exists(self.path))

        # Simulates the endpoint's except branch after db.rollback().
        self.assertEqual(transaction.rollback(), [])
        discard_entry_dir(manifest)

        self.assertTrue(os.path.isfile(self.path))
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), b"payload")
        self.assertEqual(list_trash(self.prerolls_dir, self.data_dir), [])

    def test_commit_leaves_the_trashed_file_recoverable(self):
        transaction = ReversibleFileTransaction()
        manifest = move_to_trash(self.path, self.prerolls_dir, self.data_dir)
        transaction.record_move(self.path, manifest["trashed_path"])

        # Only staged deletions (the thumbnail) are finalized here; the video was
        # already moved and must survive so the user can restore it.
        self.assertEqual(transaction.commit(), [])

        self.assertFalse(os.path.exists(self.path))
        entries = list_trash(self.prerolls_dir, self.data_dir)
        self.assertEqual(len(entries), 1)
        self.assertTrue(os.path.isfile(entries[0]["trashed_path"]))

    def test_thumbnail_is_staged_and_only_removed_after_a_successful_commit(self):
        thumbnail = os.path.join(self.data_dir, "thumbnails", "1_intro.jpg")
        os.makedirs(os.path.dirname(thumbnail))
        with open(thumbnail, "wb") as handle:
            handle.write(b"jpeg")

        transaction = ReversibleFileTransaction()
        transaction.stage_delete(thumbnail)
        self.assertFalse(os.path.exists(thumbnail))

        self.assertEqual(transaction.rollback(), [])
        self.assertTrue(os.path.isfile(thumbnail))

        transaction = ReversibleFileTransaction()
        transaction.stage_delete(thumbnail)
        self.assertEqual(transaction.commit(), [])
        self.assertFalse(os.path.exists(thumbnail))


if __name__ == "__main__":
    unittest.main()
