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
