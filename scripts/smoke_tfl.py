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
