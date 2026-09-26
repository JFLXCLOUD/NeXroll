"""Backups carry what the Backup page says they do, and restores put it back.

Found in the 2.2.1 review: the Plex token and Jellyfin/Emby keys live in the
OS secret store, so no backup carried them; a restore translated schedule ids
everywhere except ignored conflicts, which then named unrelated schedules;
sidebar favorites were left out; the system backup copied nexroll.db while
recent commits were still in its WAL file; and a system restore kept the old
machine's folders and brand-asset paths.
"""
import ast
import copy
import datetime
import json
import os
import shutil
import sqlite3
from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend import models
from backend.backup_utils import (normalize_preroll_id, remap_preroll_ids_json, remap_sequence_blocks,
                                  remap_sequence_json)
from tests.test_trailer_filters import main_ast

FUNCTIONS = {
    'backup_database', 'restore_database', '_export_settings', '_restore_settings', '_stamp_backup_taken',
    '_export_credentials', '_restore_credentials', '_remap_ignored_conflicts', '_snapshot_sqlite',
    '_fit_restored_database_to_this_install', '_backup_may_include_credentials',
}
CONSTANT_PREFIXES = ('_SETTINGS_', '_BACKUP_CREDENTIALS')


class FakeSecrets:
    def __init__(self, **values):
        self.values = dict(values)

    def __getattr__(self, name):
        action, _, key = name.partition('_')
        if action == 'get':
            return lambda: self.values.get(key)
        if action == 'set':
            return lambda value: self.values.__setitem__(key, value) or True
        raise AttributeError(name)


