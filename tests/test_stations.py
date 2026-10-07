from tube.tfl.stations import (Station, StationDirectory, clean_name, fetch_stations,
                               merge_stations, normalise, parse_line_stops)


def directory():
    return StationDirectory([
        Station("940GZZLUVIC", "Victoria", ["Victoria", "District"]),
        Station("940GZZLUVIP", "Victoria Park", []),            # made-up, to test ranking
        Station("940GZZLUOXC", "Oxford Circus", ["Victoria", "Central", "Bakerloo"]),
        Station("940GZZLUPCC", "Piccadilly Circus", ["Piccadilly", "Bakerloo"]),
        Station("940GZZLUKSX", "King's Cross St. Pancras", ["Victoria", "Northern"]),
        Station("940GZZLUEAC", "Elephant & Castle", ["Northern", "Bakerloo"]),
        Station("940GZZLUHR5", "Heathrow Terminal 5", ["Piccadilly"]),
    ])


def test_clean_and_normalise():
    assert clean_name("Oxford Circus Underground Station") == "Oxford Circus"
    assert clean_name("Paddington (Elizabeth line)") == "Paddington (Elizabeth line)"
    assert normalise("King's Cross St. Pancras") == "kings cross st pancras"
    assert normalise("Elephant & Castle") == "elephant and castle"


def test_find_exact_prefix_contains_and_typos():
    d = directory()
    assert d.find("Oxford Circus Station").id == "940GZZLUOXC"
    assert d.find("victoria").name == "Victoria"            # not Victoria Park
    assert d.find("kings cross").id == "940GZZLUKSX"
    assert d.find("elephant and castle").id == "940GZZLUEAC"
    assert d.find("picadilly circus").id == "940GZZLUPCC"   # typo
    assert d.find("terminal 5").id == "940GZZLUHR5"         # contains
    assert d.find("hogwarts") is None and d.find("") is None


def test_parse_line_stops_skips_non_stations(load_fixture):
    stops = parse_line_stops(load_fixture("victoria_stops.json"), "Victoria")
    assert [s.id for s in stops] == ["940GZZLUVIC", "940GZZLUOXC", "940GZZLUKSX"]
    assert stops[2].name == "King's Cross St. Pancras" and stops[0].lines == ["Victoria"]


def test_merge_combines_lines_and_prefers_tube_ids():
    merged = merge_stations([
        Station("910GPADTLL", "Paddington", ["Elizabeth line"]),
        Station("940GZZLUPAC", "Paddington", ["Bakerloo"]),
        Station("940GZZLUPAC", "Paddington", ["Circle"]),
    ])
    assert len(merged) == 1
    assert merged[0].id == "940GZZLUPAC"
    assert merged[0].lines == ["Bakerloo", "Circle", "Elizabeth line"]


def test_fetch_stations_walks_every_line(load_fixture):
    class FakeClient:
        def __init__(self):
            self.paths = []

        def get_json(self, path, params=None):
            self.paths.append(path)
            if path.startswith("Line/Mode/"):
                return [{"id": "victoria", "name": "Victoria"}]
            return load_fixture("victoria_stops.json")

    c = FakeClient()
    stations = fetch_stations(c, ["tube"])
    assert c.paths == ["Line/Mode/tube", "Line/victoria/StopPoints"]
    assert {s.name for s in stations} == {"Victoria", "Oxford Circus", "King's Cross St. Pancras"}


def test_save_and_load_round_trip(tmp_path):
    p = tmp_path / "stations.json"
    directory().save(p)
    again = StationDirectory.load(p)
    assert again.names() == directory().names()
    assert again.find("oxford circus").lines == ["Victoria", "Central", "Bakerloo"]
