from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any

import requests
import streamlit as st

try:
    import docker
    from docker.errors import DockerException, NotFound
except Exception:  # pragma: no cover - optional dependency fallback
    docker = None
    DockerException = Exception
    NotFound = Exception


_SERVICE_CONTAINERS = {
    "translator": "juriq-translator-service",
    "solver": "juriq-solver-service",
}


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
    st.session_state.setdefault("last_translator_payload", {})
    st.session_state.setdefault("last_translator_response", {})
    st.session_state.setdefault("last_solver_input", {})
    st.session_state.setdefault("last_solver_response", {})
    st.session_state.setdefault("service_log_cache", {})


def _safe_service_name(container_name: str) -> str:
    return container_name.replace("juriq-", "").replace("-service", "").strip()


def _detect_log_level(message: str) -> str:
    lowered = message.lower()
    if "error" in lowered or "traceback" in lowered or "exception" in lowered:
        return "ERROR"
    if "warning" in lowered or "warn" in lowered:
        return "WARNING"
    if "debug" in lowered:
        return "DEBUG"
    return "INFO"


def _humanize_message(message: str) -> str:
    replacements = {
        "TRANSLATION REQUEST START": "Translation request started",
        "LLM SYSTEM PROMPT START": "LLM prompt starts",
        "LLM SYSTEM PROMPT END": "LLM prompt ends",
        "LLM USER MESSAGE START": "LLM user message starts",
        "LLM USER MESSAGE END": "LLM user message ends",
        "LLM RAW OUTPUT START": "LLM output starts",
        "LLM RAW OUTPUT END": "LLM output ends",
        "LLM PARSED JSON START": "Parsed LLM JSON starts",
        "LLM PARSED JSON END": "Parsed LLM JSON ends",
        "DB SNAPSHOT STATS START": "Database snapshot stats starts",
        "DB SNAPSHOT STATS END": "Database snapshot stats ends",
        "SOLVER INPUT START": "Solver full input starts",
        "SOLVER INPUT END": "Solver full input ends",
    }
    for key, replacement in replacements.items():
        if key in message:
            return replacement
    return message


def _parse_logs(raw_text: str, container_name: str) -> list[dict[str, str]]:
    timestamp_pattern = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T[^\s]+)\s+(?P<msg>.*)$")
    parsed: list[dict[str, str]] = []

    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        matched = timestamp_pattern.match(stripped)
        if matched:
            timestamp = matched.group("ts")
            message = matched.group("msg").strip()
        else:
            timestamp = "-"
            message = stripped

        parsed.append(
            {
                "time": timestamp,
                "service": _safe_service_name(container_name),
                "level": _detect_log_level(message),
                "message": _humanize_message(message),
            }
        )

    return parsed


