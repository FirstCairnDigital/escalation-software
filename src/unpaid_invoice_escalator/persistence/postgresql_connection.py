from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator, Any

try:
    import psycopg
    from psycopg import Connection
except Exception:  # pragma: no cover - runtime dependency may be absent during editable install
    psycopg = None
    Connection = Any  # type: ignore[misc,assignment]


@contextmanager
def postgresql_connection(database_url: str, *, autocommit: bool = False) -> Iterator[Connection]:
    if psycopg is None:
        raise RuntimeError("psycopg is required for PostgreSQL persistence support.")
    conn = psycopg.connect(database_url, autocommit=autocommit, connect_timeout=10)
    try:
        conn.row_factory = psycopg.rows.dict_row
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


__all__ = ["postgresql_connection"]
