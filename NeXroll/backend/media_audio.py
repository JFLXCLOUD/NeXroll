"""Stored audio formats, never a claim about the client's selected/output track."""
import hashlib
import json
import threading
import time

import requests

FORMATS = ('ac3', 'eac3', 'truehd', 'dts', 'aac', 'flac', 'pcm', 'mp3', 'opus', 'vorbis')
LABELS = dict(zip(FORMATS, ('Dolby Digital', 'Dolby Digital Plus', 'Dolby TrueHD', 'DTS / DTS-HD',
                          'AAC', 'FLAC', 'PCM', 'MP3', 'Opus', 'Vorbis')))
CACHE_TTL = 60
_cache = {}
_lock = threading.Lock()


def codec_format(codec):
    codec = str(codec or '').strip().lower().replace('-', '').replace('_', '').replace(' ', '')
    if codec.startswith('pcm'):
        return 'pcm'
    return {'ac3': 'ac3', 'eac3': 'eac3', 'truehd': 'truehd',
            'dts': 'dts', 'dca': 'dts', 'dtshd': 'dts', 'dtshdma': 'dts', 'dtshdhra': 'dts',
            'aac': 'aac', 'flac': 'flac', 'mp3': 'mp3', 'opus': 'opus', 'vorbis': 'vorbis'}.get(codec)


def describe_audio(item):
    """Resolve only unambiguous stored defaults; any-track includes all sources.

    Multiple editions have no identifiable selected source at the intro hook,
    so their default stays unknown. Missing/unsupported stream metadata also
    stays unknown, including for a negated condition.
    """
    if not isinstance(item, dict):
        return None
    sources = item.get('MediaSources')
    if not isinstance(sources, list) or not sources:
        sources = [item] if isinstance(item.get('MediaStreams'), list) else []
    if not sources:
        return None
    formats, defaults, complete = set(), [], True
    for source in sources:
        if not isinstance(source, dict) or not isinstance(source.get('MediaStreams'), list):
            defaults.append(None); complete = False; continue
        streams = source['MediaStreams']
        audio = [s for s in streams if isinstance(s, dict) and str(s.get('Type', '')).lower() == 'audio']
        if not audio or any(not isinstance(s, dict) or not s.get('Type') for s in streams):
            complete = False
        for stream in audio:
            fmt = codec_format(stream.get('Codec'))
            if fmt: formats.add(fmt)
            else: complete = False
        index = source.get('DefaultAudioStreamIndex')
        if index is not None:
            selected = [s for s in audio if type(index) is int and type(s.get('Index')) is int and s['Index'] == index]
        else:
            selected = [s for s in audio if s.get('IsDefault') is True]
            if not selected and len(audio) == 1:
                selected = audio
        defaults.append(codec_format(selected[0].get('Codec')) if len(selected) == 1 else None)
    return {'default': defaults[0] if len(sources) == 1 else None,
            'formats': sorted(formats), 'complete': complete}


def matches_audio(details, values, track='default'):
    if not isinstance(values, list) or not values or any(v not in FORMATS for v in values if isinstance(v, str)) or any(not isinstance(v, str) for v in values):
        return None
    if not isinstance(details, dict) or track not in ('default', 'any'):
        return None
    if track == 'default':
        fmt = details.get('default')
        return fmt in values if fmt in FORMATS else None
    formats = details.get('formats')
    if not isinstance(formats, list):
        return None
    if set(values).intersection(formats):
        return True
    return False if details.get('complete') is True else None


def item_audio(db, item_id, server_type):
    """One bounded lookup on the named server only, cached per connection.

    Item IDs from different servers are not interchangeable. Never try a second
    server if the one that requested these intros is unavailable.
    """
    from backend.media_genres import _servers
    kind = str(server_type or '').lower()
    item_id = str(item_id or '').strip()
    if kind not in ('jellyfin', 'emby') or not item_id or item_id == '0':
        return None
    for candidate, base, headers, prefix in _servers(db, kind):
        if candidate != kind:
            continue
        fingerprint = hashlib.sha256(json.dumps(headers, sort_keys=True).encode()).hexdigest()
        key = (kind, base, fingerprint, item_id)
        with _lock:
            cached = _cache.get(key)
            if cached and time.monotonic() - cached[0] < CACHE_TTL:
                return cached[1]
        try:
            response = requests.get(f'{base}{prefix}/Items', params={
                'Ids': item_id, 'Fields': 'MediaStreams,MediaSources', 'Recursive': 'true',
                'EnableImages': 'false', 'EnableUserData': 'false'}, headers=headers, timeout=1.0)
            response.raise_for_status()
            items = response.json().get('Items') or []
            result = describe_audio(items[0]) if len(items) == 1 else None
        except Exception:
            return None
        if result is not None:
            with _lock:
                if len(_cache) >= 4000: _cache.clear()
                _cache[key] = (time.monotonic(), result)
        return result
    return None
