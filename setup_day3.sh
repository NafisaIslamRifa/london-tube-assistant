#!/usr/bin/env bash
# Day 3 setup: cross-encoder reranking + retrieval evaluation
set -e
[ -f tube/rag/retriever.py ] || { echo "Run this from the project folder (Day 2 files not found)"; exit 1; }
echo "Writing Day 3 files..."
mkdir -p "$(dirname 'README.md')"
cat > 'README.md' <<'EOF_UKT'
# London Tube Assistant

An agentic RAG assistant for travelling on the London Underground: grounded answers from official TfL guidance, plus live line status, next trains and fares from the TfL Unified API.

> Work in progress. Built step by step with unit tests, Docker and CI.

## Run the tests
```bash
pip install -r requirements.txt
python -m pytest -q
```

## Build the knowledge base
```bash
python -m tube.ingest.fetch_tfl        # TfL guidance pages -> data/raw/tfl_pages.jsonl
python -m tube.rag.build_index         # chunk, embed, store in Chroma (data/chroma)
python -m tube.rag.retriever "Do I need to touch out on the bus?"
```

## Search with reranking, and measure it
```bash
python -m tube.rag.search --compare "Do I need to touch out on the bus?"
python -m tube.evaluation.retrieval_eval     # vector-only vs + cross-encoder, saved to eval/
```

## Live check against the TfL API
```bash
python -m scripts.fetch_stations   # builds data/stations.json
python -m scripts.smoke_tfl
```

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Powered by TfL Open Data.
EOF_UKT
echo "  ✓ README.md ($(wc -l < 'README.md') lines)"
mkdir -p "$(dirname 'tube/config.py')"
cat > 'tube/config.py' <<'EOF_UKT'
"""Settings, read once from environment variables (and .env when present)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Transport for London Unified API. A free key raises the rate limit (500 requests/min);
# without one the API still works but is throttled harder.
TFL_BASE_URL = os.getenv("TFL_BASE_URL", "https://api.tfl.gov.uk").rstrip("/")
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "").strip()
TFL_TIMEOUT = float(os.getenv("TFL_TIMEOUT", "10"))

# Modes whose stations we index for fares and arrivals.
STATION_MODES = [m.strip() for m in os.getenv("STATION_MODES", "tube,elizabeth-line").split(",")
                 if m.strip()]
STATIONS_PATH = os.getenv("STATIONS_PATH", "data/stations.json")

# Knowledge base (Day 2)
RAW_DOCS_PATH = os.getenv("RAW_DOCS_PATH", "data/raw/tfl_pages.jsonl")
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma")
COLLECTION = os.getenv("CHROMA_COLLECTION", "tfl_guidance")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))  # small = low memory
CHUNK_MAX_WORDS = int(os.getenv("CHUNK_MAX_WORDS", "220"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "40"))

# Reranking (Day 3): retrieve many candidates by vector similarity, then let a
# cross-encoder read each (question, passage) pair and keep the best few.
RERANK_MODEL = os.getenv("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
RETRIEVE_CANDIDATES = int(os.getenv("RETRIEVE_CANDIDATES", "20"))
EOF_UKT
echo "  ✓ tube/config.py ($(wc -l < 'tube/config.py') lines)"
mkdir -p "$(dirname 'tube/rag/reranker.py')"
cat > 'tube/rag/reranker.py' <<'EOF_UKT'
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
EOF_UKT
echo "  ✓ tube/rag/reranker.py ($(wc -l < 'tube/rag/reranker.py') lines)"
mkdir -p "$(dirname 'tube/rag/search.py')"
cat > 'tube/rag/search.py' <<'EOF_UKT'
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


def search(question: str, k: int = 5, use_rerank: bool = True,
           candidates: int = config.RETRIEVE_CANDIDATES, topic: str | None = None,
           collection=None, embed=embed_query, score_fn=cross_encoder_scores) -> list[dict]:
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
    if args.compare:
        _show("Vector search only", search(q, use_rerank=False))
    _show("Vector search + cross-encoder rerank", search(q))


if __name__ == "__main__":
    main()
EOF_UKT
echo "  ✓ tube/rag/search.py ($(wc -l < 'tube/rag/search.py') lines)"
mkdir -p "$(dirname 'tube/evaluation/__init__.py')"
cat > 'tube/evaluation/__init__.py' <<'EOF_UKT'

EOF_UKT
echo "  ✓ tube/evaluation/__init__.py ($(wc -l < 'tube/evaluation/__init__.py') lines)"
mkdir -p "$(dirname 'tube/evaluation/retrieval_eval.py')"
cat > 'tube/evaluation/retrieval_eval.py' <<'EOF_UKT'
"""Retrieval evaluation: vector search vs vector search + cross-encoder rerank.

    python -m tube.evaluation.retrieval_eval

