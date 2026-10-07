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
    hits = search("children under 11 free", k=1, use_rerank=True, candidates=3, collection=collection,
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
