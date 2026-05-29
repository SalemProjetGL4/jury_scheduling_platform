from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal, Optional, TypedDict

try:
    from log_setup import logger as _logger
except Exception:
    _logger = logging.getLogger("orchestrator")


NodeStatus = Literal["running", "success", "failed"]
RouteType = Literal["GENERATE", "EDIT", "QUERY"]
FinalStatus = Literal["running", "success", "infeasible", "error"]


class NodeEvent(TypedDict):
    node: str
    started_at: str
    ended_at: Optional[str]
    status: NodeStatus
    summary: Optional[str]


class StepEvent(TypedDict):
    agentName: str
    stepName: str
    startedAt: str        # ISO string; empty for synthetic entries injected from remote services
    endedAt: Optional[str]
    durationMs: Optional[float]


class SchedulingState(TypedDict):
    request_id: str
    user_id: Optional[str]
    user_prompt: str

    route: Optional[RouteType]
    intent_summary: Optional[str]

    db_snapshot: Optional[dict[str, Any]]

    translator_payload: Optional[dict[str, Any]]
    recognized_constraints: list[dict[str, Any]]
    unrecognized_constraints: list[dict[str, Any]]

    old_solver_result: Optional[dict[str, Any]]
    solver_result: Optional[dict[str, Any]]
    updater_result: Optional[dict[str, Any]]
    reflector_result: Optional[dict[str, Any]]

    current_node: Optional[str]
    node_history: list[NodeEvent]
    step_history: list[StepEvent]
    errors: list[str]
    final_status: FinalStatus


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_state(
    *,
    request_id: str,
    prompt: str,
    user_id: str | None,
    old_solver_result: dict | None = None,
) -> SchedulingState:
    return SchedulingState(
        request_id=request_id,
        user_id=user_id,
        user_prompt=prompt,
        route=None,
        intent_summary=None,
        db_snapshot=None,
        translator_payload=None,
        recognized_constraints=[],
        unrecognized_constraints=[],
        old_solver_result=old_solver_result,
        solver_result=None,
        updater_result=None,
        reflector_result=None,
        current_node=None,
        node_history=[],
        step_history=[],
        errors=[],
        final_status="running",
    )


def mark_node_start(state: SchedulingState, node: str) -> None:
    state["current_node"] = node
    state["node_history"].append(
        NodeEvent(node=node, started_at=utc_now_iso(), ended_at=None, status="running", summary=None)
    )
    _logger.info("[%s] ▶ node START — request_id=%s", node, state.get("request_id", "?"))


def mark_node_end(state: SchedulingState, node: str, *, status: NodeStatus, summary: str | None) -> None:
    for event in reversed(state["node_history"]):
        if event["node"] == node and event["ended_at"] is None:
            event["ended_at"] = utc_now_iso()
            event["status"] = status
            event["summary"] = summary
            break

    if state["current_node"] == node:
        state["current_node"] = None

    _logger.info("[%s] ■ node END   status=%s summary=%s", node, status, summary)


def mark_step_start(state: SchedulingState, agent_name: str, step_name: str) -> None:
    state["step_history"].append(
        StepEvent(agentName=agent_name, stepName=step_name, startedAt=utc_now_iso(), endedAt=None, durationMs=None)
    )


def mark_step_end(state: SchedulingState, agent_name: str, step_name: str) -> None:
    now = utc_now_iso()
    for event in reversed(state["step_history"]):
        if event["agentName"] == agent_name and event["stepName"] == step_name and event["endedAt"] is None:
            event["endedAt"] = now
            try:
                start_ms = datetime.fromisoformat(event["startedAt"]).timestamp() * 1000
                end_ms = datetime.fromisoformat(now).timestamp() * 1000
                event["durationMs"] = round(end_ms - start_ms, 1)
            except Exception:
                pass
            break


def add_error(state: SchedulingState, message: str) -> None:
    state["errors"].append(message)
    _logger.error("[orchestrator] ERROR — %s", message)


def clone_state(state: SchedulingState) -> SchedulingState:
    return deepcopy(state)
