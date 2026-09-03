from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Any

from unpaid_invoice_escalator.persistence.migrations.postgresql.postgresql_migrations import PostgreSQLMigrationRunner
from unpaid_invoice_escalator.persistence.postgresql_connection import postgresql_connection


class PostgreSQLStore:
    def __init__(self, database_url: str, *, migration_dir: str | Path | None = None) -> None:
        self.database_url = database_url
        self.migration_dir = Path(migration_dir) if migration_dir else Path(__file__).resolve().parent / "migrations" / "postgresql"

    def run_migrations(self) -> list[str]:
        runner = PostgreSQLMigrationRunner(self.database_url, migration_dir=self.migration_dir)
        return runner.apply()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        with postgresql_connection(self.database_url) as conn:
            yield conn


__all__ = ["PostgreSQLStore"]
