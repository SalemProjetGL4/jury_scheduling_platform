from __future__ import annotations

import re
import time
from typing import Any

import streamlit as st

try:
    import docker
    from docker.errors import DockerException, NotFound
except Exception:  # pragma: no cover - optional dependency
    docker = None
    DockerException = Exception
    NotFound = Exception


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
    should_refresh = st.button("Refresh Logs", key=f"refresh_{container_name}", use_container_width=True)

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

    error_count = sum(1 for e in entries if e.get("level") == "ERROR")
    warning_count = sum(1 for e in entries if e.get("level") == "WARNING")
    info_count = sum(1 for e in entries if e.get("level") == "INFO")

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
        e for e in entries
        if e.get("level") in {"ERROR", "WARNING"} or "LLM" in str(e.get("message", ""))
    ]
    if highlights:
        st.markdown("#### Highlights")
        st.dataframe(highlights[:50], use_container_width=True, hide_index=True)

    st.markdown("#### Full Log View")
    st.dataframe(entries, use_container_width=True, hide_index=True)

    with st.expander("Raw log text"):
        st.text(data.get("raw", ""))
