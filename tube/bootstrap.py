"""Make sure everything the app needs exists before it serves anyone.

    python -m tube.bootstrap

Used by the Docker container on start and by the web app on its first load
(Streamlit Community Cloud). Steps, each skipped when already done:
1. data/stations.json (committed to git; rebuilt from the TfL API only if missing)
2. TfL guidance pages -> data/raw/tfl_pages.jsonl
3. the Chroma index    -> data/chroma
"""

from __future__ import annotations

import os
from pathlib import Path

from tube import config


def index_count(collection=None) -> int:
    from tube.rag.store import get_collection
    try:
        return (collection or get_collection()).count()
    except Exception:  # noqa: BLE001 - a missing/corrupt index counts as empty
        return 0


def ensure_ready(log=print, fetch_stations=None, fetch_pages=None, build=None,
                 count=index_count) -> dict:
    if os.getenv("SKIP_BOOTSTRAP", "").lower() in ("1", "true", "yes"):
        return {"skipped": True}
    report = {}
    force = os.getenv("FORCE_REINDEX", "").lower() in ("1", "true", "yes")

    if Path(config.STATIONS_PATH).exists():
        report["stations"] = "present"
    else:
        log("Station list missing: fetching it from the TfL API...")
        if fetch_stations is None:
            from tube.tfl.client import TflClient
            from tube.tfl.stations import StationDirectory, fetch_stations as fetch_list

            def fetch_stations():
                StationDirectory(fetch_list(TflClient())).save()
        fetch_stations()
        report["stations"] = "fetched"

    n = count()
    if n > 0 and not force:
        log(f"Knowledge base ready: {n} chunks.")
        report["index"] = "present"
        return report

    if force or not Path(config.RAW_DOCS_PATH).exists():
        log("Downloading TfL guidance pages...")
        if fetch_pages is None:
            from tube.ingest.fetch_tfl import fetch_all as fetch_pages
        saved, _ = fetch_pages(log=log)
        if saved == 0:
            raise RuntimeError("Could not download any TfL guidance pages.")
    log("Building the search index (first run downloads a ~70 MB model)...")
    if build is None:
        from tube.rag.build_index import build_index as build
    build()
    report["index"] = "built"
    return report


if __name__ == "__main__":
    print(ensure_ready())
