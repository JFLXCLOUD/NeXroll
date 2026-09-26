"""A sequence exported on one NeXroll and imported on another comes back whole.

Found in the 2.2.1 review: fixed blocks exported only their first preroll;
full bundles left out the categories of in-order blocks and alternatives;
bundle folder and file names lost their apostrophes, so the imported blocks
pointed at categories and prerolls that did not exist; .m4v and .webm files
were bundled but never imported; and a sequence named with characters outside
Latin-1 could not be exported as a bundle at all.
"""
import asyncio
import copy
import datetime
import io
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from types import SimpleNamespace
from typing import Optional

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, or_
from sqlalchemy.orm import sessionmaker

import ast
from backend import models
from backend.preroll_files import validate_storage_component
from tests.test_trailer_filters import main_ast

FUNCTIONS = {
    '_bundle_safe_name', '_attachment_header', '_loose_name', '_match_category_by_name', '_safe_tag_list',
    '_fixed_block_preroll_ids', '_block_category_ids', '_export_otherwise_block', '_import_otherwise_block',
    '_carry_block_condition', '_export_community_id', '_export_preroll_ref', '_build_sequence_export',
    '_pattern_reference_names', '_pattern_preroll_details', '_read_bundle', '_bundle_preview',
    '_bundle_target_category', '_register_bundle_video', '_import_bundle_files',
    '_is_within_directory', '_safe_extractall', 'import_sequence_pattern',
}
CONSTANTS = {'_PORTABLE_OTHERWISE_TYPES', '_PORTABLE_BLOCK_FIELDS', '_BUNDLE_VIDEO_EXTS',
             '_BUNDLE_UNSAFE_CHARS', '_WINDOWS_RESERVED_NAMES'}


def load(prerolls_dir):
    """The export and import code from main.py, sharing one namespace."""
    nodes = []
    for node in main_ast().body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in FUNCTIONS:
            node = copy.deepcopy(node)
            node.decorator_list = []
            if node.name == 'import_sequence_pattern':  # File(...), Query(...) and Form(...) defaults
                node.args.defaults = [ast.Constant(None) for _ in node.args.defaults]
            nodes.append(node)
        elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in CONSTANTS:
            nodes.append(node)
    env = dict(
        models=models, os=os, json=json, io=io, zipfile=zipfile, uuid=uuid, datetime=datetime, or_=or_,
        Optional=Optional, HTTPException=HTTPException, app_version='test',
        StreamingResponse=lambda content, media_type, headers: SimpleNamespace(content=content, headers=headers),
        _file_log=lambda *a, **k: None, log_event=lambda *a, **k: None,
        _find_community_id_by_name=lambda name: None, _unmangle_community_id=lambda cid: None,
        validate_storage_component=validate_storage_component, PREROLLS_DIR=str(prerolls_dir),
        _generate_thumbnail_for_preroll=lambda *a: None,
        UploadFile=object, File=None, Query=None, Form=None, Session=object, Depends=None,
    )
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), '<main-portability>', 'exec'), env)
    return env


class Upload:
    def __init__(self, name, data):
        self.filename, self._data = name, data

    async def read(self):
        return self._data


def session(path):
    engine = create_engine(f'sqlite:///{path}')
    models.Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


@pytest.fixture
def installs(tmp_path):
    """A source install with every kind of block, and an empty target."""
    src_dir, dst_dir = tmp_path / 'src', tmp_path / 'dst'
    src_dir.mkdir()
    dst_dir.mkdir()
    db = session(tmp_path / 'src.db')
    cats = {name: models.Category(name=name) for name in ("Halloween", "Kids' Night", "Holiday Mix", "Noël")}
    db.add_all(cats.values())
    db.flush()
    files = {
        "Pumpkin Patch.mp4": ["Halloween"], "Jack's Intro.mp4": ["Halloween", "Kids' Night"],
        "Snow Globe.mp4": ["Holiday Mix"], "Tree Lights.m4v": ["Holiday Mix"], "Sleigh Ride.webm": ["Holiday Mix"],
        "Welcome.mp4": ["Kids' Night"], "Noel Lights.mp4": ["Noël"],
    }
    prerolls = {}
    for i, (name, in_cats) in enumerate(files.items()):
        folder = src_dir / in_cats[0]
        folder.mkdir(exist_ok=True)
        (folder / name).write_bytes(f'video {i}'.encode() * (i + 1))
        p = models.Preroll(filename=name, display_name=name, path=str(folder / name), category_id=cats[in_cats[0]].id)
        p.categories = [cats[c] for c in in_cats]
        db.add(p)
        prerolls[name] = p
    db.flush()
    blocks = [
        {'type': 'random', 'category_id': cats['Halloween'].id, 'count': 2},
        {'type': 'sequential', 'category_id': cats['Holiday Mix'].id, 'count': 1},
        {'type': 'fixed', 'preroll_ids': [prerolls["Jack's Intro.mp4"].id, prerolls['Welcome.mp4'].id]},
        {'type': 'nexup_trailers', 'source': 'coming_soon', 'count': 2, 'mode': 'random',
         'ratings': ['PG'], 'restrict_ratings': True},
        {'type': 'library_trailers', 'count': 1, 'mode': 'random', 'genres': ['Horror'], 'match_playing': True},
        {'type': 'separator', 'duration': 5},
        {'type': 'coming_soon_list', 'layout': 'list'},
        {'type': 'dynamic_preroll', 'filename': 'welcome.mp4'},
        {'type': 'random', 'category_id': cats["Kids' Night"].id, 'count': 1,
         'condition': {'match': 'all', 'rules': [{'kind': 'time_window', 'start': '17:00', 'end': '21:00'}]},
         'otherwise': {'type': 'sequential', 'category_id': cats['Holiday Mix'].id, 'count': 1}},
        {'type': 'random', 'category_id': cats['Noël'].id, 'count': 1},
    ]
    db.commit()
    target = session(tmp_path / 'dst.db')
    yield SimpleNamespace(db=db, target=target, blocks=blocks, cats=cats, prerolls=prerolls,
                          src=load(src_dir), dst=load(dst_dir), dst_dir=dst_dir)
    db.close()
    target.close()


