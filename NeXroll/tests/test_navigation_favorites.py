import ast
from pathlib import Path

import pytest
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from backend import models, navigation_favorites as favorites
from backend.dashboard_layout import upgrade_layout

@pytest.fixture
def database(tmp_path):
    engine = create_engine(f'sqlite:///{tmp_path / "favorites.db"}', connect_args={'check_same_thread': False})
    models.Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    with factory() as db:
        db.add_all([models.User(username='alice', password_hash='fixture'), models.User(username='bob', password_hash='fixture')])
        db.commit()
    yield factory
    engine.dispose()

def test_favorites_persist_across_sessions_and_remain_user_owned(database):
    with database() as db:
        alice, bob = db.query(models.User).order_by(models.User.id).all()
        assert favorites.set_page(db, alice, 'nexup/library', True) == ['nexup/library']
        favorites.set_page(db, alice, 'schedules/builder', True)
        favorites.set_page(db, bob, 'settings', True)
        favorites.set_page(db, None, 'dashboard', True)
        favorites.set_page(db, alice, 'nexup/library', True)  # idempotent, no duplicate
    with database() as db:
        alice, bob = db.query(models.User).order_by(models.User.id).all()
        assert favorites.list_pages(db, alice) == ['nexup/library', 'schedules/builder']
        assert favorites.list_pages(db, bob) == ['settings']
        assert favorites.list_pages(db, None) == ['dashboard']
        favorites.set_page(db, alice, 'settings', False)  # cannot remove Bob's row
        assert favorites.list_pages(db, bob) == ['settings']
        favorites.set_page(db, alice, 'nexup/library', False)
        assert favorites.list_pages(db, alice) == ['schedules/builder']
        db.delete(alice); db.commit()
        assert db.query(models.NavigationFavorite).count() == 2

@pytest.mark.parametrize('page', ['https://example.com', '../settings', 'schedules/missing', ''])
def test_only_known_pages_can_be_stored(database, page):
    with database() as db:
        with pytest.raises(ValueError): favorites.set_page(db, None, page, True)
        assert favorites.list_pages(db, None) == []

def test_new_tile_preserves_old_order_hidden_choices_and_geometry():
    old = {'version': 2, 'preset': 'custom', 'order': ['community', 'prerolls'],
           'hidden': ['community'], 'sizes': {'prerolls': 'lg'}, 'layouts': {'lg': [{'i':'prerolls','x':0,'y':2}]}}
    migrated = upgrade_layout(old)
    assert migrated['order'][:2] == old['order']
    assert 'library_trailers' in migrated['order']
    assert migrated['hidden'] == ['community']
    assert migrated['sizes']['prerolls'] == 'lg'
    assert migrated['layouts'] == old['layouts']
    assert upgrade_layout(migrated) == migrated

def test_routes_require_signin_and_never_accept_a_client_owner(database):
    app = FastAPI()
    def get_db():
        with database() as db: yield db
    def validate(token, db):
        return db.query(models.User).filter_by(username=token).first()
    env = dict(app=app, models=models, BaseModel=BaseModel, Session=Session, Depends=Depends,
               Request=Request, HTTPException=HTTPException, get_db=get_db,
               _check_auth_enabled=lambda db: True, _validate_session=validate)
    tree=ast.parse((Path(__file__).parents[1]/'backend/main.py').read_text(encoding='utf-8'))
    wanted={'require_auth','NavigationFavoriteUpdate','get_navigation_favorites','update_navigation_favorite'}
    nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in wanted]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),'<favorites-routes>','exec'),env)
    with TestClient(app) as client:
        assert client.get('/navigation/favorites').status_code == 401
        assert client.put('/navigation/favorites/dashboard',json={'favorite':True}).status_code == 401
        client.cookies.set('nexroll_session','alice')
        assert client.put('/navigation/favorites/nexup/library',json={'favorite':True,'user_id':2,'scope':'user:2'}).json() == {'pages':['nexup/library']}
        assert client.put('/navigation/favorites/bad',json={'favorite':True}).status_code == 422
        client.cookies.set('nexroll_session','bob')
        assert client.get('/navigation/favorites').json() == {'pages':[]}
