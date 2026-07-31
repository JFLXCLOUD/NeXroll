from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .constants import TARGET_SUBREDDIT
from .errors import ConfigurationError


def normalize_subreddit(value: str) -> str:
    if isinstance(value, dict):
        value = value.get("name", "")
    name = str(value or "").strip()
    if name.casefold().startswith("r/"):
        name = name[2:]
    if not name:
        raise ConfigurationError("`subreddit` must name a community.")
    return f"r/{name}"


def _safe_path(root: Path, raw_path: str, *, field: str) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ConfigurationError(f"{field} must be a non-empty relative path.")
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ConfigurationError(f"{field} escapes the community directory.") from exc
    return candidate


def _front_matter(text: str, *, source: Path) -> tuple[dict[str, Any], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        closing = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise ConfigurationError(f"{source}: front matter is missing its closing `---`.") from exc

    metadata: dict[str, Any] = {}
    for line in lines[1:closing]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ConfigurationError(f"{source}: invalid front matter line {line!r}.")
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value: Any = raw_value.strip().strip("\"'")
        if key == "sticky_slot" and value:
            try:
                value = int(value)
            except ValueError as exc:
                raise ConfigurationError(
                    f"{source}: sticky_slot must be 1 or 2."
                ) from exc
        metadata[key] = value
    body = "\n".join(lines[closing + 1 :]).lstrip("\n")
    if text.endswith("\n"):
        body += "\n"
    return metadata, body


def _as_list(value: Any, field: str, errors: list[str]) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(f"`{field}` must be a list.")
        return []
    items: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"`{field}[{index}]` must be an object.")
            continue
        items.append(copy.deepcopy(item))
    return items


def _require_unique(
    items: list[dict[str, Any]],
    keys: tuple[str, ...],
    field: str,
    errors: list[str],
) -> None:
    seen: set[str] = set()
    for index, item in enumerate(items):
        value = next((item.get(key) for key in keys if item.get(key)), None)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"`{field}[{index}]` requires `{keys[0]}`.")
            continue
        normalized = value.strip().casefold()
        if normalized in seen:
            errors.append(f"`{field}` contains duplicate key {value!r}.")
        seen.add(normalized)


@dataclass
class CommunitySpec:
    config_path: Path
    root: Path
    data: dict[str, Any]

    @property
    def subreddit(self) -> str:
        return normalize_subreddit(self.data["subreddit"])

    def resolve_path(self, raw_path: str, *, field: str = "path") -> Path:
        return _safe_path(self.root, raw_path, field=field)

    def section(self, name: str) -> Any:
        if name == "posts":
            return self.data.get("pinned_posts", [])
        return self.data.get(name)


