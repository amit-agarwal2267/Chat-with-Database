from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import config
from app.errors.exceptions import LLMError
from app.logger import get_logger

logger = get_logger(__name__)

_client: ChatNVIDIA | None = None


def get_client() -> ChatNVIDIA:
    global _client
    if _client is None:
        _client = ChatNVIDIA(
            model=config.LLM_MODEL,
            api_key=config.LLM_API_KEY,
            temperature=config.LLM_TEMPERATURE,
            base_url=config.LLM_BASE_URL or None,
        )
    return _client


def call_llm(system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> str:
    try:
        client = get_client()

        effective_system_prompt = system_prompt
        if json_mode:
            effective_system_prompt += "\n\nRespond ONLY with valid JSON. No markdown, no prose, no code fences."

        messages = [
            SystemMessage(content=effective_system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = client.invoke(messages)
        content = response.content

        if not content or not content.strip():
            raise LLMError("LLM returned an empty response.")

        return content.strip()

    except LLMError:
        raise
    except Exception as e:
        logger.exception("LLM call failed")
        raise LLMError(f"LLM call failed: {e}") from e