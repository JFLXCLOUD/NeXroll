import ast
import datetime
import json
import os
import uuid
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend import models, scheduler as sched
from backend.sequence_conditions import evaluate_rule, sequence_block_to_play
from backend.trailer_filters import filter_trailer_ratings, migrate_trailer_ratings, refresh_trailer_ratings, has_trailer_policy


@pytest.fixture
def db(tmp_path):
    engine = create_engine('sqlite:///:memory:')
    models.Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        session.add(models.Setting(timezone='UTC'))
        for model in (models.LibraryTrailer, models.ComingSoonTrailer, models.ComingSoonTVTrailer):
            for i, rating in enumerate(('PG', 'R', None, 'TV-PG', '12')):
                path = tmp_path / f'{model.__name__}-{i}.mp4'
                path.write_bytes(b'trailer')
                extra = {'genres': '["Comedy"]', 'tmdb_id': i + 1} if model == models.LibraryTrailer else {}
                session.add(model(title=f'{model.__name__}-{rating}', certification=rating,
                                  local_path=str(path), status='available' if model == models.LibraryTrailer else 'downloaded',
                                  is_enabled=True, **extra))
        session.commit()
        yield session
    engine.dispose()


@pytest.mark.parametrize('kind', ['nexup_trailers', 'library_trailers'])
def test_rating_restriction_survives_count_order_and_genre_fallback(db, kind):
    block = {'type': kind, 'source': 'both', 'count': 10, 'ratings': ['PG'], 'restrict_ratings': True,
             'match_playing': True, 'genres': ['Comedy']}
    ctx = sched.playback_context(db, genres=['Horror'])
    for mode in ('random', 'sequential', 'newest'):
        block['mode'] = mode
        rows = (sched.resolve_library_trailer_block(block, db, context=ctx) if kind == 'library_trailers'
                else sched.resolve_nexup_trailer_block(block, db))
        assert rows and all(r.certification == 'PG' for r in rows)
    block['ratings'] = []
    assert sched.resolve_sequence_paths([block], db, ('test', kind), context=ctx) == []


def test_legacy_unrestricted_and_explicit_unrated_are_distinct(db):
    rows = db.query(models.LibraryTrailer).all()
    assert filter_trailer_ratings(rows, {}) == rows
    assert filter_trailer_ratings(rows, {'ratings': []}) == rows
    unrated = filter_trailer_ratings(rows, {'ratings': ['Unrated']})
    assert len(unrated) == 1 and unrated[0].certification is None
    assert not filter_trailer_ratings(rows, {'ratings': ['G']})


@pytest.mark.parametrize('ratings', [None, 'PG', {}, ['garbage'], ['PG', 42]])
def test_malformed_restrictions_never_become_unrestricted(db, ratings):
    assert filter_trailer_ratings(db.query(models.LibraryTrailer).all(), {'ratings': ratings}) == []


def test_source_specific_availability_uses_real_files_and_filters(db):
    ctx = sched.playback_context(db)
    rule = {'kind': 'trailers_available', 'pool': 'library', 'ratings': ['PG'], 'min': 1}
    assert evaluate_rule(rule, ctx)
    assert not evaluate_rule({**rule, 'min': 2}, ctx)
    assert evaluate_rule({**rule, 'pool': 'upcoming', 'min': 2}, ctx)
    assert not evaluate_rule({**rule, 'pool': 'upcoming', 'source': 'movies', 'min': 2}, ctx)
    row = db.query(models.LibraryTrailer).filter_by(certification='PG').one()
    row.is_enabled = False
    db.commit()
    assert not evaluate_rule(rule, sched.playback_context(db))
    row.is_enabled = True
    os.unlink(row.local_path)
    assert not evaluate_rule(rule, sched.playback_context(db))


