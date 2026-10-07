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

# Reranking (Day 3): retrieve many candidates by vector similarity, then let a
# cross-encoder read each (question, passage) pair and keep the best few.
RERANK_MODEL = os.getenv("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
RETRIEVE_CANDIDATES = int(os.getenv("RETRIEVE_CANDIDATES", "20"))
# Day 3 result: on 32 questions reranking did not beat vector search
# (section Hit@1 0.78 vs 0.81), so it is off by default. Set USE_RERANK=true to try it.
USE_RERANK = os.getenv("USE_RERANK", "false").lower() in ("1", "true", "yes")

# LLM (Day 4). Any OpenAI-compatible API. Presets:
#   groq   -> free hosted gpt-oss-120b (needs LLM_API_KEY from console.groq.com)
#   ollama -> local model, no key (needs Ollama running; see Day 6 Docker)
#   openai -> any other OpenAI-compatible endpoint (set LLM_BASE_URL)
LLM_PRESETS = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-120b"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3.2"},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
}
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "groq").strip().lower()
_preset = LLM_PRESETS.get(LLM_PROVIDER, LLM_PRESETS["openai"])
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or _preset["base_url"]
LLM_MODEL = os.getenv("LLM_MODEL") or _preset["model"]
LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip() or ("ollama" if LLM_PROVIDER == "ollama" else "")
LLM_RPM = int(os.getenv("LLM_RPM", "0") or 0)        # client-side pacing; 0 = off
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "60"))
