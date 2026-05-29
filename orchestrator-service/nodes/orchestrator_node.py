from __future__ import annotations

from adapters.llm_provider_adapter import get_provider
from adapters.prompt_registry import prompt_registry
from contracts.orchestrator_output import safe_parse_orchestrator_output
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start, mark_step_end, mark_step_start


def _fallback_route(prompt: str, has_old_result: bool) -> tuple[str, str]:
    lowered = prompt.lower()
    query_tokens = ("how many", "list", "show", "what", "which", "status")
    edit_tokens = ("edit", "update", "modify", "change", "adjust", "fix", "replace", "swap")

    if any(token in lowered for token in query_tokens) and "schedule" not in lowered:
        return "QUERY", "Fallback route: informational query"
    if has_old_result and any(token in lowered for token in edit_tokens):
        return "EDIT", "Fallback route: editing existing schedule"
    return "GENERATE", "Fallback route: generating new schedule"


def orchestrator_node(state: SchedulingState) -> SchedulingState:
    node_name = "orchestrator"
    mark_node_start(state, node_name)

    has_old_result = state.get("old_solver_result") is not None

    try:
        mark_step_start(state, node_name, "prompt_load")
        try:
            system_prompt, prompt_hash = prompt_registry.get_with_hash("orchestrator.system.txt")
        finally:
            mark_step_end(state, node_name, "prompt_load")

        context_prefix = (
            "[CONTEXT: A previous scheduling result exists. The user may want to edit it.]\n"
            if has_old_result
            else "[CONTEXT: No previous result exists. This is a fresh request.]\n"
        )
        user_message = context_prefix + state["user_prompt"]

        try:
            provider = get_provider()

            mark_step_start(state, node_name, "llm_call")
            try:
                raw_output = provider.complete(system_prompt=system_prompt, user_message=user_message)
            finally:
                mark_step_end(state, node_name, "llm_call")

            mark_step_start(state, node_name, "parse_output")
            try:
                parsed, error = safe_parse_orchestrator_output(raw_output)
            finally:
                mark_step_end(state, node_name, "parse_output")

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

            mark_step_start(state, node_name, "fallback_route")
            try:
                route, summary = _fallback_route(state["user_prompt"], has_old_result)
            finally:
                mark_step_end(state, node_name, "fallback_route")

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
