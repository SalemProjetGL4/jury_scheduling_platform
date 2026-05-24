from __future__ import annotations

from adapters.solver_gateway_client import solve_via_gateway
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start

_GOOD_STATUSES = {"OPTIMAL", "FEASIBLE"}


def solver_refine_node(state: SchedulingState) -> SchedulingState:
    """Re-run the solver with the refined payload.

    If the refined solve is INFEASIBLE but the original solver_result was good
    (OPTIMAL/FEASIBLE), the original result is preserved so the user still sees
    their solutions.
    """
    node_name = "solver_refine"
    mark_node_start(state, node_name)

    try:
        payload = state.get("translator_payload")
        if payload is None:
            add_error(state, "solver_refine_input_missing: translator_payload is null")
            mark_node_end(state, node_name, status="failed", summary="Missing translator payload")
            return state

        payload = dict(payload)
        payload["request_id"] = state["request_id"]
        result = solve_via_gateway(payload)

        original = state.get("solver_result")
        original_status = (original or {}).get("status", "")
        new_status = result.get("status", "")

        if new_status == "INFEASIBLE" and original_status in _GOOD_STATUSES:
            # Refined solve made things worse — keep the original good result.
            add_error(state, "solver_refine_infeasible: refined solve returned INFEASIBLE; original result preserved")
            mark_node_end(
                state,
                node_name,
                status="failed",
                summary=f"Refined solve INFEASIBLE — original {original_status} result kept",
            )
            return state

        state["solver_result"] = result
        state["final_status"] = "infeasible" if new_status == "INFEASIBLE" else "success"
        mark_node_end(
            state,
            node_name,
            status="success",
            summary=f"Refined solver returned {new_status}",
        )
        return state

    except Exception as exc:
        add_error(state, f"solver_refine_failed: {exc}")
        mark_node_end(state, node_name, status="failed", summary="Solver refine gateway call failed")
        return state
