"""Community preroll lengths read from file headers (backend/community_durations.py)."""
import json
import struct

import pytest

from backend import community_durations as cd


# ---------------------------------------------------------------- fixtures

def box(kind: bytes, payload: bytes = b"", large: bool = False) -> bytes:
    if large:
        return struct.pack(">I4sQ", 1, kind, 16 + len(payload)) + payload
    return struct.pack(">I4s", 8 + len(payload), kind) + payload


def mvhd(timescale: int, duration: int, version: int = 0) -> bytes:
    if version == 1:
        body = bytes([1, 0, 0, 0]) + struct.pack(">QQIQ", 0, 0, timescale, duration)
    else:
        body = bytes([0, 0, 0, 0]) + struct.pack(">IIII", 0, 0, timescale, duration)
    return box(b"mvhd", body + b"\x00" * 80)


def moov(*children: bytes) -> bytes:
    return box(b"moov", b"".join(children) + box(b"trak", b"\x00" * 500))


FTYP = box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2avc1mp41")
MEDIA = box(b"mdat", b"\x00" * 50_000)


def ebml_id(value: int) -> bytes:
    return value.to_bytes((value.bit_length() + 7) // 8, "big")


def ebml_size(n: int, unknown: bool = False) -> bytes:
    if unknown:
        return b"\x01\xff\xff\xff\xff\xff\xff\xff"
    return (0x10000000 | n).to_bytes(4, "big")


def element(ident: int, payload: bytes) -> bytes:
    return ebml_id(ident) + ebml_size(len(payload)) + payload


def mkv(seconds: float, scale: int = 1_000_000, before_info: bytes = b"", unknown_segment=False,
        info=True) -> bytes:
    header = element(0x1A45DFA3, element(0x4282, b"matroska"))
    info_body = element(0x2AD7B1, scale.to_bytes(3, "big"))
    info_body += element(0x4489, struct.pack(">d", seconds * 1e9 / scale))
    info_body += element(0x4D80, b"Lavf61")
    cluster = element(0x1F43B675, b"\x00" * 20_000)
    children = before_info + (element(0x1549A966, info_body) if info else b"") + cluster
    segment = ebml_id(0x18538067) + ebml_size(len(children), unknown=unknown_segment) + children
    return header + segment


class FakeFile:
    def __init__(self, data: bytes):
        self.data = data
        self.calls = []

    def __call__(self, start: int, length: int) -> bytes:
        self.calls.append((start, length))
        return self.data[start:start + length]


# ---------------------------------------------------------------- MP4 / MOV

def test_faststart_mp4_takes_one_read():
    f = FakeFile(FTYP + moov(mvhd(1000, 12_500)) + MEDIA)
    assert cd.read_duration(f) == 12.5
    assert len(f.calls) == 1


def test_moov_after_media_takes_a_second_read_at_its_offset():
    data = FTYP + box(b"free") + MEDIA + moov(mvhd(90_000, 90_000 * 30))
    f = FakeFile(data)
    assert cd.read_duration(f) == 30.0
    assert len(f.calls) == 2
    assert f.calls[1][0] == len(FTYP) + 8 + len(MEDIA)


def test_version_1_mvhd_and_64_bit_box_sizes():
    data = FTYP + box(b"mdat", b"\x00" * 9000, large=True) + moov(mvhd(600, 600 * 95, version=1))
    assert cd.read_duration(FakeFile(data)) == 95.0


def test_quicktime_mov_without_ftyp():
    data = box(b"wide") + MEDIA + moov(mvhd(2997, 2997 * 20))
    assert cd.read_duration(FakeFile(data)) == 20.0


def test_fragmented_mp4_uses_mehd():
    mehd = box(b"mehd", bytes(4) + struct.pack(">I", 1000 * 42))
    data = FTYP + moov(mvhd(1000, 0), box(b"mvex", mehd)) + MEDIA
    assert cd.read_duration(FakeFile(data)) == 42.0


def test_fragmented_mp4_without_a_duration_is_unknown():
    data = FTYP + moov(mvhd(1000, 0), box(b"mvex")) + MEDIA
    assert cd.read_duration(FakeFile(data)) is None


def test_mp4_without_moov_is_unknown_and_reads_are_capped():
    data = FTYP + b"".join(box(b"mdat", b"\x00" * 10_000) for _ in range(20))
    f = FakeFile(data)
    assert cd.read_duration(f) is None
    assert len(f.calls) <= cd.MAX_READS_PER_FILE


# ------------------------------------------------------------ Matroska / WebM

def test_matroska_duration_from_segment_info():
    assert cd.read_duration(FakeFile(mkv(12.523))) == 12.52


def test_matroska_skips_seekhead_and_void_before_info():
    before = element(0x114D9B74, b"\x00" * 60) + element(0xEC, b"\x00" * 6000)
    f = FakeFile(mkv(7.25, before_info=before))
    assert cd.read_duration(f) == 7.25
    assert len(f.calls) == 2


def test_matroska_live_segment_with_unknown_size():
    assert cd.read_duration(FakeFile(mkv(64.0, unknown_segment=True))) == 64.0


def test_matroska_custom_timestamp_scale():
    assert cd.read_duration(FakeFile(mkv(15.0, scale=1000))) == 15.0


def test_matroska_info_after_cluster_is_unknown():
    assert cd.read_duration(FakeFile(mkv(15.0, info=False))) is None


def test_other_containers_are_unknown():
    assert cd.read_duration(FakeFile(b"RIFF\x00\x00\x00\x00AVI LIST" + b"\x00" * 100)) is None
    assert cd.read_duration(FakeFile(b"")) is None


def test_implausible_lengths_are_rejected():
    assert cd.read_duration(FakeFile(FTYP + moov(mvhd(1, 10 * 24 * 3600)))) is None


# ------------------------------------------------------------ HTTP fetch

class FakeResponse:
    def __init__(self, status, body=b""):
        self.status_code = status
        self.body = body
        self.closed = False

    def iter_content(self, chunk_size):
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i:i + chunk_size]

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = None

    def get(self, url, headers=None, stream=False, timeout=None):
        assert stream
        self.headers = headers
        return self.response


