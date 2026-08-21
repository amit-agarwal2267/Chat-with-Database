import json
from app.core.agent.state import AgentState
from app.core.agent.llm import call_llm
from app.core.agent import prompts
from app.errors.exceptions import LLMError, DBQueryError
from app.logger import get_logger

logger = get_logger(__name__)

FORBIDDEN_KEYWORDS = ("insert", "update", "delete", "drop", "alter", "truncate", "create")


def _extract_json(raw: str) -> str:
    """
    NIM models sometimes wrap JSON in prose or code fences despite instructions —
    strip fences and slice out the outermost {...} block defensively.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").removeprefix("json").strip()

    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]
    return raw


def plan_node(state: AgentState) -> AgentState:
    schema_str = json.dumps(state["schema"], indent=2)
    history_str = _format_history(state.get("messages", []))

    raw = call_llm(
        system_prompt=prompts.PLANNER_SYSTEM_PROMPT.format(schema=schema_str, history=history_str),
        user_prompt=state["user_query"],
        json_mode=True,
    )

    cleaned = _extract_json(raw)

    try:
        parsed = json.loads(cleaned)
        decision = parsed["decision"]
        reasoning = parsed.get("reasoning", "")
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("Planner returned unparseable output: %s", raw)
        raise LLMError("Planner failed to produce a valid decision.") from e

    if decision not in ("answerable", "needs_clarification", "out_of_scope"):
        decision = "needs_clarification"

    logger.info("Plan decision: %s | reasoning: %s", decision, reasoning)
    return {**state, "plan_decision": decision, "plan_reasoning": reasoning}


def clarify_node(state: AgentState) -> AgentState:
    schema_str = json.dumps(state["schema"], indent=2)
    history_str = _format_history(state.get("messages", []))

    question = call_llm(
        system_prompt="You write concise clarifying questions, aware of prior conversation.",
        user_prompt=prompts.CLARIFICATION_PROMPT.format(
            schema=schema_str, history=history_str, user_query=state["user_query"]
        ),
    )
    return {**state, "clarification_question": question, "final_response": question}


def out_of_scope_node(state: AgentState) -> AgentState:
    schema_str = json.dumps(state["schema"], indent=2)
    response = call_llm(
        system_prompt="You explain data limitations clearly and briefly.",
        user_prompt=prompts.OUT_OF_SCOPE_PROMPT.format(
            schema=schema_str, user_query=state["user_query"]
        ),
    )
    return {**state, "final_response": response}


def generate_sql_node(state: AgentState) -> AgentState:
    schema_str = json.dumps(state["schema"], indent=2)
    history_str = _format_history(state.get("messages", []))

    sql = call_llm(
        system_prompt="You write precise, safe, read-only SQL queries.",
        user_prompt=prompts.SQL_GENERATION_PROMPT.format(
            dialect=state["db_type"],
            schema=schema_str,
            history=history_str,
            user_query=state["user_query"],
        ),
    )
    sql = sql.strip().strip("`").removeprefix("sql").strip()

    lowered = sql.lower()
    if any(kw in lowered for kw in FORBIDDEN_KEYWORDS):
        raise DBQueryError("Generated query attempted a non-read-only operation and was blocked.")

    logger.info("Generated SQL: %s", sql)
    return {**state, "generated_sql": sql}


def execute_sql_node(state: AgentState, connector) -> AgentState:
    try:
        results = connector.execute_query(state["generated_sql"])
        return {**state, "query_result": results, "query_error": None}
    except DBQueryError as e:
        logger.warning("Query execution failed: %s", e.message)
        return {**state, "query_result": None, "query_error": e.message}


def generate_response_node(state: AgentState) -> AgentState:
    if state.get("query_error"):
        response = (
            f"I tried to run that query but it failed: {state['query_error']}. "
            "Could you rephrase your question?"
        )
        return {**state, "final_response": response}

    result_str = json.dumps(state["query_result"], indent=2, default=str)
    response = call_llm(
        system_prompt="You explain data results clearly in plain language.",
        user_prompt=prompts.RESPONSE_SYNTHESIS_PROMPT.format(
            user_query=state["user_query"], query_result=result_str
        ),
    )
    return {**state, "final_response": response}


def _format_history(messages: list) -> str:
    if not messages:
        return "(no prior conversation)"
    lines = []
    for m in messages[-10:]: 
        role = "User" if m.type == "human" else "Assistant"
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)