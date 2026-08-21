class AppError(Exception):
    """Base class for all application-specific errors."""
    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ConfigError(AppError):
    """Raised when required configuration is missing or invalid."""


class ValidationError(AppError):
    """Raised when uploaded file/input fails validation."""


class DataLoadError(AppError):
    """Raised when a file cannot be read into a DataFrame."""


class SchemaExtractionError(AppError):
    """Raised when schema/profile extraction fails."""


class LLMError(AppError):
    """Raised when the LLM call fails or returns an unusable response."""


class LLMRateLimitError(LLMError):
    """Raised on HTTP 429 — API key hit its rate limit. Retryable."""
    retryable = True


class LLMServiceUnavailableError(LLMError):
    """Raised on HTTP 503 — provider overloaded/down. Retryable."""
    retryable = True


class LLMTimeoutError(LLMError):
    """Raised when the LLM call times out. Retryable."""
    retryable = True


class DBConnectionError(AppError):
    """Raised when a database connection cannot be established."""


class DBQueryError(AppError):
    """Raised when a SQL query fails to execute."""


class UnsupportedDBError(AppError):
    """Raised when an unsupported DB_TYPE is requested."""