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
