import time
import httpx
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import config
from app.errors.exceptions import (
    LLMError, LLMRateLimitError, LLMServiceUnavailableError, LLMTimeoutError
)
from app.logger import get_logger

logger = get_logger(__name__)

_client: ChatNVIDIA | None = None

MAX_AUTO_RETRIES = 2          
BACKOFF_SECONDS = [1, 3]      


def get_client() -> ChatNVIDIA:
    global _client
    if _client is None:
        logger.debug("Initializing ChatNVIDIA client with model=%s", config.LLM_MODEL)
        _client = ChatNVIDIA(
            model=config.LLM_MODEL,
            api_key=config.LLM_API_KEY,
            temperature=config.LLM_TEMPERATURE,
            base_url=config.LLM_BASE_URL or None,
        )
    return _client


def _classify_http_error(e: Exception) -> LLMError:
    """Map underlying HTTP/status errors to specific, retryable exception types."""
    status_code = None

    if isinstance(e, httpx.HTTPStatusError):
        status_code = e.response.status_code
    else:
        status_code = getattr(e, "status_code", None)

    if status_code == 429:
        return LLMRateLimitError(
            "You've hit the API rate limit for your current plan. Please wait a moment and retry."
        )
    if status_code == 503:
        return LLMServiceUnavailableError(
            "The LLM service is temporarily overloaded or unavailable. Please retry shortly."
        )
    if isinstance(e, (httpx.TimeoutException, TimeoutError)):
        return LLMTimeoutError("The request to the LLM timed out. Please retry.")

    return LLMError(f"LLM call failed: {e}")


def call_llm(system_prompt: str, user_prompt: str, *, json_mode: bool = False) -> str:
    effective_system_prompt = system_prompt
    if json_mode:
        effective_system_prompt += "\n\nRespond ONLY with valid JSON. No markdown, no prose, no code fences."

    messages = [
        SystemMessage(content=effective_system_prompt),
        HumanMessage(content=user_prompt),
    ]

    logger.debug("LLM request | system_prompt_len=%d user_prompt_len=%d json_mode=%s",
                 len(effective_system_prompt), len(user_prompt), json_mode)

    last_error: LLMError | None = None

    for attempt in range(MAX_AUTO_RETRIES + 1):
        try:
            client = get_client()
            response = client.invoke(messages)
            content = response.content

            if not content or not content.strip():
                raise LLMError("LLM returned an empty response.")

            logger.info("LLM call succeeded (attempt %d/%d)", attempt + 1, MAX_AUTO_RETRIES + 1)
            logger.debug("LLM response: %s", content[:500])
            return content.strip()

        except LLMError:
            raise 
        except Exception as e:
            classified = _classify_http_error(e)
            last_error = classified

            if getattr(classified, "retryable", False) and attempt < MAX_AUTO_RETRIES:
                delay = BACKOFF_SECONDS[min(attempt, len(BACKOFF_SECONDS) - 1)]
                logger.warning(
                    "LLM call failed with retryable error (%s) — retrying in %ds (attempt %d/%d)",
                    type(classified).__name__, delay, attempt + 1, MAX_AUTO_RETRIES,
                )
                time.sleep(delay)
                continue

            if getattr(classified, "retryable", False):
                logger.error("LLM call failed after %d retries: %s", MAX_AUTO_RETRIES, classified.message)
            else:
                logger.critical("Unrecoverable LLM error: %s", classified.message, exc_info=True)

            raise classified from e

    raise last_error or LLMError("LLM call failed for an unknown reason.")