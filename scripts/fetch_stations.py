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