def load_spec(config_path: Path) -> CommunitySpec:
    config_path = Path(config_path).resolve()
    if not config_path.is_file():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    root = config_path.parent.parent if config_path.parent.name == "config" else config_path.parent
    root = root.resolve()
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Unable to read {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Community configuration must be a JSON object.")

    errors: list[str] = []
    data = copy.deepcopy(raw)
    if data.get("schema_version") not in {1, "1", "1.0"}:
        errors.append("`schema_version` must be 1.")
    try:
        subreddit_config = data.get("subreddit", {})
        subreddit = normalize_subreddit(subreddit_config)
        if subreddit.casefold() != TARGET_SUBREDDIT.casefold():
            errors.append(f"`subreddit` must target {TARGET_SUBREDDIT}.")
        else:
            if not isinstance(subreddit_config, dict):
                subreddit_config = {"name": TARGET_SUBREDDIT[2:]}
            else:
                subreddit_config = copy.deepcopy(subreddit_config)
                subreddit_config["name"] = TARGET_SUBREDDIT[2:]
            data["subreddit"] = subreddit_config
    except ConfigurationError as exc:
        errors.append(str(exc))

    if not isinstance(data.get("settings", {}), dict):
        errors.append("`settings` must be an object.")
        data["settings"] = {}
    settings = copy.deepcopy(data.get("settings", {}))
    subreddit_metadata = data.get("subreddit", {})
    if isinstance(subreddit_metadata, dict):
        for key in ("title", "public_description", "submit_text"):
            if subreddit_metadata.get(key) not in {None, ""}:
                settings.setdefault(key, subreddit_metadata[key])
        if subreddit_metadata.get("language") not in {None, ""}:
            settings.setdefault("language", subreddit_metadata["language"])
        if subreddit_metadata.get("welcome_message"):
            settings.setdefault("welcome_message_enabled", True)
            settings.setdefault("welcome_message_text", subreddit_metadata["welcome_message"])
    setting_aliases = {
        "community_type": "subreddit_type",
        "allow_spoilers": "spoilers_enabled",
    }
    for friendly, api_name in setting_aliases.items():
        if friendly in settings:
            settings.setdefault(api_name, settings.pop(friendly))
    if "wiki_enabled" in settings:
        enabled = bool(settings.pop("wiki_enabled"))
        settings.setdefault("wikimode", "modonly" if enabled else "disabled")
    data["settings"] = settings
    if not isinstance(data.get("branding", {}), dict):
        errors.append("`branding` must be an object.")
        data["branding"] = {}
    if data["branding"].get("primary_color"):
        settings.setdefault("key_color", data["branding"]["primary_color"])

    rules = _as_list(data.get("rules"), "rules", errors)
    for rule in rules:
        if "short_name" not in rule and "name" in rule:
            rule["short_name"] = rule["name"]
        if rule.get("kind", "all") not in {"all", "link", "comment"}:
            errors.append(f"Rule {rule.get('short_name', '<unnamed>')!r} has an invalid kind.")
    _require_unique(rules, ("short_name",), "rules", errors)
    data["rules"] = rules

    for field in ("post_flair", "user_flair"):
        entries = _as_list(data.get(field), field, errors)
        _require_unique(entries, ("text", "name"), field, errors)
        for entry in entries:
            if "text" not in entry and "name" in entry:
                entry["text"] = entry["name"]
            if "text_editable" not in entry and "editable" in entry:
                entry["text_editable"] = bool(entry.pop("editable"))
        data[field] = entries
    if data["post_flair"]:
        settings.setdefault("post_flair_enabled", True)
        settings.setdefault("post_flair_self_assignable", True)

    reasons = _as_list(data.get("removal_reasons"), "removal_reasons", errors)
    _require_unique(reasons, ("title",), "removal_reasons", errors)
    for reason in reasons:
        if not isinstance(reason.get("message"), str) or not reason["message"].strip():
            errors.append(f"Removal reason {reason.get('title', '<unnamed>')!r} needs `message`.")
    data["removal_reasons"] = reasons

    sidebar = data.get("sidebar", {})
    if sidebar is None:
        sidebar = {}
    if not isinstance(sidebar, dict):
        errors.append("`sidebar` must be an object.")
        sidebar = {}
    widgets = _as_list(sidebar.get("widgets"), "sidebar.widgets", errors)
    for widget in widgets:
        if "short_name" not in widget:
            widget["short_name"] = widget.get("title") or widget.get("name")
        if "kind" not in widget:
            widget["kind"] = widget.get("type", "text_area")
        widget["kind"] = {
            "text": "text_area",
            "buttons": "button",
        }.get(widget["kind"], widget["kind"])
        if "text" not in widget and "markdown" in widget:
            widget["text"] = widget["markdown"]
        widget.setdefault(
            "styles",
            {
                "backgroundColor": data["branding"].get(
                    "background_color", "#1A1A1A"
                ),
                "headerColor": data["branding"].get(
                    "primary_color", "#00D4FF"
                ),
            },
        )
        if widget.get("content_path"):
            try:
                content_path = _safe_path(
                    root, widget["content_path"], field="sidebar.widgets.content_path"
                )
                widget["text"] = content_path.read_text(encoding="utf-8")
            except (ConfigurationError, OSError) as exc:
                errors.append(str(exc))
    _require_unique(widgets, ("short_name",), "sidebar.widgets", errors)
    sidebar["widgets"] = widgets
    if sidebar.get("legacy_markdown_path"):
        try:
            legacy_path = _safe_path(
                root, sidebar["legacy_markdown_path"], field="sidebar.legacy_markdown_path"
            )
            sidebar["legacy_markdown"] = legacy_path.read_text(encoding="utf-8")
        except (ConfigurationError, OSError) as exc:
            errors.append(str(exc))
    data["sidebar"] = sidebar

    wiki = data.get("wiki", {})
    if wiki is None:
        wiki = {}
    if not isinstance(wiki, dict):
        errors.append("`wiki` must be an object.")
        wiki = {}
    pages = _as_list(wiki.get("pages"), "wiki.pages", errors)
    for page in pages:
        if "name" not in page:
            page["name"] = page.get("path")
        if page.get("content_path"):
            try:
                content_path = _safe_path(root, page["content_path"], field="wiki.pages.content_path")
                page["content"] = content_path.read_text(encoding="utf-8")
            except (ConfigurationError, OSError) as exc:
                errors.append(str(exc))
        elif not isinstance(page.get("content"), str):
            errors.append(f"Wiki page {page.get('name', '<unnamed>')!r} needs `content_path`.")
    _require_unique(pages, ("name",), "wiki.pages", errors)
    wiki["pages"] = pages
    data["wiki"] = wiki

    posts = _as_list(data.get("pinned_posts"), "pinned_posts", errors)
    hydrated_posts: list[dict[str, Any]] = []
    for post in posts:
        if not post.get("content_path"):
            errors.append("Each `pinned_posts` entry needs `content_path`.")
            continue
        try:
            path = _safe_path(root, post["content_path"], field="pinned_posts.content_path")
            metadata, body = _front_matter(path.read_text(encoding="utf-8"), source=path)
        except (ConfigurationError, OSError) as exc:
            errors.append(str(exc))
            continue
        merged = {**metadata, **post, "body": body}
        if not isinstance(merged.get("title"), str) or not merged["title"].strip():
            errors.append(f"{path}: pinned post front matter needs `title`.")
        slot = merged.get("sticky_slot")
        if slot not in {None, "", 1, 2}:
            errors.append(f"{path}: sticky_slot must be 1 or 2.")
        hydrated_posts.append(merged)
    _require_unique(hydrated_posts, ("title",), "pinned_posts", errors)
    data["pinned_posts"] = hydrated_posts

    automoderator = data.get("automoderator", {})
    if automoderator is None:
        automoderator = {}
    if not isinstance(automoderator, dict):
        errors.append("`automoderator` must be an object.")
        automoderator = {}
    if automoderator.get("path"):
        try:
            path = _safe_path(root, automoderator["path"], field="automoderator.path")
            automoderator["content"] = path.read_text(encoding="utf-8")
        except (ConfigurationError, OSError) as exc:
            errors.append(str(exc))
    data["automoderator"] = automoderator

    for key, path_value in data["branding"].items():
        if key not in {"icon", "banner", "mobile_banner"} or not path_value:
            continue
        try:
            path = _safe_path(root, path_value, field=f"branding.{key}")
            if not path.is_file():
                errors.append(f"`branding.{key}` file not found: {path}")
        except ConfigurationError as exc:
            errors.append(str(exc))

    if errors:
        joined = "\n- ".join(errors)
        raise ConfigurationError(f"Community configuration is invalid:\n- {joined}")
    return CommunitySpec(config_path=config_path, root=root, data=data)
