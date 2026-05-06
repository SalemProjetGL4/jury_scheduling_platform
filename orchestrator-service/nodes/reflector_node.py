from __future__ import annotations

from adapters.reflector_gateway_client import reflect_via_gateway
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start


def reflector_node(state: SchedulingState) -> SchedulingState:
    node_name = "reflector"
    mark_node_start(state, node_name)

    try:
        solver_result = state.get("solver_result")
        if solver_result is None:
            add_error(state, "reflector_input_missing: solver_result is null")
            state["final_status"] = "error"
            mark_node_end(state, node_name, status="failed", summary="Missing solver result")
            return state

        result = reflect_via_gateway(
            request_id=state["request_id"],
            solver_result=solver_result,
            solver_payload=state.get("translator_payload"),
            db_snapshot=state.get("db_snapshot"),
        )
        state["reflector_result"] = result
        mark_node_end(
            state,
            node_name,
            status="success",
            summary=f"Reflector returned status={result.get('status', 'UNKNOWN')}",
        )
        return state

    except Exception as exc:
        add_error(state, f"reflector_failed: {exc}")
        mark_node_end(state, node_name, status="failed", summary="Reflector gateway call failed")
        return state
