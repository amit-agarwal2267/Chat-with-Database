from abc import ABC, abstractmethod


class SQLConnector(ABC):
    """Common contract every relational DB adapter must implement."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def execute_query(self, sql: str, params: tuple | dict | None = None) -> list[dict]: ...

    @abstractmethod
    def list_tables(self) -> list[str]: ...

    @abstractmethod
    def get_schema(self, table: str) -> list[dict]: ...