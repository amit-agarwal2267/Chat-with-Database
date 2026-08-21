import os
from dotenv import load_dotenv
from app.errors.exceptions import ConfigError

load_dotenv(override=True)


class Config:
    """
    Reads from an in-memory override dict first, then environment
    variables, then defaults. UI-provided values (e.g. DB connection
    form) go into _overrides at runtime and take priority immediately,
    with nothing written to disk or .env.
    """

    def __init__(self):
        self._overrides: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._overrides[key] = value

    def clear(self, key: str | None = None) -> None:
        if key:
            self._overrides.pop(key, None)
        else:
            self._overrides.clear()

    def _get(self, key: str, default: str = "") -> str:
        if key in self._overrides:
            return self._overrides[key]
        return os.getenv(key, default)

    @property
    def ENV(self) -> str:
        return self._get("ENV", "development")

    @property
    def LOG_LEVEL(self) -> str:
        return self._get("LOG_LEVEL", "INFO").upper()

    @property
    def LLM_API_KEY(self) -> str:
        key = self._get("LLM_API_KEY")
        if not key:
            raise ConfigError("LLM_API_KEY is not set")
        return key

    @property
    def LLM_MODEL(self) -> str:
        return self._get("LLM_MODEL", "gpt-4o-mini")

    @property
    def LLM_TEMPERATURE(self) -> float:
        return float(self._get("LLM_TEMPERATURE", "0.2"))

    @property
    def LLM_BASE_URL(self) -> str:
        return self._get("LLM_BASE_URL", "")

    @property
    def DB_TYPE(self) -> str:
        return self._get("DB_TYPE", "sqlite")

    @property
    def DB_HOST(self) -> str:
        return self._get("DB_HOST", "")

    @property
    def DB_PORT(self) -> str:
        return self._get("DB_PORT", "")

    @property
    def DB_NAME(self) -> str:
        return self._get("DB_NAME", "")

    @property
    def DB_USER(self) -> str:
        return self._get("DB_USER", "")

    @property
    def DB_PASSWORD(self) -> str:
        return self._get("DB_PASSWORD", "")

    @property
    def is_db_configured(self) -> bool:
        if self.DB_TYPE == "sqlite":
            return bool(self.DB_NAME)
        return bool(self.DB_HOST and self.DB_NAME and self.DB_USER)

    @property
    def MAX_UPLOAD_SIZE_MB(self) -> int:
        return int(self._get("MAX_UPLOAD_SIZE_MB", "50"))


config = Config()