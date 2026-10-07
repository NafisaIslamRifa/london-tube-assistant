from pathlib import Path

from tube.ingest.fetch_tfl import page_record
from tube.ingest.html_extract import extract_sections
from tube.ingest.sources import SOURCES, url_for

HTML = (Path(__file__).parent / "fixtures" / "tfl_page.html").read_text()


def test_title_comes_from_page_not_cookie_banner():
    assert extract_sections(HTML)["title"] == "Touching in and out"


def test_sections_follow_headings():
    secs = extract_sections(HTML)["sections"]
    assert [s["heading"] for s in secs] == [
        "Overview", "Why touch in and touch out", "Touch pink card readers when changing trains", "Empty"]
    assert "yellow card readers" in secs[0]["text"]
    assert "Buses and trams: touch in only." in secs[1]["text"]       # list items kept
    assert "Touch in only when you board the bus" in secs[3]["text"]  # table cells kept


def test_noise_is_removed():
    text = " ".join(s["text"] for s in extract_sections(HTML)["sections"])
    for junk in ["cookies", "footer", "tracking", "Share this page", "Home"]:
        assert junk not in text


def test_page_record_shape():
    rec = page_record({"path": "/fares/x/touching-in-and-out", "topic": "paying"}, HTML)
    assert rec["doc_id"] == "fares__x__touching-in-and-out"
    assert rec["url"] == "https://tfl.gov.uk/fares/x/touching-in-and-out"
    assert rec["topic"] == "paying" and rec["sections"] and rec["fetched_at"]


def test_sources_are_unique_tfl_paths():
    paths = [s["path"] for s in SOURCES]
    assert len(paths) == len(set(paths))
    assert all(url_for(s).startswith("https://tfl.gov.uk/") for s in SOURCES)
