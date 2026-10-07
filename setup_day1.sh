#!/usr/bin/env bash
# Day 1 setup: London Tube Assistant (TfL client + tests + CI)
set -e
echo "Writing Day 1 files..."
mkdir -p ".devcontainer"
cat > '.devcontainer/devcontainer.json' <<'EOF_UKT'
{
  "name": "London Tube Assistant",
  "image": "mcr.microsoft.com/devcontainers/python:3.12",
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {}
  },
  "postCreateCommand": "pip install -r requirements.txt",
  "forwardPorts": [8501],
  "customizations": {
    "vscode": { "extensions": ["ms-python.python"] }
  }
}
EOF_UKT
echo "  ✓ .devcontainer/devcontainer.json ($(wc -l < '.devcontainer/devcontainer.json') lines)"
mkdir -p "."
cat > '.env.example' <<'EOF_UKT'
# Copy to .env and fill in. Never commit .env.
# Free key from https://api-portal.tfl.gov.uk (optional, raises the rate limit)
TFL_APP_KEY=
EOF_UKT
echo "  ✓ .env.example ($(wc -l < '.env.example') lines)"
mkdir -p ".github/workflows"
cat > '.github/workflows/ci.yml' <<'EOF_UKT'
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
      - run: pip install -r requirements.txt
      - name: Unit tests (no network, no API keys)
        run: python -m pytest -q
EOF_UKT
echo "  ✓ .github/workflows/ci.yml ($(wc -l < '.github/workflows/ci.yml') lines)"
mkdir -p "."
cat > '.gitignore' <<'EOF_UKT'
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
EOF_UKT
echo "  ✓ .gitignore ($(wc -l < '.gitignore') lines)"
mkdir -p "."
cat > 'README.md' <<'EOF_UKT'
# London Tube Assistant

An agentic RAG assistant for travelling on the London Underground: grounded answers from official TfL guidance, plus live line status, next trains and fares from the TfL Unified API.

> Work in progress. Built step by step with unit tests, Docker and CI.

## Run the tests
```bash
pip install -r requirements.txt
python -m pytest -q
```

## Live check against the TfL API
```bash
python -m scripts.fetch_stations   # builds data/stations.json
python -m scripts.smoke_tfl
```

Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). Powered by TfL Open Data.
EOF_UKT
echo "  ✓ README.md ($(wc -l < 'README.md') lines)"
mkdir -p "."
cat > 'pytest.ini' <<'EOF_UKT'
[pytest]
pythonpath = .
testpaths = tests
EOF_UKT
echo "  ✓ pytest.ini ($(wc -l < 'pytest.ini') lines)"
mkdir -p "."
cat > 'requirements.txt' <<'EOF_UKT'
# Day 1: TfL API client
requests>=2.31
python-dotenv>=1.0

# Tests
pytest>=8.0
EOF_UKT
echo "  ✓ requirements.txt ($(wc -l < 'requirements.txt') lines)"
mkdir -p "scripts"
cat > 'scripts/__init__.py' <<'EOF_UKT'

EOF_UKT
echo "  ✓ scripts/__init__.py ($(wc -l < 'scripts/__init__.py') lines)"
mkdir -p "scripts"
cat > 'scripts/fetch_stations.py' <<'EOF_UKT'
"""Build data/stations.json from the TfL API (run once; re-run to refresh).

    python -m scripts.fetch_stations
"""

from tube import config
from tube.tfl.client import TflClient
from tube.tfl.stations import StationDirectory, fetch_stations


def main() -> None:
    stations = fetch_stations(TflClient())
    StationDirectory(stations).save()
    print(f"Saved {len(stations)} stations ({', '.join(config.STATION_MODES)}) "
          f"to {config.STATIONS_PATH}")


if __name__ == "__main__":
    main()
EOF_UKT
echo "  ✓ scripts/fetch_stations.py ($(wc -l < 'scripts/fetch_stations.py') lines)"
mkdir -p "scripts"
cat > 'scripts/smoke_tfl.py' <<'EOF_UKT'
"""Live check that every TfL call works (needs internet; not part of the unit tests).

    python -m scripts.smoke_tfl
"""