def _load_container_logs(container_name: str) -> tuple[bool, dict[str, Any]]:
    if docker is None:
        return False, {"error": "Python Docker SDK is not available in the frontend container."}

    try:
        client = docker.from_env()
        container = client.containers.get(container_name)
        raw = container.logs(stdout=True, stderr=True, timestamps=True).decode("utf-8", errors="replace")
        entries = _parse_logs(raw, container_name)
        return True, {
            "container": container_name,
            "entries": entries,
            "raw": raw,
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    except NotFound:
        return False, {"error": f"Container {container_name} was not found. Ensure docker compose is running."}
    except DockerException as exc:
        return False, {
            "error": (
                "Could not access Docker from frontend. "
                "Mount /var/run/docker.sock into the frontend service. "
                f"Details: {exc}"
            )
        }


def render_service_logs_tab(label: str, container_name: str) -> None:
    st.markdown(f"### {label} Logs")
    st.caption("Readable service logs with severity, timestamps, and quick highlights")

    cache = st.session_state["service_log_cache"]
    refresh_key = f"refresh_{container_name}"
    should_refresh = st.button("Refresh Logs", key=refresh_key, use_container_width=True)

    if should_refresh or container_name not in cache:
        ok, data = _load_container_logs(container_name)
        cache[container_name] = {"ok": ok, "data": data}

    snapshot = cache.get(container_name, {})
    if not snapshot:
        st.info("No logs loaded yet")
        return

    if not snapshot.get("ok"):
        st.error(snapshot.get("data", {}).get("error", "Failed to load logs"))
        return

    data = snapshot["data"]
    entries = data.get("entries", [])
    st.caption(f"Last updated: {data.get('updated_at', '-')}")

    error_count = sum(1 for item in entries if item.get("level") == "ERROR")
    warning_count = sum(1 for item in entries if item.get("level") == "WARNING")
    info_count = sum(1 for item in entries if item.get("level") == "INFO")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Total Lines", len(entries))
    with c2:
        st.metric("Errors", error_count)
    with c3:
        st.metric("Warnings", warning_count)
    with c4:
        st.metric("Info", info_count)

    if not entries:
        st.info("No log lines returned for this service")
        return

    highlights = [
        item
        for item in entries
        if item.get("level") in {"ERROR", "WARNING"} or "LLM" in str(item.get("message", ""))
    ]

    if highlights:
        st.markdown("#### Highlights")
        st.dataframe(highlights[:50], use_container_width=True, hide_index=True)

    st.markdown("#### Full Log View")
    st.dataframe(entries, use_container_width=True, hide_index=True)

    with st.expander("Raw log text"):
        st.text(data.get("raw", ""))


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


def overview_tab(translator_url: str, solver_url: str, timeout: int) -> None:
    st.markdown("### Overview")
    st.caption("Direct pipeline: Translator reads DB + prompt, then Solver receives formatted JSON")
    prompt = st.text_area(
        "Prompt",
        value="Create a jury schedule for all current projects and prefer morning sessions when possible.",
        height=120,
    )
    user_id = st.text_input("User ID", value="demo-user")
    request_id = st.text_input("Request ID", value=st.session_state.get("last_request_id") or str(uuid.uuid4())[:8])

    submit_col, clear_col = st.columns([2, 1])
    with submit_col:
        if st.button("Run Translator -> Solver", type="primary", use_container_width=True):
            st.session_state["last_request_id"] = request_id
            translator_req = {"request_id": request_id, "prompt": prompt, "user_id": user_id or None}

            ok, data = api_call("POST", f"{translator_url.rstrip('/')}/translate", timeout, translator_req)
            if ok:
                st.session_state["last_translator_response"] = data
                translator_payload = data.get("translator_payload") if isinstance(data, dict) else None
                if not isinstance(translator_payload, dict):
                    st.error("Translator did not return a valid translator_payload")
                    return

                st.session_state["last_translator_payload"] = translator_payload
                st.session_state["last_solver_input"] = translator_payload

                st.success("Translator finished, now calling solver")
                solver_ok, solver_data = api_call(
                    "POST",
                    f"{solver_url.rstrip('/')}/solve",
                    timeout,
                    translator_payload,
                )
                if solver_ok:
                    st.session_state["last_solver_response"] = solver_data
                    st.success("Solver finished")
                else:
                    st.error("Solver call failed")
                    st.session_state["last_solver_response"] = {}
                    st.json(solver_data)
            else:
                st.error("Translation failed")
                st.json(data)

    with clear_col:
        if st.button("Clear Stored Result", use_container_width=True):
            st.session_state["last_translator_response"] = {}
            st.session_state["last_translator_payload"] = {}
            st.session_state["last_solver_input"] = {}
            st.session_state["last_solver_response"] = {}
            st.session_state["last_request_id"] = ""

    last_request_id = st.session_state.get("last_request_id", "")
    if last_request_id:
        st.markdown(f"**Current Request ID:** {last_request_id}")
    else:
        st.info("No direct run submitted yet")

    translator_response = st.session_state.get("last_translator_response") or {}
    solver_input = st.session_state.get("last_solver_input") or {}
    solver_response = st.session_state.get("last_solver_response") or {}

    if translator_response:
        recognized = translator_response.get("recognized_constraints", [])
        unrecognized = translator_response.get("unrecognized_constraints", [])
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Recognized Constraints", len(recognized))
        with c2:
            st.metric("Unrecognized Constraints", len(unrecognized))

        st.markdown("#### Translator Response")
        st.json(translator_response)

    if solver_input:
        st.markdown("#### Solver Input (From Translator)")
        st.json(solver_input)

    if solver_response:
        st.markdown("#### Solver Result")
        st.json(solver_response)


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


def health_tab(translator_url: str, solver_url: str, timeout: int) -> None:
    st.markdown("### Service Health")
    c1, c2 = st.columns(2)
    with c1:
        render_health_card("Translator", translator_url, timeout)
    with c2:
        render_health_card("Solver", solver_url, timeout)


st.set_page_config(page_title="Juriq Test Console", page_icon="J", layout="wide")
init_state()

st.title("Juriq Frontend Test Console")
st.caption("Direct translator-to-solver console with readable service logs")

with st.expander("Connection Settings", expanded=False):
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

tabs = st.tabs(["Overview", "Translator Logs", "Solver Logs", "Health"])
with tabs[0]:
    overview_tab(translator_url, solver_url, timeout)
with tabs[1]:
    render_service_logs_tab("Translator", _SERVICE_CONTAINERS["translator"])
with tabs[2]:
    render_service_logs_tab("Solver", _SERVICE_CONTAINERS["solver"])
with tabs[3]:
    health_tab(translator_url, solver_url, timeout)
