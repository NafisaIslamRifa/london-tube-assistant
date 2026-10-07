"""Settings, read once from environment variables (and .env when present)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()

# Transport for London Unified API. A free key raises the rate limit (500 requests/min);
# without one the API still works but is throttled harder.
TFL_BASE_URL = os.getenv("TFL_BASE_URL", "https://api.tfl.gov.uk").rstrip("/")
TFL_APP_KEY = os.getenv("TFL_APP_KEY", "").strip()
TFL_TIMEOUT = float(os.getenv("TFL_TIMEOUT", "10"))

# Modes whose stations we index for fares and arrivals.
STATION_MODES = [m.strip() for m in os.getenv("STATION_MODES", "tube,elizabeth-line").split(",")
                 if m.strip()]
STATIONS_PATH = os.getenv("STATIONS_PATH", "data/stations.json")

# Knowledge base (Day 2)
RAW_DOCS_PATH = os.getenv("RAW_DOCS_PATH", "data/raw/tfl_pages.jsonl")
CHROMA_PATH = os.getenv("CHROMA_PATH", "data/chroma")
COLLECTION = os.getenv("CHROMA_COLLECTION", "tfl_guidance")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "16"))  # small = low memory
CHUNK_MAX_WORDS = int(os.getenv("CHUNK_MAX_WORDS", "220"))
CHUNK_OVERLAP_WORDS = int(os.getenv("CHUNK_OVERLAP_WORDS", "40"))
