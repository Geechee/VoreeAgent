"""RAG system: chunk documents, embed chunks, and retrieve relevant context."""
from typing import List

from sqlalchemy.orm import Session

from memory import embed, embed_batch
from models import Document, DocumentChunk

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def chunk_text(text: str) -> List[str]:
    """Split text into overlapping chunks by character count."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk.strip())
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return chunks


def ingest_document(db: Session, filename: str, content_type: str, text: str) -> Document:
    """Chunk a document, batch-embed all chunks, and store everything."""
    chunks = chunk_text(text)

    doc = Document(
        filename=filename,
        content_type=content_type,
        size_bytes=len(text.encode()),
        chunk_count=len(chunks),
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    vectors = embed_batch(chunks, input_type="document")

    for i, (chunk_content, vector) in enumerate(zip(chunks, vectors)):
        chunk = DocumentChunk(
            document_id=doc.id,
            chunk_index=i,
            content=chunk_content,
            embedding=vector,
        )
        db.add(chunk)

    db.commit()
    return doc


def retrieve_chunks(db: Session, query: str, k: int = 5) -> List[DocumentChunk]:
    """Return the top-k most relevant document chunks by cosine similarity."""
    query_vector = embed(query, input_type="query")
    return (
        db.query(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_vector))
        .limit(k)
        .all()
    )
