"""Tests for RAG chunking logic."""
from rag import chunk_text, CHUNK_SIZE, CHUNK_OVERLAP


def test_short_text_single_chunk():
    chunks = chunk_text("Hello world")
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_empty_text():
    chunks = chunk_text("")
    assert len(chunks) == 0


def test_whitespace_only():
    chunks = chunk_text("   \n\n   ")
    assert len(chunks) == 0


def test_exact_chunk_size():
    text = "a" * CHUNK_SIZE
    chunks = chunk_text(text)
    assert len(chunks) >= 1
    assert len(chunks[0]) == CHUNK_SIZE


def test_overlapping_chunks():
    text = "a" * (CHUNK_SIZE + 100)
    chunks = chunk_text(text)
    assert len(chunks) == 2


def test_many_chunks():
    text = "word " * 500
    chunks = chunk_text(text)
    assert len(chunks) > 2
    for chunk in chunks:
        assert len(chunk) <= CHUNK_SIZE


def test_chunk_overlap_exists():
    text = "The quick brown fox jumps over the lazy dog. " * 30
    chunks = chunk_text(text)
    if len(chunks) >= 2:
        end_of_first = chunks[0][-20:]
        assert end_of_first in chunks[1]
