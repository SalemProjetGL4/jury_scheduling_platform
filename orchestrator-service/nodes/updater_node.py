from __future__ import annotations

from adapters.updater_gateway_client import update_via_gateway
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start


def updater_node(state: SchedulingState) -> SchedulingState:
    node_name = "updater"
    mark_node_start(state, node_name)

    try:
        old_result = state.get("old_solver_result")
        translator_payload = state.get("translator_payload")

        if old_result is None:
            add_error(state, "updater_input_missing: old_solver_result is null")
            state["final_status"] = "error"
            mark_node_end(state, node_name, status="failed", summary="Missing old solver result")
            return state

        if translator_payload is None:
            add_error(state, "updater_input_missing: translator_payload is null")
            state["final_status"] = "error"
            mark_node_end(state, node_name, status="failed", summary="Missing translator payload")
            return state

        result = update_via_gateway(
            request_id=state["request_id"],
            old_solver_result=old_result,
            translator_payload=translator_payload,
            db_snapshot=state.get("db_snapshot"),
        )
        state["updater_result"] = result
        state["final_status"] = "success"
        mark_node_end(state, node_name, status="success", summary="Updater applied changes to existing schedule")
        return state

    except Exception as exc:
        add_error(state, f"updater_failed: {exc}")
        state["final_status"] = "error"
        mark_node_end(state, node_name, status="failed", summary="Updater gateway call failed")
        return state