from tube.tfl.arrivals import get_arrivals
from tube.tfl.client import TflClient
from tube.tfl.fares import get_fares
from tube.tfl.stations import StationDirectory
from tube.tfl.status import get_line_status


def main() -> None:
    client = TflClient()
    stations = StationDirectory.load()

    print("== Line status ==")
    for s in get_line_status(client)[:6]:
        print(f"  {s.name:<22} {s.status}")

    oxc = stations.find("oxford circus")
    print(f"\n== Next trains at {oxc.name} ({oxc.id}) ==")
    for a in get_arrivals(client, oxc.id, limit=5):
        print("  " + a.describe())

    a, b = stations.find("bank"), stations.find("victoria")
    print(f"\n== Fares {a.name} -> {b.name} ==")
    for f in get_fares(client, a.id, b.id):
        print("  " + f.describe())

    for q in ["kings cross", "picadilly circus", "heathrow terminal 5"]:
        s = stations.find(q)
        print(f"\n'{q}' -> {s.name if s else None} {s.lines if s else ''}")


if __name__ == "__main__":
    main()
EOF_UKT
echo "  ✓ scripts/smoke_tfl.py ($(wc -l < 'scripts/smoke_tfl.py') lines)"
mkdir -p "tests"
cat > 'tests/__init__.py' <<'EOF_UKT'

EOF_UKT
echo "  ✓ tests/__init__.py ($(wc -l < 'tests/__init__.py') lines)"
mkdir -p "tests"
cat > 'tests/conftest.py' <<'EOF_UKT'
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
EOF_UKT
echo "  ✓ tests/conftest.py ($(wc -l < 'tests/conftest.py') lines)"
mkdir -p "tests/fixtures"
cat > 'tests/fixtures/arrivals.json' <<'EOF_UKT'
[
  {"lineName": "Victoria", "destinationName": "Brixton Underground Station", "timeToStation": 250, "platformName": "Southbound - Platform 4"},
  {"lineName": "Central", "destinationName": "Epping Underground Station", "timeToStation": 20, "platformName": "Eastbound - Platform 1"},
  {"lineName": "Bakerloo", "towards": "Elephant and Castle", "timeToStation": 95, "platformName": ""}
]
EOF_UKT
echo "  ✓ tests/fixtures/arrivals.json ($(wc -l < 'tests/fixtures/arrivals.json') lines)"
mkdir -p "tests/fixtures"
cat > 'tests/fixtures/fares.json' <<'EOF_UKT'
[
  {"header": "Single fare", "index": 0,
   "rows": [
     {"ticketsAvailable": [
       {"passengerType": "Adult", "cost": "3.00", "ticketType": {"type": "Pay as you go"}, "ticketTime": {"type": "Peak"}},
       {"passengerType": "Adult", "cost": "2.90", "ticketType": {"type": "Pay as you go"}, "ticketTime": {"type": "Off Peak"}},
       {"passengerType": "Adult", "cost": "7.10", "ticketType": {"type": "CashSingle"}, "ticketTime": {"type": "Anytime"}},
       {"passengerType": "Child", "cost": "0.00", "ticketType": {"type": "Pay as you go"}, "ticketTime": {"type": "Anytime"}}]},
     {"ticketsAvailable": [
       {"passengerType": "Adult", "cost": "3.00", "ticketType": {"type": "Pay as you go"}, "ticketTime": {"type": "Peak"}}]}]}
]
EOF_UKT
echo "  ✓ tests/fixtures/fares.json ($(wc -l < 'tests/fixtures/fares.json') lines)"
mkdir -p "tests/fixtures"
cat > 'tests/fixtures/line_status.json' <<'EOF_UKT'
[
  {"id": "victoria", "name": "Victoria", "modeName": "tube",
   "lineStatuses": [{"statusSeverity": 10, "statusSeverityDescription": "Good Service"}]},
  {"id": "central", "name": "Central", "modeName": "tube",
   "lineStatuses": [{"statusSeverity": 9, "statusSeverityDescription": "Minor Delays",
                     "reason": "Central Line: Minor delays due to an earlier signal failure."}]},
  {"id": "district", "name": "District", "modeName": "tube",
   "lineStatuses": [
     {"statusSeverity": 3, "statusSeverityDescription": "Part Closure", "reason": "No service between Earl's Court and Wimbledon."},
     {"statusSeverity": 9, "statusSeverityDescription": "Minor Delays", "reason": "Minor delays on the rest of the line."}]}
]
EOF_UKT
echo "  ✓ tests/fixtures/line_status.json ($(wc -l < 'tests/fixtures/line_status.json') lines)"
mkdir -p "tests/fixtures"
cat > 'tests/fixtures/victoria_stops.json' <<'EOF_UKT'
[
  {"naptanId": "940GZZLUVIC", "commonName": "Victoria Underground Station", "stopType": "NaptanMetroStation", "lat": 51.4965, "lon": -0.1447},
  {"naptanId": "940GZZLUOXC", "commonName": "Oxford Circus Underground Station", "stopType": "NaptanMetroStation", "lat": 51.5152, "lon": -0.1415},
  {"naptanId": "940GZZLUKSX", "commonName": "King's Cross St. Pancras Underground Station", "stopType": "NaptanMetroStation", "lat": 51.5302, "lon": -0.1238},
  {"naptanId": "HUBKGX", "commonName": "King's Cross & St Pancras International", "stopType": "TransportInterchange"}
]
EOF_UKT
echo "  ✓ tests/fixtures/victoria_stops.json ($(wc -l < 'tests/fixtures/victoria_stops.json') lines)"
mkdir -p "tests"
cat > 'tests/test_client.py' <<'EOF_UKT'
import pytest
import requests

