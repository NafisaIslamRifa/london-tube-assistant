import json

from tube.agent.agent import GAVE_UP, MAX_STEPS, TubeAgent
from tube.agent.guardrails import check_answer
from tube.agent.llm import Reply, ToolCall

from tests.test_agent_tools import STATIONS, FakeClient, fake_search
from tube.agent.tools import Toolbox


class ScriptedLLM:
    """Replays fixed replies, like a recorded LLM, and records what it was sent."""

    def __init__(self, *replies):
        self.replies, self.seen = list(replies), []

    def chat(self, messages, tools):
        self.seen.append([dict(m) for m in messages])
        return self.replies.pop(0)


def tool_reply(*calls):
    tcs = [ToolCall(f"c{i}", name, args) for i, (name, args) in enumerate(calls)]
    msg = {"role": "assistant", "content": "", "tool_calls": [
        {"id": t.id, "type": "function", "function": {"name": t.name, "arguments": json.dumps(t.args)}}
        for t in tcs]}
    return Reply("", tcs, msg, {"input_tokens": 100, "output_tokens": 10})


def text_reply(text):
    return Reply(text, [], {"role": "assistant", "content": text}, {"input_tokens": 50, "output_tokens": 20})


def make(*replies):
    llm = ScriptedLLM(*replies)
    box = Toolbox(client=FakeClient(), stations=STATIONS, search_fn=fake_search,
                  clock=lambda: "Wed 07 Oct 2026, 15:40")
    return TubeAgent(toolbox=box, llm=llm, clock=lambda: "Wed 07 Oct 2026, 15:40"), llm


def test_tool_then_answer_with_citation():
    agent, llm = make(
        tool_reply(("search_tfl_guidance", {"query": "touch out"})),
        text_reply("Yes, always touch out. [Touching in and out](https://tfl.gov.uk/fares/touching)"))
    r = agent.ask("Do I need to touch out?")
    assert r.tools_used == ["search_tfl_guidance"]
    assert r.sources == [{"title": "Touching in and out", "section": "Overview",
                          "url": "https://tfl.gov.uk/fares/touching", "retrieved": "2026-10-07"}]
    assert r.guardrails["unsupported_urls"] == []
    assert r.usage == {"input_tokens": 150, "output_tokens": 30}
    sent = llm.seen[1]                                   # second call saw the tool result
    assert sent[-1]["role"] == "tool" and sent[-1]["tool_call_id"] == "c0"
    assert "15:40" in sent[0]["content"]                 # current London time in the prompt


def test_parallel_tool_calls_in_one_turn():
    agent, _ = make(
        tool_reply(("get_fare", {"from_station": "Bank", "to_station": "Victoria"}),
                   ("get_line_status", {"line": "Victoria"})),
        text_reply("It's £2.90 off-peak and the Victoria line has a good service."))
    r = agent.ask("How much is Bank to Victoria and is the line OK?")
    assert r.tools_used == ["get_fare", "get_line_status"]
    assert not any(t["error"] for t in r.trace)


def test_invented_link_is_flagged():
    agent, _ = make(text_reply("See https://tfl.gov.uk/made-up-page for details."))
    r = agent.ask("Anything")
    assert r.guardrails["unsupported_urls"] == ["https://tfl.gov.uk/made-up-page"]
    assert "could not be checked" in r.answer


def test_search_limit_enforced_in_code():
    s = lambda q: ("search_tfl_guidance", {"query": q})
    agent, _ = make(tool_reply(s("a")), tool_reply(s("b")), tool_reply(s("c")), text_reply("Done."))
    r = agent.ask("Tell me everything about fares")
    assert r.answer == "Done." and len(r.trace) == 3
    assert r.trace[2]["error"] and "limit" in r.trace[2]["result"]


def test_gives_up_after_max_steps():
    agent, _ = make(*[tool_reply(("get_line_status", {}))] * MAX_STEPS)
    assert agent.ask("loop forever").answer == GAVE_UP


def test_history_keeps_answers_but_not_tool_messages():
    agent, llm = make(
        tool_reply(("get_fare", {"from_station": "Bank", "to_station": "Victoria"})),
        text_reply("£2.90 off-peak."),
        text_reply("From Oxford Circus it is similar."))
    agent.ask("Fare from Bank to Victoria?")
    agent.ask("And from Oxford Circus?")
    follow_up = llm.seen[-1]
    roles = [m["role"] for m in follow_up]
    assert roles == ["system", "user", "assistant", "user"]          # no tool messages kept
    assert follow_up[2]["content"] == "£2.90 off-peak."
    agent.reset()
    assert agent.history == []


def test_guardrail_allows_trailing_slash_and_home_page():
    out = check_answer("See https://tfl.gov.uk/ and https://tfl.gov.uk/fares/x/.",
                       {"https://tfl.gov.uk/fares/x"})
    assert out["report"]["unsupported_urls"] == []


def test_guardrail_handles_cjk_bracket_citations():
    """Regression: gpt-oss writes 【url】; the closing bracket was read as part of the URL."""
    url = "https://tfl.gov.uk/modes/tube/night-tube"
    out = check_answer(f"Source: Night Tube page【{url}】.", {url})
    assert out["report"]["unsupported_urls"] == [] and "could not be checked" not in out["answer"]
    bad = check_answer("See https://tfl.gov.uk/made-up】.", {url})
    assert bad["report"]["unsupported_urls"] == ["https://tfl.gov.uk/made-up"]


def test_prompt_forbids_memory_answers_and_placeholder_citations():
    from tube.agent.prompts import build_system_prompt
    p = build_system_prompt("now")
    assert "Never answer a rules question from memory" in p and "【source】" in p
