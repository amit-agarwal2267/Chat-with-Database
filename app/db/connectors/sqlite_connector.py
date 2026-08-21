import sqlite3
from app.db.base import SQLConnector
from app.db.errors import DBConnectionError, DBQueryError
from app.config import config
from app.logger import get_logger

logger = get_logger(__name__)


class SQLiteConnector(SQLConnector):
    def __init__(self):
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        try:
            self._conn = sqlite3.connect(config.DB_NAME, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            logger.info("Connected to SQLite DB '%s'", config.DB_NAME)
        except sqlite3.Error as e:
            raise DBConnectionError(f"SQLite connection failed: {e}") from e

    def disconnect(self) -> None:
        if self._conn:
            try:
                self._conn.close()
                logger.info("Disconnected from SQLite DB '%s'", config.DB_NAME)
            except sqlite3.Error as e:
                logger.warning("Error closing SQLite connection: %s", e)
            finally:
                self._conn = None
        else:
            logger.debug("disconnect() called with no active connection")

    def execute_query(self, sql: str, params=None) -> list[dict]:
        if not self._conn:
            raise DBConnectionError("Not connected to SQLite DB.")
        try:
            cur = self._conn.execute(sql, params or ())
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        except sqlite3.Error as e:
            raise DBQueryError(f"SQLite query failed: {e}") from e

    def list_tables(self) -> list[str]:
        rows = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        )
        return [r["name"] for r in rows]

    def get_schema(self, table: str) -> list[dict]:
        return self.execute_query(f"PRAGMA table_info({table});")