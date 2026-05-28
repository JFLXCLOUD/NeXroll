"""
Filesystem scanner for NeXroll preroll files.

Reconciles DB Preroll rows against the actual files in PREROLLS_DIR:
  - Rewrites `path` when a row's file lives somewhere else than the DB claims
    (this is the Windows -> Docker migration fix: paths like C:\\... are
     replaced with the real /data/prerolls/... path).
  - Regenerates missing thumbnails.
  - Creates new Preroll rows for files that appear on disk without an upload
    (e.g. dropped into a category folder manually, or copied in by an external tool).
  - Assigns new prerolls to a category based on their parent folder name when an
    existing category matches. Files in the prerolls root or in folders with no
    matching category are left uncategorized (category_id = None).

Run at startup, after JSON restore, and on demand via POST /prerolls/rescan.
"""

import os
from typing import Optional, Callable

from sqlalchemy.orm import Session

from backend import models

VALID_VIDEO_EXTENSIONS = {
    '.mp4', '.mkv', '.mov', '.avi', '.m4v', '.webm', '.wmv', '.flv', '.ts'
}

# Subdirectory basenames the scanner should never recurse into.
SKIP_DIRS = {'thumbnails', 'temp', 'nexup_temp', 'tmp', '__pycache__'}


def _iter_preroll_files(prerolls_dir: str):
    """Yield (abs_path, parent_folder_basename, filename) for every valid video file."""
    if not prerolls_dir or not os.path.isdir(prerolls_dir):
        return
    prerolls_abs = os.path.abspath(prerolls_dir)
    for root, dirs, files in os.walk(prerolls_abs):
        # Prune skipped subdirectories in-place so os.walk does not recurse into them
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith('.')]
        for f in files:
            if f.startswith('.'):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext not in VALID_VIDEO_EXTENSIONS:
                continue
            abs_path = os.path.join(root, f)
            # Parent folder name relative to prerolls_dir: '' for the root itself
            try:
                rel = os.path.relpath(root, prerolls_abs)
            except Exception:
                rel = ''
            parent = '' if rel == '.' else rel.split(os.sep)[0]
            yield abs_path, parent, f


def _thumbnail_resolves(thumbnail_field: Optional[str], data_dir: Optional[str],
                       prerolls_dir: Optional[str]) -> bool:
    """Best-effort check that the stored thumbnail string points at a real file."""
    if not thumbnail_field:
        return False
    candidates = []
    if data_dir:
        candidates.append(os.path.join(data_dir, thumbnail_field))
    if prerolls_dir:
        candidates.append(os.path.join(os.path.dirname(prerolls_dir), thumbnail_field))
        candidates.append(os.path.join(prerolls_dir, thumbnail_field))
    candidates.append(thumbnail_field)  # absolute path stored verbatim
    return any(os.path.isfile(c) for c in candidates if c)


