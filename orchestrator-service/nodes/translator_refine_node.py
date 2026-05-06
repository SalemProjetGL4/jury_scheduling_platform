from __future__ import annotations

import json

from adapters.translator_gateway_client import translate_via_gateway
from contracts.translator_gateway_response import TranslatorGatewayResponse
from graph.state import SchedulingState, add_error, mark_node_end, mark_node_start


def translator_refine_node(state: SchedulingState) -> SchedulingState:
    node_name = "translator_refine"
    mark_node_start(state, node_name)

    try:
        reflector_result = state.get("reflector_result")
        suggestions = reflector_result.get("relaxation_suggestions", []) if reflector_result else []

        enriched_prompt = state["user_prompt"]
        if suggestions:
            enriched_prompt += (
                "\n\n[Refinement hints from analysis — apply these relaxations to the schedule constraints:\n"
                + json.dumps(suggestions, indent=2)
                + "\n]"
            )

        response = translate_via_gateway(
            request_id=state["request_id"],
            prompt=enriched_prompt,
            user_id=state.get("user_id"),
        )
        parsed = TranslatorGatewayResponse.model_validate(response)

        state["translator_payload"] = parsed.translator_payload
        state["recognized_constraints"] = list(parsed.recognized_constraints)
        state["unrecognized_constraints"] = list(parsed.unrecognized_constraints)

        if not state["translator_payload"]:
            add_error(state, "translator_refine_payload_missing: empty payload returned")
            mark_node_end(state, node_name, status="failed", summary="Empty refined translator payload")
            return state

        mark_node_end(
            state,
            node_name,
            status="success",
            summary=f"Translator refined payload with {len(suggestions)} suggestion(s)",
        )
        return state

    except Exception as exc:
        add_error(state, f"translator_refine_failed: {exc}")
        mark_node_end(state, node_name, status="failed", summary="Translator refine call failed")
        return state
