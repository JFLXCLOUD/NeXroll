"""NeX-Up trailers matched to the genre of what is about to play.

NeX-Up (Coming Soon) trailer rows store their movie's or show's genres from
Radarr/Sonarr, and trailer blocks can keep to trailers that share a genre with
the Jellyfin/Emby item that is starting. "match_playing" prefers them and
falls back to the whole pool; "match_playing_only" plays none instead.
"""

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import models, scheduler as sched
from backend.sequence_conditions import evaluate_rule
from backend.shuffle_bag import clear_shuffle_bags
from backend.trailer_filters import (genre_keys, genre_rotation_key, has_trailer_policy,
                                     match_playing_genre, refresh_trailer_ratings)

MOVIES = {"Scream VII": ["Horror", "Mystery"], "Toy Story 5": ["Animation", "Family", "Comedy"],
          "Dune: Part Three": ["Science Fiction", "Adventure"]}
SHOWS = {"Stranger Things": ["Sci-Fi & Fantasy", "Mystery"], "Bluey": ["Kids", "Animation"]}


@pytest.fixture
def db(tmp_path):
    engine = create_engine("sqlite:///:memory:")
    models.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(models.Setting(timezone="UTC"))
        for i, (title, genres) in enumerate(MOVIES.items()):
            path = tmp_path / f"movie-{i}.mp4"
            path.write_bytes(b"trailer")
            session.add(models.ComingSoonTrailer(radarr_movie_id=i + 1, title=title, genres=json.dumps(genres),
                                                 local_path=str(path), status="downloaded", is_enabled=True))
        for i, (title, genres) in enumerate(SHOWS.items()):
            path = tmp_path / f"show-{i}.mp4"
            path.write_bytes(b"trailer")
            session.add(models.ComingSoonTVTrailer(sonarr_series_id=i + 1, title=title, genres=json.dumps(genres),
                                                   local_path=str(path), status="downloaded", is_enabled=True))
        # Downloaded before genres were stored: unknown until the next sync.
        path = tmp_path / "legacy.mp4"
        path.write_bytes(b"trailer")
        session.add(models.ComingSoonTrailer(radarr_movie_id=50, title="Legacy", local_path=str(path),
                                             status="downloaded", is_enabled=True))
        session.commit()
        yield session
    engine.dispose()
    clear_shuffle_bags()


def titles(rows):
    return sorted(r.title for r in rows)


def block(**extra):
    return {"type": "nexup_trailers", "source": "both", "count": 10, "mode": "random",
            "match_playing": True, **extra}


def test_compound_and_alias_genre_names_match():
    assert {"science fiction", "fantasy"} <= genre_keys(["Sci-Fi & Fantasy"])
    assert {"action", "adventure"} <= genre_keys(["Action & Adventure"])
    assert genre_keys(["  Science   Fiction "]) == {"science fiction"}
    assert not genre_keys(["Horror"]) & genre_keys(["Comedy"])
    assert genre_keys([None, "", "  "]) == set()


def test_prefers_trailers_sharing_a_genre_with_the_playing_movie(db):
    ctx = sched.playback_context(db, genres=["Science Fiction", "Thriller"])
    rows = sched.resolve_nexup_trailer_block(block(), db, context=ctx)
    # The TV show's "Sci-Fi & Fantasy" counts as science fiction.
    assert titles(rows) == ["Dune: Part Three", "Stranger Things"]


def test_source_still_applies_before_the_genre(db):
    ctx = sched.playback_context(db, genres=["Mystery"])
    assert titles(sched.resolve_nexup_trailer_block(block(source="movies"), db, context=ctx)) == ["Scream VII"]
    assert titles(sched.resolve_nexup_trailer_block(block(source="tv"), db, context=ctx)) == ["Stranger Things"]


def test_no_match_falls_back_unless_only(db):
    ctx = sched.playback_context(db, genres=["Western"])
    assert len(sched.resolve_nexup_trailer_block(block(), db, context=ctx)) == 6
    assert sched.resolve_nexup_trailer_block(block(match_playing_only=True), db, context=ctx) == []


@pytest.mark.parametrize("playing", [None, []])
def test_unknown_genre_on_plex_falls_back_unless_only(db, playing):
    # Plex passes no genres (None); an item with no genres at all gives [].
    ctx = sched.playback_context(db, media_type="movie", server_type="plex", genres=playing)
    assert len(sched.resolve_nexup_trailer_block(block(), db, context=ctx)) == 6
    assert sched.resolve_nexup_trailer_block(block(match_playing_only=True), db, context=ctx) == []


