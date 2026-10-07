"""London Tube Assistant: Streamlit UI.

    python -m streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # project root on the path

import streamlit as st  # noqa: E402

from app import services  # noqa: E402

services.copy_secrets_to_env()  # before anything reads tube.config

from app.ui import EXAMPLES, describe_step, friendly_error, line_chip  # noqa: E402

st.set_page_config(page_title="London Tube Assistant", page_icon=":material/subway:",
                   layout="centered")

st.markdown("""
<style>
  .block-container {padding-top: 2.2rem; max-width: 820px;}
  .wordmark {font-size: 2rem !important; font-weight: 700 !important; letter-spacing: -0.02em;
             margin: 0 !important; line-height: 1.2 !important;
             border-left: 6px solid #0b6e99; padding-left: 12px;}
  .tagline {color: #5f6b7a !important; margin: 0.35rem 0 0.8rem 0 !important;}
  .status-row {display:flex; justify-content:space-between; align-items:center;
               padding: 7px 2px; border-bottom: 1px solid rgba(128,128,128,0.18);}
  .status-good {color: #1b7f3b; font-weight: 600;}
  .status-bad {color: #b3261e; font-weight: 600;}
  .reason {font-size: 0.86rem; color: #5f6b7a; margin: 2px 0 6px 2px;}
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------ state
def init_state() -> None:
    if "agent" not in st.session_state:
        st.session_state.agent = services.new_agent()
        st.session_state.chat = []      # [{"role", "content", "result"?}]
        st.session_state.asked = 0


def reset_chat() -> None:
    st.session_state.agent.reset()
    st.session_state.chat = []


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.button("New conversation", icon=":material/add_comment:", use_container_width=True,
              on_click=lambda: reset_chat() if "agent" in st.session_state else None)
    show_steps = st.toggle("Show how each answer was found", value=True)
    with st.expander("About this assistant", icon=":material/info:"):
        st.markdown(
            "An unofficial portfolio project, not a TfL service.\n\n"
            "- **Live data** (status, arrivals, fares): TfL Unified API\n"
            "- **Guidance**: official tfl.gov.uk pages, searched with embeddings (Chroma)\n"
            f"- **AI model**: {services.llm_label()}\n\n"
            "Always check important journeys on tfl.gov.uk. Powered by TfL Open Data.")

st.markdown('<p class="wordmark">London Tube Assistant</p>'
            '<p class="tagline">Live line status, next trains and fares, plus answers from '
            'official TfL guidance. Unofficial project, not affiliated with TfL.</p>',
            unsafe_allow_html=True)

view = st.segmented_control("View", ["Assistant", "Line status", "Fares", "Next trains"],
                            default="Assistant", label_visibility="collapsed") or "Assistant"


# ------------------------------------------------------------------ assistant
def render_result(result) -> None:
    if result.sources:
        st.caption("Sources")
        for s in result.sources:
            st.markdown(f"- [{s['title']} – {s['section']}]({s['url']})")
    if show_steps and result.trace:
        with st.expander("How I answered", icon=":material/route:"):
            for step in result.trace:
                st.markdown(f"- {describe_step(step)}")
            st.caption(f"{result.seconds}s · {result.usage.get('input_tokens', 0)} tokens in / "
                       f"{result.usage.get('output_tokens', 0)} out")


def ask(question: str) -> None:
    limit = services.demo_limit()
    st.session_state.chat.append({"role": "user", "content": question})
    if limit and st.session_state.asked >= limit:
        st.session_state.chat.append({"role": "assistant", "content":
            f"This public demo allows {limit} questions per visitor. Thanks for trying it! "
            "You can run your own copy from the GitHub repo."})
        return
    try:
        with st.spinner("Checking TfL..."):
            result = st.session_state.agent.ask(question)
        st.session_state.asked += 1
        st.session_state.chat.append({"role": "assistant", "content": result.answer,
                                      "result": result})
    except Exception as exc:  # noqa: BLE001 - show a friendly message, keep the app alive
        st.session_state.chat.append({"role": "assistant", "content": friendly_error(exc)})


def assistant_view() -> None:
    if not st.session_state.chat:
        st.markdown("**Try asking**")
        cols = st.columns(2)
        for i, (label, q) in enumerate(EXAMPLES.items()):
            if cols[i % 2].button(label, key=f"ex{i}", use_container_width=True):
                ask(q)
                st.rerun()
    for msg in st.session_state.chat:
        with st.chat_message(msg["role"], avatar=":material/person:" if msg["role"] == "user"
                             else ":material/subway:"):
            st.markdown(msg["content"])
            if msg.get("result"):
                render_result(msg["result"])


# ------------------------------------------------------------------ live views
@st.cache_data(ttl=60, show_spinner=False)
def cached_status():
    from tube.tfl.status import get_line_status
    return get_line_status(services.get_toolbox().client)


def status_view() -> None:
    from tube.agent.tools import now_london
    c1, c2 = st.columns([3, 1])
    c1.subheader("Live line status")
    if c2.button("Refresh", icon=":material/refresh:", use_container_width=True):
        cached_status.clear()
    try:
        statuses = cached_status()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Couldn't reach TfL: {exc}")
        return
    bad = [s for s in statuses if not s.is_good]
    st.caption(f"Updated {now_london()} · " + (f"{len(bad)} line{'s' if len(bad) != 1 else ''} with problems" if bad
                                                else "Good service on all lines"))
    for s in statuses:
        cls = "status-good" if s.is_good else "status-bad"
        st.markdown(f'<div class="status-row">{line_chip(s.name)}'
                    f'<span class="{cls}">{s.status}</span></div>', unsafe_allow_html=True)
        if s.reason:
            st.markdown(f'<div class="reason">{s.reason}</div>', unsafe_allow_html=True)


def fares_view() -> None:
    from tube.tfl.fares import get_fares
    box = services.get_toolbox()
    names = box.stations.names()
    st.subheader("Single fare between two stations")
    c1, c2 = st.columns(2)
    a = c1.selectbox("From", names, index=names.index("Bank") if "Bank" in names else 0)
    b = c2.selectbox("To", names, index=names.index("Victoria") if "Victoria" in names else 1)
    if st.button("Get fare", type="primary"):
        if a == b:
            st.warning("Choose two different stations.")
            return
        try:
            fares = get_fares(box.client, box.stations.find(a).id, box.stations.find(b).id)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't reach TfL: {exc}")
            return
        if not fares:
            st.info("TfL returned no fare for this journey.")
        st.table([{"Ticket": f.ticket, "When": f.time or "Anytime", "Adult fare": f"£{f.cost:.2f}"}
                  for f in fares])
        st.caption("Live adult single fares from the TfL API.")


def arrivals_view() -> None:
    from tube.tfl.arrivals import get_arrivals
    box = services.get_toolbox()
    names = box.stations.names()
    st.subheader("Next trains")
    station = st.selectbox("Station", names,
                           index=names.index("Oxford Circus") if "Oxford Circus" in names else 0)
    st_obj = box.stations.find(station)
    line = st.selectbox("Line", ["All lines"] + st_obj.lines)
    if st.button("Show next trains", type="primary"):
        try:
            arr = get_arrivals(box.client, st_obj.id, limit=20)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Couldn't reach TfL: {exc}")
            return
        if line != "All lines":
            arr = [a for a in arr if a.line.lower() == line.lower()]
        if not arr:
            st.info("No arrival predictions right now.")
        for a in arr[:10]:
            st.markdown(f'<div class="status-row">{line_chip(a.line)} '
                        f'<span>{a.destination}</span><b>{"due" if a.minutes == 0 else f"{a.minutes} min"}</b></div>',
                        unsafe_allow_html=True)


# ------------------------------------------------------------------ page
try:
    with st.spinner("Preparing the TfL knowledge base (first start only, about a minute)..."):
        services.ensure_ready()
except Exception as exc:  # noqa: BLE001 - live tools still work without the index
    st.warning(f"The guidance search isn't available yet ({exc}). Live status, fares and "
               "next trains still work.")

try:
    init_state()
except SystemExit as exc:  # e.g. LLM_API_KEY missing
    st.error(str(exc))
    st.stop()

if view == "Assistant":
    assistant_view()
    if question := st.chat_input("Ask about the Tube, fares or how to pay"):
        ask(question)
        st.rerun()
elif view == "Line status":
    status_view()
elif view == "Fares":
    fares_view()
else:
    arrivals_view()
