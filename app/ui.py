"""Small pure helpers for the Streamlit app (no Streamlit imports, easy to test)."""

from __future__ import annotations

import json

# Official line colours (public TfL design data), used for the status board.
LINE_COLOURS = {
    "Bakerloo": "#B36305", "Central": "#E32017", "Circle": "#FFD300", "District": "#00782A",
    "Elizabeth line": "#6950A1", "Hammersmith & City": "#F3A9BB", "Jubilee": "#A0A5A9",
    "Metropolitan": "#9B0056", "Northern": "#000000", "Piccadilly": "#003688",
    "Victoria": "#0098D4", "Waterloo & City": "#95CDBA", "DLR": "#00A4A7",
    "Liberty": "#61686B", "Lioness": "#F8A61C", "Mildmay": "#006FE6",
    "Suffragette": "#18A95D", "Weaver": "#9B0058", "Windrush": "#DC241F",
}
DARK_TEXT_LINES = {"Circle", "Hammersmith & City", "Waterloo & City", "Lioness"}

EXAMPLES = {
    "Is the Victoria line running?": "Is the Victoria line running?",
    "Next trains at Oxford Circus": "When are the next trains at Oxford Circus?",
    "Fare: Bank to King's Cross": "How much is a single from Bank to King's Cross?",
    "Do I touch out on the bus?": "Do I need to touch out on the bus?",
    "Delay refunds": "My Tube was 20 minutes late. Can I get a refund?",
    "Night Tube": "Which lines run the Night Tube?",
}

TOOL_LABELS = {
    "search_tfl_guidance": "Searched TfL guidance",
    "get_line_status": "Checked live line status",
    "get_next_trains": "Checked live arrivals",
    "get_fare": "Looked up the live fare",
}


def line_chip(name: str) -> str:
    """HTML for a small coloured line badge."""
    bg = LINE_COLOURS.get(name, "#5f6b7a")
    fg = "#111111" if name in DARK_TEXT_LINES else "#ffffff"
    return (f'<span style="background:{bg};color:{fg};padding:2px 10px;border-radius:4px;'
            f'font-weight:600;font-size:0.9rem;white-space:nowrap">{name}</span>')


def describe_step(step: dict) -> str:
    """One readable line per tool call for the 'How I answered' panel."""
    label = TOOL_LABELS.get(step["tool"], step["tool"])
    args = step.get("args") or {}
    detail = ""
    if step["tool"] == "search_tfl_guidance":
        detail = f" for “{args.get('query', '')}”"
    elif step["tool"] == "get_line_status":
        detail = f": {args['line']}" if args.get("line") else ": all lines"
    elif step["tool"] == "get_next_trains":
        detail = f" at {args.get('station', '?')}"
    elif step["tool"] == "get_fare":
        detail = f": {args.get('from_station', '?')} → {args.get('to_station', '?')}"
    if step.get("error"):
        try:
            reason = json.loads(step.get("result", "{}")).get("error", "")
        except json.JSONDecodeError:
            reason = ""
        return f"{label}{detail} (failed{': ' + reason if reason else ''})"
    return label + detail


def friendly_error(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "RateLimitError":
        return "The free AI quota is busy right now. Please wait a minute and try again."
    if name in ("AuthenticationError", "PermissionDeniedError"):
        return "The AI service rejected the API key. Check `LLM_API_KEY`."
    if name == "NotFoundError":
        return "The AI model wasn't found. Check `LLM_MODEL`."
    if name in ("APIConnectionError", "APITimeoutError", "InternalServerError", "TimeoutError"):
        return "The AI service didn't respond. Please try again in a moment."
    if name == "FileNotFoundError":
        return f"Some data is missing on the server: {exc}"
    return f"Something went wrong ({name}). Please try again."
