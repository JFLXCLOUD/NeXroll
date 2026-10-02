"""Category edits from the preroll edit dialog stick.

The dialog sent only a non-empty list, and the server always kept the primary
category. Removing a preroll's first category moved its file but left it in
that category (which still played it), and removing its last category did
nothing. The dialog now sends the whole list; an empty list removes them all.
"""

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models
from backend import preroll_files
from tests.test_trailer_filters import route


class Payload:
    """main.PrerollUpdate's fields, without importing main and its workers."""

    FIELDS = ("tags", "category_id", "category_ids", "description", "display_name",
              "new_filename", "exclude_from_matching")

    def __init__(self, **values):
        for field in self.FIELDS:
            setattr(self, field, values.get(field))


@pytest.fixture
def env(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    intros, kids = models.Category(name="Intros"), models.Category(name="Kids")
    db.add_all([intros, kids])
    db.flush()
    video = tmp_path / "prerolls" / "Intros" / "clip.mp4"
    video.parent.mkdir(parents=True)
    video.write_bytes(b"video")
    preroll = models.Preroll(filename="clip.mp4", path=str(video), category_id=intros.id, managed=True)
    preroll.categories = [intros, kids]
    db.add(preroll)
    db.commit()
    update = route(
        "update_preroll",
        HTTPException=HTTPException,
        ReversibleFileTransaction=preroll_files.ReversibleFileTransaction,
        managed_category_suffix=preroll_files.managed_category_suffix,
        move_to_unique_destination=preroll_files.move_to_unique_destination,
        validate_storage_component=preroll_files.validate_storage_component,
        rename_file_case_safe=preroll_files.rename_file_case_safe,
        validate_preroll_filename=preroll_files.validate_preroll_filename,
        # Thumbnails are not what this test is about.
        _stage_preroll_thumbnail=lambda *a, **k: (None, None),
        _log_file_transaction_errors=lambda *a, **k: None,
        _file_log=lambda *a, **k: None,
        log_event=lambda *a, **k: None,
        PREROLLS_DIR=str(tmp_path / "prerolls"),
        THUMBNAILS_DIR=str(tmp_path / "thumbnails"),
        data_dir=str(tmp_path),
    )
    yield db, preroll, intros, kids, update, Payload, tmp_path
    db.close()
    engine.dispose()


def names(preroll):
    return sorted(c.name for c in preroll.categories)


def test_removing_the_first_category_takes_it_off_the_preroll(env):
    db, preroll, intros, kids, update, Payload, tmp_path = env
    # What the dialog sends after Intros is removed: Kids becomes first.
    update(preroll.id, Payload(category_id=kids.id, category_ids=[kids.id]), db)
    db.refresh(preroll)
    assert names(preroll) == ["Kids"]
    assert preroll.category_id == kids.id
    assert (tmp_path / "prerolls" / "Kids" / "clip.mp4").exists()


def test_an_empty_list_leaves_the_preroll_uncategorized_and_its_file_in_place(env):
    db, preroll, intros, kids, update, Payload, tmp_path = env
    update(preroll.id, Payload(category_ids=[]), db)
    db.refresh(preroll)
    assert names(preroll) == []
    assert preroll.category_id is None
    assert (tmp_path / "prerolls" / "Intros" / "clip.mp4").exists()


def test_a_list_without_the_primary_still_keeps_it(env):
    # Older clients sent only the extra categories; that still works.
    db, preroll, intros, kids, update, Payload, tmp_path = env
    update(preroll.id, Payload(category_ids=[kids.id]), db)
    db.refresh(preroll)
    assert names(preroll) == ["Intros", "Kids"]
    assert preroll.category_id == intros.id


def test_leaving_categories_out_changes_nothing(env):
    db, preroll, intros, kids, update, Payload, tmp_path = env
    update(preroll.id, Payload(display_name="Renamed"), db)
    db.refresh(preroll)
    assert names(preroll) == ["Intros", "Kids"]
    assert preroll.display_name == "Renamed"
