"""UI tests with Streamlit's AppTest: a fake agent and fake TfL data, no network."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from app import services
from app.ui import describe_step, friendly_error, line_chip
from tube.agent.agent import AgentResult
from tube.agent.tools import Toolbox

from tests.test_agent_tools import STATIONS, FakeClient, fake_search

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


class FakeAgent:
    def __init__(self, fail=None):
        self.questions, self.fail = [], fail

    def ask(self, q):
        if self.fail:
            raise self.fail
        self.questions.append(q)
        return AgentResult(
            answer=f"Answer to: {q}",
            sources=[{"title": "Touching in and out", "section": "Overview",
                      "url": "https://tfl.gov.uk/fares/touching", "retrieved": "2026-10-07"}],
            trace=[{"step": 1, "tool": "search_tfl_guidance", "args": {"query": q},
                    "error": False, "result": "{}"}],
            usage={"input_tokens": 100, "output_tokens": 20}, seconds=1.2)

    def reset(self):
        self.questions = []


@pytest.fixture
def fake_services(monkeypatch):
    agent = FakeAgent()
    box = Toolbox(client=FakeClient(), stations=STATIONS, search_fn=fake_search)
    monkeypatch.setattr(services, "new_agent", lambda: agent)
    monkeypatch.setattr(services, "get_toolbox", lambda: box)
    monkeypatch.setattr(services, "llm_label", lambda: "fake-model via test")
    monkeypatch.setattr(services, "ensure_ready", lambda: {"index": "present"})
    monkeypatch.delenv("DEMO_MAX_QUESTIONS", raising=False)
    return agent


def run(at=None):
    at = at or AppTest.from_file(APP, default_timeout=30)
    return at.run()


def test_home_shows_examples(fake_services):
    at = run()
    assert not at.exception
    labels = [b.label for b in at.button]
    assert "Is the Victoria line running?" in labels and "New conversation" in labels


def test_chat_question_shows_answer_and_sources(fake_services):
    at = run()
    at.chat_input[0].set_value("Do I touch out on the bus?").run()
    assert not at.exception
    assert fake_services.questions == ["Do I touch out on the bus?"]
    text = " ".join(m.value for m in at.markdown)
    assert "Answer to: Do I touch out on the bus?" in text
    assert "https://tfl.gov.uk/fares/touching" in text
    assert "Searched TfL guidance" in text


def test_example_button_asks_question(fake_services):
    at = run()
    next(b for b in at.button if b.label == "Do I touch out on the bus?").click().run()
    assert fake_services.questions == ["Do I need to touch out on the bus?"]


def test_demo_limit(fake_services, monkeypatch):
    monkeypatch.setenv("DEMO_MAX_QUESTIONS", "1")
    at = run()
    at.chat_input[0].set_value("one").run()
    at.chat_input[0].set_value("two").run()
    assert fake_services.questions == ["one"]
    assert any("allows 1 questions" in m.value for m in at.markdown)


def test_llm_error_is_friendly(monkeypatch, fake_services):
    class RateLimitError(Exception):
        pass
    monkeypatch.setattr(services, "new_agent", lambda: FakeAgent(fail=RateLimitError("429")))
    at = run()
    at.chat_input[0].set_value("hi").run()
    assert not at.exception
    assert any("free AI quota is busy" in m.value for m in at.markdown)


def test_status_view_lists_disruptions_first(fake_services):
    at = run()
    at.segmented_control[0].set_value("Line status").run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert html.index("Central") < html.index("Victoria")
    assert "Signal failure at Bank." in html and "Minor Delays" in html


def test_fares_view(fake_services):
    at = run()
    at.segmented_control[0].set_value("Fares").run()
    at.selectbox[0].set_value("Bank")
    at.selectbox[1].set_value("Victoria")
    next(b for b in at.button if b.label == "Get fare").click().run()
    assert not at.exception
    assert at.table[0].value.iloc[0]["Adult fare"] == "£2.90"


def test_next_trains_view(fake_services):
    at = run()
    at.segmented_control[0].set_value("Next trains").run()
    next(b for b in at.button if b.label == "Show next trains").click().run()
    assert not at.exception
    html = " ".join(m.value for m in at.markdown)
    assert "Epping" in html and "due" in html


def test_helpers():
    assert "#0098D4" in line_chip("Victoria") and "#111111" in line_chip("Circle")
    assert "#5f6b7a" in line_chip("Unknown line")
    assert describe_step({"tool": "get_fare", "args": {"from_station": "Bank", "to_station": "Angel"},
                          "error": False}) == "Looked up the live fare: Bank → Angel"
    failed = describe_step({"tool": "get_next_trains", "args": {"station": "Hogwarts"}, "error": True,
                            "result": '{"error": "I couldn\'t find a station called \'Hogwarts\'."}'})
    assert failed.startswith("Checked live arrivals at Hogwarts (failed: I couldn't find")
    class AuthenticationError(Exception):
        pass
    assert "API key" in friendly_error(AuthenticationError())


def test_index_failure_shows_warning_but_app_works(fake_services, monkeypatch):
    def boom():
        raise RuntimeError("Could not download any TfL guidance pages.")
    monkeypatch.setattr(services, "ensure_ready", boom)
    at = run()
    assert not at.exception
    assert "guidance search isn't available" in at.warning[0].value
    at.chat_input[0].set_value("Is the Victoria line running?").run()
    assert fake_services.questions == ["Is the Victoria line running?"]
