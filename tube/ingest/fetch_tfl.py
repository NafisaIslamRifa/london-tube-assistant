"""Download the TfL guidance pages into data/raw/tfl_pages.jsonl.

    python -m tube.ingest.fetch_tfl

Pages that fail are listed at the end; fix their paths in sources.py and re-run.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from tube import config
from tube.ingest.html_extract import extract_sections
from tube.ingest.sources import SOURCES, url_for

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/126.0 Safari/537.36 london-tube-assistant (portfolio project)"),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-GB,en;q=0.9",
}


def fetch_page(url: str, session=None) -> str:
    resp = (session or requests).get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def page_record(source: dict, html: str) -> dict:
    page = extract_sections(html)
    return {
        "doc_id": source["path"].strip("/").replace("/", "__"),
        "url": url_for(source),
        "topic": source["topic"],
        "title": page["title"],
        "sections": page["sections"],
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> None:
    out = Path(config.RAW_DOCS_PATH)
    out.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    ok, failed = [], []
    with out.open("w", encoding="utf-8") as f:
        for src in SOURCES:
            url = url_for(src)
            try:
                rec = page_record(src, fetch_page(url, session))
                if not rec["sections"]:
                    raise ValueError("no text found on page")
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                words = sum(len(s["text"].split()) for s in rec["sections"])
                ok.append(src)
                print(f"  ✓ {rec['title'][:55]:<55} {len(rec['sections']):>3} sections {words:>6} words")
            except Exception as exc:
                failed.append((url, exc))
                print(f"  ✗ {url}\n      {type(exc).__name__}: {str(exc)[:120]}")
            time.sleep(1.0)  # be polite to tfl.gov.uk
    print(f"\nSaved {len(ok)}/{len(SOURCES)} pages to {out}")
    if failed:
        print("Fix or remove the failed paths in tube/ingest/sources.py "
              "(tip: python -m tube.ingest.find_links https://tfl.gov.uk/fares/)")


if __name__ == "__main__":
    main()
