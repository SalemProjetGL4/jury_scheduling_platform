from __future__ import annotations

from adapters.solver_gateway_client import solve_via_gateway
from graph.state import SchedulingState, StepEvent, add_error, mark_node_end, mark_node_start, mark_step_end, mark_step_start

# Maps timing_info keys returned by solver_runner to human-readable step names.
_SOLVER_STEP_LABELS: dict[str, str] = {
    "precheck_ms":    "precheck",
    "model_build_ms": "model_build",
    "solve_ms":       "solve",
    "extract_ms":     "extraction",
    "postprocess_ms": "postprocess",
}


def solver_node(state: SchedulingState) -> SchedulingState:
    node_name = "solver"
    mark_node_start(state, node_name)

    try:
        payload = state.get("translator_payload")
        if payload is None:
            add_error(state, "solver_input_missing: translator_payload is null")
            state["final_status"] = "error"
            mark_node_end(state, node_name, status="failed", summary="Missing translator payload")
            return state

        payload = dict(payload)
        payload["request_id"] = state["request_id"]

        mark_step_start(state, node_name, "gateway_call")
        try:
            result = solve_via_gateway(payload)
        finally:
            mark_step_end(state, node_name, "gateway_call")

        # Inject internal solver timings as synthetic step entries (no wall-clock timestamps
        # since they were measured inside the remote solver service).
        timing_info: dict = result.pop("timing_info", None) or {}
        for key, label in _SOLVER_STEP_LABELS.items():
            duration = timing_info.get(key)
            if duration is not None:
                state["step_history"].append(
                    StepEvent(agentName=node_name, stepName=label, startedAt="", endedAt="", durationMs=float(duration))
                )

        state["solver_result"] = result
        reflector_result = result.get("reflector_result")
        if reflector_result is not None:
            state["reflector_result"] = reflector_result
        state["final_status"] = "infeasible" if result.get("status") == "INFEASIBLE" else "success"
        mark_node_end(state, node_name, status="success", summary=f"Solver returned {result.get('status', 'UNKNOWN')}")
        return state

    except Exception as exc:
        add_error(state, f"solver_failed: {exc}")
        state["final_status"] = "error"
        mark_node_end(state, node_name, status="failed", summary="Solver gateway call failed")
        return state
