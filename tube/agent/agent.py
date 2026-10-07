"""The agent loop: the LLM decides which tools to call, sees their results, answers.

    question -> LLM -> tool calls -> tool results -> LLM -> ... -> answer
                                                              -> guardrails

The loop stops after MAX_STEPS model turns. The conversation is kept between
questions for follow-ups ("and what about from Bank?"), but once a question is
answered its tool messages are dropped and only the final answer is kept, so the
history stays small enough for free LLM tiers.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

from tube.agent.guardrails import check_answer, extract_urls
from tube.agent.llm import LLM
from tube.agent.prompts import build_system_prompt
from tube.agent.tools import Toolbox, now_london

MAX_STEPS = 5
MAX_SEARCHES = 2
MAX_HISTORY_TURNS = 4  # previous question/answer pairs kept for follow-ups
SEARCH_LIMIT_MSG = ("Search limit reached for this question. Answer from the passages you "
                    "already have, and say so if they don't cover it.")
GAVE_UP = ("Sorry, I couldn't finish answering that. Please try rephrasing it, or check "
           "https://tfl.gov.uk.")


@dataclass
class AgentResult:
    answer: str
    sources: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    guardrails: dict = field(default_factory=dict)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    seconds: float = 0.0

    @property
    def tools_used(self) -> list[str]:
        return [t["tool"] for t in self.trace]


class TubeAgent:
    def __init__(self, toolbox: Toolbox | None = None, llm: LLM | None = None, clock=now_london):
        self.toolbox = toolbox or Toolbox()
        self.llm = llm or LLM()
        self.clock = clock
        self.history: list[dict] = []  # past user/assistant messages only

    def reset(self) -> None:
        self.history = []

    def ask(self, question: str) -> AgentResult:
        start = time.time()
        result = AgentResult(answer="")
        messages = ([{"role": "system", "content": build_system_prompt(self.clock())}]
                    + self.history + [{"role": "user", "content": question}])
        allowed_urls: set[str] = set()
        sources: dict = {}
        searches = 0

        for step in range(1, MAX_STEPS + 1):
            reply = self.llm.chat(messages, self.toolbox.specs)
            for k, v in reply.usage.items():
                result.usage[k] = result.usage.get(k, 0) + v
            if not reply.tool_calls:
                result.answer = reply.text or GAVE_UP
                break

            messages.append(reply.message)
            for call in reply.tool_calls:
                if call.name == "search_tfl_guidance":
                    searches += 1
                if call.name == "search_tfl_guidance" and searches > MAX_SEARCHES:
                    text, is_err = json.dumps({"error": SEARCH_LIMIT_MSG}), True
                else:
                    text, is_err = self.toolbox.call(call.name, call.args)
                allowed_urls |= extract_urls(text)
                _collect_sources(call.name, text, sources)
                result.trace.append({"step": step, "tool": call.name, "args": call.args,
                                     "error": is_err, "result": text[:400]})
                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})
        else:
            result.answer = GAVE_UP

        checked = check_answer(result.answer, allowed_urls)
        result.answer, result.guardrails = checked["answer"], checked["report"]
        result.sources = list(sources.values())
        result.seconds = round(time.time() - start, 2)

        self.history += [{"role": "user", "content": question},
                         {"role": "assistant", "content": result.answer}]
        self.history = self.history[-2 * MAX_HISTORY_TURNS:]
        return result


def _collect_sources(tool: str, text: str, sources: dict) -> None:
    if tool != "search_tfl_guidance":
        return
    try:
        results = json.loads(text).get("results", [])
    except (json.JSONDecodeError, AttributeError):
        return
    for r in results:
        sources.setdefault((r["url"], r["section"]), {
            "title": r["title"], "section": r["section"], "url": r["url"],
            "retrieved": r.get("retrieved", "")})
