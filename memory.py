"""Memory system (Step 3): real Voyage embeddings + pgvector similarity search."""
import time
from typing import List

import voyageai
from sqlalchemy.orm import Session

from config import settings
from models import Memory

_client = None

MAX_RETRIES = 3
RETRY_DELAY = 25


def _get_client() -> voyageai.Client:
    """Lazily build the Voyage client so importing this module needs no API key."""
    global _client
    if _client is None:
        _client = voyageai.Client(api_key=settings.voyage_api_key)
    return _client


def _embed_with_retry(texts: List[str], input_type: str) -> list:
    for attempt in range(MAX_RETRIES):
        try:
            return _get_client().embed(
                texts,
                model=settings.embedding_model,
                input_type=input_type,
                output_dimension=settings.embedding_dim,
            )
        except voyageai.error.RateLimitError:
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
            else:
                raise


def embed(text: str, input_type: str = "document") -> List[float]:
    """Return a real embedding vector for the given text using Voyage AI."""
    result = _embed_with_retry([text], input_type)
    return result.embeddings[0]


def embed_batch(texts: List[str], input_type: str = "document") -> List[List[float]]:
    """Embed multiple texts in a single API call."""
    result = _embed_with_retry(texts, input_type)
    return result.embeddings


def store_memory(db: Session, content: str) -> Memory:
    """Embed the content and persist it as a memory row."""
    vector = embed(content, input_type="document")
    memory = Memory(content=content, embedding=vector)
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def retrieve_memories(db: Session, query: str, k: int = 10) -> List[Memory]:
    """Return the top-k most relevant memories by cosine similarity."""
    query_vector = embed(query, input_type="query")
    return (
        db.query(Memory)
        .order_by(Memory.embedding.cosine_distance(query_vector))
        .limit(k)
        .all()
    )