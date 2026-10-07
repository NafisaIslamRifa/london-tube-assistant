"""Chroma vector store. We compute embeddings ourselves (fastembed) and give Chroma
plain vectors, so Chroma never downloads a model of its own."""

from __future__ import annotations

import chromadb

from tube import config

META_KEYS = ("doc_id", "url", "title", "section", "topic", "fetched_at")


def get_client(path: str = config.CHROMA_PATH):
    return chromadb.PersistentClient(path=path)


def get_collection(client=None, name: str = config.COLLECTION, reset: bool = False):
    client = client or get_client()
    if reset and name in [c.name for c in client.list_collections()]:
        client.delete_collection(name)
    return client.get_or_create_collection(name, embedding_function=None,
                                           metadata={"hnsw:space": "cosine"})


def add_chunks(collection, chunks: list[dict], vectors: list[list[float]], batch: int = 128) -> None:
    for i in range(0, len(chunks), batch):
        part, vecs = chunks[i:i + batch], vectors[i:i + batch]
        collection.upsert(
            ids=[c["chunk_id"] for c in part],
            embeddings=vecs,
            documents=[c["text"] for c in part],
            metadatas=[{k: c.get(k, "") for k in META_KEYS} for c in part],
        )