For each question we know the right page (and usually the right section). Metrics:
- Page Hit@1 / Recall@5: is the right page first / in the top 5?
- Section Hit@1 / Hit@3: the stricter test: is the exact section near the top?
- MRR (section): 1/rank of the first correct section, averaged (0 if missing).
Questions whose page is not in the index (fetch failed) are skipped and listed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from tube.rag.search import search
from tube.rag.store import get_collection

QUESTIONS = Path("eval/retrieval_questions.json")
RESULTS = Path("eval/results_retrieval.json")
K = 5


def doc_id_for(path: str) -> str:
    return path.strip("/").replace("/", "__")


def is_match(hit: dict, q: dict, level: str) -> bool:
    if hit.get("doc_id") != doc_id_for(q["path"]):
        return False
    if level == "page" or not q.get("sections"):
        return True
    sec = hit.get("section", "").lower()
    return any(s.lower() in sec for s in q["sections"])


def first_rank(hits: list[dict], q: dict, level: str) -> int | None:
    for i, h in enumerate(hits, 1):
        if is_match(h, q, level):
            return i
    return None


def summarize(rows: list[dict]) -> dict:
    """rows: [{"page_rank": int|None, "section_rank": int|None}, ...]"""
    n = len(rows)
    if not n:
        return {"n": 0}
    hit = lambda key, k: sum(1 for r in rows if r[key] and r[key] <= k) / n
    return {
        "n": n,
        "page_hit@1": round(hit("page_rank", 1), 3),
        "page_recall@5": round(hit("page_rank", K), 3),
        "section_hit@1": round(hit("section_rank", 1), 3),
        "section_hit@3": round(hit("section_rank", 3), 3),
        "section_mrr": round(sum(1 / r["section_rank"] for r in rows if r["section_rank"]) / n, 3),
    }


def evaluate(questions: list[dict], search_fn) -> list[dict]:
    rows = []
    for q in questions:
        hits = search_fn(q["question"])
        rows.append({"id": q["id"], "question": q["question"],
                     "page_rank": first_rank(hits, q, "page"),
                     "section_rank": first_rank(hits, q, "section"),
                     "top1": f"{hits[0]['title']} > {hits[0]['section']}" if hits else None})
    return rows


def indexed_doc_ids(collection) -> set[str]:
    return {m["doc_id"] for m in collection.get(include=["metadatas"])["metadatas"]}


def main() -> None:
    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    have = indexed_doc_ids(get_collection())
    usable = [q for q in questions if doc_id_for(q["path"]) in have]
    skipped = [q["id"] for q in questions if q not in usable]

    modes = {"vector only": lambda q: search(q, k=K, use_rerank=False),
             "vector + rerank": lambda q: search(q, k=K, use_rerank=True)}
    report = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "skipped": skipped, "modes": {}}
    for name, fn in modes.items():
        rows = evaluate(usable, fn)
        report["modes"][name] = {"summary": summarize(rows), "rows": rows}

    keys = ["page_hit@1", "page_recall@5", "section_hit@1", "section_hit@3", "section_mrr"]
    print(f"\n{'Mode':<18}" + "".join(f"{k:>15}" for k in keys) + f"{'n':>5}")
    for name, m in report["modes"].items():
        s = m["summary"]
        print(f"{name:<18}" + "".join(f"{s[k]:>15.2f}" for k in keys) + f"{s['n']:>5}")

    print("\nWhere reranking changed the section rank:")
    before = {r["id"]: r for r in report["modes"]["vector only"]["rows"]}
    for r in report["modes"]["vector + rerank"]["rows"]:
        b = before[r["id"]]["section_rank"]
        if b != r["section_rank"]:
            print(f"  {r['id']}: {b or '-'} -> {r['section_rank'] or '-'}  {r['question']}")
    if skipped:
        print(f"\nSkipped (page not indexed): {', '.join(skipped)}")
    RESULTS.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved to {RESULTS}")


