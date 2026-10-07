"""Section-aware chunking.

A chunk never mixes two sections, so every search result can cite one heading.
Long sections are split into overlapping word windows. Each chunk's text starts
with "Page title > Section heading", which helps retrieval for short questions.
"""

from __future__ import annotations

import json
from pathlib import Path

from tube import config


def split_words(text: str, max_words: int, overlap: int) -> list[str]:
    words = text.split()
    if len(words) <= max_words:
        return [" ".join(words)] if words else []
    step = max(1, max_words - overlap)
    out = []
    for start in range(0, len(words), step):
        out.append(" ".join(words[start:start + max_words]))
        if start + max_words >= len(words):
            break
    return out


def chunk_page(page: dict, max_words: int = config.CHUNK_MAX_WORDS,
               overlap: int = config.CHUNK_OVERLAP_WORDS) -> list[dict]:
    chunks = []
    for s_idx, section in enumerate(page["sections"]):
        for p_idx, piece in enumerate(split_words(section["text"], max_words, overlap)):
            chunks.append({
                "chunk_id": f"{page['doc_id']}#{s_idx}-{p_idx}",
                "doc_id": page["doc_id"],
                "url": page["url"],
                "title": page["title"],
                "section": section["heading"],
                "topic": page.get("topic", ""),
                "fetched_at": page.get("fetched_at", ""),
                "text": f"{page['title']} > {section['heading']}\n{piece}",
            })
    return chunks


def load_pages(path: str | Path = config.RAW_DOCS_PATH) -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"{p} not found. Run: python -m tube.ingest.fetch_tfl")
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_chunks(pages: list[dict] | None = None) -> list[dict]:
    pages = load_pages() if pages is None else pages
    return [c for page in pages for c in chunk_page(page)]
