"""Cross-encoder reranking.

A bi-encoder (embeddings) compares a question and a passage as two separate vectors:
fast, but it can miss details. A cross-encoder reads the question and the passage
*together* and scores how well the passage answers it: slower, so it is used only
on the top ~20 candidates, but much more precise.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Callable

from tube import config

ScoreFn = Callable[[str, list[str]], list[float]]


@lru_cache(maxsize=1)
def get_model():
    from fastembed.rerank.cross_encoder import TextCrossEncoder  # lazy: tests never load it
    return TextCrossEncoder(model_name=config.RERANK_MODEL,
                            cache_dir=os.getenv("FASTEMBED_CACHE_PATH") or None)


def cross_encoder_scores(question: str, passages: list[str]) -> list[float]:
    return [float(s) for s in get_model().rerank(question, passages)]


def rerank(question: str, hits: list[dict], top_n: int = 5,
           score_fn: ScoreFn = cross_encoder_scores) -> list[dict]:
    """Return the top_n hits ordered by cross-encoder score (kept as 'rerank_score').

    The vector rank is kept as 'vector_rank' so the UI and evaluation can show how
    much reranking moved each passage.
    """
    if not hits:
        return []
    scores = score_fn(question, [h["text"] for h in hits])
    ranked = sorted(
        ({**h, "vector_rank": i + 1, "rerank_score": round(s, 4)}
         for i, (h, s) in enumerate(zip(hits, scores))),
        key=lambda h: h["rerank_score"], reverse=True)
    return ranked[:top_n]