from tube.tfl.client import TflClient, TflError


def make(fake, *responses, key=""):
    Session, _ = fake
    session = Session(*responses)
    return TflClient(base_url="https://api.example/", app_key=key, session=session,
                     sleep=lambda s: None), session


def test_builds_url_and_adds_app_key(fake):
    _, Resp = fake
    client, session = make(fake, Resp(200, [1]), key="secret")
    assert client.get_json("/Line/Mode/tube/Status") == [1]
    call = session.calls[0]
    assert call["url"] == "https://api.example/Line/Mode/tube/Status"
    assert call["params"] == {"app_key": "secret"}


def test_no_key_means_no_key_param(fake):
    _, Resp = fake
    client, session = make(fake, Resp(200, {}))
    client.get_json("x", {"a": 1})
    assert session.calls[0]["params"] == {"a": 1}


def test_retries_once_on_429_then_succeeds(fake):
    _, Resp = fake
    client, session = make(fake, Resp(429), Resp(200, ["ok"]))
    assert client.get_json("x") == ["ok"] and len(session.calls) == 2


def test_gives_up_after_retry(fake):
    _, Resp = fake
    client, _ = make(fake, Resp(503), Resp(503))
    with pytest.raises(TflError) as e:
        client.get_json("x")
    assert e.value.status == 503


def test_404_is_not_retried(fake):
    _, Resp = fake
    client, session = make(fake, Resp(404))
    with pytest.raises(TflError):
        client.get_json("x")
    assert len(session.calls) == 1


def test_network_error_becomes_tflerror(fake):
    client, _ = make(fake, requests.ConnectionError("down"), requests.ConnectionError("down"))
    with pytest.raises(TflError, match="Could not reach TfL"):
        client.get_json("x")


def test_non_json_reply(fake):
    _, Resp = fake
    client, _ = make(fake, Resp(200, text_only=True))
    with pytest.raises(TflError, match="non-JSON"):
        client.get_json("x")
EOF_UKT
echo "  ✓ tests/test_client.py ($(wc -l < 'tests/test_client.py') lines)"
mkdir -p "tests"
cat > 'tests/test_stations.py' <<'EOF_UKT'
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
EOF_UKT
echo "  ✓ tests/test_stations.py ($(wc -l < 'tests/test_stations.py') lines)"
mkdir -p "tests"
cat > 'tests/test_status_arrivals_fares.py' <<'EOF_UKT'
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
EOF_UKT
echo "  ✓ tests/test_status_arrivals_fares.py ($(wc -l < 'tests/test_status_arrivals_fares.py') lines)"
mkdir -p "tube"
cat > 'tube/__init__.py' <<'EOF_UKT'

