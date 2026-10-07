"""End-to-end agent evaluation with real LLM and TfL calls.

    python -m tube.evaluation.agent_eval

Every answer is scored automatically (live answers change, so checks are structural):
- tool selection : all expected tools were called (and none for off-topic questions)
- citation       : guidance answers link the expected tfl.gov.uk page
- live timestamp : live answers say when the data is from (e.g. "15:40")
- no invented price: an unknown station must not produce a fare
- invented links : any URL not returned by a tool (caught by the guardrail)
Results go to eval/results_agent.json; `python -m tube.evaluation.update_readme`
copies the summary into the README.
"""

from __future__ import annotations

import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path

QUESTIONS = Path("eval/agent_questions.json")
RESULTS = Path("eval/results_agent.json")
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
PRICE_RE = re.compile(r"£\s?\d")


def grade(q: dict, answer: str, tools_used: list[str], trace: list[dict],
          unsupported_urls: list[str]) -> dict:
    checks: dict[str, bool] = {}
    expected = q["expected_tools"]
    if q["type"] == "out_of_scope":
        checks["no_tools"] = not tools_used
    else:
        checks["right_tools"] = all(t in tools_used for t in expected)
    if q["type"] == "guidance":
        checks["cites_expected_page"] = q["expected_url"].rstrip("/") in answer
    if q["type"] in ("live", "multi") and any(t != "search_tfl_guidance" for t in expected):
        checks["live_timestamp"] = bool(TIME_RE.search(answer))
    if q["type"] == "unknown_station":
        checks["tool_reported_error"] = any(t["error"] for t in trace)
        checks["no_invented_price"] = not PRICE_RE.search(answer)
    checks["no_invented_links"] = not unsupported_urls
    return {"checks": checks, "passed": all(checks.values())}


def rate(rows: list[dict], check: str) -> float | None:
    vals = [r["checks"][check] for r in rows if check in r.get("checks", {})]
    return round(sum(vals) / len(vals), 2) if vals else None


def summarize(rows: list[dict]) -> dict:
    ok = [r for r in rows if not r.get("error")]
    tool_ok = [r["checks"].get("right_tools", r["checks"].get("no_tools")) for r in ok]
    secs = [r["seconds"] for r in ok]
    return {
        "n": len(rows),
        "errors": len(rows) - len(ok),
        "pass_rate": round(sum(r["passed"] for r in ok) / len(rows), 2) if rows else 0,
        "tool_selection": round(sum(tool_ok) / len(tool_ok), 2) if tool_ok else None,
        "citation_accuracy": rate(ok, "cites_expected_page"),
        "live_timestamp_rate": rate(ok, "live_timestamp"),
        "unknown_station_handled": rate(ok, "no_invented_price"),
        "invented_link_rate": round(1 - rate(ok, "no_invented_links"), 2) if ok else None,
        "median_seconds": round(statistics.median(secs), 1) if secs else None,
        "avg_tokens": round(statistics.mean(r["tokens"] for r in ok)) if ok else None,
    }


def main() -> None:
    from tube import config
    from tube.agent.agent import TubeAgent

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    agent = TubeAgent()
    rows = []
    for q in questions:
        agent.reset()  # every question starts a fresh conversation
        try:
            r = agent.ask(q["question"])
            g = grade(q, r.answer, r.tools_used, r.trace, r.guardrails.get("unsupported_urls", []))
            rows.append({"id": q["id"], "type": q["type"], "question": q["question"],
                         "tools_used": r.tools_used, **g, "seconds": r.seconds,
                         "tokens": r.usage["input_tokens"] + r.usage["output_tokens"],
                         "answer": r.answer})
        except Exception as exc:  # noqa: BLE001 - one failure shouldn't stop the run
            rows.append({"id": q["id"], "type": q["type"], "question": q["question"],
                         "passed": False, "checks": {}, "error": f"{type(exc).__name__}: {exc}"[:300]})
        row = rows[-1]
        failed = [k for k, v in row.get("checks", {}).items() if not v]
        mark = "✅" if row["passed"] else ("⚠️ " if row.get("error") else "❌")
        detail = row.get("error") or (f"failed: {', '.join(failed)}" if failed else "")
        print(f"{mark} {q['id']} {q['type']:<15} tools={row.get('tools_used', [])} {detail}")

    summary = summarize(rows)
    report = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "model": f"{config.LLM_MODEL} via {config.LLM_PROVIDER}",
              "summary": summary, "rows": rows}
    RESULTS.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + "\n".join(f"{k:<26}{v}" for k, v in summary.items()))
    print(f"\nSaved to {RESULTS}. Next: python -m tube.evaluation.update_readme")


if __name__ == "__main__":
    main()