def reconcile_prerolls(
    db: Session,
    prerolls_dir: str,
    data_dir: Optional[str] = None,
    generate_thumbnail_fn: Optional[Callable] = None,
    file_log: Optional[Callable] = None,
    delete_missing: bool = False,
    dedupe: bool = False,
) -> dict:
    """
    Reconcile DB Preroll rows against on-disk files. See module docstring.

    `generate_thumbnail_fn(preroll, video_abs_path, category_name) -> Optional[str]`
    is injected to avoid a circular import with main.py.
    """
    log = file_log or (lambda *a, **k: None)
    stats = {
        "files_on_disk": 0,
        "db_rows_total": 0,
        "paths_updated": 0,
        "thumbnails_generated": 0,
        "missing_files": 0,
        "duplicate_rows": 0,
        "new_prerolls": 0,
        "deleted_missing": 0,
        "deduped_rows": 0,
        "errors": [],
    }

    if not prerolls_dir or not os.path.isdir(prerolls_dir):
        log(f"Scanner: prerolls dir '{prerolls_dir}' not found; skipping", level="WARNING")
        return stats

    # 1. Build on-disk index. by_parent_filename is the primary lookup
    #    (category folder + filename); by_filename is the unique-name fallback.
    by_parent_filename = {}   # (parent_lower, filename_lower) -> abs_path
    by_filename = {}          # filename_lower -> [abs_path, ...]
    for abs_path, parent, filename in _iter_preroll_files(prerolls_dir):
        stats["files_on_disk"] += 1
        key = (parent.lower(), filename.lower())
        by_parent_filename.setdefault(key, abs_path)
        by_filename.setdefault(filename.lower(), []).append(abs_path)

    # 2. Index categories so we can look them up by name (folder hint) and by id (path hint).
    all_categories = db.query(models.Category).all()
    cat_by_name_lower = {c.name.lower(): c for c in all_categories}
    cat_by_id = {c.id: c for c in all_categories}

    # 3. Reconcile existing DB rows.
    all_prerolls = db.query(models.Preroll).all()
    stats["db_rows_total"] = len(all_prerolls)
    matched_paths = set()

    for p in all_prerolls:
        if not p.filename:
            continue

        # Hint: prefer the category folder that matches this preroll's category
        parent_hint = ''
        cat = cat_by_id.get(p.category_id) if p.category_id else None
        if cat:
            parent_hint = cat.name.lower()

        actual = by_parent_filename.get((parent_hint, p.filename.lower()))
        if not actual:
            # Fallback to filename-only when it's unique on disk
            candidates = by_filename.get(p.filename.lower(), [])
            if len(candidates) == 1:
                actual = candidates[0]

        if actual:
            matched_paths.add(actual)
            try:
                current_norm = os.path.abspath(p.path) if p.path else None
                actual_norm = os.path.abspath(actual)
                if current_norm != actual_norm:
                    p.path = actual
                    stats["paths_updated"] += 1
            except Exception as e:
                stats["errors"].append(f"path update failed for preroll {p.id}: {e}")

            # Regenerate thumbnail if missing or its file isn't there
            if generate_thumbnail_fn and not _thumbnail_resolves(p.thumbnail, data_dir, prerolls_dir):
                try:
                    cat_name = cat.name if cat else None
                    thumb = generate_thumbnail_fn(p, actual, cat_name)
                    if thumb:
                        p.thumbnail = thumb
                        stats["thumbnails_generated"] += 1
                except Exception as e:
                    stats["errors"].append(f"thumbnail generation failed for preroll {p.id}: {e}")
        else:
            stats["missing_files"] += 1

    # 4. Create rows for orphan files (on disk but not in DB).
    for (parent_lower, _filename_lower), abs_path in by_parent_filename.items():
        if abs_path in matched_paths:
            continue
        try:
            cat = cat_by_name_lower.get(parent_lower) if parent_lower else None
            filename = os.path.basename(abs_path)
            new_p = models.Preroll(
                filename=filename,
                path=abs_path,
                category_id=cat.id if cat else None,
                managed=True,
            )
            db.add(new_p)
            db.flush()
            if generate_thumbnail_fn:
                try:
                    thumb = generate_thumbnail_fn(new_p, abs_path, cat.name if cat else None)
                    if thumb:
                        new_p.thumbnail = thumb
                        stats["thumbnails_generated"] += 1
                except Exception as e:
                    stats["errors"].append(f"thumbnail generation failed for new file {filename}: {e}")
            stats["new_prerolls"] += 1
        except Exception as e:
            stats["errors"].append(f"new preroll creation failed for {abs_path}: {e}")

    # Optional cleanup passes — destructive, opt-in. Skipped on the default
    # startup scan; the rescan endpoint exposes these as separate buttons.
    if delete_missing:
        # Re-query because we may have added new rows above. A row is "missing" when
        # we didn't match it to a file on disk (its path wasn't recorded in
        # matched_paths) AND its current path doesn't resolve to a real file.
        for p in db.query(models.Preroll).all():
            try:
                actual_path = os.path.abspath(p.path) if p.path else None
                if actual_path and actual_path in matched_paths:
                    continue
                if p.path and os.path.exists(p.path):
                    continue
                db.delete(p)
                stats["deleted_missing"] += 1
            except Exception as e:
                stats["errors"].append(f"delete missing failed for preroll {getattr(p, 'id', '?')}: {e}")

    if dedupe:
        # Group remaining prerolls by normalized path; keep the lowest-id row and
        # delete the rest. Multiple DB rows pointing at the same file are an
        # artifact of historical import/sync races.
        seen_by_path = {}
        for p in db.query(models.Preroll).order_by(models.Preroll.id).all():
            if not p.path:
                continue
            try:
                key = os.path.normcase(os.path.normpath(p.path))
            except Exception:
                key = p.path
            keeper = seen_by_path.get(key)
            if keeper is None:
                seen_by_path[key] = p
                continue
            try:
                # Carry over any m2m tags the duplicate had that the keeper lacks
                keeper_cat_ids = {c.id for c in (keeper.categories or [])}
                for c in (p.categories or []):
                    if c.id not in keeper_cat_ids:
                        keeper.categories = (keeper.categories or []) + [c]
                        keeper_cat_ids.add(c.id)
                db.delete(p)
                stats["deduped_rows"] += 1
            except Exception as e:
                stats["errors"].append(f"dedupe failed for preroll {p.id}: {e}")

    # Recount missing + duplicate rows against the current DB state. These
    # power the dashboard health banner via _set_last_scan_stats(), so they
    # need to reflect *post-cleanup* reality — otherwise after a successful
    # delete_missing the banner keeps showing the old count until the next
    # full rescan. Reconcile-pass counts above are overwritten on purpose.
    try:
        current_missing = 0
        current_duplicates = 0
        seen_paths = set()
        for p in db.query(models.Preroll).all():
            if p.path and not os.path.exists(p.path):
                current_missing += 1
                continue
            if not p.path:
                continue
            try:
                key = os.path.normcase(os.path.normpath(p.path))
            except Exception:
                key = p.path
            if key in seen_paths:
                current_duplicates += 1
            else:
                seen_paths.add(key)
        stats["missing_files"] = current_missing
        stats["duplicate_rows"] = current_duplicates
    except Exception as e:
        stats["errors"].append(f"post-scan health recount failed: {e}")

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        log(f"Scanner: commit failed: {e}", level="ERROR")
        stats["errors"].append(f"commit failed: {e}")

    log(
        f"Scanner: {stats['files_on_disk']} files on disk, {stats['db_rows_total']} db rows, "
        f"{stats['paths_updated']} paths updated, {stats['thumbnails_generated']} thumbnails generated, "
        f"{stats['new_prerolls']} new rows, {stats['missing_files']} missing, "
        f"{stats['duplicate_rows']} duplicates, "
        f"{stats['deleted_missing']} deleted missing, {stats['deduped_rows']} deduped"
    )
    return stats
