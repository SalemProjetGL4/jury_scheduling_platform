from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

import requests
import streamlit as st


def api_call(method: str, url: str, timeout: int, payload: dict[str, Any] | None = None) -> tuple[bool, Any]:
    try:
        response = requests.request(method=method, url=url, json=payload, timeout=timeout)
        if response.headers.get("content-type", "").startswith("application/json"):
            data = response.json()
        else:
            data = {"text": response.text}
        if response.status_code >= 400:
            return False, {"status_code": response.status_code, "body": data}
        return True, data
    except requests.RequestException as exc:
        return False, {"error": str(exc)}


def render_health_card(name: str, base_url: str, timeout: int) -> None:
    ok, data = api_call("GET", f"{base_url.rstrip('/')}/health", timeout=timeout)
    with st.container(border=True):
        st.subheader(name)
        st.caption(base_url)
        if ok:
            st.success("healthy")
            st.json(data)
        else:
            st.error("unreachable")
            st.json(data)


def init_state() -> None:
    st.session_state.setdefault("last_request_id", "")
    st.session_state.setdefault("last_status", {})
    st.session_state.setdefault("last_result", {})
    st.session_state.setdefault("last_translator_payload", {})


def _format_roles(roles: dict[str, Any]) -> str:
    if not isinstance(roles, dict) or not roles:
        return "-"
    return ", ".join(f"{k}:{v}" for k, v in roles.items())


def render_status_summary(status_data: dict[str, Any]) -> None:
    final_status = str(status_data.get("final_status", "unknown"))
    current_node = status_data.get("current_node") or "idle"
    node_history = status_data.get("node_history", [])
    errors = status_data.get("errors", [])
    unrecognized = status_data.get("unrecognized_constraints", [])

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Final Status", final_status)
    with col2:
        st.metric("Current Node", str(current_node))
    with col3:
        st.metric("Steps", len(node_history))
    with col4:
        st.metric("Errors", len(errors))

    if final_status == "running":
        st.info(f"Request is running. Current step: {current_node}")
    elif final_status == "success":
        st.success("Request completed successfully")
    elif final_status == "infeasible":
        st.warning("Request completed but solver found no feasible solution")
    else:
        st.error("Request ended with errors")

    if node_history:
        timeline_rows = [
            {
                "node": row.get("node"),
                "status": row.get("status"),
                "started_at": row.get("started_at"),
                "ended_at": row.get("ended_at"),
                "summary": row.get("summary"),
            }
            for row in node_history
        ]
        st.markdown("#### Request Timeline")
        st.dataframe(timeline_rows, use_container_width=True)

    if errors:
        st.markdown("#### Errors")
        for err in errors:
            st.error(str(err))

    if unrecognized:
        st.markdown("#### Unrecognized Constraints")
        st.dataframe(unrecognized, use_container_width=True)


def render_result_summary(result_data: dict[str, Any]) -> None:
    solver_result = result_data.get("solver_result") or {}
    solver_status = str(solver_result.get("status", "unknown"))
    assignments = solver_result.get("assignments") or []
    failed_constraints = solver_result.get("failed_constraints") or []
    recognized = result_data.get("recognized_constraints") or []
    unrecognized = result_data.get("unrecognized_constraints") or []

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Route", str(result_data.get("route", "-")))
    with col2:
        st.metric("Solver Status", solver_status)
    with col3:
        st.metric("Assignments", len(assignments))
    with col4:
        st.metric("Recognized Constraints", len(recognized))

    if result_data.get("intent_summary"):
        st.caption(f"Intent: {result_data['intent_summary']}")

    if assignments:
        rows: list[dict[str, Any]] = []
        for item in assignments:
            rows.append(
                {
                    "project_id": item.get("project_id"),
                    "session_id": item.get("session_id"),
                    "date": item.get("date"),
                    "period": item.get("period"),
                    "roles": _format_roles(item.get("roles", {})),
                }
            )
        st.markdown("#### Schedule Assignments")
        st.dataframe(rows, use_container_width=True)

    if failed_constraints:
        st.markdown("#### Failed Constraints")
        st.dataframe(failed_constraints, use_container_width=True)

    if unrecognized:
        st.markdown("#### Unrecognized Constraints")
        st.dataframe(unrecognized, use_container_width=True)


