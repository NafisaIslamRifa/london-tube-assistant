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