def load(secrets, prerolls_dir='.'):
    nodes = []
    for node in main_ast().body:
        if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS:
            node = copy.deepcopy(node)
            node.decorator_list = []
            if node.name in ('backup_database', 'restore_database'):  # Depends(get_db) defaults
                node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
            nodes.append(node)
        elif (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
              and node.targets[0].id.startswith(CONSTANT_PREFIXES)):
            nodes.append(node)
    env = dict(
        models=models, os=os, json=json, datetime=datetime, text=text, Optional=Optional,
        HTTPException=HTTPException, app_version='test', secure_store=secrets,
        log_event=lambda *a, **k: None, _file_log=lambda *a, **k: None,
        normalize_preroll_id=normalize_preroll_id, remap_preroll_ids_json=remap_preroll_ids_json,
        remap_sequence_blocks=remap_sequence_blocks, remap_sequence_json=remap_sequence_json,
        _refresh_schedule_next_run=lambda schedule: None,
        fs_scanner=SimpleNamespace(reconcile_prerolls=lambda *a, **k: None),
        PREROLLS_DIR=str(prerolls_dir), data_dir=str(prerolls_dir),
        _generate_thumbnail_for_preroll=lambda *a: None, _scanner_exclude_trees=lambda db: [],
        _load_ignored_path_keys=lambda db: set(), _set_last_scan_stats=lambda stats: None,
        Session=object, Depends=None, Request=object,
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<main-backup>', 'exec'), env)
    return env


def session(path):
    engine = create_engine(f'sqlite:///{path}')
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.fixture
def source(tmp_path):
    db = session(tmp_path / 'source.db')
    halloween, kids = models.Category(name='Halloween'), models.Category(name="Kids' Night")
    db.add_all([halloween, kids])
    db.flush()
    start = datetime.datetime(2026, 10, 1)
    # Gaps in the ids, as on any install where schedules have been deleted.
    schedules = [models.Schedule(id=sid, name=name, type='daily', start_date=start, category_id=halloween.id)
                 for sid, name in ((7, 'Halloween Month'), (12, 'Movie Night'), (15, 'Christmas'))]
    db.add_all(schedules)
    db.add(models.Setting(timezone='America/Chicago', plex_url='http://plex:32400',
                          ignored_conflicts=json.dumps(['12-7', '15-99'])))
    db.add(models.NavigationFavorite(scope='local', page='schedules/library', created_at=start))
    db.add(models.NavigationFavorite(scope='user:1', page='settings', created_at=start))
    db.commit()
    yield db
    db.close()


def test_a_json_backup_brings_back_credentials_conflict_ignores_and_favorites(source, tmp_path):
    src_env = load(FakeSecrets(plex_token='plex-secret', jellyfin_api_key='jf-secret'))
    backup = json.loads(json.dumps(src_env['backup_database'](db=source), default=str))
    assert backup['credentials'] == {'plex_token': 'plex-secret', 'jellyfin_api_key': 'jf-secret'}

    target_secrets = FakeSecrets(emby_api_key='kept')
    target = session(tmp_path / 'target.db')
    target.add(models.Schedule(name='Old', type='daily', start_date=datetime.datetime(2026, 1, 1)))
    target.commit()
    result = load(target_secrets)['restore_database'](backup, db=target)

    assert sorted(result['credentials_restored']) == ['jellyfin_api_key', 'plex_token']
    assert target_secrets.values == {'plex_token': 'plex-secret', 'jellyfin_api_key': 'jf-secret', 'emby_api_key': 'kept'}
    names = {s.id: s.name for s in target.query(models.Schedule).all()}
    ignored = json.loads(target.query(models.Setting).first().ignored_conflicts)
    # "15-99" named a schedule that was not in the backup, so it is dropped.
    assert [sorted(names[int(i)] for i in key.split('-')) for key in ignored] == [['Halloween Month', 'Movie Night']]
    assert [(f.scope, f.page) for f in target.query(models.NavigationFavorite).all()] == [('local', 'schedules/library')]
    target.close()


@pytest.mark.parametrize('headers,query,included', [
    ({}, {}, True),                          # the Backup page: signed-in session, or sign-in off
    ({'X-Api-Key': 'nx_read'}, {}, False),   # a read-only automation key must not get the Plex token
    ({}, {'api_key': 'nx_read'}, False),
])
def test_credentials_go_to_the_ui_but_not_to_an_api_key(source, headers, query, included):
    env = load(FakeSecrets(plex_token='plex-secret'))
    request = SimpleNamespace(headers=headers, query_params=query)
    backup = env['backup_database'](request=request, db=source)
    assert bool(backup['credentials']) is included


def test_an_older_backup_without_schedule_ids_drops_conflict_ignores_it_cannot_translate(source, tmp_path):
    backup = json.loads(json.dumps(load(FakeSecrets())['backup_database'](db=source), default=str))
    for schedule in backup['schedules']:
        schedule.pop('id')
    target = session(tmp_path / 'target.db')
    load(FakeSecrets())['restore_database'](backup, db=target)
    assert json.loads(target.query(models.Setting).first().ignored_conflicts) == []
    target.close()


@pytest.mark.parametrize('raw,expected', [
    (['7-12'], ['2-3']), (['12-7'], ['2-3']), (['7-15'], ['10-2']),  # text order, as the frontend sorts
    (['7-99', 'junk', '7'], []), (['7-12', '12-7'], ['2-3']), (None, []), ('not json', []),
])
def test_ignored_conflict_keys_follow_the_schedules(raw, expected):
    remap = load(FakeSecrets())['_remap_ignored_conflicts']
    assert json.loads(remap(json.dumps(raw) if isinstance(raw, list) else raw, {7: 2, 12: 3, 15: 10})) == expected


def test_the_system_backup_database_includes_commits_still_in_the_wal(tmp_path):
    live = tmp_path / 'live.db'
    con = sqlite3.connect(live)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA wal_autocheckpoint=0')
    con.execute('CREATE TABLE categories (name TEXT)')
    con.execute("INSERT INTO categories VALUES ('Late Addition')")
    con.commit()
    # A plain file copy misses the commit, which is what the backup used to take.
    shutil.copy(live, tmp_path / 'copied.db')
    assert sqlite3.connect(tmp_path / 'copied.db').execute('SELECT count(*) FROM sqlite_master').fetchone()[0] == 0

    snapshot = load(FakeSecrets())['_snapshot_sqlite'](str(live))
    try:
        assert sqlite3.connect(snapshot).execute('SELECT name FROM categories').fetchall() == [('Late Addition',)]
    finally:
        os.unlink(snapshot)
        con.close()


def test_a_restored_database_is_pointed_at_this_machines_folders_and_assets(tmp_path):
    env = load(FakeSecrets())
    own_folder = tmp_path / 'own-prerolls'
    own_folder.mkdir()
    existing_asset = tmp_path / 'still-here.png'
    existing_asset.write_bytes(b'x')
    restored = tmp_path / 'restored.db'
    con = sqlite3.connect(restored)
    columns = ['preroll_folder', 'nexup_storage_path', *env['_SETTINGS_FILE_PATH_COLUMNS']]
    con.execute(f"CREATE TABLE settings ({', '.join(c + ' TEXT' for c in columns)})")
    values = {'preroll_folder': r'D:\Prerolls', 'nexup_storage_path': '/data/nexup',
              'nexup_dynamic_preroll_custom_logo_path': r'D:\NeXup\dynamic_prerolls\assets\logo.png',
              'nexup_coming_soon_list_custom_audio_path': '/data/nexup/dynamic_prerolls/assets/gone.mp3',
              'nexup_dynamic_preroll_custom_backdrop_path': str(existing_asset)}
    con.execute(f"INSERT INTO settings ({', '.join(values)}) VALUES ({', '.join('?' * len(values))})", tuple(values.values()))
    con.commit()
    con.close()

    nexup_root = str(tmp_path / 'NeXup')
    report = env['_fit_restored_database_to_this_install'](
        str(restored), str(own_folder), nexup_root, ['nexup/dynamic_prerolls/assets/logo.png'])
    row = dict(zip(columns, sqlite3.connect(restored).execute(f"SELECT {', '.join(columns)} FROM settings").fetchone()))
    assert row['preroll_folder'] == str(own_folder)
    assert row['nexup_storage_path'] == nexup_root and os.path.isdir(nexup_root)
    assert row['nexup_dynamic_preroll_custom_logo_path'] == os.path.join(nexup_root, 'dynamic_prerolls', 'assets', 'logo.png')
    assert row['nexup_coming_soon_list_custom_audio_path'] == '/data/nexup/dynamic_prerolls/assets/gone.mp3'  # not in the backup
    assert row['nexup_dynamic_preroll_custom_backdrop_path'] == str(existing_asset)  # already fine here
    assert report['assets_relinked'] == 1 and len(report['paths_kept']) == 2


def test_a_json_restore_skips_brand_assets_that_are_not_on_this_machine(tmp_path):
    db = session(tmp_path / 'db.db')
    report = load(FakeSecrets())['_restore_settings'](
        db, {'nexup_dynamic_preroll_custom_logo_path': r'D:\gone\logo.png', 'timezone': 'UTC'}, {}, {})
    assert report['skipped_paths'] == [r'nexup_dynamic_preroll_custom_logo_path=D:\gone\logo.png']
    assert db.query(models.Setting).first().nexup_dynamic_preroll_custom_logo_path is None
    db.close()
