"""Trailer language preference for NeX-Up downloads.

Radarr's trailer link is TMDB's English trailer, and NeXroll used to ask TMDB
for videos without a language, which also returns only English ones. Asking
TMDB for a language returns that language's trailers too, each tagged with
ISO 639-1 language and ISO 3166-1 region codes ("fr"/"CA" for a French
Canadian trailer), so a download can prefer them.

English keeps the old lookup exactly: no language parameters, Radarr's trailer
first.
"""

from typing import Optional

DEFAULT_LANGUAGE = "en"
FALLBACK_ENGLISH = "english"
FALLBACK_SKIP = "skip"
DEFAULT_FALLBACK = FALLBACK_ENGLISH

# code -> (label, ISO 639-1 language, ISO 3166-1 region or None). The code is
# what TMDB's `language` parameter takes.
LANGUAGES = {
    "en": ("English", "en", None),
    "fr-FR": ("French (France)", "fr", "FR"),
    "fr-CA": ("French (Canada)", "fr", "CA"),
    "de-DE": ("German", "de", "DE"),
    "es-ES": ("Spanish (Spain)", "es", "ES"),
    "es-MX": ("Spanish (Latin America)", "es", "MX"),
    "it-IT": ("Italian", "it", "IT"),
    "pt-BR": ("Portuguese (Brazil)", "pt", "BR"),
    "pt-PT": ("Portuguese (Portugal)", "pt", "PT"),
    "nl-NL": ("Dutch", "nl", "NL"),
    "pl-PL": ("Polish", "pl", "PL"),
    "sv-SE": ("Swedish", "sv", "SE"),
    "da-DK": ("Danish", "da", "DK"),
    "fi-FI": ("Finnish", "fi", "FI"),
    "ja-JP": ("Japanese", "ja", "JP"),
    "ko-KR": ("Korean", "ko", "KR"),
}

# Words people put in localized trailer titles on YouTube, for the alternate
# trailer search. TMDB's own list comes first; this only widens the search.
SEARCH_TERMS = {
    "en": "official trailer",
    "fr-FR": "bande annonce VF",
    "fr-CA": "bande-annonce VF Québec",
    "de-DE": "Trailer Deutsch",
    "es-ES": "tráiler oficial español",
    "es-MX": "tráiler oficial latino",
    "it-IT": "trailer italiano",
    "pt-BR": "trailer dublado",
    "pt-PT": "trailer oficial português",
    "nl-NL": "trailer NL",
    "pl-PL": "zwiastun PL",
    "sv-SE": "trailer svensk",
    "da-DK": "trailer dansk",
    "fi-FI": "traileri suomi",
    "ja-JP": "予告",
    "ko-KR": "예고편",
}

# Ranks for sorting sources: lower is better.
RANK_EXACT = 0       # the language and, where one is set, the region
RANK_LANGUAGE = 1    # the language from another region
RANK_OTHER = 2       # anything else, including sources with no language


def normalize_language(value) -> str:
    """A stored or submitted language as one of LANGUAGES, else English."""
    if not value:
        return DEFAULT_LANGUAGE
    text = str(value).strip()
    if text in LANGUAGES:
        return text
    lowered = text.lower()
    for code in LANGUAGES:
        if code.lower() == lowered:
            return code
    return DEFAULT_LANGUAGE


def normalize_fallback(value) -> str:
    """What to do when no trailer is in the chosen language."""
    return FALLBACK_SKIP if str(value or "").strip().lower() == FALLBACK_SKIP else FALLBACK_ENGLISH


def is_english(code) -> bool:
    return normalize_language(code) == DEFAULT_LANGUAGE


def label(code) -> str:
    return LANGUAGES[normalize_language(code)][0]


def options() -> list:
    """The languages a user can choose, in display order."""
    return [{"code": code, "label": entry[0]} for code, entry in LANGUAGES.items()]


def tmdb_video_params(code) -> dict:
    """Extra query parameters for TMDB's /videos lookups.

    English sends none, so it behaves exactly as before. Other languages ask
    for videos in that language plus English and untagged ones, so the English
    fallback stays available from the same request.
    """
    code = normalize_language(code)
    if code == DEFAULT_LANGUAGE:
        return {}
    language = LANGUAGES[code][1]
    return {"language": code, "include_video_language": f"{language},en,null"}


def language_rank(code, video_language: Optional[str], video_region: Optional[str] = None) -> int:
    """How well a video's language tags match the chosen language."""
    code = normalize_language(code)
    _, want_language, want_region = LANGUAGES[code]
    if not video_language or str(video_language).lower() != want_language:
        return RANK_OTHER
    if want_region is None or (video_region and str(video_region).upper() == want_region):
        return RANK_EXACT
    return RANK_LANGUAGE


def tag_label(video_language: Optional[str], video_region: Optional[str] = None) -> Optional[str]:
    """A readable name for a video's TMDB language tags, e.g. "French (Canada)"."""
    if not video_language:
        return None
    lang = str(video_language).lower()
    region = str(video_region).upper() if video_region else None
    base = None
    for name, code_lang, code_region in LANGUAGES.values():
        if code_lang != lang:
            continue
        if code_region == region:
            return name
        base = base or name.split(" (")[0]
    if base is None:
        return lang
    return f"{base} ({region})" if region else base


def matches(code, video_language: Optional[str]) -> bool:
    """Whether a video is in the chosen language, from any region."""
    return language_rank(code, video_language) <= RANK_LANGUAGE


def search_query(code, title: str, year=None) -> str:
    """A YouTube search for this movie's trailer in the chosen language."""
    terms = SEARCH_TERMS.get(normalize_language(code), SEARCH_TERMS[DEFAULT_LANGUAGE])
    return " ".join(part for part in (title.strip(), str(year) if year else "", terms) if part).strip()


def downloader_options(setting) -> dict:
    """TrailerDownloader keyword arguments from the saved NeX-Up settings.

    Includes the user's TMDB key: movie downloads never passed it, so their
    TMDB lookups used NeXroll's bundled key, which TMDB now rejects (401), and
    only Radarr's link was ever tried. Language lookups need a working key.
    """
    return {
        "language": normalize_language(getattr(setting, "nexup_trailer_language", None)),
        "language_fallback": normalize_fallback(getattr(setting, "nexup_trailer_language_fallback", None)),
        "tmdb_api_key": (getattr(setting, "nexup_tmdb_api_key", None) or "").strip() or None,
    }
