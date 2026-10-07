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
    def search_tfl_guidance(self, query: str, **_ignored) -> str:
        # No topic filter: in the agent evaluation the model sometimes picked the wrong
        # topic (refunds are filed under "paying"), missed the right page and answered
        # from memory. Unfiltered search already ranks the right section in the top 3
        # for 97% of the retrieval test questions.
        hits = self.search_fn(query, k=4)
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