EOF_UKT
echo "  ✓ tube/__init__.py ($(wc -l < 'tube/__init__.py') lines)"
mkdir -p "tube"
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
EOF_UKT
echo "  ✓ tube/config.py ($(wc -l < 'tube/config.py') lines)"
mkdir -p "tube/tfl"
cat > 'tube/tfl/__init__.py' <<'EOF_UKT'

EOF_UKT
echo "  ✓ tube/tfl/__init__.py ($(wc -l < 'tube/tfl/__init__.py') lines)"
mkdir -p "tube/tfl"
cat > 'tube/tfl/arrivals.py' <<'EOF_UKT'
"""Live arrival predictions at a station."""

from __future__ import annotations

from dataclasses import dataclass

from tube.tfl.client import TflClient


@dataclass
class Arrival:
    line: str
    destination: str
    minutes: int
    platform: str = ""

    def describe(self) -> str:
        when = "due" if self.minutes == 0 else f"in {self.minutes} min"
        where = f" ({self.platform})" if self.platform else ""
        return f"{self.line} line to {self.destination} {when}{where}"


def parse_arrivals(data: list[dict], limit: int = 8) -> list[Arrival]:
    """Turn /StopPoint/{id}/Arrivals into Arrival objects, soonest first."""
    out = []
    for item in data or []:
        seconds = item.get("timeToStation") or 0
        dest = item.get("destinationName") or item.get("towards") or "Check front of train"
        out.append(Arrival(
            line=item.get("lineName", "Unknown"),
            destination=dest.replace(" Underground Station", ""),
            minutes=max(0, round(seconds / 60)),
            platform=item.get("platformName", "") or "",
        ))
    out.sort(key=lambda a: a.minutes)
    return out[:limit]


def get_arrivals(client: TflClient, stop_id: str, limit: int = 8) -> list[Arrival]:
    return parse_arrivals(client.get_json(f"StopPoint/{stop_id}/Arrivals"), limit)
EOF_UKT
echo "  ✓ tube/tfl/arrivals.py ($(wc -l < 'tube/tfl/arrivals.py') lines)"
mkdir -p "tube/tfl"
cat > 'tube/tfl/client.py' <<'EOF_UKT'
"""A small, testable client for the TfL Unified API.

Everything that talks to the network goes through `TflClient.get_json`, so tests can
swap in a fake session and never touch the internet.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from tube import config


class TflError(RuntimeError):
    """The TfL API could not be reached or returned an error."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


RETRY_STATUSES = {429, 500, 502, 503, 504}


class TflClient:
    def __init__(self, base_url: str = config.TFL_BASE_URL, app_key: str = config.TFL_APP_KEY,
                 session: Any | None = None, timeout: float = config.TFL_TIMEOUT,
                 retries: int = 1, sleep=time.sleep):
        self.base_url = base_url.rstrip("/")
        self.app_key = app_key
        self.session = session or requests.Session()
        self.timeout = timeout
        self.retries = retries
        self._sleep = sleep

    def get_json(self, path: str, params: dict | None = None) -> Any:
        """GET base_url + path and return parsed JSON. Retries briefly on 429/5xx."""
        params = dict(params or {})
        if self.app_key:
            params["app_key"] = self.app_key
        url = f"{self.base_url}/{path.lstrip('/')}"

        for attempt in range(self.retries + 1):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                if attempt < self.retries:
                    self._sleep(1.0)
                    continue
                raise TflError(f"Could not reach TfL: {exc}") from exc

            if resp.status_code in RETRY_STATUSES and attempt < self.retries:
                self._sleep(2.0 if resp.status_code == 429 else 1.0)
                continue
            if resp.status_code >= 400:
                raise TflError(f"TfL returned HTTP {resp.status_code} for {path}",
                               status=resp.status_code)
            try:
                return resp.json()
            except ValueError as exc:
                raise TflError(f"TfL returned a non-JSON reply for {path}") from exc

        raise TflError(f"TfL request failed for {path}")  # pragma: no cover