def workflow_tab(orchestrator_url: str, timeout: int) -> None:
    st.markdown("### Workflow Test")
    st.caption("1) Submit a prompt  2) Track until done  3) Read state and result below")
    prompt = st.text_area(
        "Prompt",
        value="Create a jury schedule for all current projects and prefer morning sessions when possible.",
        height=120,
    )
    user_id = st.text_input("User ID", value="demo-user")

    submit_col, clear_col = st.columns([1, 1])
    with submit_col:
        if st.button("Submit Workflow", type="primary", use_container_width=True):
            payload = {"prompt": prompt, "user_id": user_id or None}
            ok, data = api_call("POST", f"{orchestrator_url.rstrip('/')}/workflows/schedule", timeout, payload)
            if ok:
                st.session_state["last_request_id"] = data.get("request_id", "")
                st.session_state["last_status"] = {}
                st.session_state["last_result"] = {}
                st.success("Workflow submitted")
                st.caption(f"Request ID: {st.session_state['last_request_id']}")
            else:
                st.error("Submission failed")
                st.json(data)

    with clear_col:
        if st.button("Clear Stored Result", use_container_width=True):
            st.session_state["last_status"] = {}
            st.session_state["last_result"] = {}
            st.session_state["last_request_id"] = ""

    request_id = st.text_input("Request ID", value=st.session_state.get("last_request_id", ""))
    st.session_state["last_request_id"] = request_id

    status_col, track_col, result_col = st.columns([1, 1, 1])
    with status_col:
        if st.button("Refresh Status", use_container_width=True) and request_id:
            ok, data = api_call(
                "GET",
                f"{orchestrator_url.rstrip('/')}/workflows/{request_id}/status",
                timeout,
            )
            if ok:
                st.session_state["last_status"] = data
            else:
                st.error("Status fetch failed")
                st.json(data)

    progress_placeholder = st.empty()

    with track_col:
        if st.button("Track Until Done", use_container_width=True):
            if not request_id:
                st.error("Enter a request ID first")
            else:
                max_polls = 60
                poll_interval_s = 1.0
                finished = False
                with st.spinner("Tracking request..."):
                    for poll_idx in range(1, max_polls + 1):
                        ok, data = api_call(
                            "GET",
                            f"{orchestrator_url.rstrip('/')}/workflows/{request_id}/status",
                            timeout,
                        )
                        if not ok:
                            progress_placeholder.error("Failed to fetch status during tracking")
                            st.json(data)
                            break

                        st.session_state["last_status"] = data
                        current_node = data.get("current_node") or "idle"
                        final_status = data.get("final_status", "running")
                        progress_placeholder.info(
                            f"Polling {poll_idx}/{max_polls} - current node: {current_node} - state: {final_status}"
                        )

                        if final_status != "running":
                            finished = True
                            break

                        time.sleep(poll_interval_s)

                if finished:
                    ok, data = api_call(
                        "GET",
                        f"{orchestrator_url.rstrip('/')}/workflows/{request_id}/result",
                        timeout,
                    )
                    if ok:
                        st.session_state["last_result"] = data
                        translator_payload = data.get("translator_payload")
                        if isinstance(translator_payload, dict):
                            st.session_state["last_translator_payload"] = translator_payload
                        progress_placeholder.success("Request finished and result loaded")
                    else:
                        progress_placeholder.warning("Request finished, but loading final result failed")
                        st.json(data)
                else:
                    progress_placeholder.warning("Tracking stopped before completion. Click Track Until Done again.")

    with result_col:
        if st.button("Load Result", use_container_width=True) and request_id:
            ok, data = api_call(
                "GET",
                f"{orchestrator_url.rstrip('/')}/workflows/{request_id}/result",
                timeout,
            )
            if ok:
                st.session_state["last_result"] = data
                translator_payload = data.get("translator_payload")
                if isinstance(translator_payload, dict):
                    st.session_state["last_translator_payload"] = translator_payload
            else:
                st.error("Result fetch failed")
                st.json(data)

    if st.session_state["last_status"]:
        st.markdown("#### Request State")
        status_data = st.session_state["last_status"]
        render_status_summary(status_data)

    if st.session_state["last_result"]:
        st.markdown("#### Request Result")
        render_result_summary(st.session_state["last_result"])


