from app.db.base import SQLConnector
from app.db.connectors.sqlite_connector import SQLiteConnector
from app.db.connectors.mysql_connector import MySQLConnector
from app.db.connectors.oracle_connector import OracleConnector
from app.db.errors import UnsupportedDBError

_SUPPORTED = {
    "sqlite": SQLiteConnector,
    "mysql": MySQLConnector,
    "oracle": OracleConnector,
}


def get_connector(db_type: str) -> SQLConnector:
    db_type = db_type.lower().strip()
    connector_cls = _SUPPORTED.get(db_type)
    if not connector_cls:
        raise UnsupportedDBError(
            f"Unsupported database type '{db_type}'. Supported: {list(_SUPPORTED)}"
        )
    return connector_cls()