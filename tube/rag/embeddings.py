"""Text embeddings with fastembed (ONNX on CPU: no PyTorch, small Docker image).

bge models embed questions and passages slightly differently, so there are two
functions. The model downloads once (about 70 MB) and is then cached.
"""

from __future__ import annotations

import os
from functools import lru_cache

from tube import config


@lru_cache(maxsize=1)
def get_model():
    from fastembed import TextEmbedding  # imported lazily: tests never load the model
    return TextEmbedding(model_name=config.EMBEDDING_MODEL,
                         cache_dir=os.getenv("FASTEMBED_CACHE_PATH") or None)


def embed_passages(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in get_model().passage_embed(texts, batch_size=config.EMBED_BATCH_SIZE)]


def embed_query(text: str) -> list[float]:
    return next(iter(get_model().query_embed([text]))).tolist()