def test_linked_announcement_tracks_filters_count_conditions_and_reordering(db):
    announcement = {'type': 'fixed', 'condition': {'rules': [{'kind': 'trailers_available', 'pool': 'block', 'min': 1}]}}
    trailer = {'type': 'library_trailers', 'ratings': ['PG'], 'count': 1}
    blocks = [announcement, trailer]
    ctx = sched.playback_context(db)
    assert sequence_block_to_play(blocks, 0, ctx) is announcement
    trailer['ratings'] = ['G']
    assert sequence_block_to_play(blocks, 0, ctx) is None
    trailer['ratings'] = ['PG', 'R']
    announcement['condition']['rules'][0]['min'] = 2
    assert sequence_block_to_play(blocks, 0, ctx) is None  # two eligible, but block plays only one
    announcement['condition']['rules'][0]['min'] = 1
    trailer['condition'] = {'rules': [{'kind': 'media_type', 'value': 'episode'}]}
    assert sequence_block_to_play(blocks, 0, ctx) is None
    trailer['otherwise'] = {'type': 'library_trailers', 'ratings': ['PG'], 'count': 1}
    assert sequence_block_to_play(blocks, 0, ctx) is announcement
    assert sequence_block_to_play([trailer, announcement], 1, ctx) is None


def test_self_linked_trailer_condition_has_no_recursion_and_no_rotation_side_effect(db):
    block = {'type': 'library_trailers', 'ratings': ['PG'], 'count': 1,
             'condition': {'rules': [{'kind': 'trailers_available', 'pool': 'block'}]}}
    with patch.object(sched, 'shuffle_bag_sample') as bag:
        assert sequence_block_to_play([block], 0, sched.playback_context(db)) is block
        bag.assert_not_called()
    block['ratings'] = ['G']
    assert sequence_block_to_play([block], 0, sched.playback_context(db)) is None


def test_library_availability_excludes_the_playing_movie(db):
    ctx = sched.playback_context(db)
    ctx.tmdb_lookup = lambda: '1'
    # The shared callback closes over this same context.
    assert not evaluate_rule({'kind': 'trailers_available', 'pool': 'library', 'ratings': ['PG']}, ctx)


def test_sqlite_upgrade_preserves_old_rows_and_is_repeatable():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        for table in ('coming_soon_trailers', 'coming_soon_tv_trailers', 'library_trailers'):
            connection.exec_driver_sql(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY, title TEXT, local_path TEXT)')
            connection.exec_driver_sql(f"INSERT INTO {table} VALUES (7, 'Keep me', '/media/keep.mp4')")
        migrate_trailer_ratings(connection)
        migrate_trailer_ratings(connection)
        for table in ('coming_soon_trailers', 'coming_soon_tv_trailers', 'library_trailers'):
            assert connection.exec_driver_sql(f'SELECT * FROM {table}').one() == (7, 'Keep me', '/media/keep.mp4', None)
    engine.dispose()


def test_metadata_refresh_preserves_file_identity_and_unknown_country_rating(db):
    row = db.query(models.LibraryTrailer).first()
    row.radarr_movie_id = 9
    before = row.id, row.local_path, row.status
    refresh_trailer_ratings(db, models.LibraryTrailer, [{'id': 9, 'certification': '12'}], 'radarr_movie_id', 'id')
    assert row.certification == '12'
    assert before == (row.id, row.local_path, row.status)


@lru_cache
def main_ast():
    return ast.parse((Path(__file__).parents[1] / 'backend/main.py').read_text(encoding='utf-8'))


def route(name, **extra):
    import copy
    node = copy.deepcopy(next(n for n in main_ast().body if isinstance(n, ast.FunctionDef) and n.name == name))
    node.decorator_list = []
    node.returns = None
    node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
    for arg in node.args.args:
        arg.annotation = None
    env = dict(models=models, os=os, json=json, datetime=datetime, uuid=uuid,
               has_trailer_policy=has_trailer_policy, playback_context=sched.playback_context,
               resolve_sequence_paths=sched.resolve_sequence_paths,
               prerolls_for_category_query=sched.prerolls_for_category_query,
               _localized_now=lambda db: datetime.datetime(2026, 9, 25), **extra)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), '<main-route>', 'exec'), env)
    return env[name]


