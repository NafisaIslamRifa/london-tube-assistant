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
