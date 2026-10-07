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
