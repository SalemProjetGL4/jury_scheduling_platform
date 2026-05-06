from __future__ import annotations

from graph.state import SchedulingState


def route_after_orchestrator(state: SchedulingState) -> str:
    route = state.get("route")
    if route == "GENERATE":
        return "GENERATE"
    if route == "EDIT":
        return "EDIT"
    if route == "QUERY":
        return "QUERY"
    return "ERROR"
