from __future__ import annotations

from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start


def orchestrator_node(state: SchedulingState) -> SchedulingState:
    node_name = "orchestrator"
    mark_node_start(state, node_name)

    has_old_result = state.get("old_solver_result") is not None
    requested = state.get("requested_route")

    if requested == "EDIT":
        if not has_old_result:
            add_error(state, "orchestrator_invalid_request: EDIT requested without existing solver result")
            state["route"] = "GENERATE"
            state["intent_summary"] = "Defaulted to GENERATE because no previous result exists"
        else:
            state["route"] = "EDIT"
            state["intent_summary"] = "Client requested EDIT route"
    elif requested in {"GENERATE", "QUERY"}:
        state["route"] = requested
        state["intent_summary"] = f"Client requested {requested} route"
    else:
        state["route"] = "GENERATE"
        state["intent_summary"] = "Defaulted to GENERATE (no route selected)"

    mark_node_end(state, node_name, status="success", summary=state["intent_summary"])
    return state
