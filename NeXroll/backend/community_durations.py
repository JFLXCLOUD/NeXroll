"""Running times for Community Prerolls, read from each file's header.

Directory listings carry a file's name, size and date but not its length.
ffprobe can read the length over HTTP, but it buffers megabytes per file, which
across the whole catalog would be a large part of the server's traffic for
every install that indexes it. The length sits in a few bytes near one end of
the file, so this reads just those bytes with HTTP range requests:

* MP4/MOV keep it in moov/mvhd. moov is either at the front (one 4 KB read) or
  after the media data, whose box header gives its offset (a second read).
* Matroska/WebM keep it in Segment/Info, before the first Cluster.

Results go in a JSON file beside the index, keyed by the file's path (the same
on every mirror) and tied to its byte size, so a rebuilt index only costs reads
for files that are new or have changed.
"""

from __future__ import annotations

import json
import math
import os
import struct
import threading
import time
from typing import Callable, Iterable, Optional

CHUNK_BYTES = 4096
MAX_READS_PER_FILE = 6
# Failed reads (unreadable header, odd container) are tried again after this,
# not on every pass, so a file that will never parse costs one request a week.
RETRY_FAILED_AFTER = 7 * 24 * 3600
# Anything outside this is a misread header, not a preroll.
MAX_PLAUSIBLE_SECONDS = 6 * 3600


class ServerBusy(Exception):
    """The server answered 429/503: stop reading and come back later."""


class RangeUnsupported(Exception):
    """The server ignored a Range header for a read past the start of the file."""


class FileUnavailable(Exception):
    """This file could not be fetched (404 and the like); the server is fine."""


class _ReadLimit(Exception):
    pass


Fetch = Callable[[int, int], bytes]


class RangeReader:
    """Byte reads at arbitrary offsets, served from as few range requests as possible."""

    def __init__(self, fetch: Fetch, chunk: int = CHUNK_BYTES, max_requests: int = MAX_READS_PER_FILE):
        self._fetch = fetch
        self._chunk = chunk
        self._max_requests = max_requests
        self._chunks: list[tuple[int, bytes, int]] = []
        self.requests = 0

    def read(self, offset: int, length: int) -> bytes:
        for start, data, asked in self._chunks:
            if start <= offset and offset + length <= start + len(data):
                return data[offset - start:offset - start + length]
            # Fewer bytes than asked for means the file ends there.
            if start <= offset <= start + len(data) and len(data) < asked:
                return data[offset - start:]
        if self.requests >= self._max_requests:
            raise _ReadLimit()
        self.requests += 1
        asked = max(length, self._chunk)
        data = self._fetch(offset, asked) or b""
        self._chunks.append((offset, data, asked))
        return data[:length]


# ---------------------------------------------------------------- MP4 / MOV

def _box_header(reader: RangeReader, offset: int):
    """(size, type, header_length) of the box at offset; size None = runs to EOF."""
    head = reader.read(offset, 16)
    if len(head) < 8:
        return None
    size, kind = struct.unpack(">I4s", head[:8])
    if size == 1:
        if len(head) < 16:
            return None
        return struct.unpack(">Q", head[8:16])[0], kind, 16
    if size == 0:
        return None, kind, 8
    return size, kind, 8


def _full_box_value(body: bytes, small: str, large: str):
    """Version 0 boxes use 32-bit fields, version 1 boxes 64-bit ones."""
    if not body:
        return None
    fmt = large if body[0] == 1 else small
    need = struct.calcsize(fmt)
    if len(body) < 4 + need:
        return None
    return struct.unpack(fmt, body[4:4 + need])


def _children(reader: RangeReader, start: int, end: Optional[int], limit: int = 64):
    offset = start
    for _ in range(limit):
        if end is not None and offset + 8 > end:
            return
        header = _box_header(reader, offset)
        if header is None:
            return
        size, kind, header_len = header
        yield offset, size, kind, header_len
        if size is None or size < header_len:
            return
        offset += size


