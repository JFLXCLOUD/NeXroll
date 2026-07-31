import os
import tempfile
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.scanner import reconcile_prerolls


class PrerollScannerCategoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _write_video(self, *parts):
        path = os.path.join(self.temp_dir.name, *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(b"video")
        return path

    def test_rescan_categorizes_existing_uncategorized_file_after_folder_move(self):
        old_path = self._write_video("intro.mp4")
        category = models.Category(name="Generic")
        preroll = models.Preroll(filename="intro.mp4", path=old_path, managed=True)
        self.db.add_all([category, preroll])
        self.db.commit()

        new_path = os.path.join(self.temp_dir.name, "Generic", "more", "intro.mp4")
        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        os.replace(old_path, new_path)

        stats = reconcile_prerolls(self.db, self.temp_dir.name)
        self.db.refresh(preroll)

        self.assertEqual(stats["paths_updated"], 1)
        self.assertEqual(stats["categories_assigned"], 1)
        self.assertEqual(preroll.path, new_path)
        self.assertEqual(preroll.category_id, category.id)
        self.assertEqual([item.id for item in preroll.categories], [category.id])

    def test_rescan_does_not_replace_an_existing_category(self):
        path = self._write_video("Generic", "intro.mp4")
        generic = models.Category(name="Generic")
        holiday = models.Category(name="Holiday")
        preroll = models.Preroll(
            filename="intro.mp4",
            path=path,
            category_id=None,
            categories=[holiday],
            managed=True,
        )
        self.db.add_all([generic, holiday, preroll])
        self.db.commit()

        stats = reconcile_prerolls(self.db, self.temp_dir.name)
        self.db.refresh(preroll)

        self.assertEqual(stats["categories_assigned"], 0)
        self.assertIsNone(preroll.category_id)
        self.assertEqual([item.id for item in preroll.categories], [holiday.id])

    def test_rescan_new_file_populates_legacy_and_m2m_categories(self):
        path = self._write_video("Generic", "more", "intro.mp4")
        category = models.Category(name="Generic")
        self.db.add(category)
        self.db.commit()

        stats = reconcile_prerolls(self.db, self.temp_dir.name)
        preroll = self.db.query(models.Preroll).one()

        self.assertEqual(stats["new_prerolls"], 1)
        self.assertEqual(preroll.path, path)
        self.assertEqual(preroll.category_id, category.id)
        self.assertEqual([item.id for item in preroll.categories], [category.id])


if __name__ == "__main__":
    unittest.main()
