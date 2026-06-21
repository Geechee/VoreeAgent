"""Tests for the TTL cache."""
import time
from cache import TTLCache


def test_set_and_get():
    c = TTLCache(default_ttl=60)
    c.set("key", "value")
    assert c.get("key") == "value"


def test_miss_returns_none():
    c = TTLCache(default_ttl=60)
    assert c.get("nonexistent") is None


def test_expired_entry_returns_none():
    c = TTLCache(default_ttl=60)
    c.set("key", "value", ttl=1)
    time.sleep(1.1)
    assert c.get("key") is None


def test_short_vs_long_ttl():
    c = TTLCache(default_ttl=60)
    c.set("short", "val", ttl=1)
    c.set("long", "val", ttl=60)
    time.sleep(1.1)
    assert c.get("short") is None
    assert c.get("long") == "val"


def test_invalidate_all():
    c = TTLCache(default_ttl=60)
    c.set("a", 1)
    c.set("b", 2)
    c.invalidate()
    assert c.get("a") is None
    assert c.get("b") is None


def test_invalidate_prefix():
    c = TTLCache(default_ttl=60)
    c.set("stats:main", 1)
    c.set("stats:extra", 2)
    c.set("other", 3)
    c.invalidate("stats:")
    assert c.get("stats:main") is None
    assert c.get("stats:extra") is None
    assert c.get("other") == 3


def test_overwrite():
    c = TTLCache(default_ttl=60)
    c.set("key", "old")
    c.set("key", "new")
    assert c.get("key") == "new"


def test_stores_complex_types():
    c = TTLCache(default_ttl=60)
    data = {"tasks": {"total": 5}, "memories": [1, 2, 3]}
    c.set("complex", data)
    assert c.get("complex") == data
