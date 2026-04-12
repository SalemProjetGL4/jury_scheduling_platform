from __future__ import annotations

from adapters.solver_gateway_client import solve_via_gateway
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start


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

        result = solve_via_gateway(payload)
        state["solver_result"] = result
        state["final_status"] = "infeasible" if result.get("status") == "INFEASIBLE" else "success"
        mark_node_end(state, node_name, status="success", summary=f"Solver returned {result.get('status', 'UNKNOWN')}")
        return state

    except Exception as exc:
        add_error(state, f"solver_failed: {exc}")
        state["final_status"] = "error"
        mark_node_end(state, node_name, status="failed", summary="Solver gateway call failed")
        return state
