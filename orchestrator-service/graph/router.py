from __future__ import annotations

from graph.state import SchedulingState


def route_after_orchestrator(state: SchedulingState) -> str:
    route = state.get("route")
    if route == "SCHEDULE":
        return "SCHEDULE"
    if route == "QUERY":
        return "QUERY"
    return "ERROR"
