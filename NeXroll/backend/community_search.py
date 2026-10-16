"""Query matching for Community Prerolls search.

What the user typed still matches anywhere inside a title or path word, so
"hallow" finds Halloween. Related words from SEARCH_SYNONYMS are stricter:

* they match whole words only, so "turkey" no longer finds the Fallout
  prerolls through "fall", nor "summer" every "Sunset";
* they are used only when the query names a synonym key (or is the start of
  one, four letters or more), so "ow" no longer pulls in Halloween's list.

Results are ranked: the query as a whole word first, then the query inside a
longer word, then prerolls found only through a related word. Within a rank
the index order is kept.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import unquote

# Related words for common themes. Whole-word matches only (see above), so a
# short word here cannot drag in unrelated titles that merely contain it.
SEARCH_SYNONYMS = {
    "halloween": ["pumpkin", "scary", "ghost", "spooky", "witch", "haunted", "october", "trick", "treat", "monster", "zombie", "skeleton"],
    "christmas": ["santa", "xmas", "winter", "snow", "reindeer", "elf", "sleigh", "december", "festive", "merry"],
    "thanksgiving": ["turkey", "autumn", "fall", "november", "harvest", "pilgrim", "feast"],
    "turkey": ["thanksgiving", "november", "autumn", "fall", "harvest"],
    "4th july": ["independence", "july", "fireworks", "patriotic", "america"],
    "independence": ["4th july", "july", "fireworks", "patriotic", "america"],
    "valentines": ["love", "heart", "romance", "cupid", "february"],
    "easter": ["bunny", "egg", "spring", "april"],
    "new year": ["nye", "celebration", "january", "countdown", "resolution"],
    "summer": ["beach", "sun", "vacation", "june", "july", "august"],
    "spring": ["flower", "bloom", "april", "may", "easter"],
    "fall": ["autumn", "thanksgiving", "october", "november", "harvest", "leaves"],
    "winter": ["snow", "christmas", "cold", "december", "january", "february"],
    "birthday": ["party", "celebration", "cake", "celebrate"],
    "scary": ["halloween", "horror", "spooky", "ghost", "monster", "zombie"],
    "spooky": ["halloween", "scary", "ghost", "haunted"],
    "pumpkin": ["halloween", "october", "autumn", "fall"],
}

WHOLE_WORD, INSIDE_WORD, RELATED = 0, 1, 2

_WORD = re.compile(r"[a-z0-9]+")
PREFIX_MIN = 4  # a query this long that starts a key ("hallow") counts as that key


def _words(text: str) -> str:
    """Lowercase words separated by single spaces, padded so " term " finds
    whole words and phrases."""
    return " " + " ".join(_WORD.findall(str(text or "").lower())) + " "


def related_terms(query: str) -> list[str]:
    """Synonyms for every key the query names, without the query itself."""
    query_words = _words(query)
    bare = query_words.strip()
    if not bare:
        return []
    terms = []
    for key, synonyms in SEARCH_SYNONYMS.items():
        key_words = _words(key)
        if key_words in query_words or (len(bare) >= PREFIX_MIN and key_words.strip().startswith(bare)):
            terms.extend([key, *synonyms])
    return [t for t in dict.fromkeys(terms) if _words(t) != query_words]


class QueryMatcher:
    def __init__(self, query: str):
        self.query = (query or "").strip().lower()
        self._query_words = _words(self.query)
        self._related = [_words(t) for t in related_terms(self.query)]

    @staticmethod
    def _text(preroll: dict, title: str, keywords) -> str:
        path = unquote(str(preroll.get("path") or ""))
        return _words(" ".join([title, path, " ".join(keywords)]))

    def rank(self, preroll: dict) -> Optional[int]:
        """WHOLE_WORD / INSIDE_WORD / RELATED, or None when it doesn't match."""
        if not self.query:
            return WHOLE_WORD
        title = str(preroll.get("title") or "").lower()
        keywords = [str(k).lower() for k in (preroll.get("keywords") or [])]
        text = self._text(preroll, title, keywords)
        # Word-for-word too, so "pre roll" finds a "Pre-roll" title.
        whole = bool(self._query_words.strip()) and self._query_words in text
        if whole:
            return WHOLE_WORD
        if self.query in title or any(self.query in k for k in keywords):
            return INSIDE_WORD
        if any(term in text for term in self._related):
            return RELATED
        return None
