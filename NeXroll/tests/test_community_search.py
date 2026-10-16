"""Community Prerolls query matching and ranking (backend/community_search.py)."""
from backend.community_search import (
    INSIDE_WORD, RELATED, SEARCH_SYNONYMS, WHOLE_WORD, QueryMatcher, related_terms,
)


def entry(title, path="/Community/Some%20Folder/file.mp4", keywords=None):
    words = keywords if keywords is not None else [w.lower() for w in title.split() if len(w) > 2]
    return {"title": title, "path": path, "keywords": words}


def rank(query, preroll):
    return QueryMatcher(query).rank(preroll)


def test_query_as_a_whole_word_ranks_above_inside_a_word():
    assert rank("fall", entry("Autumn Fall Leaves")) == WHOLE_WORD
    assert rank("fall", entry("Fallout 01 Plex Pre Roll")) == INSIDE_WORD


def test_partial_typing_still_finds_the_title():
    assert rank("hallow", entry("Halloween Quotes")) == INSIDE_WORD


def test_synonyms_match_whole_words_only():
    # "turkey" relates to "fall"; Fallout must not ride in on it.
    assert rank("turkey", entry("Fallout 02 Plex Pre Roll", keywords=["fallout", "plex"])) is None
    assert rank("turkey", entry("Autumn Trees Plex Bumper")) == RELATED
    assert rank("summer", entry("Sunset Painting Plex")) is None
    assert rank("christmas", entry("Shelf Elf Plex", keywords=["shelf"])) == RELATED  # "Elf" in the title


def test_the_holidays_folder_alone_is_not_a_christmas_match():
    april = entry("April Fools Plex", path="/Holidays/April%20Fools/April%20Fools%20-%20Plex.mp4",
                  keywords=["holidays", "april", "fools", "plex"])
    assert rank("christmas", april) is None
    assert "holiday" not in SEARCH_SYNONYMS["christmas"]


def test_synonyms_match_folder_names_as_words():
    frost = entry("Frost Plex", path="/Seasons/Winter/Frost%20-%20Someone/Frost%20Plex.mp4",
                  keywords=["seasons", "winter", "frost", "plex"])
    assert rank("christmas", frost) == RELATED


def test_short_fragments_do_not_expand_to_a_theme():
    assert related_terms("ow") == []
    assert related_terms("a") == []
    assert rank("ow", entry("Spooky Ghost Plex")) is None


def test_keys_expand_when_named_or_started():
    assert "pumpkin" in related_terms("halloween")
    assert "pumpkin" in related_terms("hallow")
    assert "santa" in related_terms("christmas movies")
    assert "fireworks" in related_terms("4th july")
    assert related_terms("halloween").count("halloween") == 0


def test_every_key_the_query_names_contributes():
    terms = related_terms("spooky winter")
    assert "haunted" in terms and "snow" in terms


def test_no_match_and_empty_query():
    assert rank("christmas", entry("Space Plex")) is None
    assert QueryMatcher("").rank(entry("Anything")) == WHOLE_WORD


def test_ranking_keeps_index_order_within_a_rank():
    prerolls = [
        entry("Snowy Night"),          # related via no word: "snowy" is not "snow"
        entry("Snow Day Plex"),        # related (snow)
        entry("Christmas Lights"),     # whole word
        entry("Christmastime Plex"),   # inside a word
        entry("Christmas Tree"),       # whole word
    ]
    matcher = QueryMatcher("christmas")
    ranked = [(matcher.rank(p), p["title"]) for p in prerolls]
    kept = sorted((r for r in ranked if r[0] is not None), key=lambda r: r[0])
    assert [t for _, t in kept] == ["Christmas Lights", "Christmas Tree", "Christmastime Plex", "Snow Day Plex"]
