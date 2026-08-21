import pymysql
from app.db.base import SQLConnector
from app.db.errors import DBConnectionError, DBQueryError
from app.config import config
from app.logger import get_logger

logger = get_logger(__name__)


class MySQLConnector(SQLConnector):
    def __init__(self):
        self._conn = None

    def connect(self) -> None:
        try:
            self._conn = pymysql.connect(
                host=config.DB_HOST,
                port=int(config.DB_PORT or 3306),
                user=config.DB_USER,
                password=config.DB_PASSWORD,
                database=config.DB_NAME,
                cursorclass=pymysql.cursors.DictCursor,
            )
            logger.info("Connected to MySQL DB '%s' on %s", config.DB_NAME, config.DB_HOST)
        except pymysql.MySQLError as e:
            raise DBConnectionError(f"MySQL connection failed: {e}") from e

    def disconnect(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def execute_query(self, sql: str, params=None) -> list[dict]:
        if not self._conn:
            raise DBConnectionError("Not connected to MySQL DB.")
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, params or ())
                return cur.fetchall()
        except pymysql.MySQLError as e:
            raise DBQueryError(f"MySQL query failed: {e}") from e

    def list_tables(self) -> list[str]:
        rows = self.execute_query("SHOW TABLES;")
        key = f"Tables_in_{config.DB_NAME}"
        return [r[key] for r in rows]

    def get_schema(self, table: str) -> list[dict]:
        return self.execute_query(f"DESCRIBE {table};")