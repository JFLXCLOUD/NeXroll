"""Small, side-effect-free helpers for managed preroll files."""

from __future__ import annotations

import os
import shutil
import time
from typing import BinaryIO


MAX_PREROLL_UPLOAD_SIZE = 500 * 1024 * 1024
ALLOWED_PREROLL_EXTENSIONS = frozenset(
    {
        ".mp4", ".mkv", ".mov", ".avi", ".m4v", ".webm",
        ".wmv", ".flv", ".ts", ".mpg", ".mpeg",
    }
)


def preroll_has_category(preroll, category_id: int) -> bool:
    """Return whether a preroll carries a category through either schema path."""
    if preroll is None:
        return False
    if getattr(preroll, "category_id", None) == category_id:
        return True
    return any(
        getattr(item, "id", None) == category_id
        for item in (getattr(preroll, "categories", None) or [])
    )


def ensure_preroll_category(preroll, category) -> bool:
    """Attach ``category`` without replacing existing category assignments.

    The many-to-many relationship is canonical, while ``category_id`` remains
    populated for older queries. The return value reports whether a user-visible
    membership was added; a legacy-only row can still have its many-to-many link
    repaired while returning ``False`` because it was already categorized.
    """
    if preroll is None or category is None or getattr(category, "id", None) is None:
        return False

    current_categories = list(getattr(preroll, "categories", None) or [])
    if any(getattr(item, "id", None) == category.id for item in current_categories):
        return False

    already_visible_through_legacy = getattr(preroll, "category_id", None) == category.id
    was_uncategorized = (
        getattr(preroll, "category_id", None) is None and not current_categories
    )
    preroll.categories = current_categories + [category]
    if was_uncategorized:
        preroll.category_id = category.id
    return not already_visible_through_legacy


def thumbnail_path_candidates(
    stored_path: str | None,
    data_dir: str,
    prerolls_dir: str,
) -> list[str]:
    """Return compatible absolute candidates for a stored thumbnail path.

    Older API responses prefixed ``thumbnails/...`` with ``prerolls/``. When
    ``data_dir`` is already the preroll root (the Docker default), blindly
    joining that response produces ``.../prerolls/prerolls/thumbnails``. Keep
    the ordinary data-relative candidate first, then try preroll-root-relative
    forms so both legacy responses and current database values resolve.
    """
    raw = str(stored_path or "").strip()
    if not raw:
        return []

    candidates: list[str] = []

    def add(path: str) -> None:
        try:
            absolute = os.path.abspath(path)
        except (OSError, TypeError, ValueError):
            return
        key = os.path.normcase(os.path.normpath(absolute))
        if not any(os.path.normcase(os.path.normpath(item)) == key for item in candidates):
            candidates.append(absolute)

    if os.path.isabs(raw):
        add(raw)
    else:
        add(os.path.join(data_dir, raw))
        add(os.path.join(prerolls_dir, raw))

        slash_parts = [part for part in raw.replace("\\", "/").split("/") if part]
        if slash_parts:
            root_names = {
                "prerolls",
                os.path.basename(os.path.normpath(prerolls_dir)).casefold(),
            }
            if slash_parts[0].casefold() in root_names and len(slash_parts) > 1:
                add(os.path.join(prerolls_dir, *slash_parts[1:]))

    return candidates


def resolve_thumbnail_path(
    stored_path: str | None,
    data_dir: str,
    prerolls_dir: str,
    thumbnails_dir: str,
) -> str | None:
    """Resolve an existing thumbnail without exposing neighboring data files."""
    try:
        allowed_root = os.path.normcase(os.path.realpath(thumbnails_dir))
    except (OSError, TypeError, ValueError):
        return None

    for candidate in thumbnail_path_candidates(stored_path, data_dir, prerolls_dir):
        try:
            resolved = os.path.normcase(os.path.realpath(candidate))
            if os.path.commonpath((resolved, allowed_root)) != allowed_root:
                continue
        except (OSError, ValueError):
            continue
        if os.path.isfile(resolved):
            return resolved
    return None


