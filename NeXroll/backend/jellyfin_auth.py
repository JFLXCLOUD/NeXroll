"""Authentication shared by Jellyfin connector credential-loading paths."""
import json
from typing import Optional


def jellyfin_auth_headers(api_key: Optional[str]) -> dict[str, str]:
    """Use the Authorization header accepted by Jellyfin 10.11 and 12.

    Jellyfin 12 disables legacy X-Emby-Token/X-MediaBrowser-Token headers by
    default. A valid API key sent only through those headers produces a 401.
    """
    if not api_key or not api_key.strip():
        return {}
    token = api_key.strip()
    if '\r' in token or '\n' in token:
        raise ValueError('Jellyfin API key must not contain line breaks')
    return {
        'Authorization': (
            'MediaBrowser Client="NeXroll", Device="NeXroll", '
            'DeviceId="nexroll-server", Version="1.0", '
            f'Token={json.dumps(token)}'
        )
    }