def test_trailers_without_stored_genres_never_match(db):
    ctx = sched.playback_context(db, genres=["Horror"])
    rows = sched.resolve_nexup_trailer_block(block(match_playing_only=True), db, context=ctx)
    assert titles(rows) == ["Scream VII"]


def test_off_or_without_playback_leaves_the_pool_alone(db):
    ctx = sched.playback_context(db, genres=["Horror"])
    assert len(sched.resolve_nexup_trailer_block(block(match_playing=False, match_playing_only=True), db, context=ctx)) == 6
    # Previews that simulate no playback pass no context at all.
    assert len(sched.resolve_nexup_trailer_block(block(match_playing_only=True), db)) == 6


def test_sequential_mode_orders_only_the_matching_trailers(db):
    ctx = sched.playback_context(db, genres=["Animation"])
    rows = sched.resolve_nexup_trailer_block(block(mode="sequential", match_playing_only=True), db, context=ctx)
    assert titles(rows) == ["Bluey", "Toy Story 5"]


def test_library_trailers_get_the_same_only_option(tmp_path):
    rows = [SimpleNamespace(title="Alien", genre_list=lambda: ["Horror", "Science Fiction"]),
            SimpleNamespace(title="Up", genre_list=lambda: ["Animation"])]
    horror = SimpleNamespace(genres=lambda: ["horror"])
    western = SimpleNamespace(genres=lambda: ["western"])
    lib = {"type": "library_trailers", "match_playing": True}
    assert titles(match_playing_genre(rows, lib, horror)) == ["Alien"]
    assert titles(match_playing_genre(rows, lib, western)) == ["Alien", "Up"]
    assert match_playing_genre(rows, {**lib, "match_playing_only": True}, western) == []


def test_sequence_resolution_passes_the_playing_genre_to_the_block(db):
    ctx = sched.playback_context(db, genres=["Horror"])
    paths = sched.resolve_sequence_paths([block(match_playing_only=True)], db, ("test", "genre"), context=ctx)
    assert len(paths) == 1 and paths[0].endswith("movie-0.mp4")


def test_linked_availability_follows_the_only_option(db):
    target = block(match_playing_only=True)
    intro = {"type": "separator", "condition": {"rules": [{"kind": "trailers_available", "pool": "block"}]}}
    rule = intro["condition"]["rules"][0]

    def available(genres):
        ctx = sched.playback_context(db, genres=genres)
        ctx.availability_block = target
        return evaluate_rule(rule, ctx)

    assert available(["Horror"]) is True
    assert available(["Western"]) is False


def test_only_is_an_intentional_empty_policy():
    assert has_trailer_policy([block(match_playing_only=True)])
    assert not has_trailer_policy([block()])
    # "only" without the match itself switched on does nothing.
    assert not has_trailer_policy([block(match_playing=False, match_playing_only=True)])


def test_each_genre_rotates_in_its_own_bag():
    horror = SimpleNamespace(genres=lambda: ["horror"])
    comedy = SimpleNamespace(genres=lambda: ["comedy"])
    key = ("plugin", "block", 0)
    assert genre_rotation_key(key, block(), horror) != genre_rotation_key(key, block(), comedy)
    assert genre_rotation_key(key, block(match_playing=False), horror) == key
    assert genre_rotation_key(None, block(), horror) is None


def test_sync_fills_genres_on_existing_trailers_without_touching_files(db):
    legacy = db.query(models.ComingSoonTrailer).filter_by(title="Legacy").one()
    before = legacy.id, legacy.local_path, legacy.status
    refresh_trailer_ratings(db, models.ComingSoonTrailer,
                            [{"id": 50, "certification": "PG-13", "genres": ["Thriller"]}],
                            "radarr_movie_id", "id")
    assert legacy.genre_list() == ["Thriller"] and legacy.certification == "PG-13"
    assert before == (legacy.id, legacy.local_path, legacy.status)
    # Metadata without a genres list leaves what is stored alone.
    refresh_trailer_ratings(db, models.ComingSoonTrailer, [{"id": 50, "certification": "R"}],
                            "radarr_movie_id", "id")
    assert legacy.genre_list() == ["Thriller"]