def portable(block, db):
    """A block with its database ids replaced by names, for comparing installs."""
    out = {k: v for k, v in block.items() if k not in ('id', 'label', 'category_name', 'available_prerolls')}
    if out.get('category_id'):
        out['category_id'] = db.get(models.Category, out['category_id']).name
    if 'preroll_ids' in out:
        out['preroll_ids'] = [db.get(models.Preroll, pid).display_name for pid in out['preroll_ids']]
    if isinstance(out.get('otherwise'), dict):
        out['otherwise'] = portable(out['otherwise'], db)
    return out


def run_import(env, db, name, data, mappings=None):
    fn = env['import_sequence_pattern']
    return asyncio.run(fn(Upload(name, data), False, json.dumps(mappings) if mappings is not None else None, db))


def test_a_fixed_block_exports_every_preroll_and_stays_readable_by_older_releases(installs):
    exported = installs.src['_build_sequence_export']('Seq', '', installs.blocks, 'pattern_only', installs.db)
    fixed = exported['blocks'][2]
    assert [ref['name'] for ref in fixed['prerolls']] == ["Jack's Intro.mp4", 'Welcome.mp4']
    assert fixed['preroll_name'] == "Jack's Intro.mp4"  # what an older NeXroll reads
    assert fixed['category_names'] == ['Halloween', "Kids' Night"]


@pytest.mark.parametrize('mode', ['pattern_only', 'with_community_ids', 'with_preroll_data'])
def test_a_pattern_round_trips_exactly_on_the_same_install(installs, mode):
    exported = installs.src['_build_sequence_export']('Seq', '', installs.blocks, mode, installs.db)
    result = run_import(installs.src, installs.db, 'seq.nexseq', json.dumps(exported).encode())
    assert result['match_results']['unmatched'] == 0
    assert [portable(b, installs.db) for b in result['blocks']] == [portable(b, installs.db) for b in installs.blocks]


def test_a_full_bundle_rebuilds_the_sequence_on_an_empty_install(installs):
    bundle = installs.src['_build_sequence_export']('Friday Night: Horror & Noël', '', installs.blocks,
                                                    'full_bundle', installs.db)
    data = bundle.content.getvalue()
    members = zipfile.ZipFile(io.BytesIO(data)).namelist()
    # In-order blocks and alternatives bring their categories; names keep their marks.
    assert "categories/Kids' Night/Jack's Intro.mp4" in members
    assert 'categories/Holiday Mix/Sleigh Ride.webm' in members
    assert {'fixed/Welcome.mp4', "fixed/Jack's Intro.mp4"} <= set(members)
    assert not any(':' in m for m in members)

    preview = run_import(installs.dst, installs.target, 'bundle.zip', data)['bundle_preview']
    shutil.rmtree(os.path.join(tempfile.gettempdir(), f"nexroll_preview_{preview['preview_id']}"), ignore_errors=True)
    assert sorted(c['name'] for c in preview['categories']) == ['Halloween', 'Holiday Mix', "Kids' Night", 'Noël']
    assert [s['type'] for s in preview['sequence']] == ['random', 'sequential', 'fixed', 'fixed', 'random', 'random']
    mappings = {f"category:{c['name']}": f"new:{c['name']}" for c in preview['categories']}
    mappings.update({f"fixed:{f['name']}": 'new:Imported' for f in preview['fixed']})

    result = run_import(installs.dst, installs.target, 'bundle.zip', data, mappings)
    assert result['match_results']['unmatched'] == 0
    assert [portable(b, installs.target) for b in result['blocks']] == [portable(b, installs.db) for b in installs.blocks]
    imported = {p.display_name: p for p in installs.target.query(models.Preroll).all()}
    assert set(imported) == set(installs.prerolls)  # .m4v and .webm included, nothing twice
    assert sorted(c.name for c in imported["Jack's Intro.mp4"].categories) == ['Halloween', "Kids' Night"]
    assert all(os.path.isfile(p.path) and str(installs.dst_dir) in p.path for p in imported.values())

    # Importing the same bundle again adds nothing.
    again = run_import(installs.dst, installs.target, 'bundle.zip', data, mappings)
    assert again['import_results']['prerolls_imported_count'] == 0
    assert installs.target.query(models.Preroll).count() == len(installs.prerolls)


