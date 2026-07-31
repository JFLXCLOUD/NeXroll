from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .constants import (
    ALL_SECTIONS,
    SAFE_SECTIONS,
    SECTION_ALIASES,
    TARGET_SUBREDDIT,
)
from .errors import ConfigurationError, ConfirmationError
from .managed_content import (
    AUTOMOD_BEGIN,
    AUTOMOD_END,
    SIDEBAR_BEGIN,
    SIDEBAR_END,
    merge_managed_block,
)
from .spec import CommunitySpec, normalize_subreddit
from .state import sha256_file


@dataclass(frozen=True)
class Action:
    section: str
    operation: str
    key: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)

    def public(self) -> dict[str, str]:
        return {
            "section": self.section,
            "operation": self.operation,
            "key": self.key,
            "summary": self.summary,
        }


@dataclass
class Plan:
    subreddit: str
    sections: tuple[str, ...]
    actions: list[Action] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.actions)

    def public(self) -> dict[str, Any]:
        return {
            "subreddit": self.subreddit,
            "sections": list(self.sections),
            "action_count": len(self.actions),
            "actions": [action.public() for action in self.actions],
            "unchanged_count": len(self.unchanged),
            "warnings": self.warnings,
        }


def resolve_sections(values: Iterable[str] | None) -> tuple[str, ...]:
    if not values:
        return SAFE_SECTIONS
    requested: list[str] = []
    for raw in values:
        for value in raw.split(","):
            section = value.strip()
            if not section:
                continue
            if section == "all":
                for candidate in ALL_SECTIONS:
                    if candidate not in requested:
                        requested.append(candidate)
                continue
            if section in SECTION_ALIASES:
                for candidate in SECTION_ALIASES[section]:
                    if candidate not in requested:
                        requested.append(candidate)
                continue
            if section not in ALL_SECTIONS:
                raise ConfigurationError(
                    f"Unknown section {section!r}. Choose from: "
                    f"{', '.join((*ALL_SECTIONS, *SECTION_ALIASES))}."
                )
            if section not in requested:
                requested.append(section)
    if not requested:
        raise ConfigurationError("At least one non-empty section is required.")
    return tuple(requested)


def validate_confirmation(value: str | None, subreddit: str) -> None:
    target = normalize_subreddit(subreddit)
    if target.casefold() != TARGET_SUBREDDIT.casefold():
        raise ConfirmationError(f"Apply is locked to {TARGET_SUBREDDIT}.")
    if value != TARGET_SUBREDDIT:
        raise ConfirmationError(
            f"Apply requires the exact confirmation `--confirm {TARGET_SUBREDDIT}`."
        )


def _text(value: Any) -> str:
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").rstrip()
    return f"{text}\n" if text else ""


