"""Official TfL guidance pages that make up the knowledge base.

Every path here was fetched successfully from tfl.gov.uk (October 2026). If TfL moves
a page, `python -m tube.ingest.fetch_tfl` reports it and
`python -m tube.ingest.find_links <url> --under <path>` lists the real links.
"""

BASE = "https://tfl.gov.uk"

SOURCES = [
    # --- Paying for travel ---
    {"path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out",
     "topic": "paying"},
    {"path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/contactless-and-mobile-pay-as-you-go",
     "topic": "paying"},
    {"path": "/fares/refunds-and-replacements", "topic": "paying"},

    # --- Fares ---
    {"path": "/fares/find-fares/tube-and-rail-fares", "topic": "fares"},
    {"path": "/fares/find-fares/bus-and-tram-fares", "topic": "fares"},

    # --- Free and discounted travel ---
    {"path": "/fares/free-and-discounted-travel/5-10-zip-oyster-photocard", "topic": "discounts"},
    {"path": "/fares/free-and-discounted-travel/11-15-zip-oyster-photocard", "topic": "discounts"},
    {"path": "/fares/free-and-discounted-travel/18-plus-student-oyster-photocard", "topic": "discounts"},
    {"path": "/fares/free-and-discounted-travel/60-plus-oyster-photocard", "topic": "discounts"},

    # --- Using the network ---
    {"path": "/modes/tube/night-tube", "topic": "services"},
    {"path": "/transport-accessibility/", "topic": "accessibility"},
]


def url_for(source: dict) -> str:
    return BASE + source["path"]
