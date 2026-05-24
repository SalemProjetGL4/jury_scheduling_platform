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


def should_run_refine(state: SchedulingState) -> str:
    """Only run the refine cycle when the reflector produced actionable suggestions."""
    reflector_result = state.get("reflector_result")
    if not reflector_result:
        return "skip"
    suggestions = reflector_result.get("relaxation_suggestions") or []
    return "refine" if suggestions else "skip"
