import json

from tube.evaluation.agent_eval import grade, summarize
from tube.evaluation.update_readme import agent_table, retrieval_table, update

URL = "https://tfl.gov.uk/fares/x"


def test_guidance_needs_search_and_citation():
    q = {"type": "guidance", "expected_tools": ["search_tfl_guidance"], "expected_url": URL}
    good = grade(q, f"Yes. [Page]({URL})", ["search_tfl_guidance"], [], [])
    assert good["passed"]
    no_cite = grade(q, "Yes, always.", ["search_tfl_guidance"], [], [])
    assert not no_cite["passed"] and no_cite["checks"]["cites_expected_page"] is False


def test_live_answer_needs_tool_and_timestamp():
    q = {"type": "live", "expected_tools": ["get_line_status"]}
    assert grade(q, "Good service (as of 15:40).", ["get_line_status"], [], [])["passed"]
    assert not grade(q, "Good service.", ["get_line_status"], [], [])["passed"]
    assert not grade(q, "Good service at 15:40.", [], [], [])["passed"]


def test_multi_tool_needs_all_tools():
    q = {"type": "multi", "expected_tools": ["get_fare", "get_line_status"]}
    assert not grade(q, "£3.00 at 15:40", ["get_fare"], [], [])["passed"]
    assert grade(q, "£3.00, good service, 15:40", ["get_fare", "get_line_status"], [], [])["passed"]


def test_unknown_station_must_not_invent_a_price():
    q = {"type": "unknown_station", "expected_tools": ["get_fare"]}
    trace = [{"tool": "get_fare", "error": True}]
    assert grade(q, "I couldn't find Hogwarts. Did you mean...?", ["get_fare"], trace, [])["passed"]
    assert not grade(q, "It costs £3.10.", ["get_fare"], trace, [])["passed"]


def test_out_of_scope_and_invented_links():
    q = {"type": "out_of_scope", "expected_tools": []}
    assert grade(q, "Sorry, I only cover London transport.", [], [], [])["passed"]
    assert not grade(q, "Try Dishoom.", ["search_tfl_guidance"], [], [])["passed"]
    assert not grade(q, "Sorry.", [], [], ["https://made.up"])["passed"]


def test_summarize_counts_errors_as_failures():
    rows = [
        {"passed": True, "checks": {"right_tools": True, "live_timestamp": True, "no_invented_links": True},
         "seconds": 2.0, "tokens": 1500},
        {"passed": False, "checks": {"right_tools": True, "cites_expected_page": False,
                                     "no_invented_links": True}, "seconds": 4.0, "tokens": 2500},
        {"passed": False, "checks": {}, "error": "RateLimitError: 429"},
    ]
    s = summarize(rows)
    assert s["n"] == 3 and s["errors"] == 1 and s["pass_rate"] == 0.33
    assert s["tool_selection"] == 1.0 and s["citation_accuracy"] == 0.0
    assert s["invented_link_rate"] == 0.0 and s["median_seconds"] == 3.0 and s["avg_tokens"] == 2000


RETRIEVAL = {"run_at": "2026-10-07T09:30:00+00:00", "modes": {
    "vector only": {"summary": {"n": 32, "page_hit@1": 0.94, "page_recall@5": 1.0,
                                "section_hit@1": 0.81, "section_hit@3": 0.97, "section_mrr": 0.88}},
    "vector + rerank": {"summary": {"n": 32, "page_hit@1": 0.88, "page_recall@5": 1.0,
                                    "section_hit@1": 0.78, "section_hit@3": 0.97, "section_mrr": 0.87}}}}
AGENT = {"run_at": "2026-10-08T10:00:00+00:00", "model": "openai/gpt-oss-120b via groq", "summary": {
    "n": 18, "errors": 0, "pass_rate": 0.89, "tool_selection": 1.0, "citation_accuracy": 0.88,
    "live_timestamp_rate": 1.0, "unknown_station_handled": 1.0, "invented_link_rate": 0.0,
    "median_seconds": 2.4, "avg_tokens": 2300}}


def test_tables_render():
    r = retrieval_table(RETRIEVAL)
    assert "32 everyday-language questions" in r and "| vector only | 0.94 | 1.00 | 0.81 | 0.97 | 0.88 |" in r
    a = agent_table(AGENT)
    assert "| Questions passing every check | 16 / 18 |" in a and "| Median time per question (incl. free-tier pacing) | 2.4 s |" in a


def test_update_replaces_only_between_markers():
    readme = ("intro\n<!-- retrieval-eval:start -->\nold\n<!-- retrieval-eval:end -->\nmiddle\n"
              "<!-- agent-eval:start -->\nold\n<!-- agent-eval:end -->\nend")
    out = update(readme, RETRIEVAL, AGENT)
    assert out.startswith("intro\n") and "middle" in out and out.endswith("end")
    assert "old" not in out and "0.81" in out and "16 / 18" in out
    assert update(out, RETRIEVAL, AGENT) == out          # running it twice changes nothing


def test_real_readme_has_both_markers():
    from pathlib import Path
    text = Path(__file__).resolve().parents[1].joinpath("README.md").read_text()
    for name in ("retrieval-eval", "agent-eval"):
        assert f"<!-- {name}:start -->" in text and f"<!-- {name}:end -->" in text


def test_question_files_are_valid():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "eval"
    agent_qs = json.loads((root / "agent_questions.json").read_text())
    assert len({q["id"] for q in agent_qs}) == len(agent_qs) == 18
    assert all(q["type"] != "guidance" or q["expected_url"].startswith("https://tfl.gov.uk/")
               for q in agent_qs)
