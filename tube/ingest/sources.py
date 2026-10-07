"""Official TfL guidance pages that make up the knowledge base.

Three pages were checked by hand (marked "verified"); the rest follow TfL's URL
pattern. `python -m tube.ingest.fetch_tfl` reports any page that fails, and
`python -m tube.ingest.find_links <url>` lists real links on a page so you can
fix or add paths.
"""

BASE = "https://tfl.gov.uk"

SOURCES = [
    # --- Paying for travel ---
    {"path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/touching-in-and-out",
     "topic": "paying"},                                                     # verified
    {"path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/capping",
     "topic": "paying"},
    {"path": "/fares/how-to-pay-and-where-to-buy-tickets-and-oyster/pay-as-you-go/contactless-and-mobile-pay-as-you-go",
     "topic": "paying"},
    {"path": "/fares/refunds-and-replacements", "topic": "paying"},

    # --- Fares and discounts ---
    {"path": "/fares/find-fares/tube-and-rail-fares", "topic": "fares"},     # verified
    {"path": "/fares/find-fares/bus-and-tram-fares", "topic": "fares"},      # verified
    {"path": "/fares/free-and-discounted-travel/children-and-young-people", "topic": "fares"},

    # --- Using the Tube ---
    {"path": "/modes/tube/night-tube", "topic": "services"},
    {"path": "/transport-accessibility/", "topic": "accessibility"},         # verified
]


def url_for(source: dict) -> str:
    return BASE + source["path"]
