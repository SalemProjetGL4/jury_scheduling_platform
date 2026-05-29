from __future__ import annotations

from adapters.translator_gateway_client import translate_via_gateway
from contracts.translator_gateway_response import TranslatorGatewayResponse
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start, mark_step_end, mark_step_start


def translator_gateway_node(state: SchedulingState) -> SchedulingState:
    node_name = "translator"
    mark_node_start(state, node_name)

    try:
        mark_step_start(state, node_name, "http_call")
        try:
            response = translate_via_gateway(
                request_id=state["request_id"],
                prompt=state["user_prompt"],
                user_id=state.get("user_id"),
            )
        finally:
            mark_step_end(state, node_name, "http_call")

        mark_step_start(state, node_name, "parse_response")
        try:
            parsed = TranslatorGatewayResponse.model_validate(response)
        finally:
            mark_step_end(state, node_name, "parse_response")

        state["db_snapshot"] = parsed.db_snapshot
        state["translator_payload"] = parsed.translator_payload
        state["recognized_constraints"] = list(parsed.recognized_constraints)
        state["unrecognized_constraints"] = list(parsed.unrecognized_constraints)

        if not state["translator_payload"]:
            add_error(state, "translator_payload_missing: translator-service returned empty payload")
            state["final_status"] = "error"
            mark_node_end(state, node_name, status="failed", summary="Missing translator payload")
            return state

        mark_node_end(state, node_name, status="success", summary="Translator-service payload accepted")
        return state

    except Exception as exc:
        add_error(state, f"translator_gateway_failed: {exc}")
        state["final_status"] = "error"
        mark_node_end(state, node_name, status="failed", summary="Translator-service call failed")
        return state
