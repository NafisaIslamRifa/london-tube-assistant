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
