#!/usr/bin/env bash
# Day 4 setup: LLM agent with tool calling (Groq / Ollama / OpenAI-compatible)
set -e
[ -f tube/rag/search.py ] || { echo "Run this from the project folder (Day 3 files not found)"; exit 1; }
echo "Writing Day 4 files..."
mkdir -p "$(dirname 'requirements.txt')"
cat > 'requirements.txt' <<'EOF_UKT'
# Day 1: TfL API client
requests>=2.31
python-dotenv>=1.0

# Day 2: knowledge base (fastembed = ONNX on CPU, no PyTorch)
beautifulsoup4>=4.12
fastembed>=0.5
chromadb>=1.0

# Day 4: LLM agent (any OpenAI-compatible API: Groq, Ollama, OpenAI)
openai>=1.40

# Tests
pytest>=8.0
EOF_UKT
echo "  ✓ requirements.txt ($(wc -l < 'requirements.txt') lines)"
mkdir -p "$(dirname '.env.example')"
cat > '.env.example' <<'EOF_UKT'
# Copy to .env and fill in. Never commit .env.
# Free key from https://api-portal.tfl.gov.uk (optional, raises the rate limit)
TFL_APP_KEY=

# LLM: groq (free hosted), ollama (local) or openai (any OpenAI-compatible URL)
LLM_PROVIDER=groq
LLM_API_KEY=
# Optional overrides (defaults come from the provider):
# LLM_MODEL=openai/gpt-oss-120b
# LLM_BASE_URL=https://api.groq.com/openai/v1
# Groq free tier: about 8,000 tokens a minute. 4 requests/min keeps you under it.
LLM_RPM=4

# Day 3 evaluation showed reranking didn't help on this data, so it is off by default
USE_RERANK=false
EOF_UKT
echo "  ✓ .env.example ($(wc -l < '.env.example') lines)"
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

