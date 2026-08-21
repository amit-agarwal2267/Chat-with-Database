import functools
from app.logger import get_logger
from app.errors.exceptions import AppError

logger = get_logger(__name__)


def handle_errors(default_message: str = "Something went wrong. Please try again."):
    """
    Decorator for UI-facing functions. Logs the real exception,
    re-raises AppError subclasses as-is (caller/UI shows .message),
    and wraps unexpected exceptions into a generic AppError so raw
    tracebacks never reach the user.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except AppError as e:
                logger.error("%s: %s | details=%s", type(e).__name__, e.message, e.details)
                raise
            except Exception as e:
                logger.exception("Unhandled exception in %s", func.__name__)
                raise AppError(default_message) from e
        return wrapper
    return decorator