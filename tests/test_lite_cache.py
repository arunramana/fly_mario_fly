"""The lite video cache: bounded by bytes, least recently used out first, never half a file."""
import os
import time

import pytest

from fly_mario_fly.lite.cache import DiskCache


def put(cache, key, size):
    cache.tmp(key).write_bytes(b"v" * size)
    cache.put(key, {"key": key, "size": size})


def test_put_then_get(tmp_path):
    c = DiskCache(tmp_path, 10_000)
    assert c.get("a") is None
    put(c, "a", 100)
    assert c.get("a") == {"key": "a", "size": 100}
    assert c.mp4("a").read_bytes() == b"v" * 100
    assert not c.tmp("a").exists()


def test_oldest_used_goes_first(tmp_path):
    c = DiskCache(tmp_path, 450)                            # room for three entries of ~135 bytes (video + summary), not four
    base = time.time() - 1000
    for i, k in enumerate("abc"):
        put(c, k, 100)
        os.utime(c.mp4(k), (base + i, base + i))            # a is the oldest, c the newest
    assert c.get("a")                                       # looking at a makes it the newest
    put(c, "d", 100)                                        # over the limit: b (now the oldest) goes
    assert c.keys() == ["a", "c", "d"]
    put(c, "e", 100)                                        # then c
    assert c.keys() == ["a", "d", "e"]
    assert c.size() <= 450


def test_size_never_exceeds_the_limit_over_many_puts(tmp_path):
    limit = 5_000
    c = DiskCache(tmp_path, limit)
    for i in range(60):
        put(c, f"k{i:03d}", 700)
        assert c.size() <= limit
    assert 0 < len(c.keys()) <= limit // 700


def test_the_newest_entry_is_kept_even_if_it_alone_is_too_big(tmp_path):
    c = DiskCache(tmp_path, 100)
    put(c, "a", 50)
    put(c, "big", 500)
    assert c.keys() == ["big"]


def test_leftovers_of_a_crash_are_removed_at_start(tmp_path):
    (tmp_path / "x.part.mp4").write_bytes(b"half")
    (tmp_path / "x.part.json").write_text("{")
    DiskCache(tmp_path, 100)
    assert list(tmp_path.iterdir()) == []


def test_an_entry_needs_both_files(tmp_path):
    c = DiskCache(tmp_path, 1000)
    put(c, "a", 10)
    c.mp4("a").unlink()
    assert c.get("a") is None
