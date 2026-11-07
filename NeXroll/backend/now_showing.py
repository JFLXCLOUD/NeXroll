"""What the dashboard says is playing now and what plays next.

The "Current & next schedule" tile used to work this out in the browser from
the stored active category, the category list and the library. On production
(November 6) it read "Shuffle / 0 prerolls / Blending Christmas Schedule +
Thanksgiving Schedule" while Plex was still playing the previous night's Adult
Swim list. Thanksgiving's category was empty, the blend was stuck retrying it,
and nothing on the tile said so. The same assembly also:

- took the playback mode from the category, where the schedule's own Playback
  setting is what Plex gets;
- counted disabled prerolls, which never play;
- showed a category's count for a schedule that plays a sequence;
- named a fallback category after whichever schedule last used it;
- offered the next schedule to start even when another one outranks it.

describe() answers from the facts the scheduler uses: the recorded state (what
Jellyfin/Emby play and what Plex was given), the schedules in their window,
select_schedules() and each category's enabled prerolls. Every string it
returns is ready to show; times are ISO on NeXroll's clock.
"""

from __future__ import annotations

import os
from typing import Optional

import backend.models as models
from backend.scheduler import (
    ROTATION_INTERVAL_SECONDS,
    _has_valid_sequence,
    _priority,
    category_preroll_count,
    schedule_can_play,
    select_schedules,
)

# Labels for each in-window schedule, for the Upcoming schedules tile.
PLAYING = "playing"          # the winner, or the blend's current pick
BLENDING = "blending"        # in the blend, not picked this interval
NO_PREROLLS = "no_prerolls"  # in its window with nothing to play
OUTRANKED = "outranked"      # lost to a higher priority or an exclusive schedule
NOT_BLENDING = "not_blending"  # blend off while two or more others blend


def _names(names) -> str:
    names = list(names)
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def _plugin_servers(setting) -> list:
    servers = []
    if getattr(setting, "jellyfin_url", None):
        servers.append("Jellyfin")
    if getattr(setting, "emby_url", None):
        servers.append("Emby")
    return servers


def nothing_to_play_effect(setting) -> str:
    """What happens when what is showing has nothing to play: nothing plays.

    Plex gets an empty list and Jellyfin and Emby get nothing at playback
    (JB, November 6). Plex used to keep the list it was last given, so the
    previous schedule's prerolls went on playing.
    """
    if not (getattr(setting, "plex_url", None) or _plugin_servers(setting)):
        return ""
    return "No prerolls play until it has some."


def _content(db, schedule) -> dict:
    """Subtitle, playback mode and preroll count for one schedule."""
    if _has_valid_sequence(schedule):
        return {"subtitle": "Sequence", "mode": "Sequence", "preroll_count": None, "category": None}
    category = getattr(schedule, "category", None)
    if not category:
        return {"subtitle": "No category", "mode": None, "preroll_count": 0, "category": None}
    return {
        "subtitle": category.name,
        # The schedule's Playback setting is what Plex gets (comma or semicolon).
        "mode": "Sequential" if getattr(schedule, "playlist", False) else "Shuffle",
        "preroll_count": category_preroll_count(db, category.id),
        "category": category.name,
    }


def _empty_reason(schedule, content) -> Optional[str]:
    """Why a schedule has nothing to play, or None if it has something."""
    if content["preroll_count"] != 0:
        return None
    if content["category"]:
        return f"{content['category']} has no enabled prerolls"
    return f"{schedule.name} has no category or sequence"


def _category_mode(category) -> str:
    return "Sequential" if getattr(category, "plex_mode", "shuffle") == "playlist" else "Shuffle"


def _result(kind, title=None, subtitle=None, **fields) -> dict:
    out = {
        "kind": kind,
        "title": title,
        "subtitle": subtitle,
        "mode": None,
        "preroll_count": None,
        "until": None,
        "exclusive": False,
        "blend": None,
        "warnings": [],
        # A few words for the first warning, for System health's value column.
        "problem": None,
    }
    out.update(fields)
    return out


def _category_result(db, setting, kind, category_id, subtitle, mode=None) -> dict:
    category = db.query(models.Category).filter(models.Category.id == category_id).first()
    count = category_preroll_count(db, category_id)
    name = category.name if category else f"Category {category_id}"
    out = _result(kind, name, subtitle, mode=mode or (_category_mode(category) if category else "Shuffle"),
                  preroll_count=count)
    if count == 0:
        out["warnings"].append(f"{name} has no enabled prerolls. {nothing_to_play_effect(setting)}".strip())
        out["problem"] = f"{name}: no prerolls"
    return out


