"""List the tfl.gov.uk links on a page, to find real paths for sources.py.

    python -m tube.ingest.find_links https://tfl.gov.uk/fares/ [--under /fares/]
"""

import argparse
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from tube.ingest.fetch_tfl import fetch_page


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--under", default="/", help="only paths starting with this")
    args = ap.parse_args()
    soup = BeautifulSoup(fetch_page(args.url), "html.parser")
    seen = set()
    for a in soup.find_all("a", href=True):
        u = urlparse(urljoin(args.url, a["href"]))
        if u.netloc.endswith("tfl.gov.uk") and u.path.startswith(args.under) and u.path not in seen:
            seen.add(u.path)
            print(f"{u.path:<90} {a.get_text(' ', strip=True)[:50]}")


if __name__ == "__main__":
    main()
