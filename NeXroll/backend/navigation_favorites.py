"""User-owned navigation shortcuts; page IDs only, never client-provided owners."""
from backend import models

PAGES = frozenset((
    'dashboard', 'library', 'library/add', 'library/categories', 'library/scaling', 'library/trash',
    'schedules', 'schedules/create', 'schedules/calendar', 'schedules/builder', 'schedules/library', 'schedules/conflicts',
    'nexup', 'nexup/upcoming', 'nexup/trailers', 'nexup/library', 'nexup/generator', 'nexup/settings',
    'connect', 'community-prerolls/browse', 'community-prerolls/search',
    'settings', 'settings/paths', 'settings/storage', 'settings/apikeys', 'settings/logs',
    'settings/users', 'settings/backup', 'settings/system',
))

def scope_for(user):
    return f'user:{user.id}' if user is not None else 'local'

def list_pages(db, user):
    rows = db.query(models.NavigationFavorite).filter_by(scope=scope_for(user)).order_by(
        models.NavigationFavorite.created_at, models.NavigationFavorite.page).all()
    return [row.page for row in rows if row.page in PAGES]

def set_page(db, user, page, favorite):
    from sqlalchemy.exc import IntegrityError
    if page not in PAGES:
        raise ValueError('Unknown page')
    scope = scope_for(user)
    row = db.query(models.NavigationFavorite).filter_by(scope=scope, page=page).first()
    if favorite and row is None:
        db.add(models.NavigationFavorite(scope=scope, page=page, user_id=user.id if user else None))
    elif not favorite and row is not None:
        db.delete(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # Concurrent requests may both add the same shortcut; that is success.
        if not favorite or not db.query(models.NavigationFavorite).filter_by(scope=scope, page=page).first():
            raise
    return list_pages(db, user)