def _schedule_result(db, setting, schedule, exclusive=False) -> dict:
    content = _content(db, schedule)
    out = _result("schedule", schedule.name, content["subtitle"], mode=content["mode"],
                  preroll_count=content["preroll_count"], exclusive=exclusive)
    reason = _empty_reason(schedule, content)
    if reason:
        out["warnings"].append(f"{reason}. {nothing_to_play_effect(setting)}".strip())
        out["problem"] = f"{content['category']}: no prerolls" if content["category"] else "Nothing to play"
    return out


def _filler_result(db, setting, filler: str) -> dict:
    filler_type, _, value = filler.partition(":")
    subtitle = "Fallback filler (no schedule is running)"
    if filler_type == "category" and value.isdigit():
        # A filler category is applied with no schedule, so Plex gets it shuffled.
        return _category_result(db, setting, "filler", int(value), subtitle, mode="Shuffle")
    if filler_type == "sequence" and value.isdigit():
        seq = db.query(models.SavedSequence).filter(models.SavedSequence.id == int(value)).first()
        return _result("filler", seq.name if seq else "Filler sequence", subtitle, mode="Sequence")
    if filler_type == "preroll" and value.isdigit():
        preroll = db.query(models.Preroll).filter(models.Preroll.id == int(value)).first()
        name = (preroll.display_name or preroll.filename) if preroll else "Filler preroll"
        return _result("filler", name, subtitle, mode="Single file")
    if filler_type == "coming_soon":
        return _result("filler", f"Coming Soon List ({value})", subtitle, mode="Single file")
    if filler_type == "dynamic":
        return _result("filler", os.path.splitext(os.path.basename(value))[0] or "Generated preroll",
                       subtitle, mode="Single file")
    return _result("filler", "Fallback filler", subtitle)


