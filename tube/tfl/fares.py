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
