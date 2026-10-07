"""Chunk -> embed -> store. Rebuilds the collection from scratch each run.

    python -m tube.rag.build_index
"""

from __future__ import annotations

import time

from tube import config
from tube.rag.chunking import build_chunks
from tube.rag.embeddings import embed_passages
from tube.rag.store import add_chunks, get_collection


def build_index(pages=None, collection=None, embed=embed_passages) -> int:
    chunks = build_chunks(pages)
    if not chunks:
        raise SystemExit("No chunks. Run: python -m tube.ingest.fetch_tfl")
    start = time.time()
    vectors = embed([c["text"] for c in chunks])
    collection = collection or get_collection(reset=True)
    add_chunks(collection, chunks, vectors)
    print(f"Indexed {collection.count()} chunks from {len({c['doc_id'] for c in chunks})} pages "
          f"into '{config.COLLECTION}' in {time.time() - start:.1f}s")
    return collection.count()


if __name__ == "__main__":
    build_index()
