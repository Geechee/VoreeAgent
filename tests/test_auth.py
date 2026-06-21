"""Tests for API key authentication."""
from auth import hash_key, generate_key


def test_hash_key_deterministic():
    assert hash_key("test123") == hash_key("test123")


def test_hash_key_different_inputs():
    assert hash_key("key1") != hash_key("key2")


def test_generate_key_prefix():
    key = generate_key()
    assert key.startswith("voree_")


def test_generate_key_length():
    key = generate_key()
    assert len(key) > 20


def test_generate_key_unique():
    keys = {generate_key() for _ in range(10)}
    assert len(keys) == 10
