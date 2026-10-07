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


def test_search_ignores_topic_from_the_model(box):
    """Regression: a wrong topic guess hid the refunds page, so topics are ignored."""
    seen = []
    box.search_fn = lambda q, k=4, topic=None: seen.append(topic) or fake_search(q, k)
    data, err = call(box, "search_tfl_guidance", query="delay refund", topic="fares")
    assert not err and data["results"] and seen == [None]
    spec = next(t for t in box.specs if t["name"] == "search_tfl_guidance")
    assert "topic" not in spec["parameters"]["properties"]


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
