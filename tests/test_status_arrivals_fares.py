from tube.tfl.arrivals import parse_arrivals
from tube.tfl.fares import Fare, get_fares, parse_fares
from tube.tfl.status import parse_line_status


def test_status_disruptions_first_and_reasons_kept(load_fixture):
    lines = parse_line_status(load_fixture("line_status.json"))
    assert [l.name for l in lines] == ["Central", "District", "Victoria"]
    district = lines[1]
    assert district.status == "Part Closure, Minor Delays"
    assert "Wimbledon" in district.reason and "rest of the line" in district.reason
    assert lines[2].is_good and lines[2].reason == ""


def test_status_handles_empty_reply():
    assert parse_line_status([]) == []


def test_arrivals_sorted_and_cleaned(load_fixture):
    arr = parse_arrivals(load_fixture("arrivals.json"))
    assert [a.line for a in arr] == ["Central", "Bakerloo", "Victoria"]
    assert arr[0].minutes == 0 and arr[0].describe().startswith("Central line to Epping due")
    assert arr[1].destination == "Elephant and Castle"      # falls back to "towards"
    assert arr[2].destination == "Brixton" and arr[2].minutes == 4


def test_arrivals_limit(load_fixture):
    assert len(parse_arrivals(load_fixture("arrivals.json"), limit=2)) == 2


def test_fares_adult_only_deduplicated(load_fixture):
    fares = parse_fares(load_fixture("fares.json"))
    assert fares == [Fare("Pay as you go", "Peak", 3.00),
                     Fare("Pay as you go", "Off Peak", 2.90),
                     Fare("CashSingle", "Anytime", 7.10)]
    assert fares[1].describe() == "Pay as you go (Off Peak): £2.90"
    assert fares[2].describe() == "CashSingle: £7.10"


def test_same_station_needs_no_api_call():
    class Boom:
        def get_json(self, *a, **k):
            raise AssertionError("should not call the API")
    assert get_fares(Boom(), "940GZZLUBNK", "940GZZLUBNK") == []
