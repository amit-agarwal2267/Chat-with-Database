from app.config import config
from app.logger import get_logger

logger = get_logger(__name__)


def liveness_check() -> dict:
    return {"status": "ok", "check": "liveness"}


def readiness_check() -> dict:
    checks = {}

    try:
        _ = config.LLM_API_KEY
        checks["llm_config"] = {"status": "ok"}
    except Exception as e:
        checks["llm_config"] = {"status": "error", "detail": str(e)}

    if not config.is_db_configured:
        checks["database"] = {"status": "not_configured"}
    else:
        try:
            from app.db.connector_factory import get_connector
            connector = get_connector(config.DB_TYPE)
            connector.connect()
            connector.disconnect()
            checks["database"] = {"status": "ok"}
        except Exception as e:
            logger.warning("Readiness DB check failed: %s", e)
            checks["database"] = {"status": "error", "detail": str(e)}

    overall = "ok" if all(c["status"] == "ok" for c in checks.values()) else (
        "not_ready" if any(c["status"] == "error" for c in checks.values()) else "partial"
    )

    return {"status": overall, "check": "readiness", "details": checks}