def _blend_result(db, setting, blend) -> dict:
    pointer = getattr(setting, "active_schedule_id", None)
    partners, pick, warnings = [], None, []
    for schedule in blend:
        content = _content(db, schedule)
        playable = schedule_can_play(db, schedule)
        if schedule.id == pointer:
            pick = (schedule, content)
        partners.append({
            "id": schedule.id,
            "name": schedule.name,
            "subtitle": content["subtitle"],
            "preroll_count": content["preroll_count"],
            "playable": playable,
            "current": schedule.id == pointer,
        })
        if not playable:
            warnings.append(f"{schedule.name} is left out of the blend: {_empty_reason(schedule, content)}.")
    left_out = [p["name"] for p in partners if not p["playable"]]
    problem = None
    if left_out:
        problem = f"{left_out[0]} left out" if len(left_out) == 1 else f"{len(left_out)} schedules left out"
    if not any(p["playable"] for p in partners):
        warnings = ["None of the blended schedules has prerolls to play, so no prerolls play until one of them "
                    "has some."]
        problem = "Nothing to play"
    info = {"interval_minutes": ROTATION_INTERVAL_SECONDS // 60, "schedules": partners}
    if pick:
        schedule, content = pick
        return _result("blend", schedule.name, content["subtitle"], mode=content["mode"],
                       preroll_count=content["preroll_count"], blend=info, warnings=warnings, problem=problem)
    return _result("blend", "Blend", _names(p["name"] for p in partners), blend=info, warnings=warnings,
                   problem=problem)


def _current(db, setting, scheduler, now, in_window, kind, winner, blend) -> dict:
    if setting is None:
        return _result("none")

    # A manual apply (Apply on a sequence or category, or a genre override)
    # holds until it expires, but only while no schedule is in its window.
    override = getattr(setting, "override_expires_at", None)
    if override and override > now and not in_window:
        until = override.isoformat()
        if getattr(setting, "applied_sequence_id", None):
            return _result("manual", getattr(setting, "applied_sequence_name", None) or "Sequence",
                           "Applied by hand", mode="Sequence", until=until)
        if getattr(setting, "active_category", None):
            # Set by Apply on a category, and by uploads or downloads into the
            # category that is showing (they re-apply it), so not "by hand".
            out = _category_result(db, setting, "manual", setting.active_category,
                                   "Applied outside the schedules")
            out["until"] = until
            return out

    filler = getattr(setting, "filler_active", None)
    if filler:
        return _filler_result(db, setting, filler)

    if getattr(setting, "passive_mode", False) and not in_window:
        return _result("passive", "Passive mode", "NeXroll leaves prerolls alone until a schedule starts.")

    if kind == "blend":
        return _blend_result(db, setting, blend)

    pointer = getattr(setting, "active_schedule_id", None)
    if pointer:
        schedule = next((s for s in in_window if s.id == pointer), None)
        if schedule is not None:
            return _schedule_result(db, setting, schedule,
                                    exclusive=kind == "exclusive" and winner is not None and winner.id == pointer)

    category_id = getattr(setting, "active_category", None)
    if category_id:
        if not in_window and category_id == getattr(setting, "last_schedule_fallback", None):
            return _category_result(db, setting, "fallback", category_id,
                                    "Fallback category (no schedule is running)", mode="Shuffle")
        if winner is not None and winner.category_id == category_id:
            # The pointer is cleared when a schedule is edited, until the next tick.
            return _schedule_result(db, setting, winner, exclusive=kind == "exclusive")
        return _category_result(db, setting, "category", category_id, "Category")

    if winner is not None:
        # In its window with nothing recorded: it had nothing to apply.
        return _schedule_result(db, setting, winner, exclusive=kind == "exclusive")

    if getattr(setting, "clear_when_inactive", False) and not in_window:
        return _result("cleared", "Prerolls cleared",
                       "No schedule is running and Clear When Inactive is on.")
    return _result("none")


def _states(db, kind, winner, blend, in_window, pick_id) -> dict:
    blend_ids = {s.id for s in blend}
    states = {}
    for schedule in in_window:
        if not schedule_can_play(db, schedule):
            state = NO_PREROLLS
        elif kind == "blend":
            if schedule.id not in blend_ids:
                state = NOT_BLENDING
            else:
                state = PLAYING if schedule.id == pick_id else BLENDING
        elif winner is not None and schedule.id == winner.id:
            state = PLAYING
        else:
            state = OUTRANKED
        states[str(schedule.id)] = state
    return states


def _up_next(db, scheduler, now, enabled, in_window, holiday_dates) -> Optional[dict]:
    """The next schedule to start, and what happens when it does."""
    window_ids = {s.id for s in in_window}
    starts = []
    for schedule in enabled:
        if schedule.id in window_ids:
            continue
        try:
            at = scheduler._calculate_next_run(schedule)
        except Exception:
            continue
        if at and at > now:
            starts.append((at, schedule))
    if not starts:
        return None
    starts.sort(key=lambda pair: (pair[0], -_priority(pair[1]), pair[1].id))
    at, schedule = starts[0]

    then = [s for s in enabled
            if s.id == schedule.id or scheduler._is_schedule_active(s, at, holiday_dates)]
    kind, winner, blend = select_schedules(then)
    note = None
    if kind == "blend" and schedule in blend:
        # Only partners that play; one with nothing to play is left out.
        others = [s.name for s in blend if s.id != schedule.id and schedule_can_play(db, s)]
        note = f"Joins the blend with {_names(others)}" if others else None
    elif kind == "blend":
        note = f"Won't play while {_names(s.name for s in blend)} blend"
    elif winner is not None and winner.id != schedule.id:
        if kind == "exclusive":
            note = f"Won't play while {winner.name} (exclusive) runs"
        else:
            note = f"Won't play while {winner.name} runs (priority {_priority(winner)} over {_priority(schedule)})"

    content = _content(db, schedule)
    reason = _empty_reason(schedule, content)
    return {
        "id": schedule.id,
        "name": schedule.name,
        "at": at.isoformat(),
        "subtitle": content["subtitle"],
        "note": note,
        "warning": f"{reason}, so it has nothing to play." if reason else None,
    }


def describe(db, scheduler, now) -> dict:
    """Now showing, the state of each schedule in its window, and up next."""
    setting = db.query(models.Setting).first()
    enabled = db.query(models.Schedule).filter(models.Schedule.is_active == True).all()  # noqa: E712
    holiday_dates = {}
    in_window = [s for s in enabled if scheduler._is_schedule_active(s, now, holiday_dates)]
    kind, winner, blend = select_schedules(in_window)

    result = _current(db, setting, scheduler, now, in_window, kind, winner, blend)
    if (not result["warnings"] and getattr(setting, "plex_url", None)
            and result["kind"] in ("schedule", "blend", "filler", "fallback", "category")
            and scheduler.plex_behind(setting)):
        result["warnings"].append(
            "Plex hasn't taken this change yet, so it's still playing its previous prerolls. "
            "NeXroll tries again every minute; System health shows whether Plex is reachable.")
        result["problem"] = "Plex not updated"

    pick_id = getattr(setting, "active_schedule_id", None) if setting else None
    result["schedule_states"] = _states(db, kind, winner, blend, in_window, pick_id)
    result["up_next"] = _up_next(db, scheduler, now, enabled, in_window, holiday_dates)
    return result
