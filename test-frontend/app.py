from __future__ import annotations

import os

import streamlit as st

from components.logs import render_service_logs_tab
from components.tabs import health_tab, overview_tab, solver_tab, translator_tab

_SERVICE_CONTAINERS = {
    "translator": "juriq-translator-service",
    "solver": "juriq-solver-service",
}


def _init_state() -> None:
    st.session_state.setdefault("last_request_id", "")
    st.session_state.setdefault("last_translator_payload", {})
    st.session_state.setdefault("last_translator_response", {})
    st.session_state.setdefault("last_solver_input", {})
    st.session_state.setdefault("last_solver_response", {})
    st.session_state.setdefault("service_log_cache", {})


st.set_page_config(page_title="Juriq Test Console", page_icon="J", layout="wide")
_init_state()

st.title("Juriq Frontend Test Console")
st.caption("Direct translator-to-solver console with readable service logs")

with st.expander("Connection Settings", expanded=False):
    translator_url = st.text_input("Translator URL", value=os.getenv("TRANSLATOR_URL", "http://localhost:8012"))
    solver_url = st.text_input("Solver URL", value=os.getenv("SOLVER_URL", "http://localhost:8010"))
    timeout = st.number_input(
        "HTTP Timeout (s)",
        min_value=1,
        max_value=180,
        value=int(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
        step=1,
    )

tabs = st.tabs(["Overview", "Translator Logs", "Solver Logs", "Health"])
with tabs[0]:
    overview_tab(translator_url, solver_url, timeout)
with tabs[1]:
    render_service_logs_tab("Translator", _SERVICE_CONTAINERS["translator"])
with tabs[2]:
    render_service_logs_tab("Solver", _SERVICE_CONTAINERS["solver"])
with tabs[3]:
    health_tab(translator_url, solver_url, timeout)