if __name__ == "__main__":
    main()
EOF_UKT
echo "  ✓ tube/evaluation/retrieval_eval.py ($(wc -l < 'tube/evaluation/retrieval_eval.py') lines)"
mkdir -p "$(dirname 'eval/retrieval_questions.json')"
cat > 'eval/retrieval_questions.json' <<'EOF_UKT'
[
  {"id": "t01", "question": "Do I need to touch out when I get off the bus?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["Buses and trams"]},
  {"id": "t02", "question": "What happens if I forget to tap out at the end of my Tube journey?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["don't touch in and out", "Maximum fares"]},
  {"id": "t03", "question": "What are the pink card readers for?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["pink card readers"]},
  {"id": "t04", "question": "Can I tap in with my phone and tap out with my bank card?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["same card or device"]},
  {"id": "t05", "question": "The gates were left open after a football match. Do I still need to tap?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["sporting or entertainment events"]},
  {"id": "t06", "question": "I tapped in and out at the same station without travelling. Will I be charged?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["Same station exits"]},
  {"id": "t07", "question": "How do I get money back after being charged a maximum fare?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["refund"]},
  {"id": "t08", "question": "How should I tap when taking the tram to Wimbledon?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out", "sections": ["Wimbledon"]},

  {"id": "b01", "question": "How long do I have to change buses without paying again?", "path": "/fares/find-fares/bus-and-tram-fares", "sections": ["Hopper fare"]},
  {"id": "b02", "question": "What is the most an adult pays for buses in one day?", "path": "/fares/find-fares/bus-and-tram-fares", "sections": ["Adult pay as you go"]},
  {"id": "b03", "question": "How much is a weekly bus pass for a 16 year old with a Zip card?", "path": "/fares/find-fares/bus-and-tram-fares", "sections": ["16+ Zip"]},
  {"id": "b04", "question": "Do university students get cheaper bus passes?", "path": "/fares/find-fares/bus-and-tram-fares", "sections": ["18+ Student", "students"]},
  {"id": "b05", "question": "My card is out of credit. Can I still get on the bus?", "path": "/fares/find-fares/bus-and-tram-fares", "sections": ["One more bus journey"]},
  {"id": "b06", "question": "Is there a bus discount for people claiming Jobcentre Plus benefits?", "path": "/fares/find-fares/bus-and-tram-fares", "sections": ["Jobcentre Plus"]},

  {"id": "r01", "question": "What times count as peak on the Tube?", "path": "/fares/find-fares/tube-and-rail-fares", "sections": ["Peak and off-peak"]},
  {"id": "r02", "question": "How much is a Group Day Travelcard?", "path": "/fares/find-fares/tube-and-rail-fares", "sections": ["Group Day Travelcard"]},
  {"id": "r03", "question": "What is the daily cap for an adult travelling on the Tube?", "path": "/fares/find-fares/tube-and-rail-fares", "sections": ["Adult caps"]},
  {"id": "r04", "question": "Does a Disabled Persons Railcard reduce the Tube cap?", "path": "/fares/find-fares/tube-and-rail-fares", "sections": ["Disabled persons Railcard"]},

  {"id": "o01", "question": "Is there a limit to how much I pay in a day with contactless?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/capping", "sections": []},
  {"id": "o02", "question": "Can I pay for the Tube with Apple Pay or Google Pay?", "path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/contactless-and-mobile-pay-as-you-go", "sections": []},
  {"id": "o03", "question": "Do children under 11 have to pay on the Tube?", "path": "/fares/free-and-discounted-travel/children-and-young-people", "sections": []},
  {"id": "o04", "question": "Which lines run all night at the weekend?", "path": "/modes/tube/night-tube", "sections": []},
  {"id": "o05", "question": "How do I get a refund if my train was badly delayed?", "path": "/fares/refunds-and-replacements", "sections": []},
  {"id": "o06", "question": "Can wheelchair users travel on the Underground?", "path": "/transport-accessibility/", "sections": []}
]
EOF_UKT
echo "  ✓ eval/retrieval_questions.json ($(wc -l < 'eval/retrieval_questions.json') lines)"
mkdir -p "$(dirname 'tests/test_rerank_eval.py')"
cat > 'tests/test_rerank_eval.py' <<'EOF_UKT'
from tube.evaluation.retrieval_eval import doc_id_for, first_rank, is_match, summarize
from tube.rag.reranker import rerank
from tube.rag.search import search

from tests.test_rag import PAGES, collection, fake_vec  # noqa: F401  (reuse the fixture)


def keyword_scores(question, passages):
    """Fake cross-encoder: count question words that appear in the passage."""
    qw = set(question.lower().split())
    return [float(len(qw & set(p.lower().split()))) for p in passages]


def test_rerank_reorders_and_records_vector_rank():
    hits = [{"text": "night tube friday"}, {"text": "children under 11 travel free"},
            {"text": "touch out maximum fare"}]
    out = rerank("do children under 11 travel free", hits, top_n=2, score_fn=keyword_scores)
    assert [h["vector_rank"] for h in out] == [2, 1]
    assert out[0]["rerank_score"] >= out[1]["rerank_score"] and len(out) == 2


def test_rerank_empty():
    assert rerank("q", [], score_fn=keyword_scores) == []


def test_search_two_stages(collection):  # noqa: F811
    hits = search("children under 11 free", k=1, candidates=3, collection=collection,
                  embed=fake_vec, score_fn=keyword_scores)
    assert len(hits) == 1 and hits[0]["doc_id"] == "kids" and "rerank_score" in hits[0]
    plain = search("children under 11 free", k=2, use_rerank=False, collection=collection,
                   embed=fake_vec)
    assert len(plain) == 2 and "rerank_score" not in plain[0]


Q = {"path": "/fares/find-fares/bus-and-tram-fares", "sections": ["Hopper fare"]}
DOC = doc_id_for(Q["path"])


def test_doc_id_matches_ingest_format():
    assert DOC == "fares__find-fares__bus-and-tram-fares"
    assert doc_id_for("/transport-accessibility/") == "transport-accessibility"


def test_page_vs_section_matching():
    hits = [{"doc_id": DOC, "section": "Adult pay as you go prices"},
            {"doc_id": "other", "section": "Hopper fare"},
            {"doc_id": DOC, "section": "Hopper fare"}]
    assert first_rank(hits, Q, "page") == 1
    assert first_rank(hits, Q, "section") == 3
    assert is_match(hits[0], {**Q, "sections": []}, "section")   # no section given -> page match


def test_summarize_metrics():
    rows = [{"page_rank": 1, "section_rank": 1}, {"page_rank": 1, "section_rank": 2},
            {"page_rank": 4, "section_rank": None}, {"page_rank": None, "section_rank": None}]
    s = summarize(rows)
    assert s["n"] == 4 and s["page_hit@1"] == 0.5 and s["page_recall@5"] == 0.75
    assert s["section_hit@1"] == 0.25 and s["section_hit@3"] == 0.5
    assert s["section_mrr"] == round((1 + 0.5) / 4, 3)
    assert summarize([]) == {"n": 0}
EOF_UKT
echo "  ✓ tests/test_rerank_eval.py ($(wc -l < 'tests/test_rerank_eval.py') lines)"
echo
echo "Done: 8 files. Next: python -m pytest -q"