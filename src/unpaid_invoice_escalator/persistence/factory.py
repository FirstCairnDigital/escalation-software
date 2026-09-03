from __future__ import annotations

# First Cairn Digital
# P26003 persistence configuration seam

from typing import Any, Mapping

from unpaid_invoice_escalator.persistence.database_config import resolve_database_config
from unpaid_invoice_escalator.persistence.postgresql_store import PostgreSQLStore
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.postgresql_invoice_ledger import PostgreSQLInvoiceLedger
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger

StoreType = SQLiteStore | PostgreSQLStore
LedgerType = SQLiteInvoiceLedger | PostgreSQLInvoiceLedger


def build_store_and_ledger(
    *,
    env: Mapping[str, Any] | None = None,
    db_path: str = "data/escalator.db",
    database_url: str | None = None,
) -> tuple[StoreType, LedgerType]:
    target = resolve_database_config(env=env, db_path=db_path, database_url=database_url)
    if target.backend == "sqlite":
        store = SQLiteStore(target.sqlite_path or db_path)
        return store, SQLiteInvoiceLedger(store)
    if target.backend == "postgresql":
        store = PostgreSQLStore(target.database_url)
        store.run_migrations()
        return store, PostgreSQLInvoiceLedger(target.database_url)
    raise ValueError(f"Unsupported database backend: {target.backend}")