def test_a_bundle_made_before_2_2_1_gets_its_names_back(installs):
    """Older bundles kept letters, digits and a few marks only, and had no names map."""
    exported = installs.src['_build_sequence_export']('Old', '', installs.blocks, 'with_preroll_data', installs.db)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as z:
        z.writestr('Old.nexseq', json.dumps(exported))
        z.writestr('categories/Kids Night/Jacks Intro.mp4', b'jack')
        z.writestr('categories/Kids Night/Welcome.mp4', b'welcome')
        z.writestr('MANIFEST.json', json.dumps({'sequence_name': 'Old'}))
    data = buf.getvalue()
    preview = run_import(installs.dst, installs.target, 'old.zip', data)['bundle_preview']
    shutil.rmtree(os.path.join(tempfile.gettempdir(), f"nexroll_preview_{preview['preview_id']}"), ignore_errors=True)
    assert [c['name'] for c in preview['categories']] == ["Kids' Night"]
    run_import(installs.dst, installs.target, 'old.zip', data, {"category:Kids' Night": "new:Kids' Night"})
    names = {p.display_name for p in installs.target.query(models.Preroll).all()}
    assert names == {"Jack's Intro.mp4", 'Welcome.mp4'}


def test_a_category_name_this_system_cannot_use_falls_back_to_the_bundle_folder(installs):
    env = installs.dst
    created = []
    category = env['_bundle_target_category'](installs.target, 'new:Sci-Fi: Classics', 'Sci-Fi_ Classics', created)
    assert category.name == 'Sci-Fi_ Classics' and created == ['Sci-Fi_ Classics']
    with pytest.raises(ValueError):
        env['_bundle_target_category'](installs.target, 'new:..', '..', [])


@pytest.mark.parametrize('name', ['Night — 夜', 'Noël', 'Plain', 'a"b'])
def test_any_sequence_name_can_be_downloaded(installs, name):
    header = installs.src['_attachment_header'](f'{name}_bundle.zip')
    header.encode('latin-1')  # Starlette sends headers as Latin-1
    assert header.startswith('attachment; filename="')


def test_bundle_names_keep_what_people_read_and_drop_what_filesystems_refuse(installs):
    safe = installs.src['_bundle_safe_name']
    assert safe("Kids' Night") == "Kids' Night"
    assert safe('Noël & Friends') == 'Noël & Friends'
    assert safe('Sci-Fi: Classics') == 'Sci-Fi_ Classics'
    assert safe('..') == 'item' and safe('CON') == '_CON' and safe('trailing. ') == 'trailing'


def test_a_category_matches_by_punctuation_only_when_unambiguous(installs):
    match = installs.src['_match_category_by_name']
    cats = [SimpleNamespace(name="Kids' Night"), SimpleNamespace(name='Halloween')]
    assert match('kids night', cats).name == "Kids' Night"
    assert match('HALLOWEEN', cats).name == 'Halloween'
    assert match('kids night', cats + [SimpleNamespace(name='Kids-Night')]) is None


def test_a_nexbundle_trusts_a_preroll_id_only_when_the_name_agrees(installs):
    welcome = installs.prerolls['Welcome.mp4']
    other_id = installs.prerolls['Pumpkin Patch.mp4'].id
    bundle = {'type': 'nexbundle', 'sequences': [{'name': 'S', 'blocks': [
        {'type': 'fixed', 'preroll_info': [{'id': other_id, 'name': 'Welcome.mp4'}]},
        {'type': 'sequential', 'category_name': 'Holiday Mix', 'count': 3},
    ]}]}
    result = run_import(installs.src, installs.db, 's.nexbundle', json.dumps(bundle).encode())
    fixed, sequential = result['sequences'][0]['blocks']
    assert fixed['preroll_ids'] == [welcome.id]
    assert sequential['count'] == 3
