from __future__ import annotations

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.orchestrator_output import safe_parse_orchestrator_output
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start


def _fallback_route(prompt: str) -> tuple[str, str]:
    lowered = prompt.lower()
    query_tokens = ("how many", "list", "show", "what", "which", "status")
    if any(token in lowered for token in query_tokens) and "schedule" not in lowered:
        return "QUERY", "Fallback route: informational query"
    return "SCHEDULE", "Fallback route: scheduling workflow"


def orchestrator_node(state: SchedulingState) -> SchedulingState:
    node_name = "orchestrator"
    mark_node_start(state, node_name)

    try:
        system_prompt, prompt_hash = prompt_registry.get_with_hash("orchestrator.system.txt")
        try:
            provider = get_provider()
            raw_output = provider.complete(system_prompt=system_prompt, user_message=state["user_prompt"])

            parsed, error = safe_parse_orchestrator_output(raw_output)
            if parsed is None:
                raise ValueError(f"orchestrator_output_invalid: {error}")

            state["route"] = parsed.route
            state["intent_summary"] = parsed.intent_summary
            mark_node_end(
                state,
                node_name,
                status="success",
                summary=f"Intent classified as {parsed.route}. Prompt hash: {prompt_hash}",
            )
            return state
        except Exception as llm_exc:
            add_error(state, f"orchestrator_llm_fallback_used: {llm_exc}")
            route, summary = _fallback_route(state["user_prompt"])
            state["route"] = route
            state["intent_summary"] = summary
            mark_node_end(
                state,
                node_name,
                status="success",
                summary=f"Fallback classification as {route}. Prompt hash: {prompt_hash}",
            )
            return state

    except Exception as exc:
        add_error(state, f"orchestrator_failed: {exc}")
        state["final_status"] = "error"
        mark_node_end(state, node_name, status="failed", summary="Unhandled orchestrator failure")
        return state