def _different(desired: dict[str, Any], current: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    return {
        key: desired[key]
        for key in fields
        if key in desired and desired[key] != current.get(key)
    }


def _index(
    items: Iterable[dict[str, Any]], keys: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        value = next((item.get(key) for key in keys if item.get(key)), None)
        if isinstance(value, str):
            result[value.strip().casefold()] = item
    return result


def build_plan(
    spec: CommunitySpec, snapshot: dict[str, Any], sections: Iterable[str]
) -> Plan:
    selected = tuple(sections)
    snapshot_target = normalize_subreddit(snapshot.get("subreddit", ""))
    if snapshot_target.casefold() != spec.subreddit.casefold():
        raise ConfigurationError(
            f"Snapshot targets {snapshot_target}, but configuration targets {spec.subreddit}."
        )
    current_state = snapshot.get("state")
    if not isinstance(current_state, dict):
        raise ConfigurationError("Snapshot has no `state` object.")

    plan = Plan(subreddit=spec.subreddit, sections=selected)
    for section in selected:
        current_section = current_state.get(section)
        if isinstance(current_section, dict) and current_section.get("_unavailable"):
            plan.warnings.append(
                f"{section} could not be inspected and will not be changed: "
                f"{current_section['_unavailable']}"
            )
            continue
        planner = _SECTION_PLANNERS[section]
        planner(spec, current_section, plan)
    return plan


def _plan_settings(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    desired = spec.data.get("settings", {})
    current = current if isinstance(current, dict) else {}
    manual_only = {"allow_discovery", "require_post_flair", "user_flair_editable"}
    for key in sorted(manual_only & desired.keys()):
        if current.get(key) != desired[key]:
            plan.warnings.append(
                f"settings:{key} is not reliably exposed by Reddit's public API; "
                "verify it manually in Mod Tools."
            )
    changes = {
        key: value
        for key, value in desired.items()
        if key not in manual_only and current.get(key) != value
    }
    if changes:
        plan.actions.append(
            Action(
                "settings",
                "update",
                "community",
                f"Update {len(changes)} community setting(s)",
                {"changes": changes},
            )
        )
    else:
        plan.unchanged.append("settings:community")


def _plan_branding(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    desired = spec.data.get("branding", {})
    current = current if isinstance(current, dict) else {}
    managed_hashes = current.get("_managed_hashes", {})
    if not isinstance(managed_hashes, dict):
        managed_hashes = {}
    current_fields = {
        "icon": ("community_icon", "icon_img", "icon"),
        "banner": ("banner_background_image", "banner_img", "banner"),
        "mobile_banner": ("mobile_banner_image", "mobile_banner"),
    }
    for key in ("icon", "banner", "mobile_banner"):
        path = desired.get(key)
        if not path:
            continue
        resolved_path = spec.resolve_path(path, field=f"branding.{key}")
        digest = sha256_file(resolved_path)
        if managed_hashes.get(key) == digest:
            plan.unchanged.append(f"branding:{key}")
            continue
        present = any(bool(current.get(field)) for field in current_fields[key])
        if present:
            plan.warnings.append(
                f"branding:{key} has an existing, unmanaged Reddit asset; the explicit "
                "branding apply will replace it with the configured NeXroll asset."
            )
        plan.actions.append(
            Action(
                "branding",
                "upload",
                key,
                f"Upload community {key.replace('_', ' ')}",
                {
                    "asset_path": str(resolved_path),
                    "asset_kind": key,
                    "asset_sha256": digest,
                },
            )
        )


def _plan_rules(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    desired_items = spec.data.get("rules", [])
    current_items = current if isinstance(current, list) else []
    indexed = _index(current_items, ("short_name",))
    fields = ("description", "kind", "violation_reason")
    for desired in desired_items:
        name = desired["short_name"]
        existing = indexed.get(name.casefold())
        if existing is None:
            plan.actions.append(
                Action("rules", "create", name, f"Create rule {name!r}", {"item": desired})
            )
            continue
        changes = _different(desired, existing, fields)
        if changes:
            plan.actions.append(
                Action(
                    "rules",
                    "update",
                    name,
                    f"Update rule {name!r}",
                    {"short_name": name, "changes": changes},
                )
            )
        else:
            plan.unchanged.append(f"rules:{name}")


_FLAIR_FIELDS = (
    "allowable_content",
    "background_color",
    "css_class",
    "max_emojis",
    "mod_only",
    "text_color",
    "text_editable",
)


def _plan_flair(
    section: str, desired_items: list[dict[str, Any]], current: Any, plan: Plan
) -> None:
    current_items = current if isinstance(current, list) else []
    indexed = _index(current_items, ("text", "flair_text"))
    for desired in desired_items:
        text = desired["text"]
        existing = indexed.get(text.casefold())
        if existing is None:
            plan.actions.append(
                Action(section, "create", text, f"Create {section.replace('_', ' ')} {text!r}", {"item": desired})
            )
            continue
        changes = _different(desired, existing, _FLAIR_FIELDS)
        if changes:
            plan.actions.append(
                Action(
                    section,
                    "update",
                    text,
                    f"Update {section.replace('_', ' ')} {text!r}",
                    {
                        "template_id": existing.get("id")
                        or existing.get("flair_template_id"),
                        "changes": changes,
                    },
                )
            )
        else:
            plan.unchanged.append(f"{section}:{text}")


def _plan_post_flair(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    _plan_flair("post_flair", spec.data.get("post_flair", []), current, plan)


def _plan_user_flair(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    _plan_flair("user_flair", spec.data.get("user_flair", []), current, plan)


def _plan_removal_reasons(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    desired_items = spec.data.get("removal_reasons", [])
    current_items = current if isinstance(current, list) else []
    indexed = _index(current_items, ("title",))
    for desired in desired_items:
        title = desired["title"]
        existing = indexed.get(title.casefold())
        if existing is None:
            plan.actions.append(
                Action(
                    "removal_reasons",
                    "create",
                    title,
                    f"Create removal reason {title!r}",
                    {"item": desired},
                )
            )
            continue
        changes = _different(desired, existing, ("message",))
        if changes:
            plan.actions.append(
                Action(
                    "removal_reasons",
                    "update",
                    title,
                    f"Update removal reason {title!r}",
                    {"reason_id": existing.get("id"), "changes": changes},
                )
            )
        else:
            plan.unchanged.append(f"removal_reasons:{title}")


def _canonical_widget(widget: dict[str, Any]) -> dict[str, Any]:
    kind = widget.get("kind") or widget.get("type") or "text_area"
    kind = {
        "text": "text_area",
        "textarea": "text_area",
        "buttons": "button",
        "community-list": "community_list",
    }.get(str(kind), kind)
    canonical = {
        "kind": kind,
        "short_name": widget.get("short_name")
        or widget.get("shortName")
        or widget.get("title"),
    }
    for key in ("text", "styles", "buttons", "data", "links", "communities", "show_wiki"):
        if key in widget:
            canonical[key] = _text(widget[key]) if key == "text" else widget[key]
    return canonical


def _plan_sidebar(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    current_container = current if isinstance(current, dict) else {}
    desired_items = spec.data.get("sidebar", {}).get("widgets", [])
    current_items = (
        current_container.get("widgets", [])
        if isinstance(current, dict)
        else current if isinstance(current, list) else []
    )
    indexed = _index(current_items, ("short_name", "shortName", "title"))
    for desired_raw in desired_items:
        desired = _canonical_widget(desired_raw)
        name = desired["short_name"]
        existing_raw = indexed.get(str(name).casefold())
        if existing_raw is None:
            plan.actions.append(
                Action(
                    "sidebar",
                    "create",
                    str(name),
                    f"Create sidebar widget {name!r}",
                    {"item": desired_raw},
                )
            )
            continue
        existing = _canonical_widget(existing_raw)
        comparable = {key: value for key, value in desired.items() if key != "short_name"}
        changes = {
            key: value for key, value in comparable.items() if existing.get(key) != value
        }
        if changes:
            plan.actions.append(
                Action(
                    "sidebar",
                    "update",
                    str(name),
                    f"Update sidebar widget {name!r}",
                    {
                        "widget_id": existing_raw.get("id"),
                        "item": desired_raw,
                        "changes": changes,
                    },
                )
            )
        else:
            plan.unchanged.append(f"sidebar:{name}")

    desired_legacy = spec.data.get("sidebar", {}).get("legacy_markdown")
    current_legacy = current_container.get("legacy_markdown")
    if desired_legacy is not None:
        merged_legacy = merge_managed_block(
            current_legacy,
            desired_legacy,
            begin=SIDEBAR_BEGIN,
            end=SIDEBAR_END,
            label="Old Reddit sidebar",
        )
        if _text(merged_legacy) == _text(current_legacy):
            plan.unchanged.append("sidebar:legacy")
        else:
            operation = "create" if current_legacy is None else "update"
            plan.actions.append(
                Action(
                    "sidebar",
                    operation,
                    "legacy",
                    f"{operation.title()} legacy sidebar",
                    {"legacy_markdown": merged_legacy},
                )
            )


def _plan_wiki(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    current = current if isinstance(current, dict) else {}
    for page in spec.data.get("wiki", {}).get("pages", []):
        name = page["name"]
        existing = current.get(name)
        existing_content = existing.get("content") if isinstance(existing, dict) else existing
        desired_listed = bool(page.get("listed", True))
        desired_permlevel = _wiki_permlevel(page)
        settings_changed = isinstance(existing, dict) and (
            existing.get("listed") != desired_listed
            or existing.get("permlevel") != desired_permlevel
        )
        if _text(existing_content) == _text(page["content"]) and not settings_changed:
            plan.unchanged.append(f"wiki:{name}")
            continue
        operation = "create" if existing_content is None else "update"
        plan.actions.append(
            Action(
                "wiki",
                operation,
                name,
                f"{operation.title()} wiki page {name!r}",
                {
                    "name": name,
                    "content": page["content"],
                    "listed": desired_listed,
                    "permlevel": desired_permlevel,
                },
            )
        )


def _wiki_permlevel(page: dict[str, Any]) -> int:
    if page.get("visibility") in {"mods", "private"}:
        return 2
    if page.get("editing") in {"contributors", "approved"}:
        return 1
    # With the community's global `wikimode=modonly`, level 0 remains publicly
    # readable while retaining the subreddit-level moderator edit policy.
    return 0


def _plan_posts(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    current_items = current if isinstance(current, list) else []
    indexed = _index(current_items, ("title",))
    for post in spec.data.get("pinned_posts", []):
        title = post["title"]
        existing = indexed.get(title.casefold())
        if existing is None:
            plan.actions.append(
                Action("posts", "create", title, f"Create pinned post {title!r}", {"post": post})
            )
            continue
        if existing.get("managed") is False:
            plan.warnings.append(
                f"posts:{title} matches a post owned by another account; "
                "nothing will be created or edited until the title collision is resolved."
            )
            continue
        desired_slot = post.get("sticky_slot")
        current_slot = existing.get("sticky_slot")
        body_changed = _text(existing.get("body")) != _text(post.get("body"))
        flair_changed = bool(post.get("flair")) and existing.get("flair") != post.get("flair")
        slot_changed = desired_slot not in {None, ""} and desired_slot != current_slot
        if body_changed or flair_changed or slot_changed:
            plan.actions.append(
                Action(
                    "posts",
                    "update",
                    title,
                    f"Update pinned post {title!r}",
                    {"post": post, "existing": existing},
                )
            )
        else:
            plan.unchanged.append(f"posts:{title}")


def _plan_automoderator(spec: CommunitySpec, current: Any, plan: Plan) -> None:
    desired = spec.data.get("automoderator", {})
    if not desired.get("content"):
        plan.unchanged.append("automoderator:not-configured")
        return
    current_content = current.get("content") if isinstance(current, dict) else current
    merged_content = merge_managed_block(
        current_content,
        desired["content"],
        begin=AUTOMOD_BEGIN,
        end=AUTOMOD_END,
        label="AutoModerator configuration",
    )
    if _text(current_content) == _text(merged_content):
        plan.unchanged.append("automoderator:config")
        return
    operation = "create" if current_content is None else "update"
    plan.actions.append(
        Action(
            "automoderator",
            operation,
            "config/automoderator",
            f"{operation.title()} AutoModerator configuration",
            {"content": merged_content},
        )
    )


_SECTION_PLANNERS = {
    "settings": _plan_settings,
    "branding": _plan_branding,
    "rules": _plan_rules,
    "post_flair": _plan_post_flair,
    "user_flair": _plan_user_flair,
    "removal_reasons": _plan_removal_reasons,
    "sidebar": _plan_sidebar,
    "wiki": _plan_wiki,
    "posts": _plan_posts,
    "automoderator": _plan_automoderator,
}
