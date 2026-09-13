"""Preparing changelog text for display.

Extracted so the rule can be tested without standing up the app, like the other
small decision modules here.
"""
from __future__ import annotations

import re

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_BLANK_RUN = re.compile(r"\n{3,}")


def strip_html_comments(text: str) -> str:
    """Remove HTML comments from changelog text before a user sees it.

    The What's New dialog renders the changelog as markdown, and a renderer that
    does not emit raw HTML prints an HTML comment as ordinary prose rather than
    hiding it. A release-planning note at the top of CHANGELOG.md was therefore
    shown verbatim to every user, naming internal working files.

    Stripping here rather than editing the file keeps notes-to-self safe to
    write in the changelog at all.
    """
    if not text:
        return text
    cleaned = _COMMENT.sub("", text)
    # Collapse the blank lines the removal leaves behind, so the rendered
    # markdown does not open with a gap where the note used to be.
    return _BLANK_RUN.sub("\n\n", cleaned).lstrip("\n")
