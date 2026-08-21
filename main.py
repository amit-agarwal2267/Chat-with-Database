from app.logger import setup_logging, get_logger
from app.config import config
import subprocess
import sys

setup_logging()
logger = get_logger(__name__)


def main():
    logger.info("Starting app in '%s' environment (DB_TYPE=%s)", config.ENV, config.DB_TYPE)
    subprocess.run([sys.executable, "-m", "streamlit", "run", "app/ui/streamlit_app.py"])



if __name__ == "__main__":
    main()