def apply_preroll_media_replacement(
    preroll,
    *,
    filename: str,
    path: str,
    tags: str | None,
    description: str | None,
    duration: float | None,
    file_size: int,
    file_hash: str,
):
    """Update only media fields on an existing preroll record.

    Identity, display metadata, category relationships, and external references
    deliberately remain untouched so duplicate replacement cannot invalidate a
    fixed sequence or schedule that stores the preroll's primary key.
    """
    preroll.filename = filename
    preroll.path = path
    preroll.tags = tags
    preroll.description = description
    preroll.duration = duration
    preroll.file_size = file_size
    preroll.file_hash = file_hash
    preroll.managed = True
    return preroll


def _is_windows_unsafe_component(component: str) -> bool:
    """Return whether a single path component is unsafe on common hosts."""
    windows_reserved = {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    stem = component.split(".", 1)[0].upper()
    return (
        any(char in '<>:"/\\|?*' or ord(char) < 32 for char in component)
        or component.endswith((".", " "))
        or stem in windows_reserved
    )


def validate_preroll_filename(filename: str | None) -> str:
    """Return a safe basename for an uploaded video or raise ``ValueError``."""
    raw_name = str(filename or "").strip()
    # Treat both separators as path separators regardless of the host OS. Upload
    # metadata can originate on a different platform than the NeXroll server.
    safe_name = raw_name.replace("\\", "/").rsplit("/", 1)[-1]
    if (
        not safe_name
        or safe_name in {".", ".."}
        or "\x00" in safe_name
        or _is_windows_unsafe_component(safe_name)
    ):
        raise ValueError("Invalid filename")

    extension = os.path.splitext(safe_name)[1].lower()
    if extension not in ALLOWED_PREROLL_EXTENSIONS:
        accepted = ", ".join(sorted(ALLOWED_PREROLL_EXTENSIONS))
        raise ValueError(f"File type '{extension}' not allowed. Accepted: {accepted}")
    return safe_name


def validate_storage_component(name: str | None) -> str:
    """Validate a category name before using it as a storage directory."""
    component = str(name or "").strip()
    if (
        not component
        or component in {".", ".."}
        or "\x00" in component
        or _is_windows_unsafe_component(component)
    ):
        raise ValueError("Category name contains characters that are not safe for a storage folder")
    return component


def managed_category_suffix(current_path: str, prerolls_root: str) -> str:
    """Return the safe portion to preserve when moving between category folders.

    Managed prerolls normally live at ``<root>/<category>/<optional subdirs>/<file>``.
    Legacy database rows can point elsewhere, however. In that case only the basename
    is retained so a crafted or stale relative path cannot escape the new category.
    """
    current_abs = os.path.abspath(current_path)
    root_abs = os.path.abspath(prerolls_root)
    fallback = os.path.basename(current_abs)

    try:
        if os.path.commonpath((current_abs, root_abs)) != root_abs:
            return fallback
        relative = os.path.relpath(current_abs, root_abs)
    except (OSError, ValueError):
        return fallback

    parts = relative.split(os.sep)
    suffix = os.path.join(*parts[1:]) if len(parts) > 1 else fallback
    normalized = os.path.normpath(suffix)
    if (
        not normalized
        or normalized in {".", ".."}
        or os.path.isabs(normalized)
        or normalized.startswith(f"..{os.sep}")
    ):
        return fallback
    return normalized


def unique_destination(directory: str, filename: str) -> tuple[str, str]:
    """Return a non-existing filename and path within ``directory``.

    A suffix is added when a managed file already occupies the requested path.
    This prevents a new upload or category move from silently overwriting an
    existing preroll.
    """
    base, extension = os.path.splitext(filename)
    candidate_name = filename
    candidate_path = os.path.join(directory, candidate_name)
    counter = 1
    while os.path.exists(candidate_path):
        candidate_name = f"{base}_{counter}{extension}"
        candidate_path = os.path.join(directory, candidate_name)
        counter += 1
    return candidate_name, candidate_path


def open_unique_destination(directory: str, filename: str) -> tuple[str, str, BinaryIO]:
    """Atomically create and open a unique destination for an upload.

    ``unique_destination`` is appropriate when its caller immediately performs
    a filesystem move, but uploads need an exclusive create: concurrent requests
    must not both select and truncate the same path.
    """
    base, extension = os.path.splitext(filename)
    counter = 0
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)

    while True:
        candidate_name = filename if counter == 0 else f"{base}_{counter}{extension}"
        candidate_path = os.path.join(directory, candidate_name)
        try:
            descriptor = os.open(candidate_path, flags, 0o644)
        except FileExistsError:
            counter += 1
            continue

        try:
            return candidate_name, candidate_path, os.fdopen(descriptor, "wb")
        except Exception:
            os.close(descriptor)
            try:
                os.remove(candidate_path)
            except OSError:
                pass
            raise


