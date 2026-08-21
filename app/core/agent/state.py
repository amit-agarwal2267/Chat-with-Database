from typing import TypedDict, Literal, Optional
from langchain_core.messages import BaseMessage


class AgentState(TypedDict, total=False):
    messages: list[BaseMessage]        
    user_query: str                    
    schema: dict                       
    db_type: str
    plan_decision: Literal["answerable", "needs_clarification", "out_of_scope"]
    plan_reasoning: str
    generated_sql: Optional[str]
    query_result: Optional[list[dict]]
    query_error: Optional[str]
    final_response: str
    clarification_question: Optional[str]