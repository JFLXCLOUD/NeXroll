from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .constants import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_CONFIG_PATH,
    DEFAULT_ENV_PATH,
    DEFAULT_STATE_PATH,
)
from .environment import read_environment
from .errors import ConfigurationError, ConfirmationError, RedditManagerError
from .gateway import PrawGateway
from .oauth import authorize
from .planner import build_plan, resolve_sections, validate_confirmation
from .snapshot_io import read_snapshot, snapshot_filename, write_json_atomic
from .spec import CommunitySpec, load_spec


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely configure the official r/NeXroll community."
    )
    parser.add_argument(
        "--config", type=Path, default=DEFAULT_CONFIG_PATH, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--env-file", type=Path, default=DEFAULT_ENV_PATH, help=argparse.SUPPRESS
    )
    parser.add_argument(
        "--state-file", type=Path, default=DEFAULT_STATE_PATH, help=argparse.SUPPRESS
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("validate", help="Validate local configuration offline.")

    authorize_parser = subparsers.add_parser(
        "authorize", help="Authorize the dedicated Reddit moderator account."
    )
    authorize_parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Print the consent URL without opening a browser.",
    )
    authorize_parser.add_argument("--timeout", type=int, default=300)

    subparsers.add_parser(
        "doctor", help="Check OAuth scopes and subreddit moderator permissions."
    )

    snapshot_parser = subparsers.add_parser(
        "snapshot", help="Save a secret-free snapshot of managed Reddit state."
    )
    _add_sections(snapshot_parser)
    snapshot_parser.add_argument("--output", type=Path)

    plan_parser = subparsers.add_parser(
        "plan", help="Compare desired configuration with Reddit without changing it."
    )
    _add_sections(plan_parser)
    plan_parser.add_argument(
        "--snapshot",
        type=Path,
        help="Plan from an existing snapshot instead of contacting Reddit.",
    )

    apply_parser = subparsers.add_parser(
        "apply", help="Back up and apply only explicitly selected changes."
    )
    _add_sections(apply_parser)
    apply_parser.add_argument("--confirm", required=True)
    apply_parser.add_argument(
        "--publish-posts",
        action="store_true",
        help="Required in addition to selecting the posts section.",
    )
    return parser


def _add_sections(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--sections",
        action="append",
        help=(
            "Comma-separated managed sections. Defaults to safe setup sections; "
            "posts and automoderator are opt-in."
        ),
    )


def _print_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True))


def _gateway(args: argparse.Namespace, spec: CommunitySpec) -> PrawGateway:
    credentials = read_environment(args.env_file)
    return PrawGateway(
        credentials,
        spec,
        state_path=args.state_file,
    )


def _validation_result(spec: CommunitySpec) -> dict[str, Any]:
    return {
        "ok": True,
        "subreddit": spec.subreddit,
        "config": str(spec.config_path),
        "counts": {
            "rules": len(spec.data.get("rules", [])),
            "post_flair": len(spec.data.get("post_flair", [])),
            "user_flair": len(spec.data.get("user_flair", [])),
            "removal_reasons": len(spec.data.get("removal_reasons", [])),
            "sidebar_widgets": len(
                spec.data.get("sidebar", {}).get("widgets", [])
            ),
            "wiki_pages": len(spec.data.get("wiki", {}).get("pages", [])),
            "pinned_posts": len(spec.data.get("pinned_posts", [])),
        },
    }


def _incomplete_sections(snapshot: dict[str, Any]) -> list[str]:
    state = snapshot.get("state", {})
    if not isinstance(state, dict):
        return ["snapshot"]
    return [
        section
        for section, value in state.items()
        if isinstance(value, dict) and value.get("_unavailable")
    ]


def _run(args: argparse.Namespace) -> int:
    spec = load_spec(args.config)
    if args.command == "validate":
        _print_json(_validation_result(spec))
        return 0

    if args.command == "authorize":
        if args.timeout < 1:
            raise ConfirmationError("--timeout must be at least one second.")
        result = authorize(
            args.env_file,
            open_browser=not args.no_browser,
            timeout_seconds=args.timeout,
        )
        _print_json(
            {
                "ok": True,
                "username": f"u/{result.username}",
                "scopes": list(result.scopes),
                "stored": "REDDIT_REFRESH_TOKEN was saved to the local .env file.",
            }
        )
        return 0

    if args.command == "doctor":
        result = _gateway(args, spec).doctor()
        _print_json(result)
        return 0 if result["ok"] else 1

    sections = resolve_sections(args.sections)
    if args.command == "snapshot":
        snapshot = _gateway(args, spec).capture(sections)
        output = args.output or DEFAULT_BACKUP_DIR / snapshot_filename()
        write_json_atomic(output, snapshot)
        _print_json(
            {
                "ok": not _incomplete_sections(snapshot),
                "snapshot": str(Path(output).resolve()),
                "sections": list(sections),
            }
        )
        return 1 if _incomplete_sections(snapshot) else 0

    if args.command == "plan":
        if args.snapshot:
            snapshot = read_snapshot(args.snapshot)
            state = snapshot.get("state", {})
            missing = [
                section
                for section in sections
                if not isinstance(state, dict) or section not in state
            ]
            if missing:
                raise ConfigurationError(
                    "Snapshot does not contain the requested section(s): "
                    + ", ".join(missing)
                    + ". Select only sections captured in that snapshot."
                )
        else:
            snapshot = _gateway(args, spec).capture(sections)
        plan = build_plan(spec, snapshot, sections)
        _print_json(plan.public())
        return 0

    validate_confirmation(args.confirm, spec.subreddit)
    if "posts" in sections and not args.publish_posts:
        raise ConfirmationError(
            "Publishing posts also requires `--publish-posts`."
        )
    gateway = _gateway(args, spec)
    backup = gateway.capture(sections)
    backup_path = DEFAULT_BACKUP_DIR / snapshot_filename("backup")
    write_json_atomic(backup_path, backup)
    incomplete = _incomplete_sections(backup)
    if incomplete:
        raise ConfigurationError(
            "Pre-apply inspection was incomplete for "
            + ", ".join(incomplete)
            + f". Nothing was changed; review backup {backup_path.resolve()}."
        )
    plan = build_plan(spec, backup, sections)
    report = gateway.apply(plan.actions)
    result = {
        "ok": report.ok,
        "backup": str(backup_path.resolve()),
        "plan": plan.public(),
        "result": report.public(),
    }
    _print_json(result)
    return 0 if report.ok else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        return _run(parser.parse_args(argv))
    except RedditManagerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("ERROR: Interrupted; no credentials were printed.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(
            f"ERROR: Reddit operation failed ({type(exc).__name__}). "
            "No secrets were printed.",
            file=sys.stderr,
        )
        return 1
