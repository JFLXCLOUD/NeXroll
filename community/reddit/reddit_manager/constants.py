from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = PACKAGE_ROOT / "config" / "community.json"
DEFAULT_ENV_PATH = PACKAGE_ROOT / ".env"
DEFAULT_BACKUP_DIR = PACKAGE_ROOT / "snapshots"
DEFAULT_STATE_PATH = PACKAGE_ROOT / ".state.json"

TARGET_SUBREDDIT = "r/NeXroll"
REDIRECT_URI = "http://localhost:8080"
CALLBACK_HOST = "127.0.0.1"
CALLBACK_PORT = 8080

OAUTH_SCOPES = (
    "identity",
    "read",
    "modconfig",
    "modflair",
    "modposts",
    "structuredstyles",
    "wikiread",
    "wikiedit",
    "modwiki",
    "submit",
    "edit",
)

SAFE_SECTIONS = (
    "settings",
    "branding",
    "rules",
    "post_flair",
    "user_flair",
    "removal_reasons",
    "sidebar",
    "wiki",
)

OPT_IN_SECTIONS = ("posts", "automoderator")
ALL_SECTIONS = SAFE_SECTIONS + OPT_IN_SECTIONS

SECTION_ALIASES = {
    "appearance": ("branding",),
    "flair": ("post_flair", "user_flair", "removal_reasons"),
    "widgets": ("sidebar",),
}

REQUIRED_MOD_PERMISSIONS = ("config", "flair", "posts", "wiki")

BRANDING_KEYS = {
    "icon": "community_icon",
    "banner": "banner_background_image",
    "mobile_banner": "mobile_banner_image",
}