@pytest.mark.parametrize('selection', ['manual', 'schedule', 'filler'])
def test_plugin_does_not_fall_back_to_unrestricted_active_category(db, tmp_path, selection):
    path = tmp_path / 'unrestricted.mp4'
    path.write_bytes(b'x')
    category = models.Category(name='Unrestricted')
    db.add(category)
    db.flush()
    db.add(models.Preroll(filename=path.name, path=str(path), category_id=category.id, enabled=True))
    setting = db.query(models.Setting).first()
    setting.active_category = category.id
    blocks = [{'type': 'library_trailers', 'restrict_ratings': True, 'ratings': ['G']}]
    saved = models.SavedSequence(name='Restricted', blocks=json.dumps(blocks))
    db.add(saved)
    db.flush()
    if selection == 'manual':
        setting.applied_sequence_id = saved.id
        setting.override_expires_at = datetime.datetime(2026, 9, 26)
    elif selection == 'filler':
        setting.filler_active = f'sequence:{saved.id}'
    else:
        schedule = models.Schedule(name='Restricted', type='daily', start_date=datetime.datetime(2026, 1, 1),
                                   category_id=category.id, sequence=json.dumps(blocks), is_active=True)
        db.add(schedule)
        db.flush()
        setting.active_schedule_id = schedule.id
    db.commit()
    assert route('_resolve_current_intros')(db)['paths'] == []


def test_empty_restricted_schedule_clears_old_plex_prerolls(db):
    setting = db.query(models.Setting).first()
    setting.plex_url, setting.plex_token = 'http://plex.invalid', 'test'
    schedule = models.Schedule(id=77, name='Restricted', type='daily', start_date=datetime.datetime(2026, 1, 1),
                               sequence=json.dumps([{'type': 'library_trailers', 'ratings': ['G']}]))
    db.commit()
    connector = Mock()
    connector.get_server_info.return_value = {}
    connector.set_preroll.return_value = True
    scheduler = sched.Scheduler()
    with patch.object(sched, 'PlexConnector', return_value=connector), patch.object(scheduler, '_defer_preroll_write', return_value=False):
        result = scheduler._apply_schedule_sequence_to_plex(schedule, db)
    assert result.plex
    connector.set_preroll.assert_called_once_with('')


def test_export_preserves_main_and_alternative_ratings(db):
    from fastapi import HTTPException
    constants = {}
    for node in main_ast().body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in ('_PORTABLE_BLOCK_FIELDS', '_PORTABLE_OTHERWISE_TYPES'):
            constants[node.targets[0].id] = ast.literal_eval(node.value)
    otherwise = route('_export_otherwise_block', **constants)
    export = route('_build_sequence_export', **constants, _export_otherwise_block=otherwise,
                   app_version='test', HTTPException=HTTPException, _file_log=Mock(), log_event=Mock())
    for kind in ('library_trailers', 'nexup_trailers'):
        block = {'type': kind, 'count': 2, 'ratings': ['PG'], 'restrict_ratings': True,
                 'condition': {'rules': [{'kind': 'trailers_available', 'pool': 'block'}]},
                 'otherwise': {'type': kind, 'ratings': ['G'], 'restrict_ratings': True}}
        exported = export('Ratings', '', [block], 'pattern_only', db)['blocks'][0]
        assert exported['ratings'] == ['PG'] and exported['restrict_ratings'] is True
        assert exported['otherwise']['ratings'] == ['G']
        assert exported['condition'] == block['condition']


def test_existing_library_downloads_receive_metadata_without_redownload(db):
    import asyncio
    from backend import library_trailers as lt
    row = db.query(models.LibraryTrailer).filter_by(certification=None).one()
    row.radarr_movie_id = 99
    before = row.id, row.local_path, row.downloaded_at
    db.commit()
    movie = {'id': 99, 'tmdbId': 99, 'title': 'Existing', 'hasFile': True, 'certification': 'PG'}
    config = lt.normalize_config({'enabled': True, 'download': False, 'use_local': False})
    asyncio.run(lt.sync_library_trailers(db, [movie], str(Path(row.local_path).parent), config))
    assert row.certification == 'PG'
    assert before == (row.id, row.local_path, row.downloaded_at)
