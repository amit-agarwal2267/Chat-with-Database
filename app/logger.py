import logging
import sys
from app.config import config

_configured = False


def setup_logging():
    global _configured
    if _configured:
        return

    level = getattr(logging, config.LOG_LEVEL, logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root.handlers.clear()
    root.addHandler(handler)

    for noisy in ("httpx", "httpcore", "urllib3", "watchdog", "watchdog.observers", "streamlit"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    if not _configured:
        setup_logging()
    return logging.getLogger(name)