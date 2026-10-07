"""Shared, cached building blocks for the app. Kept in one module so tests can
replace them (e.g. with a fake agent) without touching the page code."""

from __future__ import annotations

import os

import streamlit as st


def copy_secrets_to_env() -> None:
    """On Streamlit Community Cloud settings live in st.secrets; mirror them into
    the environment so tube.config sees them (no-op locally)."""
    try:
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float, bool)):
                os.environ.setdefault(k, str(v))
    except Exception:  # noqa: BLE001 - no secrets file locally is fine
        pass


@st.cache_resource(show_spinner=False)
def get_toolbox():
    from tube.agent.tools import Toolbox
    return Toolbox()


@st.cache_resource(show_spinner=False)
def get_llm():
    from tube.agent.llm import LLM
    return LLM()  # shared: one rate limiter for all visitors


def new_agent():
    from tube.agent.agent import TubeAgent
    return TubeAgent(toolbox=get_toolbox(), llm=get_llm())


def demo_limit() -> int:
    return int(os.getenv("DEMO_MAX_QUESTIONS", "0") or 0)


def llm_label() -> str:
    from tube import config  # imported late: secrets must be in the environment first
    return f"{config.LLM_MODEL} via {config.LLM_PROVIDER}"


@st.cache_resource(show_spinner=False)
def ensure_ready() -> dict:
    """Build the station list and search index if missing (once per server)."""
    from tube.bootstrap import ensure_ready as run
    return run()