def test_range_fetch_asks_for_the_bytes_it_needs():
    session = FakeSession(FakeResponse(206, b"x" * 4096))
    fetch = cd.http_range_fetch(session, "https://example/a.mp4", {"User-Agent": "NeXRoll"})
    assert fetch(100, 4096) == b"x" * 4096
    assert session.headers == {"User-Agent": "NeXRoll", "Range": "bytes=100-4195"}
    assert session.response.closed


def test_range_fetch_stops_reading_a_full_200_response():
    session = FakeSession(FakeResponse(200, b"y" * 1_000_000))
    assert len(cd.http_range_fetch(session, "u", {})(0, 4096)) == 4096
    with pytest.raises(cd.RangeUnsupported):
        cd.http_range_fetch(FakeSession(FakeResponse(200, b"y")), "u", {})(5000, 4096)


@pytest.mark.parametrize("status, error", [(429, cd.ServerBusy), (503, cd.ServerBusy),
                                           (404, cd.FileUnavailable), (403, cd.FileUnavailable),
                                           (500, IOError)])
def test_range_fetch_errors(status, error):
    with pytest.raises(error):
        cd.http_range_fetch(FakeSession(FakeResponse(status)), "u", {})(0, 4096)


# --------------------------------------------------------------------- store

def test_store_records_saves_and_reloads(tmp_path):
    path = tmp_path / "community_durations.json"
    store = cd.DurationStore(path)
    store.record("/a.mp4", 1000, 12.5)
    store.record("/b.mp4", 2000, None, error="no duration in header")
    assert store.save()
    again = cd.DurationStore(path)
    assert again.seconds("/a.mp4", 1000) == 12.5
    assert again.seconds("/b.mp4", 2000) is None
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_a_replaced_file_is_read_again(tmp_path):
    store = cd.DurationStore(tmp_path / "d.json")
    store.record("/a.mp4", 1000, 12.5)
    assert not store.needs_reading("/a.mp4", 1000)
    assert store.needs_reading("/a.mp4", 1001)
    assert store.seconds("/a.mp4", 1001) is None
    # Old HTML-listing indexes have no size; the stored length still applies.
    assert store.seconds("/a.mp4", None) == 12.5


def test_failed_reads_wait_a_week(tmp_path):
    store = cd.DurationStore(tmp_path / "d.json")
    store.record("/x.mkv", 5, None, now=1_000_000)
    assert not store.needs_reading("/x.mkv", 5, now=1_000_000 + 3600)
    assert store.needs_reading("/x.mkv", 5, now=1_000_000 + cd.RETRY_FAILED_AFTER)
    assert store.needs_reading("/never-seen.mp4", 5)


def test_durations_for_index_entries_and_prune(tmp_path):
    store = cd.DurationStore(tmp_path / "d.json")
    store.record("/a.mp4", 10, 9.0)
    store.record("/b.mp4", 20, 31.0)
    store.record("/gone.mp4", 30, 5.0)
    entries = [{"path": "/a.mp4", "size_bytes": 10}, {"path": "/b.mp4", "size_bytes": 99},
               {"path": "/c.mp4", "size_bytes": 1}]
    assert store.durations(entries) == {"/a.mp4": 9.0}
    assert store.prune(["/a.mp4", "/b.mp4", "/c.mp4"]) == 1
    assert store.seconds("/gone.mp4") is None


def test_unreadable_store_file_starts_empty(tmp_path):
    path = tmp_path / "d.json"
    path.write_text("{not json", encoding="utf-8")
    assert cd.DurationStore(path).seconds("/a.mp4") is None


# ------------------------------------------------------------ search helpers

def test_length_bounds_use_the_displayed_whole_seconds():
    assert cd.length_matches(30.4, max_seconds=30)
    assert not cd.length_matches(30.6, max_seconds=30)
    assert cd.length_matches(60.0, min_seconds=60, max_seconds=120)
    assert not cd.length_matches(120.6, min_seconds=60, max_seconds=120)
    assert cd.length_matches(121, min_seconds=121)
    assert cd.length_matches(5.0)
    assert not cd.length_matches(None)
    assert not cd.length_matches(None, max_seconds=30)


def test_unmeasured_prerolls_sort_last_both_ways():
    lengths = [12.0, None, 45.0, 3.0]
    assert sorted(lengths, key=cd.length_sort_key) == [3.0, 12.0, 45.0, None]
    assert sorted(lengths, key=lambda s: cd.length_sort_key(s, longest=True)) == [45.0, 12.0, 3.0, None]
