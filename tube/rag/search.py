"""The search pipeline the agent will use: vector search -> cross-encoder rerank.

    python -m tube.rag.search "Do I need to touch out on the bus?"
    python -m tube.rag.search --compare "Do I need to touch out on the bus?"
"""

from __future__ import annotations

import argparse

from tube import config
from tube.rag.embeddings import embed_query
from tube.rag.reranker import cross_encoder_scores, rerank
from tube.rag.retriever import retrieve


def search(question: str, k: int = 5, use_rerank: bool | None = None,
           candidates: int = config.RETRIEVE_CANDIDATES, topic: str | None = None,
           collection=None, embed=embed_query, score_fn=cross_encoder_scores) -> list[dict]:
    if use_rerank is None:
        use_rerank = config.USE_RERANK
    if not use_rerank:
        return retrieve(question, k=k, topic=topic, collection=collection, embed=embed)
    pool = retrieve(question, k=max(k, candidates), topic=topic, collection=collection, embed=embed)
    return rerank(question, pool, top_n=k, score_fn=score_fn)


def _show(title: str, hits: list[dict]) -> None:
    print(f"\n== {title} ==")
    for i, h in enumerate(hits, 1):
        moved = f" (was #{h['vector_rank']})" if "vector_rank" in h else ""
        print(f"{i}. {h['title']} > {h['section']}{moved}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="+")
    ap.add_argument("--compare", action="store_true", help="show vector-only vs reranked")
    args = ap.parse_args()
    q = " ".join(args.question)
    _show("Vector search only", search(q, use_rerank=False))
    if args.compare or config.USE_RERANK:
        _show("Vector search + cross-encoder rerank", search(q, use_rerank=True))


if __name__ == "__main__":
    main()
