import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    return lambda name: json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, status=200, payload=None, text_only=False):
        self.status_code, self._payload, self._text_only = status, payload, text_only

    def json(self):
        if self._text_only:
            raise ValueError("not json")
        return self._payload


class FakeSession:
    """Replays queued responses and records every request made."""

    def __init__(self, *responses):
        self.responses, self.calls = list(responses), []

    def get(self, url, params=None, timeout=None):
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def fake():
    return FakeSession, FakeResponse