def move_to_unique_destination(source: str, directory: str, filename: str) -> tuple[str, str]:
    """Move ``source`` into ``directory`` without racing another writer.

    The destination is exclusively reserved before the source is moved. This
    avoids the check-then-replace race in which two concurrent category moves
    can select the same filename and one silently overwrites the other.
    """
    os.makedirs(directory, exist_ok=True)
    candidate_name, candidate_path, reservation = open_unique_destination(directory, filename)
    reservation.close()

    try:
        try:
            # Replacing our own empty reservation is safe: no other request can
            # acquire this path between selection and the move.
            os.replace(source, candidate_path)
        except Exception:
            # Retain the existing cross-device fallback while ensuring failure
            # to remove the source does not leave a misleading successful move.
            shutil.copy2(source, candidate_path)
            try:
                os.remove(source)
            except Exception:
                try:
                    os.remove(candidate_path)
                except OSError:
                    pass
                raise
    except Exception:
        try:
            os.remove(candidate_path)
        except OSError:
            pass
        raise

    return candidate_name, candidate_path


def _move_to_exact_destination(source: str, destination: str) -> None:
    """Move a file to an unoccupied exact path without an overwrite race."""
    source_abs = os.path.abspath(source)
    destination_abs = os.path.abspath(destination)
    if source_abs == destination_abs:
        return

    same_parent = (
        os.path.normcase(os.path.dirname(source_abs))
        == os.path.normcase(os.path.dirname(destination_abs))
    )
    if same_parent and os.path.basename(source_abs).casefold() == os.path.basename(destination_abs).casefold():
        rename_file_case_safe(source_abs, destination_abs)
        return

    os.makedirs(os.path.dirname(destination_abs), exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(destination_abs, flags, 0o644)
    os.close(descriptor)
    try:
        try:
            os.replace(source_abs, destination_abs)
        except Exception:
            shutil.copy2(source_abs, destination_abs)
            try:
                os.remove(source_abs)
            except Exception:
                try:
                    os.remove(destination_abs)
                except OSError:
                    pass
                raise
    except Exception:
        try:
            os.remove(destination_abs)
        except OSError:
            pass
        raise


class ReversibleFileTransaction:
    """Track file mutations that must follow a database transaction's outcome."""

    def __init__(self) -> None:
        self._moves: list[tuple[str, str]] = []
        self._new_files: list[str] = []
        self._delete_after_commit: list[str] = []
        self._staged_deletions: list[tuple[str, str]] = []

    def record_move(self, original: str, current: str) -> None:
        """Record a completed move so rollback can reverse it in stack order."""
        if os.path.abspath(original) != os.path.abspath(current):
            self._moves.append((os.path.abspath(original), os.path.abspath(current)))

    def record_new_file(self, path: str) -> None:
        """Record a newly created file that must be removed on rollback."""
        self._new_files.append(os.path.abspath(path))

    def delete_after_commit(self, path: str | None) -> None:
        """Keep an existing file through rollback, deleting it only after commit."""
        if path:
            self._delete_after_commit.append(os.path.abspath(path))

    def stage_delete(self, path: str | None) -> str | None:
        """Move an existing file aside until the database deletion commits."""
        if not path:
            return None
        original = os.path.abspath(path)
        if not os.path.isfile(original):
            return None
        staged_name = f".{os.path.basename(original)}.nexroll-delete"
        _, staged = move_to_unique_destination(original, os.path.dirname(original), staged_name)
        self._staged_deletions.append((original, staged))
        return staged

    @staticmethod
    def _remove(path: str) -> None:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            raise

    def rollback(self) -> list[str]:
        """Undo recorded mutations, returning descriptions of any restore errors."""
        errors: list[str] = []

        for path in reversed(self._new_files):
            try:
                self._remove(path)
            except OSError as exc:
                errors.append(f"remove new file '{path}': {exc}")

        for original, current in reversed(self._moves):
            try:
                if os.path.isfile(current):
                    _move_to_exact_destination(current, original)
                elif not os.path.isfile(original):
                    errors.append(f"restore '{original}': current file '{current}' is missing")
            except OSError as exc:
                errors.append(f"restore '{current}' to '{original}': {exc}")

        for original, staged in reversed(self._staged_deletions):
            try:
                if os.path.isfile(staged):
                    _move_to_exact_destination(staged, original)
                elif not os.path.isfile(original):
                    errors.append(f"restore deleted file '{original}': staged file is missing")
            except OSError as exc:
                errors.append(f"restore deleted file '{original}': {exc}")

        return errors

    def commit(self) -> list[str]:
        """Finalize deferred deletions after the database commit succeeds."""
        errors: list[str] = []
        protected = {os.path.normcase(path) for path in self._new_files}
        paths = [staged for _, staged in self._staged_deletions]
        paths.extend(
            path for path in self._delete_after_commit
            if os.path.normcase(path) not in protected
        )
        for path in paths:
            try:
                self._remove(path)
            except OSError as exc:
                errors.append(f"delete superseded file '{path}': {exc}")
        return errors


def rename_file_case_safe(source: str, destination: str) -> None:
    """Rename a file without rejecting a Windows case-only name change.

    A case-only rename is staged through an exclusively reserved sibling path.
    On case-insensitive filesystems the requested destination initially resolves
    to the source itself, so a regular collision check would incorrectly reject
    it. Other destination collisions still raise ``FileExistsError``.
    """
    source_abs = os.path.abspath(source)
    destination_abs = os.path.abspath(destination)
    if source_abs == destination_abs:
        return

    source_parent = os.path.dirname(source_abs)
    destination_parent = os.path.dirname(destination_abs)
    case_only = (
        os.path.normcase(source_parent) == os.path.normcase(destination_parent)
        and os.path.basename(source_abs).casefold() == os.path.basename(destination_abs).casefold()
    )

    if not case_only:
        if os.path.exists(destination_abs):
            raise FileExistsError(destination_abs)
        os.rename(source_abs, destination_abs)
        return

    temp_name = f".{os.path.basename(source_abs)}.nexroll-rename"
    _, temp_path, reservation = open_unique_destination(source_parent, temp_name)
    reservation.close()
    source_is_staged = False

    def replace_with_retry(old_path: str, new_path: str) -> None:
        for attempt in range(5):
            try:
                os.replace(old_path, new_path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))

    try:
        # Windows file scanners can briefly retain a handle to a just-closed
        # reservation. A bounded retry avoids turning that transient sharing
        # violation into a failed user rename.
        replace_with_retry(source_abs, temp_path)
        source_is_staged = True
        try:
            replace_with_retry(temp_path, destination_abs)
            source_is_staged = False
        except Exception:
            # Best effort rollback. If rollback itself fails, deliberately leave
            # the staged file in place rather than deleting the user's media.
            replace_with_retry(temp_path, source_abs)
            source_is_staged = False
            raise
    finally:
        if not source_is_staged:
            try:
                os.remove(temp_path)
            except OSError:
                pass