def mp4_duration(reader: RangeReader) -> Optional[float]:
    for offset, size, kind, header_len in _children(reader, 0, None):
        if kind != b"moov":
            continue
        moov_end = offset + size if size else None
        timescale = None
        for child, child_size, child_kind, child_hl in _children(reader, offset + header_len, moov_end):
            if child_kind == b"mvhd":
                body = reader.read(child + child_hl, 36)
                # creation, modification, timescale, duration
                fields = _full_box_value(body, ">IIII", ">QQIQ")
                if not fields:
                    return None
                timescale, duration = fields[2], fields[3]
                unknown = 0xFFFFFFFFFFFFFFFF if body[0] == 1 else 0xFFFFFFFF
                if timescale and duration and duration != unknown:
                    return duration / timescale
            elif child_kind == b"mvex" and timescale:
                # Fragmented files leave mvhd's duration at 0; mehd has it.
                mvex_end = child + child_size if child_size else moov_end
                for sub, _s, sub_kind, sub_hl in _children(reader, child + child_hl, mvex_end):
                    if sub_kind == b"mehd":
                        fields = _full_box_value(reader.read(sub + sub_hl, 12), ">I", ">Q")
                        if fields and fields[0]:
                            return fields[0] / timescale
        return None
    return None


# ------------------------------------------------------------ Matroska / WebM

_EBML = 0x1A45DFA3
_SEGMENT = 0x18538067
_INFO = 0x1549A966
_CLUSTER = 0x1F43B675
_TIMESTAMP_SCALE = 0x2AD7B1
_DURATION = 0x4489


def _vint(buf: bytes, pos: int, keep_marker: bool):
    """(value, length, all_ones) of the EBML variable-length integer at pos."""
    if pos >= len(buf) or buf[pos] == 0:
        return None
    first = buf[pos]
    length = 9 - first.bit_length()
    if pos + length > len(buf):
        return None
    value = first if keep_marker else first & ((1 << (8 - length)) - 1)
    for b in buf[pos + 1:pos + length]:
        value = (value << 8) | b
    all_ones = not keep_marker and value == (1 << (7 * length)) - 1
    return value, length, all_ones


def _element(reader: RangeReader, offset: int):
    """(id, data_offset, data_size) of the element at offset; size None = unknown."""
    head = reader.read(offset, 12)
    ident = _vint(head, 0, keep_marker=True)
    if not ident:
        return None
    size = _vint(head, ident[1], keep_marker=False)
    if not size:
        return None
    return ident[0], offset + ident[1] + size[1], (None if size[2] else size[0])


def matroska_duration(reader: RangeReader) -> Optional[float]:
    header = _element(reader, 0)
    if not header or header[0] != _EBML or header[2] is None:
        return None
    segment = _element(reader, header[1] + header[2])
    if not segment or segment[0] != _SEGMENT:
        return None
    offset = segment[1]
    for _ in range(32):
        element = _element(reader, offset)
        if not element:
            return None
        ident, data_offset, size = element
        if ident == _CLUSTER:
            return None
        if ident == _INFO:
            if size is None or size > 65536:
                return None
            body = reader.read(data_offset, size)
            return _info_duration(body)
        if size is None:
            return None
        offset = data_offset + size
    return None


def _info_duration(body: bytes) -> Optional[float]:
    scale, duration, pos = 1_000_000, None, 0
    while pos < len(body):
        ident = _vint(body, pos, keep_marker=True)
        if not ident:
            break
        size = _vint(body, pos + ident[1], keep_marker=False)
        if not size or size[2]:
            break
        start = pos + ident[1] + size[1]
        data = body[start:start + size[0]]
        if ident[0] == _TIMESTAMP_SCALE and data:
            scale = int.from_bytes(data, "big")
        elif ident[0] == _DURATION and len(data) in (4, 8):
            duration = struct.unpack(">f" if len(data) == 4 else ">d", data)[0]
        pos = start + size[0]
    if duration is None or not scale:
        return None
    return duration * scale / 1e9


# ------------------------------------------------------------------ dispatch

def read_duration(fetch: Fetch) -> Optional[float]:
    """Seconds, or None when the header does not say.

    Raises FileUnavailable, ServerBusy and RangeUnsupported, and whatever
    ``fetch`` raises for network errors, so the caller can tell "this file"
    from "this server".
    """
    reader = RangeReader(fetch)
    try:
        magic = reader.read(0, 8)
        if magic[:4] == b"\x1a\x45\xdf\xa3":
            seconds = matroska_duration(reader)
        elif magic[4:8] in (b"ftyp", b"moov", b"free", b"skip", b"wide", b"mdat", b"pnot"):
            seconds = mp4_duration(reader)
        else:
            return None
    except (_ReadLimit, struct.error, IndexError, ValueError, OverflowError):
        return None
    if seconds is None or not math.isfinite(seconds) or not 0 < seconds < MAX_PLAUSIBLE_SECONDS:
        return None
    return round(seconds, 2)


