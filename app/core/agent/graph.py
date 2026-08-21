from functools import partial
from langgraph.graph import StateGraph, END
from app.core.agent.state import AgentState
from app.core.agent import nodes


def build_graph(connector):
    """
    Builds a fresh graph bound to a specific DB connector instance
    (one per user session, since the connector holds a live connection).
    """
    graph = StateGraph(AgentState)

    graph.add_node("plan", nodes.plan_node)
    graph.add_node("clarify", nodes.clarify_node)
    graph.add_node("out_of_scope", nodes.out_of_scope_node)
    graph.add_node("generate_sql", nodes.generate_sql_node)
    graph.add_node("execute_sql", partial(nodes.execute_sql_node, connector=connector))
    graph.add_node("generate_response", nodes.generate_response_node)

    graph.set_entry_point("plan")

    graph.add_conditional_edges(
        "plan",
        lambda state: state["plan_decision"],
        {
            "answerable": "generate_sql",
            "needs_clarification": "clarify",
            "out_of_scope": "out_of_scope",
        },
    )

    graph.add_edge("generate_sql", "execute_sql")
    graph.add_edge("execute_sql", "generate_response")
    graph.add_edge("generate_response", END)
    graph.add_edge("clarify", END)
    graph.add_edge("out_of_scope", END)

    return graph.compile()