def translator_tab(translator_url: str, timeout: int) -> None:
    st.markdown("### Translator Service Test")
    prompt = st.text_area(
        "Translator Prompt",
        value="Prefer morning sessions and avoid assigning Dr. Karim in session 1.",
        key="translator_prompt",
        height=100,
    )
    req_id = st.text_input("Translator Request ID", value=str(uuid.uuid4())[:8], key="translator_req")
    user_id = st.text_input("Translator User ID", value="demo-user", key="translator_user")

    if st.button("Run Translation", use_container_width=True):
        payload = {"request_id": req_id, "prompt": prompt, "user_id": user_id or None}
        ok, data = api_call("POST", f"{translator_url.rstrip('/')}/translate", timeout, payload)
        if ok:
            st.success("Translation completed")
            st.json(data)
            translator_payload = data.get("translator_payload")
            if isinstance(translator_payload, dict):
                st.session_state["last_translator_payload"] = translator_payload
        else:
            st.error("Translation failed")
            st.json(data)


def solver_tab(solver_url: str, timeout: int) -> None:
    st.markdown("### Solver Service Test")

    default_payload = st.session_state.get("last_translator_payload") or {
        "professors": [],
        "projects": [],
        "sessions": [],
        "constraints": {
            "hard_max_juries": 2,
            "weights": {
                "workload": 10,
                "expertise": 5,
                "clustering": 3,
                "overload": 20,
                "custom": 1,
            },
            "hard": [],
            "soft": [],
        },
        "unavailabilities": [],
        "conflicts": [],
        "constraint_rules": [],
    }

    payload_text = st.text_area(
        "Solver Payload (JSON)",
        value=json.dumps(default_payload, indent=2),
        key="solver_payload",
        height=280,
    )

    if st.button("Run Solver", type="primary", use_container_width=True):
        try:
            payload = json.loads(payload_text)
        except json.JSONDecodeError as exc:
            st.error(f"Invalid JSON: {exc}")
            return

        ok, data = api_call("POST", f"{solver_url.rstrip('/')}/solve", timeout, payload)
        if ok:
            st.success("Solver response")
            st.json(data)
        else:
            st.error("Solver call failed")
            st.json(data)


def health_tab(orchestrator_url: str, translator_url: str, solver_url: str, timeout: int) -> None:
    st.markdown("### Service Health")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_health_card("Orchestrator", orchestrator_url, timeout)
    with c2:
        render_health_card("Translator", translator_url, timeout)
    with c3:
        render_health_card("Solver", solver_url, timeout)


st.set_page_config(page_title="Juriq Test Console", page_icon="J", layout="wide")
init_state()

st.title("Juriq Streamlit Test Console")
st.caption("Manual test frontend for orchestrator, translator, and solver services")

with st.expander("Connection Settings", expanded=False):
    orchestrator_url = st.text_input(
        "Orchestrator URL",
        value=os.getenv("ORCHESTRATOR_URL", "http://localhost:8011"),
    )
    translator_url = st.text_input(
        "Translator URL",
        value=os.getenv("TRANSLATOR_URL", "http://localhost:8012"),
    )
    solver_url = st.text_input(
        "Solver URL",
        value=os.getenv("SOLVER_URL", "http://localhost:8010"),
    )
    timeout = st.number_input(
        "HTTP Timeout (s)",
        min_value=1,
        max_value=180,
        value=int(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
        step=1,
    )

tabs = st.tabs(["Workflow", "Translator", "Solver", "Health"])
with tabs[0]:
    workflow_tab(orchestrator_url, timeout)
with tabs[1]:
    translator_tab(translator_url, timeout)
with tabs[2]:
    solver_tab(solver_url, timeout)
with tabs[3]:
    health_tab(orchestrator_url, translator_url, solver_url, timeout)