def http_range_fetch(session, url: str, headers: dict, timeout: float = 15) -> Fetch:
    """A fetch for read_duration over requests, reading no more than asked for.

    A server that ignores Range sends the whole file with a 200; the stream is
    closed after the bytes we need, and a read past the start is refused rather
    than downloading up to it.
    """
    def fetch(start: int, length: int) -> bytes:
        request_headers = dict(headers or {})
        request_headers["Range"] = f"bytes={start}-{start + length - 1}"
        response = session.get(url, headers=request_headers, stream=True, timeout=timeout)
        try:
            if response.status_code in (429, 503):
                raise ServerBusy(f"HTTP {response.status_code}")
            if response.status_code == 416:
                return b""
            if response.status_code == 200 and start > 0:
                raise RangeUnsupported(url)
            if 400 <= response.status_code < 500:
                raise FileUnavailable(f"HTTP {response.status_code}")
            if response.status_code not in (200, 206):
                raise IOError(f"HTTP {response.status_code}")
            data = bytearray()
            for piece in response.iter_content(chunk_size=length):
                data.extend(piece)
                if len(data) >= length:
                    break
            return bytes(data[:length])
        finally:
            response.close()
    return fetch


# --------------------------------------------------------------------- store

class DurationStore:
    """{path: {"seconds", "size", "checked", "error"?}} kept in a JSON file."""

    def __init__(self, path):
        self._path = str(path)
        self._lock = threading.RLock()
        self._entries: Optional[dict] = None
        self._dirty = False

    def _load(self) -> dict:
        if self._entries is None:
            entries = {}
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("entries"), dict):
                    entries = data["entries"]
            except (OSError, ValueError):
                pass
            self._entries = entries
        return self._entries

    def _current(self, key: str, size) -> Optional[dict]:
        entry = self._load().get(key)
        if not isinstance(entry, dict):
            return None
        known = entry.get("size")
        if size and known and int(size) != int(known):
            return None  # the file was replaced under the same name
        return entry

    def seconds(self, key: str, size=None) -> Optional[float]:
        with self._lock:
            entry = self._current(key, size)
            value = entry.get("seconds") if entry else None
            return float(value) if isinstance(value, (int, float)) and value > 0 else None

    def needs_reading(self, key: str, size=None, now: Optional[float] = None) -> bool:
        with self._lock:
            entry = self._current(key, size)
            if entry is None:
                return True
            if entry.get("seconds"):
                return False
            now = time.time() if now is None else now
            return now - float(entry.get("checked") or 0) >= RETRY_FAILED_AFTER

    def record(self, key: str, size, seconds: Optional[float], error: str = "", now: Optional[float] = None):
        with self._lock:
            entry = {"seconds": seconds, "size": int(size) if size else None,
                     "checked": round(time.time() if now is None else now)}
            if not seconds:
                entry["error"] = error or "no duration in header"
            self._load()[key] = entry
            self._dirty = True

    def durations(self, entries: Iterable[dict]) -> dict:
        """{path: seconds} for the index entries whose length is known."""
        out = {}
        with self._lock:
            for entry in entries:
                key = entry.get("path") or entry.get("id")
                if key:
                    seconds = self.seconds(key, entry.get("size_bytes"))
                    if seconds:
                        out[key] = seconds
        return out

    def prune(self, keep: Iterable[str]) -> int:
        """Forget files that are no longer in the index."""
        keep = set(keep)
        with self._lock:
            entries = self._load()
            gone = [key for key in entries if key not in keep]
            for key in gone:
                del entries[key]
            if gone:
                self._dirty = True
            return len(gone)

    def save(self) -> bool:
        with self._lock:
            if not self._dirty or self._entries is None:
                return True
            tmp = self._path + ".tmp"
            try:
                os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump({"version": 1, "entries": self._entries}, f, ensure_ascii=False)
                os.replace(tmp, self._path)
                self._dirty = False
                return True
            except OSError:
                return False


# ------------------------------------------------------------ search helpers

def length_matches(seconds: Optional[float], min_seconds=None, max_seconds=None) -> bool:
    """Bounds are inclusive and compared with the length as displayed (whole
    seconds), so a 30.4 s preroll shown as 0:30 counts as "30 seconds or less"."""
    if seconds is None:
        return False
    shown = round(seconds)
    if min_seconds is not None and shown < min_seconds:
        return False
    if max_seconds is not None and shown > max_seconds:
        return False
    return True


def length_sort_key(seconds: Optional[float], longest: bool = False):
    """Unmeasured files sort after measured ones in either direction."""
    if seconds is None:
        return (1, 0.0)
    return (0, -seconds if longest else seconds)
