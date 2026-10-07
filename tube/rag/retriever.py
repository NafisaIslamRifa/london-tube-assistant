"""Vector search: question -> the most similar chunks, with metadata for citations.

    python -m tube.rag.retriever "Do I need to touch out?"
"""

from __future__ import annotations

import sys

from tube.rag.embeddings import embed_query
from tube.rag.store import get_collection


def retrieve(question: str, k: int = 5, topic: str | None = None, collection=None,
             embed=embed_query) -> list[dict]:
    collection = collection or get_collection()
    if collection.count() == 0:
        return []
    res = collection.query(
        query_embeddings=[embed(question)],
        n_results=min(k, collection.count()),
        where={"topic": topic} if topic else None,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        hits.append({**meta, "text": doc, "score": round(1 - dist, 4)})  # cosine similarity
    return hits


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Do I need to touch out at the end of my journey?"
    for i, h in enumerate(retrieve(q), 1):
        body = h["text"].split("\n", 1)[-1]
        print(f"{i}. [{h['score']:.3f}] {h['title']} > {h['section']}\n   {body[:160]}...\n   {h['url']}")
