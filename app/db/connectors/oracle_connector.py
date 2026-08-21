import oracledb
from app.db.base import SQLConnector
from app.db.errors import DBConnectionError, DBQueryError
from app.config import config
from app.logger import get_logger

logger = get_logger(__name__)


class OracleConnector(SQLConnector):
    def __init__(self):
        self._conn = None

    def connect(self) -> None:
        try:
            dsn = oracledb.makedsn(config.DB_HOST, int(config.DB_PORT or 1521), service_name=config.DB_NAME)
            self._conn = oracledb.connect(user=config.DB_USER, password=config.DB_PASSWORD, dsn=dsn)
            logger.info("Connected to Oracle DB '%s' on %s", config.DB_NAME, config.DB_HOST)
        except oracledb.Error as e:
            raise DBConnectionError(f"Oracle connection failed: {e}") from e

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_query(self, sql: str, params=None) -> list[dict]:
        if not self._conn:
            raise DBConnectionError("Not connected to Oracle DB.")
        try:
            cur = self._conn.cursor()
            cur.execute(sql, params or {})
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
        except oracledb.Error as e:
            raise DBQueryError(f"Oracle query failed: {e}") from e

    def list_tables(self) -> list[str]:
        rows = self.execute_query("SELECT table_name FROM user_tables")
        return [r["TABLE_NAME"] for r in rows]

    def get_schema(self, table: str) -> list[dict]:
        return self.execute_query(
            "SELECT column_name, data_type FROM user_tab_columns WHERE table_name = :t",
            {"t": table.upper()},
        )