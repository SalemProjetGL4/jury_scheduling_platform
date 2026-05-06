from __future__ import annotations

from langgraph.graph import END, StateGraph

from graph.router import route_after_orchestrator
from graph.state import SchedulingState
from nodes.orchestrator_node import orchestrator_node
from nodes.reflector_node import reflector_node
from nodes.solver_node import solver_node
from nodes.translator_gateway_node import translator_gateway_node
from nodes.translator_refine_node import translator_refine_node
from nodes.updater_node import updater_node


def build_graph():
    builder = StateGraph(SchedulingState)

    builder.add_node("translator", translator_gateway_node)
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("solver", solver_node)
    builder.add_node("reflector", reflector_node)
    builder.add_node("translator_refine", translator_refine_node)
    builder.add_node("solver_refine", solver_node)
    builder.add_node("updater", updater_node)

    builder.set_entry_point("translator")

    builder.add_edge("translator", "orchestrator")

    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "GENERATE": "solver",
            "EDIT": "updater",
            "QUERY": END,
            "ERROR": END,
        },
    )

    # generate path: solver → reflector → translator_refine → solver_refine → END
    builder.add_edge("solver", "reflector")
    builder.add_edge("reflector", "translator_refine")
    builder.add_edge("translator_refine", "solver_refine")
    builder.add_edge("solver_refine", END)

    # edit path
    builder.add_edge("updater", END)

    return builder.compile()


graph = build_graph()