EOF_UKT
echo "  ✓ tube/tfl/client.py ($(wc -l < 'tube/tfl/client.py') lines)"
mkdir -p "tube/tfl"
cat > 'tube/tfl/fares.py' <<'EOF_UKT'
"""Single fares between two stations (TfL /Stoppoint/{from}/FareTo/{to})."""

from __future__ import annotations

from dataclasses import dataclass

from tube.tfl.client import TflClient


@dataclass(frozen=True)
class Fare:
    ticket: str      # e.g. "Pay as you go"
    time: str        # e.g. "Peak", "Off Peak", "Anytime"
    cost: float      # pounds

    def describe(self) -> str:
        when = "" if self.time in ("", "Anytime") else f" ({self.time})"
        return f"{self.ticket}{when}: £{self.cost:.2f}"


def parse_fares(data: list[dict]) -> list[Fare]:
    """Flatten TfL's nested fare reply: sections -> rows -> ticketsAvailable.

    Only adult fares are kept; duplicates are removed, order is preserved.
    """
    fares: list[Fare] = []
    for section in data or []:
        for row in section.get("rows") or []:
            for t in row.get("ticketsAvailable") or []:
                if t.get("passengerType", "Adult") != "Adult" or t.get("cost") in (None, ""):
                    continue
                try:
                    cost = float(t["cost"])
                except (TypeError, ValueError):
                    continue
                fare = Fare(ticket=(t.get("ticketType") or {}).get("type", "Ticket"),
                            time=(t.get("ticketTime") or {}).get("type", ""),
                            cost=cost)
                if fare not in fares:
                    fares.append(fare)
    return fares


def get_fares(client: TflClient, from_id: str, to_id: str) -> list[Fare]:
    if from_id == to_id:
        return []
    return parse_fares(client.get_json(f"Stoppoint/{from_id}/FareTo/{to_id}"))
