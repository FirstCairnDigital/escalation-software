from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from unpaid_invoice_escalator.persistence.postgresql_connection import postgresql_connection


class MigrationChecksumMismatchError(RuntimeError):
    """Raised when a migration file changes after being recorded."""


class PostgreSQLMigrationRunner:
    def __init__(self, database_url: str, *, migration_dir: str | Path | None = None) -> None:
        self.database_url = database_url
        self.migration_dir = Path(migration_dir or Path(__file__).resolve().parent)

    def _migration_files(self) -> list[Path]:
        return sorted(self.migration_dir.glob("*.sql"), key=lambda path: path.name)

    def _checksum(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def _ensure_schema_migrations(self, conn) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )

    def apply(self) -> list[str]:
        applied_versions: list[str] = []
        with postgresql_connection(self.database_url) as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_lock(hashtext('fcd_postgres_migrations'))")
                self._ensure_schema_migrations(conn)
                for migration_path in self._migration_files():
                    version = migration_path.stem
                    checksum = self._checksum(migration_path)
                    existing = conn.execute(
                        "SELECT checksum FROM schema_migrations WHERE version = %s",
                        (version,),
                    ).fetchone()
                    if existing is not None and existing["checksum"] != checksum:
                        raise MigrationChecksumMismatchError(
                            f"Migration {version} checksum mismatch detected and blocked."
                        )
                    if existing is None:
                        sql_text = migration_path.read_text(encoding="utf-8").strip()
                        if not sql_text:
                            continue
                        conn.execute(sql_text)
                        conn.execute(
                            "INSERT INTO schema_migrations (version, checksum, applied_at) VALUES (%s, %s, %s)",
                            (version, checksum, datetime.now(timezone.utc)),
                        )
                        applied_versions.append(version)
                conn.execute("SELECT pg_advisory_unlock(hashtext('fcd_postgres_migrations'))")
        return applied_versions

    def apply_migrations(self) -> list[str]:
        return self.apply()


__all__ = ["MigrationChecksumMismatchError", "PostgreSQLMigrationRunner"]
