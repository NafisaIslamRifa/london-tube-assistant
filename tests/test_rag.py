import hashlib
import math
import re

import pytest

from tube.rag.build_index import build_index
from tube.rag.chunking import chunk_page, split_words
from tube.rag.retriever import retrieve
from tube.rag.store import get_client, get_collection

PAGES = [
    {"doc_id": "touch", "url": "https://tfl.gov.uk/touch", "title": "Touching in and out",
     "topic": "paying", "fetched_at": "2026-10-07",
     "sections": [{"heading": "Maximum fares",
                   "text": "If you forget to touch out you may be charged a maximum fare."}]},
    {"doc_id": "night", "url": "https://tfl.gov.uk/night", "title": "Night Tube",
     "topic": "services", "fetched_at": "2026-10-07",
     "sections": [{"heading": "When it runs",
                   "text": "The Night Tube runs on Friday and Saturday nights on five lines."}]},
    {"doc_id": "kids", "url": "https://tfl.gov.uk/kids", "title": "Children",
     "topic": "fares", "fetched_at": "2026-10-07",
     "sections": [{"heading": "Under 11s",
                   "text": "Children under 11 travel free when accompanied by an adult."}]},
]


def fake_vec(text: str, dim: int = 64) -> list[float]:
    """Deterministic bag-of-words vector: shared words -> similar vectors."""
    v = [0.0] * dim
    for w in re.findall(r"[a-z]+", text.lower()):
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


@pytest.fixture
def collection(tmp_path):
    col = get_collection(get_client(str(tmp_path / "chroma")), name="test_tfl", reset=True)
    build_index(PAGES, collection=col, embed=lambda texts: [fake_vec(t) for t in texts])
    return col


def test_split_words_overlap_and_coverage():
    words = [f"w{i}" for i in range(500)]
    parts = split_words(" ".join(words), max_words=220, overlap=40)
    assert len(parts) == 3
    assert all(len(p.split()) <= 220 for p in parts)
    assert parts[0].split()[-40:] == parts[1].split()[:40]          # overlap
    assert parts[-1].split()[-1] == "w499"                           # nothing lost
    assert split_words("", 10, 2) == [] and split_words("a b", 10, 2) == ["a b"]


def test_chunk_page_prefixes_title_and_section():
    chunks = chunk_page(PAGES[0])
    assert chunks[0]["chunk_id"] == "touch#0-0"
    assert chunks[0]["text"].startswith("Touching in and out > Maximum fares\n")
    assert chunks[0]["section"] == "Maximum fares" and chunks[0]["url"] == "https://tfl.gov.uk/touch"


def test_index_and_retrieve(collection):
    assert collection.count() == 3
    hits = retrieve("forget to touch out maximum fare", k=2, collection=collection, embed=fake_vec)
    assert hits[0]["doc_id"] == "touch"
    assert hits[0]["section"] == "Maximum fares" and 0 < hits[0]["score"] <= 1
    assert hits[0]["score"] >= hits[1]["score"]


def test_topic_filter(collection):
    hits = retrieve("night tube friday", k=3, topic="fares", collection=collection, embed=fake_vec)
    assert {h["doc_id"] for h in hits} == {"kids"}


def test_rebuild_does_not_duplicate(collection):
    build_index(PAGES, collection=collection, embed=lambda texts: [fake_vec(t) for t in texts])
    assert collection.count() == 3


def test_empty_collection_returns_nothing(tmp_path):
    col = get_collection(get_client(str(tmp_path / "c2")), name="empty_one")
    assert retrieve("anything", collection=col, embed=fake_vec) == []
