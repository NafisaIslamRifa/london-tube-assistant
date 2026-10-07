"""Turn a TfL web page into clean sections: [{heading, text}].

Pure function (HTML in, data out), so it is unit-tested without the network.
Cookie banners, navigation, footers and scripts are removed first, then the text
is grouped under the nearest heading so every chunk can cite a section.
"""

from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

NOISE_TAGS = ["script", "style", "noscript", "nav", "header", "footer", "form", "aside",
              "svg", "iframe"]
# Accordion titles are often <button>s inside a heading, or a <summary>. Keep their text.
UNWRAP_TAGS = ["button"]
NOISE_ATTR = re.compile(r"cookie|consent|banner|breadcrumb|nav|footer|share|feedback|"
                        r"skip|newsletter|search", re.I)
HEADINGS = {"h1", "h2", "h3", "h4", "summary"}
BLOCKS = {"p", "li", "td", "th", "dd", "dt", "blockquote"}
CONTAINERS = BLOCKS | HEADINGS | {"div", "section", "article", "ul", "ol", "table", "details"}


def _is_noise(tag: Tag) -> bool:
    attrs = " ".join([tag.get("id") or ""] + list(tag.get("class") or []))
    return bool(attrs and NOISE_ATTR.search(attrs))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _main_container(soup: BeautifulSoup) -> Tag:
    """<main> or role=main if present; otherwise the element with the most paragraph text."""
    main = soup.find("main") or soup.find(attrs={"role": "main"})
    if main:
        return main
    best, best_len = soup.body or soup, 0
    for div in soup.find_all(["article", "div", "section"]):
        n = sum(len(p.get_text()) for p in div.find_all("p", recursive=False))
        if n > best_len:
            best, best_len = div, n
    return best


def extract_sections(html: str) -> dict:
    """Return {"title": str, "sections": [{"heading": str, "text": str}, ...]}."""
    soup = BeautifulSoup(html, "html.parser")
    for t in soup.find_all(NOISE_TAGS):
        t.decompose()
    for t in soup.find_all(UNWRAP_TAGS):
        t.unwrap()
    for t in soup.find_all(True):
        if not t.decomposed and _is_noise(t):
            t.decompose()

    main = _main_container(soup)
    h1 = main.find("h1") or soup.find("h1")
    title = _clean(h1.get_text()) if h1 else _clean(soup.title.get_text() if soup.title else "")

    sections, heading, parts = [], "Overview", []

    def flush():
        text = _clean(" ".join(parts))
        if len(text.split()) >= 5:          # skip empty or one-word sections
            sections.append({"heading": heading, "text": text})

    for el in main.find_all(list(HEADINGS | BLOCKS | {"div"})):
        if el.name in HEADINGS:
            if el is h1 or el.find_parent(list(HEADINGS)):
                continue
            new = _clean(el.get_text(" "))
            if new:
                flush()
                heading, parts = new, []
        elif el.find_parent(list(HEADINGS)):
            continue
        elif not el.find(list(CONTAINERS)):  # leaf only, so nested text isn't counted twice
            # a <div> holding plain text (common in accordion panels) counts as a block too
            txt = _clean(el.get_text(" "))
            if txt:
                parts.append(txt if txt[-1] in ".:;!?" else txt + ".")
    flush()
    return {"title": title, "sections": sections}
