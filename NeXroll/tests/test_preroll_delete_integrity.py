import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.preroll_files import apply_preroll_media_replacement


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


if __name__ == "__main__":
    unittest.main()