EOF_UKT
echo "  ✓ tube/tfl/fares.py ($(wc -l < 'tube/tfl/fares.py') lines)"
mkdir -p "tube/tfl"
cat > 'tube/tfl/stations.py' <<'EOF_UKT'
"""Station directory: turn what a person types ("kings x", "oxford circus") into a
TfL station id.

The list is built once from the API (`python -m scripts.fetch_stations`) and saved
to data/stations.json, so the app does not depend on a big API call at start-up.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from tube import config
from tube.tfl.client import TflClient

SUFFIXES = re.compile(r"\s*\b(underground|dlr|rail|elizabeth line)?\s*station\b.*$", re.I)


@dataclass
class Station:
    id: str                       # Naptan id, e.g. 940GZZLUOXC
    name: str                     # cleaned, e.g. "Oxford Circus"
    lines: list[str] = field(default_factory=list)
    lat: float | None = None
    lon: float | None = None


def clean_name(common_name: str) -> str:
    """'Oxford Circus Underground Station' -> 'Oxford Circus'."""
    return SUFFIXES.sub("", common_name).strip() or common_name.strip()


def normalise(text: str) -> str:
    """Lower-case, '&' -> 'and', drop punctuation and 'station', squash spaces."""
    t = text.lower().replace("&", " and ").replace("st.", "st ")
    t = re.sub(r"\b(underground|station|tube)\b", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", "", t)
    return re.sub(r"\s+", " ", t).strip()


def parse_line_stops(data: list[dict], line_name: str) -> list[Station]:
    """Parse /Line/{id}/StopPoints into stations served by that line."""
    out = []
    for sp in data or []:
        sid = sp.get("naptanId") or sp.get("id")
        if not sid or sp.get("stopType") not in (None, "NaptanMetroStation", "NaptanRailStation"):
            continue
        out.append(Station(id=sid, name=clean_name(sp.get("commonName", sid)),
                           lines=[line_name], lat=sp.get("lat"), lon=sp.get("lon")))
    return out


def merge_stations(stations: list[Station]) -> list[Station]:
    """Merge duplicates by name (one station, many lines). Prefer Underground ids."""
    merged: dict[str, Station] = {}
    for s in stations:
        key = normalise(s.name)
        if key not in merged:
            merged[key] = Station(s.id, s.name, list(s.lines), s.lat, s.lon)
            continue
        m = merged[key]
        m.lines = sorted(set(m.lines) | set(s.lines))
        if s.id.startswith("940G") and not m.id.startswith("940G"):
            m.id = s.id
    return sorted(merged.values(), key=lambda s: s.name)


def fetch_stations(client: TflClient, modes: list[str] = config.STATION_MODES) -> list[Station]:
    """Ask TfL for every line in `modes`, then every stop on each line."""
    stations: list[Station] = []
    for line in client.get_json(f"Line/Mode/{','.join(modes)}"):
        stops = client.get_json(f"Line/{line['id']}/StopPoints")
        stations += parse_line_stops(stops, line.get("name", line["id"]))
    return merge_stations(stations)


class StationDirectory:
    def __init__(self, stations: list[Station]):
        self.stations = stations
        self._by_key = {normalise(s.name): s for s in stations}

    @classmethod
    def load(cls, path: str | Path = config.STATIONS_PATH) -> "StationDirectory":
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"{p} not found. Run: python -m scripts.fetch_stations")
        return cls([Station(**s) for s in json.loads(p.read_text(encoding="utf-8"))])

    def save(self, path: str | Path = config.STATIONS_PATH) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps([asdict(s) for s in self.stations], indent=1), encoding="utf-8")

    def names(self) -> list[str]:
        return [s.name for s in self.stations]

    def find(self, query: str) -> Station | None:
        """Best match for what the user typed, or None.

        1. exact (after normalising)  2. a station name that starts with / contains
        the query (shortest wins: "victoria" -> Victoria, not Victoria Park)
        3. fuzzy match for typos ("picadilly circus").
        """
        q = normalise(query)
        if not q:
            return None
        if q in self._by_key:
            return self._by_key[q]
        starts = [k for k in self._by_key if k.startswith(q + " ")]
        contains = [k for k in self._by_key if f" {q} " in f" {k} "]
        for group in (starts, contains):
            if group:
                return self._by_key[min(group, key=len)]
        close = difflib.get_close_matches(q, self._by_key.keys(), n=1, cutoff=0.75)
        return self._by_key[close[0]] if close else None
EOF_UKT
echo "  ✓ tube/tfl/stations.py ($(wc -l < 'tube/tfl/stations.py') lines)"
mkdir -p "tube/tfl"
cat > 'tube/tfl/status.py' <<'EOF_UKT'
"""Live line status: is the line running, and if not, why."""

from __future__ import annotations

from dataclasses import dataclass

from tube.tfl.client import TflClient

GOOD_SERVICE = "Good Service"


@dataclass
class LineStatus:
    line_id: str
    name: str
    mode: str
    status: str          # e.g. "Good Service", "Minor Delays", "Part Closure"
    reason: str = ""     # TfL's explanation when there is a disruption

    @property
    def is_good(self) -> bool:
        return self.status == GOOD_SERVICE


def parse_line_status(data: list[dict]) -> list[LineStatus]:
    """Turn TfL's /Line/Mode/{modes}/Status reply into LineStatus objects.

    A line can have several statuses at once (e.g. "Part Closure" + "Minor Delays");
    they are joined so nothing is hidden. Disrupted lines come first.
    """
    out = []
    for line in data or []:
        statuses = line.get("lineStatuses") or []
        descs = list(dict.fromkeys(s.get("statusSeverityDescription", "Unknown") for s in statuses))
        reasons = list(dict.fromkeys((s.get("reason") or "").strip() for s in statuses))
        out.append(LineStatus(
            line_id=line.get("id", ""),
            name=line.get("name", "Unknown"),
            mode=line.get("modeName", ""),
            status=", ".join(descs) or "Unknown",
            reason=" ".join(r for r in reasons if r),
        ))
    out.sort(key=lambda s: (s.is_good, s.name))
    return out


def get_line_status(client: TflClient, modes: str = "tube,elizabeth-line,dlr,overground") -> list[LineStatus]:
    return parse_line_status(client.get_json(f"Line/Mode/{modes}/Status"))
EOF_UKT
echo "  ✓ tube/tfl/status.py ($(wc -l < 'tube/tfl/status.py') lines)"
echo
echo "Done: 27 files. Next: pip install -r requirements.txt && python -m pytest -q"