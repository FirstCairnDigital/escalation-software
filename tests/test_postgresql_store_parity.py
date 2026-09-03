import inspect

from unpaid_invoice_escalator.persistence.postgresql_store import PostgreSQLStore
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


def _public_methods(cls):
    return {
        name
        for name, member in inspect.getmembers(cls, predicate=inspect.isfunction)
        if not name.startswith("_")
    }


def test_sqlite_store_public_methods_are_covered_by_postgresql_store():
    sqlite_methods = _public_methods(SQLiteStore)
    postgres_methods = _public_methods(PostgreSQLStore)

    missing = sorted(sqlite_methods - postgres_methods)
    assert not missing, f"PostgreSQLStore missing SQLite public methods: {missing}"

    for name in sorted(sqlite_methods):
        sqlite_sig = inspect.signature(getattr(SQLiteStore, name))
        pg_sig = inspect.signature(getattr(PostgreSQLStore, name))

        sqlite_params = list(sqlite_sig.parameters.keys())[1:]
        pg_params = list(pg_sig.parameters.keys())[1:]
        assert sqlite_params == pg_params, (
            f"Method {name} parameter mismatch: SQLite={sqlite_params}, PostgreSQL={pg_params}"
        )
