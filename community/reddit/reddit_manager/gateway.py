from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .constants import (
    DEFAULT_STATE_PATH,
    OAUTH_SCOPES,
    REQUIRED_MOD_PERMISSIONS,
)
from .environment import Credentials
from .errors import AuthorizationError, DependencyError
from .planner import Action
from .spec import CommunitySpec
from .state import managed_branding_hashes, mark_branding_applied


def _load_praw():
    try:
        import praw
    except ImportError as exc:
        raise DependencyError(
            "PRAW is required for online commands. Install `community/reddit/requirements.txt`."
        ) from exc
    return praw


def _error_kind(exc: Exception) -> str:
    return type(exc).__name__


def _missing_resource(exc: Exception) -> bool:
    return type(exc).__name__ in {"NotFound", "Redirect"}


def _clean_text(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").rstrip()


def _name(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "display_name", value))


@dataclass
class ApplyReport:
    applied: list[str] = field(default_factory=list)
    manual_fallbacks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def public(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "applied_count": len(self.applied),
            "applied": self.applied,
            "manual_fallbacks": self.manual_fallbacks,
            "errors": self.errors,
        }


class PrawGateway:
    """Small, mockable boundary around Reddit's moderator APIs."""

    def __init__(
        self,
        credentials: Credentials,
        spec: CommunitySpec,
        *,
        state_path: Path = DEFAULT_STATE_PATH,
        reddit: Any = None,
    ) -> None:
        self.credentials = credentials
        self.spec = spec
        self.state_path = Path(state_path)
        if reddit is None:
            credentials.require_authorized()
            praw = _load_praw()
            reddit = praw.Reddit(
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                refresh_token=credentials.refresh_token,
                user_agent=credentials.user_agent,
            )
        self.reddit = reddit
        self.subreddit = reddit.subreddit(spec.subreddit[2:])

    def doctor(self) -> dict[str, Any]:
        username = _name(self.reddit.user.me())
        if not username:
            raise AuthorizationError("Reddit did not return an authenticated identity.")
        granted = set(self.reddit.auth.scopes())
        missing_scopes = sorted(set(OAUTH_SCOPES) - granted)

        permissions: set[str] = set()
        for moderator in self.subreddit.moderator():
            if _name(moderator).casefold() == username.casefold():
                permissions = set(getattr(moderator, "mod_permissions", []) or [])
                break
        effective_permissions = (
            set(REQUIRED_MOD_PERMISSIONS) if "all" in permissions else permissions
        )
        missing_permissions = sorted(
            set(REQUIRED_MOD_PERMISSIONS) - effective_permissions
        )
        return {
            "ok": not missing_scopes and not missing_permissions,
            "username": f"u/{username}",
            "subreddit": self.spec.subreddit,
            "scopes": sorted(granted),
            "missing_scopes": missing_scopes,
            "moderator_permissions": sorted(permissions),
            "missing_moderator_permissions": missing_permissions,
        }

    def capture(self, sections: Iterable[str]) -> dict[str, Any]:
        selected = tuple(sections)
        state: dict[str, Any] = {}
        for section in selected:
            capture = getattr(self, f"_capture_{section}")
            try:
                state[section] = capture()
            except Exception as exc:
                state[section] = {
                    "_unavailable": (
                        f"Reddit inspection failed ({_error_kind(exc)}). "
                        "No changes will be planned for this section."
                    )
                }
        return {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "subreddit": self.spec.subreddit,
            "sections": list(selected),
            "state": state,
        }

    def _capture_settings(self) -> dict[str, Any]:
        remote = dict(self.subreddit.mod.settings())
        aliases = {
            "subreddit_type": ("subreddit_type", "type"),
            "language": ("language", "lang"),
            "user_flair_enabled": ("user_flair_enabled", "flair_enabled"),
            "user_flair_self_assignable": (
                "user_flair_self_assignable",
                "flair_self_assign_enabled",
            ),
            "post_flair_enabled": ("post_flair_enabled", "link_flair_enabled"),
            "post_flair_self_assignable": (
                "post_flair_self_assignable",
                "link_flair_self_assign_enabled",
            ),
        }
        captured: dict[str, Any] = {}
        for key in self.spec.data.get("settings", {}):
            candidates = aliases.get(key, (key,))
            value = next((remote[name] for name in candidates if name in remote), None)
            if value is None and key == "user_flair_enabled":
                value = bool(remote.get("flair_position"))
            if value is None and key == "post_flair_enabled":
                value = bool(remote.get("link_flair_position"))
            captured[key] = value
        return captured

    def _capture_branding(self) -> dict[str, Any]:
        fields = (
            "community_icon",
            "icon_img",
            "banner_background_image",
            "banner_img",
            "mobile_banner_image",
            "key_color",
        )
        captured = {field: getattr(self.subreddit, field, "") for field in fields}
        captured["_managed_hashes"] = managed_branding_hashes(self.state_path)
        return captured

    def _capture_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "short_name": rule.short_name,
                "description": getattr(rule, "description", ""),
                "kind": getattr(rule, "kind", "all"),
                "violation_reason": getattr(rule, "violation_reason", ""),
                "priority": getattr(rule, "priority", None),
            }
            for rule in self.subreddit.rules
        ]

    def _capture_post_flair(self) -> list[dict[str, Any]]:
        return [self._flair_template(item) for item in self.subreddit.flair.link_templates]

    def _capture_user_flair(self) -> list[dict[str, Any]]:
        return [self._flair_template(item) for item in self.subreddit.flair.templates]

    @staticmethod
    def _flair_template(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id") or item.get("flair_template_id"),
            "text": item.get("text") or item.get("flair_text") or "",
            "allowable_content": item.get("allowable_content"),
            "background_color": item.get("background_color"),
            "css_class": item.get("css_class") or item.get("flair_css_class") or "",
            "max_emojis": item.get("max_emojis"),
            "mod_only": item.get("mod_only"),
            "text_color": item.get("text_color"),
            "text_editable": item.get("text_editable"),
        }

    def _capture_removal_reasons(self) -> list[dict[str, Any]]:
        return [
            {
                "id": reason.id,
                "title": reason.title,
                "message": reason.message,
            }
            for reason in self.subreddit.mod.removal_reasons
        ]

    def _capture_sidebar(self) -> dict[str, Any]:
        widgets = [self._snapshot_widget(widget) for widget in self.subreddit.widgets.sidebar]
        try:
            legacy = self.subreddit.wiki["config/sidebar"].content_md
        except Exception as exc:
            if not _missing_resource(exc):
                raise
            legacy = None
        return {"widgets": widgets, "legacy_markdown": legacy}

    @staticmethod
    def _snapshot_widget(widget: Any) -> dict[str, Any]:
        def value(source: Any, key: str, default: Any = None) -> Any:
            if isinstance(source, dict):
                return source.get(key, default)
            return getattr(source, key, default)

        raw_kind = str(getattr(widget, "kind", "") or "")
        kind = {
            "textarea": "text_area",
            "button": "button",
            "community-list": "community_list",
        }.get(raw_kind, raw_kind)
        item: dict[str, Any] = {
            "id": getattr(widget, "id", None),
            "kind": kind,
            "short_name": getattr(widget, "shortName", ""),
            "styles": dict(getattr(widget, "styles", {}) or {}),
        }
        if kind == "text_area":
            item["text"] = getattr(widget, "text", "")
        elif kind == "button":
            item["buttons"] = [
                {
                    "label": value(button, "text", ""),
                    "url": value(button, "url") or value(button, "linkUrl") or "",
                }
                for button in (getattr(widget, "buttons", []) or [])
            ]
        elif kind == "community_list":
            data = getattr(widget, "data", None)
            if data is None:
                try:
                    data = list(widget)
                except TypeError:
                    data = []
            item["communities"] = [_name(value) for value in data]
        return item

    def _capture_wiki(self) -> dict[str, Any]:
        pages: dict[str, Any] = {}
        for configured in self.spec.data.get("wiki", {}).get("pages", []):
            name = configured["name"]
            page = self.subreddit.wiki[name]
            try:
                settings = page.mod.settings()
                pages[name] = {
                    "content": page.content_md,
                    "listed": settings.get("listed"),
                    "permlevel": settings.get("permlevel"),
                }
            except Exception as exc:
                if not _missing_resource(exc):
                    raise
                pages[name] = None
        return pages

    def _capture_posts(self) -> list[dict[str, Any]]:
        username = _name(self.reddit.user.me())
        desired_titles = {
            post["title"].casefold()
            for post in self.spec.data.get("pinned_posts", [])
        }
        sticky_slots: dict[str, int] = {}
        candidates: dict[str, Any] = {}
        for slot in (1, 2):
            try:
                submission = self.subreddit.sticky(number=slot)
            except Exception as exc:
                if not _missing_resource(exc):
                    raise
                continue
            sticky_slots[str(submission.id)] = slot
            if str(submission.title).casefold() in desired_titles:
                candidates[str(submission.id)] = submission

        for configured in self.spec.data.get("pinned_posts", []):
            title = configured["title"]
            escaped_title = title.replace('"', '\\"')
            results = self.subreddit.search(
                f'title:"{escaped_title}"',
                syntax="lucene",
                sort="new",
                time_filter="all",
                limit=25,
            )
            for submission in results:
                if str(submission.title).casefold() == title.casefold():
                    candidates[str(submission.id)] = submission
                    break

        captured: list[dict[str, Any]] = []
        for submission in candidates.values():
            author = _name(getattr(submission, "author", None))
            if author.casefold() != username.casefold():
                captured.append(
                    {
                        "title": submission.title,
                        "managed": False,
                    }
                )
                continue
            captured.append(
                {
                    "id": submission.id,
                    "title": submission.title,
                    "body": getattr(submission, "selftext", ""),
                    "flair": getattr(submission, "link_flair_text", None),
                    "author": username,
                    "managed": True,
                    "sticky_slot": sticky_slots.get(str(submission.id)),
                }
            )
        return captured

    def _capture_automoderator(self) -> dict[str, Any]:
        page = self.subreddit.wiki["config/automoderator"]
        try:
            return {"content": page.content_md}
        except Exception as exc:
            if _missing_resource(exc):
                return {"content": None}
            raise

    def apply(self, actions: Iterable[Action]) -> ApplyReport:
        report = ApplyReport()
        brittle_sections = {"branding", "sidebar"}
        for action in actions:
            handler: Callable[[Action], list[str]] = getattr(
                self, f"_apply_{action.section}"
            )
            try:
                manual = handler(action)
                report.applied.append(action.summary)
                report.manual_fallbacks.extend(manual)
            except Exception as exc:
                reason = _error_kind(exc)
                if action.section in brittle_sections:
                    report.manual_fallbacks.append(
                        self._manual_fallback(action, reason)
                    )
                else:
                    report.errors.append(
                        f"{action.section}:{action.key} failed ({reason}); "
                        "no later data was removed or reset."
                    )
        return report

    def _apply_settings(self, action: Action) -> list[str]:
        changes = dict(action.payload["changes"])
        flair_keys = {
            "user_flair_enabled",
            "user_flair_self_assignable",
            "post_flair_enabled",
            "post_flair_self_assignable",
        }
        flair_changes = {
            key: changes.pop(key) for key in tuple(changes) if key in flair_keys
        }
        if changes:
            self.subreddit.mod.update(**changes)
        manual: list[str] = []
        if flair_changes:
            current = dict(self.subreddit.mod.settings())
            user_enabled = flair_changes.get(
                "user_flair_enabled", current.get("flair_enabled", True)
            )
            user_position: str | bool = (
                current.get("flair_position") or "right"
            ) if user_enabled else False
            post_enabled = flair_changes.get(
                "post_flair_enabled", current.get("link_flair_enabled", True)
            )
            post_position: str | bool = (
                current.get("link_flair_position") or "left"
            ) if post_enabled else False
            try:
                self.subreddit.flair.configure(
                    position=user_position,
                    self_assign=flair_changes.get(
                        "user_flair_self_assignable",
                        current.get("flair_self_assign_enabled", False),
                    ),
                    link_position=post_position,
                    link_self_assign=flair_changes.get(
                        "post_flair_self_assignable",
                        current.get("link_flair_self_assign_enabled", False),
                    ),
                )
            except Exception as exc:
                manual.append(
                    "settings:flair configuration needs manual verification in "
                    f"Mod Tools > Post and User Flair ({_error_kind(exc)})."
                )
        return manual

    def _apply_branding(self, action: Action) -> list[str]:
        praw = _load_praw()
        asset_path = Path(action.payload["asset_path"])
        kind = action.payload["asset_kind"]
        if kind == "icon":
            self.subreddit.stylesheet.upload_mobile_icon(
                praw.models.StylesheetImage(str(asset_path))
            )
        elif kind == "banner":
            self.subreddit.stylesheet.upload_banner(
                praw.models.StylesheetAsset(str(asset_path))
            )
        elif kind == "mobile_banner":
            self.subreddit.stylesheet.upload_mobile_banner(
                praw.models.StylesheetAsset(str(asset_path))
            )
        else:
            raise ValueError(f"Unsupported branding asset kind: {kind}")
        mark_branding_applied(
            self.state_path,
            asset_kind=kind,
            asset_path=asset_path,
            digest=action.payload["asset_sha256"],
        )
        return []

    def _apply_rules(self, action: Action) -> list[str]:
        if action.operation == "create":
            item = action.payload["item"]
            self.subreddit.rules.mod.add(
                short_name=item["short_name"],
                description=item.get("description", ""),
                kind=item.get("kind", "all"),
                violation_reason=item.get("violation_reason"),
            )
        else:
            self.subreddit.rules[action.payload["short_name"]].mod.update(
                **action.payload["changes"]
            )
        return []

    def _apply_post_flair(self, action: Action) -> list[str]:
        return self._apply_flair(action, self.subreddit.flair.link_templates)

    def _apply_user_flair(self, action: Action) -> list[str]:
        return self._apply_flair(action, self.subreddit.flair.templates)

    @staticmethod
    def _apply_flair(action: Action, templates: Any) -> list[str]:
        if action.operation == "create":
            item = dict(action.payload["item"])
            text = item.pop("text")
            for key in ("id", "editable"):
                item.pop(key, None)
            templates.add(text, **item)
        else:
            template_id = action.payload.get("template_id")
            if not template_id:
                raise ValueError("Reddit did not return a flair template ID")
            templates.update(template_id, **action.payload["changes"])
        return []

    def _apply_removal_reasons(self, action: Action) -> list[str]:
        reasons = self.subreddit.mod.removal_reasons
        if action.operation == "create":
            item = action.payload["item"]
            reasons.add(title=item["title"], message=item["message"])
        else:
            reason_id = action.payload.get("reason_id")
            if not reason_id:
                raise ValueError("Reddit did not return a removal reason ID")
            reasons[reason_id].update(**action.payload["changes"])
        return []

    def _apply_sidebar(self, action: Action) -> list[str]:
        if action.key == "legacy":
            self.subreddit.wiki["config/sidebar"].edit(
                content=action.payload["legacy_markdown"],
                reason="Managed by NeXroll community manager",
            )
            return []

        item = action.payload["item"]
        kind = item.get("kind") or item.get("type") or "text_area"
        kind = {
            "text": "text_area",
            "textarea": "text_area",
            "buttons": "button",
            "community-list": "community_list",
        }.get(kind, kind)
        short_name = item.get("short_name") or item.get("title")
        styles = item.get("styles") or {
            "backgroundColor": self.spec.data["branding"].get(
                "background_color", "#1A1A1A"
            ),
            "headerColor": self.spec.data["branding"].get(
                "primary_color", "#00D4FF"
            ),
        }
        payload = self._widget_payload(kind, item, short_name, styles)
        if action.operation == "create":
            widgets = self.subreddit.widgets.mod
            if kind == "text_area":
                widgets.add_text_area(
                    short_name=short_name,
                    text=payload["text"],
                    styles=styles,
                )
            elif kind == "button":
                widgets.add_button_widget(
                    short_name=short_name,
                    description=payload["description"],
                    buttons=payload["buttons"],
                    styles=styles,
                )
            elif kind == "community_list":
                widgets.add_community_list(
                    short_name=short_name,
                    description=payload["description"],
                    data=payload["data"],
                    styles=styles,
                )
            else:
                raise ValueError(f"Unsupported sidebar widget kind: {kind}")
            return []

        widget = self._find_widget(
            action.payload.get("widget_id"), str(short_name)
        )
        widget.mod.update(**payload)
        return []

    def _widget_payload(
        self,
        kind: str,
        item: dict[str, Any],
        short_name: str,
        styles: dict[str, str],
    ) -> dict[str, Any]:
        base: dict[str, Any] = {"shortName": short_name, "styles": styles}
        if kind == "text_area":
            base["text"] = item.get("text") or item.get("markdown") or ""
        elif kind == "button":
            base["description"] = item.get("description", "")
            base["buttons"] = [
                {
                    "kind": "text",
                    "text": button["label"],
                    "url": button["url"],
                    "color": self.spec.data["branding"].get(
                        "primary_color", "#00D4FF"
                    ),
                    "textColor": "#111111",
                    "fillColor": self.spec.data["branding"].get(
                        "primary_color", "#00D4FF"
                    ),
                }
                for button in item.get("buttons", [])
            ]
        elif kind == "community_list":
            base["description"] = item.get("description", "")
            base["data"] = item.get("communities") or item.get("data") or []
        return base

    def _find_widget(self, widget_id: Any, short_name: str) -> Any:
        for widget in self.subreddit.widgets.sidebar:
            if widget_id and getattr(widget, "id", None) == widget_id:
                return widget
            if str(getattr(widget, "shortName", "")).casefold() == short_name.casefold():
                return widget
        raise LookupError(f"Widget {short_name!r} is no longer present")

    def _apply_wiki(self, action: Action) -> list[str]:
        page = self.subreddit.wiki[action.payload["name"]]
        page.edit(
            content=action.payload["content"],
            reason="Managed by NeXroll community manager",
        )
        try:
            page.mod.update(
                listed=action.payload["listed"],
                permlevel=action.payload["permlevel"],
            )
        except Exception as exc:
            return [
                f"wiki:{action.key} content was applied, but page visibility/editing "
                f"needs manual verification ({_error_kind(exc)})."
            ]
        return []

    def _apply_posts(self, action: Action) -> list[str]:
        post = action.payload["post"]
        username = _name(self.reddit.user.me())
        desired_flair = post.get("flair")
        flair_id = self._flair_id(desired_flair)
        if desired_flair and not flair_id:
            raise ValueError(
                f"Configured post flair {desired_flair!r} does not exist on Reddit"
            )
        if action.operation == "create":
            submission = self.subreddit.submit(
                post["title"],
                selftext=post.get("body", ""),
                flair_id=flair_id,
                without_websockets=True,
            )
            if submission is None:
                raise RuntimeError("Reddit did not return the created submission")
            submission.mod.distinguish(how="yes")
        else:
            existing = action.payload["existing"]
            if str(existing.get("author", "")).casefold() != username.casefold():
                return [
                    f"posts:{post['title']} is not authored by the authorized account; "
                    "its body was not edited."
                ]
            submission = self.reddit.submission(id=existing["id"])
            if _clean_text(existing.get("body")) != _clean_text(post.get("body")):
                submission.edit(post.get("body", ""))
            if flair_id and existing.get("flair") != post.get("flair"):
                submission.flair.select(flair_id)

        slot = post.get("sticky_slot")
        if slot in {1, 2}:
            try:
                occupant = self.subreddit.sticky(number=slot)
            except Exception as exc:
                if not _missing_resource(exc):
                    raise
                occupant = None
            if occupant is not None and str(occupant.id) != str(submission.id):
                return [
                    f"posts:sticky slot {slot} is occupied by an unmanaged post; "
                    f"{post['title']!r} was not pinned over it."
                ]
            submission.mod.sticky(bottom=slot == 2)
        return []

    def _flair_id(self, text: Any) -> str | None:
        if not text:
            return None
        for template in self.subreddit.flair.link_templates:
            template_text = template.get("text") or template.get("flair_text") or ""
            if str(template_text).casefold() == str(text).casefold():
                return template.get("id") or template.get("flair_template_id")
        return None

    def _apply_automoderator(self, action: Action) -> list[str]:
        self.subreddit.wiki["config/automoderator"].edit(
            content=action.payload["content"],
            reason="Managed by NeXroll community manager",
        )
        return []

    @staticmethod
    def _manual_fallback(action: Action, reason: str) -> str:
        if action.section == "branding":
            destination = "Mod Tools > Community Appearance"
        else:
            destination = "Mod Tools > Community Appearance > Sidebar widgets"
        return (
            f"{action.section}:{action.key} was not changed automatically "
            f"({reason}). Apply {action.summary.lower()} in {destination}."
        )
