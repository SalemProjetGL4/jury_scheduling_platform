from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from contracts.api_models import ScheduleAcceptedResponse, ScheduleRequest, StatusResponse
from graph.graph_builder import graph
from graph.state import SchedulingState, init_state
from store.workflow_store import store

try:
    from log_setup import logger
except Exception:
    import logging
    logger = logging.getLogger("orchestrator")


router = APIRouter(prefix="/workflows", tags=["workflows"])


def _run_workflow(request_id: str) -> None:
    state = store.get(request_id)
    if state is None:
        return

    logger.info("WORKFLOW START — request_id=%s prompt=%r", request_id, (state.get("user_prompt") or "")[:120])
    result = graph.invoke(state)
    logger.info(
        "WORKFLOW END — request_id=%s final_status=%s errors=%s route=%s",
        request_id,
        result.get("final_status"),
        result.get("errors"),
        result.get("route"),
    )
    solver = result.get("solver_result") or {}
    logger.info(
        "SOLVER RESULT — status=%s solutions=%s assignments=%s failed_constraints=%s",
        solver.get("status"),
        len(solver.get("solutions") or []),
        len(solver.get("assignments") or []),
        solver.get("failed_constraints"),
    )
    store.put(result)


@router.post("/schedule", response_model=ScheduleAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
def schedule_workflow(payload: ScheduleRequest, background_tasks: BackgroundTasks):
    request_id = str(uuid4())
    state: SchedulingState = init_state(
        request_id=request_id,
        prompt=payload.prompt,
        user_id=payload.user_id,
        old_solver_result=payload.old_solver_result,
    )
    store.put(state)
    background_tasks.add_task(_run_workflow, request_id)
    return ScheduleAcceptedResponse(request_id=request_id, status="running")


@router.get("/{request_id}/status", response_model=StatusResponse)
def workflow_status(request_id: str):
    state = store.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="request_id not found")

    return StatusResponse(
        request_id=request_id,
        final_status=state["final_status"],
        current_node=state["current_node"],
        node_history=state["node_history"],
        errors=state["errors"],
        unrecognized_constraints=state["unrecognized_constraints"],
    )


@router.get("/{request_id}/result")
def workflow_result(request_id: str):
    state = store.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="request_id not found")

    if state["final_status"] == "running":
        raise HTTPException(status_code=409, detail="workflow is still running")

    return state
