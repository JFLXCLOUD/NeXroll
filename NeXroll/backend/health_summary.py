"""Composite system-health score for the dashboard's System health tile.

The tile shows one number and a short list of what is and is not healthy. The
scoring lives here, separate from the endpoint that gathers the facts, so the
rules can be tested without standing up the app.

Design rule: a check we could not measure never costs the user points. An
unreachable media server is a real problem and scores as one; a check that
simply did not run (no community index configured, conflicts not supplied by
the caller) is reported as "unknown" and left out of the maths entirely.
Otherwise a fresh install would open on a scary-looking score.
"""

from __future__ import annotations

from typing import Optional

OK = "ok"
WARN = "warn"
ERROR = "error"
UNKNOWN = "unknown"

# How many points each failing check costs. The scheduler and the media server
# are what actually put prerolls on screen, so they dominate; storage hygiene is
# real but not fatal. These sum to 100, so a system failing everything scores 0.
DEFAULT_WEIGHTS = {
    "scheduler": 30,
    "media_server": 30,
    "library": 15,
    "storage": 10,
    "conflicts": 10,
    "community_index": 5,
}

# Fraction of a check's weight deducted at each status.
_PENALTY = {OK: 0.0, WARN: 0.5, ERROR: 1.0}


def make_check(key: str, label: str, status: str, detail: str = "",
               value=None) -> dict:
    return {
        "key": key,
        "label": label,
        "status": status if status in (OK, WARN, ERROR, UNKNOWN) else UNKNOWN,
        "detail": detail,
        "value": value,
        "weight": DEFAULT_WEIGHTS.get(key, 10),
    }


def score_checks(checks: list) -> int:
    """0-100: start at full health and deduct for each problem found.

    Deduction rather than a weighted average of credits, because averaging has a
    perverse property - a half-credit check pulls a below-average score *up*, so
    discovering a new problem could raise the number. Here every problem can only
    ever lower it, and a check that could not be measured costs nothing.
    """
    penalty = sum(
        c.get("weight", 0) * _PENALTY[c["status"]]
        for c in checks
        if c.get("status") in _PENALTY
    )
    return max(0, int(round(100 - penalty)))


def overall_status(checks: list, score: int) -> str:
    """A single word for the tile heading. Any hard error caps the result at
    'degraded' regardless of score, so one dead service cannot be averaged away
    by a pile of healthy ones."""
    if any(c.get("status") == ERROR for c in checks):
        return "degraded"
    if any(c.get("status") == WARN for c in checks) or score < 90:
        return "attention"
    return "healthy"


def summary_note(checks: list, status: str) -> str:
    """The one-line note under the greeting. Names the single most important
    problem rather than a count, because 'one thing is wrong' is only useful if
    you say which thing."""
    problems = [c for c in checks if c.get("status") in (ERROR, WARN)]
    if not problems:
        return "Your preroll system is healthy."

    problems.sort(key=lambda c: (c["status"] != ERROR, -c.get("weight", 0)))
    first = problems[0]
    rest = len(problems) - 1

    lead = first.get("detail") or f"{first.get('label')} needs attention"
    if rest == 0:
        return lead
    return f"{lead} ({rest} more item{'s' if rest > 1 else ''} to review)"


def build_summary(checks: list) -> dict:
    """Assemble the payload the System health tile renders."""
    score = score_checks(checks)
    status = overall_status(checks, score)
    attention = [c for c in checks if c.get("status") in (ERROR, WARN)]
    return {
        "score": score,
        "status": status,
        "note": summary_note(checks, status),
        "attention_count": len(attention),
        "checks": checks,
    }


def community_index_check(age_days: Optional[float]) -> dict:
    """Community index freshness. Missing entirely is unknown, not a failure -
    plenty of installs never use community prerolls."""
    if age_days is None:
        return make_check("community_index", "Community index", UNKNOWN,
                          "Community index not downloaded")
    rounded = int(round(age_days))
    label_age = f"{rounded} day{'s' if rounded != 1 else ''} old"
    if age_days >= 30:
        return make_check("community_index", "Community index", WARN,
                          f"Community index is {label_age}", label_age)
    return make_check("community_index", "Community index", OK, "", label_age)


def conflicts_check(count: Optional[int]) -> dict:
    """Schedule conflicts are detected in the frontend, so the count arrives
    from the caller. None means it was not supplied, which is unknown."""
    if count is None:
        return make_check("conflicts", "Schedule conflicts", UNKNOWN)
    if count <= 0:
        return make_check("conflicts", "Schedule conflicts", OK, "", 0)
    return make_check(
        "conflicts", "Schedule conflicts", WARN,
        f"{count} schedule conflict{'s' if count != 1 else ''} need a look", count
    )
