from __future__ import annotations

from langgraph.graph import END, StateGraph

from graph.router import route_after_orchestrator
from graph.state import SchedulingState
from nodes.orchestrator_node import orchestrator_node
from nodes.solver_node import solver_node
from nodes.translator_gateway_node import translator_gateway_node


def build_graph():
    builder = StateGraph(SchedulingState)

    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("translator", translator_gateway_node)
    builder.add_node("solver", solver_node)

    builder.set_entry_point("orchestrator")

    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "SCHEDULE": "translator",
            "QUERY": END,
            "ERROR": END,
        },
    )

    builder.add_edge("translator", "solver")
    builder.add_edge("solver", END)

    return builder.compile()


graph = build_graph()
