"""Checks that run in code after every answer (not just instructions in the prompt).

Invented links: every URL in the answer must have appeared in a tool result (or be
the TfL home page). Anything else is flagged and a warning is added for the user.
"""

from __future__ import annotations

import re

# Stops at brackets and quotes, including the 【】 that some models wrap citations in
URL_RE = re.compile(r"https?://[^\s)\]>\"'【】「」<（）]+")
ALWAYS_ALLOWED = {"https://tfl.gov.uk", "https://tfl.gov.uk/"}
WARNING = ("\n\n> ⚠️ Some links above could not be checked against the TfL pages this "
           "assistant searched. Please check them on tfl.gov.uk.")


def extract_urls(text: str) -> set[str]:
    return {u.rstrip(".,;:。、") for u in URL_RE.findall(text or "")}


def check_answer(answer: str, allowed_urls: set[str]) -> dict:
    cited = extract_urls(answer)
    allowed = {u.rstrip("/") for u in allowed_urls | ALWAYS_ALLOWED}
    unsupported = sorted(u for u in cited if u.rstrip("/") not in allowed)
    if unsupported:
        answer += WARNING
    return {"answer": answer, "report": {"cited_urls": sorted(cited),
                                         "unsupported_urls": unsupported}}