## Ask the agent
```bash
cp .env.example .env        # add LLM_API_KEY (free at console.groq.com)
python -m tube.agent.cli "Is the Victoria line running?"
python -m tube.agent.cli    # interactive chat with follow-ups
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
# Day 3 result: on 32 questions reranking did not beat vector search
# (section Hit@1 0.78 vs 0.81), so it is off by default. Set USE_RERANK=true to try it.
USE_RERANK = os.getenv("USE_RERANK", "false").lower() in ("1", "true", "yes")

# LLM (Day 4). Any OpenAI-compatible API. Presets:
#   groq   -> free hosted gpt-oss-120b (needs LLM_API_KEY from console.groq.com)
#   ollama -> local model, no key (needs Ollama running; see Day 6 Docker)
#   openai -> any other OpenAI-compatible endpoint (set LLM_BASE_URL)
LLM_PRESETS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3.2"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
_preset = LLM_PRESETS.get(LLM_PROVIDER, LLM_PRESETS["openai"])
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or _preset["base_url"]
LLM_MODEL = os.getenv("LLM_MODEL") or _preset["model"]
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip() or ("ollama" if LLM_PROVIDER == "ollama" else "")
LLM_RPM = int(os.getenv("LLM_RPM", "0") or 0)        # client-side pacing; 0 = off
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
EOF_UKT
echo "  ✓ tube/config.py ($(wc -l < 'tube/config.py') lines)"
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


def search(question: str, k: int = 5, use_rerank: bool | None = None,
           candidates: int = config.RETRIEVE_CANDIDATES, topic: str | None = None,
           collection=None, embed=embed_query, score_fn=cross_encoder_scores) -> list[dict]:
    if use_rerank is None:
        use_rerank = config.USE_RERANK
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
    _show("Vector search only", search(q, use_rerank=False))
    if args.compare or config.USE_RERANK:
        _show("Vector search + cross-encoder rerank", search(q, use_rerank=True))


if __name__ == "__main__":
    main()
EOF_UKT
echo "  ✓ tube/rag/search.py ($(wc -l < 'tube/rag/search.py') lines)"
mkdir -p "$(dirname 'tube/agent/__init__.py')"
cat > 'tube/agent/__init__.py' <<'EOF_UKT'

EOF_UKT
echo "  ✓ tube/agent/__init__.py ($(wc -l < 'tube/agent/__init__.py') lines)"
mkdir -p "$(dirname 'tube/agent/llm.py')"
cat > 'tube/agent/llm.py' <<'EOF_UKT'
"""One chat client for every OpenAI-compatible LLM API (Groq, Ollama, OpenAI, ...).

Free tiers have tight limits, so requests are paced (LLM_RPM) and retried:
- 429 rate limit: wait as long as the provider asks (Retry-After header or the
  "try again in 7.5s" text in the error), up to 4 times
- 5xx / timeouts / connection errors: 2 quick retries
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field

from tube import config

MAX_TOKENS = 1200


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: dict = field(default_factory=dict)       # assistant message to append to history
    usage: dict = field(default_factory=dict)


class RateLimiter:
    """Never send more than `rpm` requests in any 60-second window (0 = no limit)."""

    def __init__(self, rpm: int, clock=time.monotonic, sleep=time.sleep):
        self.rpm, self.sent, self._clock, self._sleep = rpm, deque(), clock, sleep

    def wait(self) -> None:
        if self.rpm <= 0:
            return
        now = self._clock()
        while self.sent and now - self.sent[0] >= 60:
            self.sent.popleft()
        if len(self.sent) >= self.rpm:
            delay = 60 - (now - self.sent[0]) + 0.5
            print(f"  ⏳ pacing ({self.rpm}/min), waiting {delay:.0f}s", file=sys.stderr)
            self._sleep(delay)
        self.sent.append(self._clock())


def _status(exc: Exception) -> int | None:
    return getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)


def retry_delay(exc: Exception, attempt: int) -> float:
    """How long to wait after a 429: the provider's hint if given, else backoff."""
    headers = getattr(getattr(exc, "response", None), "headers", None) or {}
    if headers.get("retry-after"):
        try:
            return min(float(headers["retry-after"]) + 0.5, 60)
        except ValueError:
            pass
    m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", str(exc), re.I)
    if m:
        return min(int(m.group(1) or 0) * 60 + float(m.group(2)) + 0.5, 60)
    return min(5 * 2 ** attempt, 40)


def is_rate_limit(exc: Exception) -> bool:
    return _status(exc) == 429 or type(exc).__name__ == "RateLimitError"


def is_transient(exc: Exception) -> bool:
    s = _status(exc)
    return (s is not None and s >= 500) or type(exc).__name__ in (
        "APITimeoutError", "APIConnectionError", "InternalServerError", "TimeoutError")


def call_with_retry(fn, limiter: RateLimiter, sleep=time.sleep, max_rate_retries: int = 4):
    attempt = 0
    while True:
        limiter.wait()
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - we re-raise anything we can't handle
            if is_rate_limit(exc) and attempt < max_rate_retries:
                delay, why = retry_delay(exc, attempt), "rate limited"
            elif is_transient(exc) and attempt < 2:
                delay, why = 3.0 * (attempt + 1), f"provider error ({type(exc).__name__})"
            else:
                raise
            print(f"  ⏳ {why}, retrying in {delay:.0f}s", file=sys.stderr)
            sleep(delay)
            attempt += 1


def to_openai_tools(tools: list[dict]) -> list[dict]:
    return [{"type": "function", "function": t} for t in tools]


def parse_response(resp) -> Reply:
    if isinstance(resp, str):  # the SDK returns raw text when the server's reply isn't JSON
        raise RuntimeError(f"LLM endpoint did not return JSON (check LLM_BASE_URL): {resp[:150]!r}")
    msg = resp.choices[0].message
    calls = []
    for tc in msg.tool_calls or []:
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            args = {}
        calls.append(ToolCall(tc.id, tc.function.name, args if isinstance(args, dict) else {}))
    usage = getattr(resp, "usage", None)
    message = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        message["tool_calls"] = [{"id": tc.id, "type": "function",
                                  "function": {"name": tc.function.name,
                                               "arguments": tc.function.arguments or "{}"}}
                                 for tc in msg.tool_calls]
    return Reply(text=(msg.content or "").strip(), tool_calls=calls, message=message,
                 usage={"input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                        "output_tokens": getattr(usage, "completion_tokens", 0) or 0})


class LLM:
    """chat(messages, tools) -> Reply. Messages use the OpenAI chat format."""

    def __init__(self, client=None, model: str = config.LLM_MODEL, rpm: int = config.LLM_RPM,
                 sleep=time.sleep):
        if client is None:
            import openai
            if not config.LLM_API_KEY:
                raise SystemExit("LLM_API_KEY is not set. Add it to .env (see .env.example).")
            client = openai.OpenAI(api_key=config.LLM_API_KEY, base_url=config.LLM_BASE_URL,
                                   timeout=config.LLM_TIMEOUT, max_retries=0)
        self.client, self.model = client, model
        self.limiter, self._sleep = RateLimiter(rpm, sleep=sleep), sleep

    def chat(self, messages: list[dict], tools: list[dict]) -> Reply:
        kwargs = {"model": self.model, "messages": messages, "max_tokens": MAX_TOKENS,
                  "temperature": 0.1}
        if tools:
            kwargs["tools"] = to_openai_tools(tools)
        resp = call_with_retry(lambda: self.client.chat.completions.create(**kwargs),
                               self.limiter, sleep=self._sleep)
        return parse_response(resp)
EOF_UKT
echo "  ✓ tube/agent/llm.py ($(wc -l < 'tube/agent/llm.py') lines)"
mkdir -p "$(dirname 'tube/agent/tools.py')"
cat > 'tube/agent/tools.py' <<'EOF_UKT'
"""The agent's tools: what the LLM may call, and the code that runs each call.

Each tool returns (json_text, is_error). Errors are explained in plain words
("I couldn't find a station called ...") so the model can relay them or ask the
user, instead of guessing. Dependencies are injected, so tests run with fakes.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from tube.tfl.arrivals import get_arrivals
from tube.tfl.client import TflClient, TflError
from tube.tfl.fares import get_fares
from tube.tfl.stations import StationDirectory, normalise
from tube.tfl.status import get_line_status

LONDON = ZoneInfo("Europe/London")
TOPICS = ["paying", "fares", "discounts", "services", "accessibility"]
PASSAGE_CHARS = 700  # keep tool results small: free LLM tiers have tight token limits

TOOL_SPECS = [
    {
        "name": "search_tfl_guidance",
        "description": ("Search official TfL guidance pages: how to pay (contactless, Oyster, "
                        "touching in and out), fares rules, caps, refunds, discounts and free "
                        "travel, the Night Tube, accessibility. Returns passages with their URL "
                        "and section. Use for any question about rules or how things work."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to look up, in plain words."},
                "topic": {"type": "string", "enum": TOPICS,
                          "description": "Optional: narrow the search to one topic."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_line_status",
        "description": ("Live status of Tube, Elizabeth line, DLR and Overground lines (good "
                        "service, delays, closures and the reason). Omit 'line' for all lines."),
        "parameters": {
            "type": "object",
            "properties": {"line": {"type": "string", "description": "e.g. 'Victoria'"}},
        },
    },
    {
        "name": "get_next_trains",
        "description": "Live next-train arrival predictions at a station.",
        "parameters": {
            "type": "object",
            "properties": {
                "station": {"type": "string", "description": "Station name, e.g. 'Oxford Circus'"},
                "line": {"type": "string", "description": "Optional line to filter by"},
            },
            "required": ["station"],
        },
    },
    {
        "name": "get_fare",
        "description": ("Live single fares between two stations from TfL (adult pay as you go "
                        "peak/off-peak and cash fares). Use this for 'how much from A to B'."),
        "parameters": {
            "type": "object",
            "properties": {
                "from_station": {"type": "string"},
                "to_station": {"type": "string"},
            },
            "required": ["from_station", "to_station"],
        },
    },
]


def now_london() -> str:
    return datetime.now(LONDON).strftime("%a %d %b %Y, %H:%M")


def _dump(data) -> str:
    return json.dumps(data, ensure_ascii=False)


class Toolbox:
    specs = TOOL_SPECS

    def __init__(self, client: TflClient | None = None, stations: StationDirectory | None = None,
                 search_fn=None, clock=now_london):
        self.client = client or TflClient()
        self._stations = stations
        if search_fn is None:
            from tube.rag.search import search as search_fn  # loads models lazily
        self.search_fn = search_fn
        self.clock = clock

    @property
    def stations(self) -> StationDirectory:
        if self._stations is None:
            self._stations = StationDirectory.load()
        return self._stations

    # ------------------------------------------------------------------ dispatch
    def call(self, name: str, args: dict) -> tuple[str, bool]:
        handler = {
            "search_tfl_guidance": self.search_tfl_guidance,
            "get_line_status": self.get_line_status,
            "get_next_trains": self.get_next_trains,
            "get_fare": self.get_fare,
        }.get(name)
        if handler is None:
            return _dump({"error": f"Unknown tool '{name}'."}), True
        try:
            return handler(**args), False
        except ToolError as exc:
            return _dump({"error": str(exc)}), True
        except TflError as exc:
            return _dump({"error": f"TfL live data is unavailable right now ({exc})."}), True
        except TypeError as exc:  # missing or unexpected arguments from the model
            return _dump({"error": f"Bad arguments for {name}: {exc}"}), True

    # ------------------------------------------------------------------ tools
    def search_tfl_guidance(self, query: str, topic: str | None = None) -> str:
        topic = topic if topic in TOPICS else None
        hits = self.search_fn(query, k=4, topic=topic)
        if not hits and topic:
            hits = self.search_fn(query, k=4)  # topic guess was too narrow
        return _dump({"results": [{
            "title": h["title"], "section": h["section"], "url": h["url"],
            "retrieved": (h.get("fetched_at") or "")[:10],
            "text": h["text"].split("\n", 1)[-1][:PASSAGE_CHARS],
        } for h in hits]})

    def get_line_status(self, line: str | None = None) -> str:
        statuses = get_line_status(self.client)
        if line:
            q = normalise(line).replace(" line", "")
            statuses = [s for s in statuses if q and q in normalise(s.name)]
            if not statuses:
                raise ToolError(f"No line called '{line}'. Try e.g. Victoria, Central, Elizabeth.")
            return _dump({"as_of": self.clock(), "lines": [
                {"line": s.name, "status": s.status, "reason": s.reason} for s in statuses]})
        disrupted = [s for s in statuses if not s.is_good]
        return _dump({
            "as_of": self.clock(),
            "disrupted": [{"line": s.name, "status": s.status, "reason": s.reason} for s in disrupted],
            "good_service": [s.name for s in statuses if s.is_good],
        })

    def get_next_trains(self, station: str, line: str | None = None) -> str:
        st = self._station(station)
        arrivals = get_arrivals(self.client, st.id, limit=20)
        if line:
            q = normalise(line).replace(" line", "")
            arrivals = [a for a in arrivals if q in normalise(a.line)]
        return _dump({"as_of": self.clock(), "station": st.name, "lines": st.lines,
                      "next_trains": [a.describe() for a in arrivals[:6]]
                      or ["No arrival predictions right now."]})

    def get_fare(self, from_station: str, to_station: str) -> str:
        a, b = self._station(from_station), self._station(to_station)
        if a.id == b.id:
            raise ToolError("The start and end stations are the same.")
        fares = get_fares(self.client, a.id, b.id)
        if not fares:
            raise ToolError(f"TfL returned no fare for {a.name} to {b.name}.")
        return _dump({"as_of": self.clock(), "from": a.name, "to": b.name,
                      "adult_single_fares": [f.describe() for f in fares]})

    # ------------------------------------------------------------------ helpers
    def _station(self, name: str):
        st = self.stations.find(name or "")
        if st is None:
            close = difflib.get_close_matches(name or "", self.stations.names(), n=3, cutoff=0.5)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            raise ToolError(f"I couldn't find a station called '{name}'.{hint}")
        return st


class ToolError(Exception):
    """A problem the user should hear about in plain words."""
EOF_UKT
echo "  ✓ tube/agent/tools.py ($(wc -l < 'tube/agent/tools.py') lines)"
mkdir -p "$(dirname 'tube/agent/prompts.py')"
cat > 'tube/agent/prompts.py' <<'EOF_UKT'
"""System prompt for the London Tube Assistant."""

SYSTEM_PROMPT = """You are the London Tube Assistant. You help people travel on the London \
Underground and other TfL services. The current date and time in London is {now}.

## Tools: always prefer them to memory
- Live questions (is a line running, delays, next trains, the fare between two stations) \
-> call get_line_status, get_next_trains or get_fare. Never guess live information or prices.
- Rules and how things work (paying, touching in and out, caps, refunds, discounts, \
Night Tube, accessibility) -> call search_tfl_guidance and answer ONLY from the passages it \
returns. If they don't answer the question, say so and suggest https://tfl.gov.uk.
- A question can need several tools (e.g. a fare and whether the line is running).
- Be efficient: one search is usually enough, never more than two per question.
- If a station name isn't recognised, tell the user and offer the suggestions the tool gave.

## Answers
- Lead with the direct answer in one or two sentences, then any detail. Keep it short.
- For guidance, cite the page as a markdown link with its section, e.g. \
[Touching in and out – Pay as you go](https://tfl.gov.uk/...). Only use URLs that appear in \
tool results; never invent links.
- For live data, say it is live and give the time (the tool's "as_of").
- Use £ and UK spelling. Peak/off-peak depends on the current time above.
- You only cover London transport. Politely decline anything else."""


def build_system_prompt(now: str) -> str:
    return SYSTEM_PROMPT.format(now=now)
EOF_UKT
echo "  ✓ tube/agent/prompts.py ($(wc -l < 'tube/agent/prompts.py') lines)"
mkdir -p "$(dirname 'tube/agent/guardrails.py')"
cat > 'tube/agent/guardrails.py' <<'EOF_UKT'
"""Checks that run in code after every answer (not just instructions in the prompt).

Invented links: every URL in the answer must have appeared in a tool result (or be
the TfL home page). Anything else is flagged and a warning is added for the user.
"""

from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
ALWAYS_ALLOWED = {"https://tfl.gov.uk", "https://tfl.gov.uk/"}
WARNING = ("\n\n> ⚠️ Some links above could not be checked against the TfL pages this "
           "assistant searched. Please check them on tfl.gov.uk.")


def extract_urls(text: str) -> set[str]:
    return {u.rstrip(".,;:") for u in URL_RE.findall(text or "")}


def check_answer(answer: str, allowed_urls: set[str]) -> dict:
    cited = extract_urls(answer)
    allowed = {u.rstrip("/") for u in allowed_urls | ALWAYS_ALLOWED}
    unsupported = sorted(u for u in cited if u.rstrip("/") not in allowed)
    if unsupported:
        answer += WARNING
    return {"answer": answer, "report": {"cited_urls": sorted(cited),
                                         "unsupported_urls": unsupported}}
EOF_UKT
echo "  ✓ tube/agent/guardrails.py ($(wc -l < 'tube/agent/guardrails.py') lines)"
mkdir -p "$(dirname 'tube/agent/agent.py')"
cat > 'tube/agent/agent.py' <<'EOF_UKT'
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
EOF_UKT
echo "  ✓ tube/agent/agent.py ($(wc -l < 'tube/agent/agent.py') lines)"
mkdir -p "$(dirname 'tube/agent/cli.py')"
cat > 'tube/agent/cli.py' <<'EOF_UKT'
"""Chat with the agent in the terminal.

    python -m tube.agent.cli "Is the Victoria line running?"
    python -m tube.agent.cli            # interactive; 'reset' clears the conversation
"""

from __future__ import annotations

import sys

from tube.agent.agent import TubeAgent


def show(r) -> None:
    print(f"\n{r.answer}\n")
    for t in r.trace:
        flag = " ✗" if t["error"] else ""
        print(f"  🔧 {t['tool']}({', '.join(f'{k}={v!r}' for k, v in t['args'].items())}){flag}")
    if r.guardrails.get("unsupported_urls"):
        print(f"  🛡 unverified links: {r.guardrails['unsupported_urls']}")
    print(f"  ⏱ {r.seconds}s · tokens {r.usage['input_tokens']}/{r.usage['output_tokens']}\n")


def safe_ask(agent: TubeAgent, q: str) -> None:
    try:
        show(agent.ask(q))
    except Exception as exc:  # noqa: BLE001 - show a readable message, not a stack trace
        name = type(exc).__name__
        hint = {"AuthenticationError": "check LLM_API_KEY in .env",
                "NotFoundError": "check LLM_MODEL in .env",
                "RateLimitError": "free-tier limit hit; wait a minute",
                "APIConnectionError": "can't reach the LLM (is LLM_BASE_URL right / Ollama running?)"}
        print(f"\n⚠️  {name}: {hint.get(name, str(exc)[:200])}\n")


def main() -> None:
    agent = TubeAgent()
    if len(sys.argv) > 1:
        safe_ask(agent, " ".join(sys.argv[1:]))
        return
    print("London Tube Assistant. Ask a question ('reset' to start over, Enter to quit).")
    while True:
        try:
            q = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q:
            break
        if q.lower() == "reset":
            agent.reset()
            print("(conversation cleared)")
            continue
        safe_ask(agent, q)


if __name__ == "__main__":
    main()
EOF_UKT
echo "  ✓ tube/agent/cli.py ($(wc -l < 'tube/agent/cli.py') lines)"
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
EOF_UKT
echo "  ✓ tests/test_rerank_eval.py ($(wc -l < 'tests/test_rerank_eval.py') lines)"
mkdir -p "$(dirname 'tests/test_agent_tools.py')"
cat > 'tests/test_agent_tools.py' <<'EOF_UKT'
import json

import pytest

from tube.agent.tools import Toolbox
from tube.tfl.client import TflError
from tube.tfl.stations import Station, StationDirectory

STATIONS = StationDirectory([
    Station("940GZZLUOXC", "Oxford Circus", ["Bakerloo", "Central", "Victoria"]),
    Station("940GZZLUBNK", "Bank", ["Central", "Northern"]),
    Station("940GZZLUVIC", "Victoria", ["Victoria", "District", "Circle"]),
])


class FakeClient:
    """Answers TfL API paths from canned data (shapes match the real API)."""

    def __init__(self, fail=False):
        self.fail, self.paths = fail, []

    def get_json(self, path, params=None):
        self.paths.append(path)
        if self.fail:
            raise TflError("HTTP 503")
        if path.startswith("Line/Mode/"):
            return [
                {"id": "victoria", "name": "Victoria", "lineStatuses": [{"statusSeverityDescription": "Good Service"}]},
                {"id": "central", "name": "Central", "lineStatuses": [
                    {"statusSeverityDescription": "Minor Delays", "reason": "Signal failure at Bank."}]},
            ]
        if path.endswith("/Arrivals"):
            return [{"lineName": "Victoria", "destinationName": "Brixton Underground Station", "timeToStation": 120},
                    {"lineName": "Central", "destinationName": "Epping Underground Station", "timeToStation": 30}]
        if "/FareTo/" in path:
            return [{"rows": [{"ticketsAvailable": [
                {"passengerType": "Adult", "cost": "2.90", "ticketType": {"type": "Pay as you go"},
                 "ticketTime": {"type": "Off Peak"}}]}]}]
        raise AssertionError(path)


def fake_search(query, k=4, topic=None):
    if topic == "accessibility":
        return []
    return [{"title": "Touching in and out", "section": "Overview",
             "url": "https://tfl.gov.uk/fares/touching", "fetched_at": "2026-10-07T09:00:00",
             "text": "Touching in and out > Overview\nTouch in and out on every journey."}]


@pytest.fixture
def box():
    return Toolbox(client=FakeClient(), stations=STATIONS, search_fn=fake_search,
                   clock=lambda: "Wed 07 Oct 2026, 15:40")


def call(box, name, **args):
    text, err = box.call(name, args)
    return json.loads(text), err


def test_search_returns_compact_cited_passages(box):
    data, err = call(box, "search_tfl_guidance", query="do I touch out")
    r = data["results"][0]
    assert not err and r["url"] == "https://tfl.gov.uk/fares/touching"
    assert r["text"] == "Touch in and out on every journey."   # title prefix stripped
    assert r["retrieved"] == "2026-10-07"


def test_search_falls_back_when_topic_finds_nothing(box):
    data, _ = call(box, "search_tfl_guidance", query="lifts", topic="accessibility")
    assert data["results"]


def test_all_lines_shows_disruptions_first(box):
    data, err = call(box, "get_line_status")
    assert not err and data["as_of"] == "Wed 07 Oct 2026, 15:40"
    assert data["disrupted"] == [{"line": "Central", "status": "Minor Delays",
                                  "reason": "Signal failure at Bank."}]
    assert data["good_service"] == ["Victoria"]


def test_one_line_and_unknown_line(box):
    data, _ = call(box, "get_line_status", line="victoria line")
    assert data["lines"][0]["status"] == "Good Service"
    data, err = call(box, "get_line_status", line="Hogwarts Express")
    assert err and "No line called" in data["error"]


def test_next_trains_with_fuzzy_station_and_line_filter(box):
    data, err = call(box, "get_next_trains", station="oxford circus station", line="victoria")
    assert not err and data["station"] == "Oxford Circus"
    assert data["next_trains"] == ["Victoria line to Brixton in 2 min"]


def test_fare_between_two_stations(box):
    data, err = call(box, "get_fare", from_station="bank", to_station="Victoria")
    assert not err and data["from"] == "Bank" and data["to"] == "Victoria"
    assert data["adult_single_fares"] == ["Pay as you go (Off Peak): £2.90"]


def test_small_typos_are_fixed(box):
    data, err = call(box, "get_fare", from_station="Bnak", to_station="Victoria")
    assert not err and data["from"] == "Bank"


def test_unknown_station_gives_suggestions(box):
    data, err = call(box, "get_fare", from_station="Victorian Gardens", to_station="Bank")
    assert err and "couldn't find a station called 'Victorian Gardens'" in data["error"]
    assert "Did you mean: Victoria" in data["error"]
    data, err = call(box, "get_next_trains", station="Hogwarts")
    assert err and "Did you mean" not in data["error"]


def test_same_station_fare(box):
    data, err = call(box, "get_fare", from_station="Bank", to_station="bank")
    assert err and "same" in data["error"]


def test_tfl_outage_is_reported_not_raised():
    box = Toolbox(client=FakeClient(fail=True), stations=STATIONS, search_fn=fake_search)
    data, err = call(box, "get_line_status")
    assert err and "unavailable" in data["error"]


def test_bad_arguments_and_unknown_tool(box):
    data, err = call(box, "get_fare", from_station="Bank")          # missing to_station
    assert err and "Bad arguments" in data["error"]
    data, err = call(box, "teleport", to="Paris")
    assert err and "Unknown tool" in data["error"]


def test_tool_specs_are_valid_function_schemas(box):
    names = [t["name"] for t in box.specs]
    assert names == ["search_tfl_guidance", "get_line_status", "get_next_trains", "get_fare"]
    for t in box.specs:
        assert t["parameters"]["type"] == "object" and t["description"]
EOF_UKT
echo "  ✓ tests/test_agent_tools.py ($(wc -l < 'tests/test_agent_tools.py') lines)"
mkdir -p "$(dirname 'tests/test_agent_loop.py')"
cat > 'tests/test_agent_loop.py' <<'EOF_UKT'
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
EOF_UKT
echo "  ✓ tests/test_agent_loop.py ($(wc -l < 'tests/test_agent_loop.py') lines)"
mkdir -p "$(dirname 'tests/test_llm.py')"
cat > 'tests/test_llm.py' <<'EOF_UKT'
from types import SimpleNamespace as NS

import pytest

from tube.agent.llm import LLM, RateLimiter, call_with_retry, parse_response, retry_delay


class RateLimitError(Exception):
    status_code = 429


class InternalServerError(Exception):
    status_code = 500


def completion(content="", tool_calls=None, usage=(10, 5)):
    msg = NS(content=content, tool_calls=tool_calls)
    return NS(choices=[NS(message=msg)], usage=NS(prompt_tokens=usage[0], completion_tokens=usage[1]))


def test_parse_text_and_tool_calls():
    tc = NS(id="t1", function=NS(name="get_fare", arguments='{"from_station": "Bank", "to_station": "Angel"}'))
    r = parse_response(completion("", [tc]))
    assert r.tool_calls[0].name == "get_fare" and r.tool_calls[0].args["to_station"] == "Angel"
    assert r.message["tool_calls"][0]["function"]["name"] == "get_fare"
    assert r.usage == {"input_tokens": 10, "output_tokens": 5}
    r2 = parse_response(completion("Hello"))
    assert r2.text == "Hello" and r2.tool_calls == [] and "tool_calls" not in r2.message


def test_bad_tool_json_becomes_empty_args():
    tc = NS(id="t1", function=NS(name="get_line_status", arguments="{not json"))
    assert parse_response(completion("", [tc])).tool_calls[0].args == {}


def test_non_json_endpoint_is_explained():
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        parse_response("<html>OK</html>")


def test_retry_delay_uses_provider_hint():
    assert retry_delay(RateLimitError("Please try again in 7.5s."), 0) == 8.0
    assert retry_delay(RateLimitError("Please try again in 1m2s."), 0) == 60   # capped
    exc = RateLimitError("x"); exc.response = NS(headers={"retry-after": "3"}, status_code=429)
    assert retry_delay(exc, 0) == 3.5
    assert retry_delay(RateLimitError("no hint"), 1) == 10


def test_retries_rate_limit_then_succeeds():
    sleeps, calls = [], {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RateLimitError("try again in 2s")
        return "ok"
    assert call_with_retry(flaky, RateLimiter(0), sleep=sleeps.append) == "ok"
    assert sleeps == [2.5, 2.5]


def test_server_errors_get_two_quick_retries():
    sleeps = []

    def always_500():
        raise InternalServerError("boom")
    with pytest.raises(InternalServerError):
        call_with_retry(always_500, RateLimiter(0), sleep=sleeps.append)
    assert sleeps == [3.0, 6.0]


def test_other_errors_are_not_retried():
    with pytest.raises(ValueError):
        call_with_retry(lambda: (_ for _ in ()).throw(ValueError("bad")), RateLimiter(0), sleep=lambda s: None)


def test_rate_limiter_paces_requests():
    t = {"now": 0.0}
    sleeps = []
    lim = RateLimiter(2, clock=lambda: t["now"], sleep=lambda s: (sleeps.append(s), t.__setitem__("now", t["now"] + s)))
    lim.wait(); lim.wait()          # two allowed immediately
    lim.wait()                      # third must wait ~60s
    assert sleeps and 59 <= sleeps[0] <= 61


def test_llm_chat_sends_tools_only_when_given():
    sent = []

    class FakeCompletions:
        def create(self, **kw):
            sent.append(kw)
            return completion("hi")
    client = NS(chat=NS(completions=FakeCompletions()))
    llm = LLM(client=client, model="m", rpm=0)
    assert llm.chat([{"role": "user", "content": "x"}], []).text == "hi"
    llm.chat([{"role": "user", "content": "x"}], [{"name": "t", "description": "d", "parameters": {"type": "object"}}])
    assert "tools" not in sent[0] and sent[1]["tools"][0]["type"] == "function"
EOF_UKT
echo "  ✓ tests/test_llm.py ($(wc -l < 'tests/test_llm.py') lines)"
echo
echo "Done: 16 files. Next: pip install -r requirements.txt && python -m pytest -q"