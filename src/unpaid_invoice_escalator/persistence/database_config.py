from __future__ import annotations

# First Cairn Digital
# P26003 persistence configuration seam

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse


VALID_POSTGRES_TLS_MODES = {"require", "verify-ca", "verify-full"}


@dataclass(frozen=True)
class DatabaseConfig:
    backend: str
    database_url: str
    sqlite_path: str | None = None
    configured: bool = False
    source: str = "db_path"
    tls_required: bool = False
    tls_enabled: bool = False

    @property
    def safe_metadata(self) -> dict[str, Any]:
        return {
            "database_backend": self.backend,
            "database_configured": self.configured,
            "database_source": self.source,
            "database_tls_required": self.tls_required,
            "database_tls_enabled": self.tls_enabled,
        }


def _is_postgresql_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"postgres", "postgresql"}


def _is_sqlite_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"sqlite", "sqlite3"}


def _normalise_sqlite_path(raw_path: str) -> str:
    if not raw_path:
        return raw_path
    candidate = raw_path.strip()
    if candidate.startswith("/"):
        return candidate
    if candidate.startswith("./"):
        return candidate[2:]
    return candidate


def _sqlite_path_from_url(value: str) -> str:
    parsed = urlparse(value)
    path = parsed.path or ""
    if parsed.netloc and not path:
        path = parsed.netloc
    if parsed.query:
        path = f"{path}?{parsed.query}"
    return _normalise_sqlite_path(path)


def _postgres_tls_status(value: str) -> tuple[bool, bool]:
    parsed = urlparse(value)
    query = parsed.query.lower()
    sslmode = None
    for part in query.split("&"):
        if not part:
            continue
        key, separator, item = part.partition("=")
        if separator and key.strip() == "sslmode":
            sslmode = item.strip().lower()
            break
    if sslmode is None:
        sslmode = "disable"
    tls_required = sslmode in VALID_POSTGRES_TLS_MODES
    tls_enabled = tls_required
    return tls_required, tls_enabled


def _resolve_database_url(
    *,
    env: Mapping[str, Any] | None = None,
    explicit_database_url: str | None = None,
    db_path: str,
) -> tuple[str, str]:
    if explicit_database_url is not None and str(explicit_database_url).strip():
        return str(explicit_database_url).strip(), "explicit_database_url"
    effective_env = dict(env or {})
    configured = effective_env.get("DATABASE_URL")
    if configured is not None and str(configured).strip():
        return str(configured).strip(), "configured_database_url"
    return str(db_path).strip(), "db_path"


def resolve_database_config(
    env: Mapping[str, Any] | None = None,
    *,
    db_path: str = "data/escalator.db",
    database_url: str | None = None,
) -> DatabaseConfig:
    raw_database_url, source = _resolve_database_url(env=env, explicit_database_url=database_url, db_path=db_path)
    candidate = raw_database_url.strip()
    if not candidate:
        raise ValueError("Database configuration is empty.")

    if _is_sqlite_url(candidate):
        sqlite_path = _sqlite_path_from_url(candidate)
        return DatabaseConfig(
            backend="sqlite",
            database_url=candidate,
            sqlite_path=sqlite_path,
            configured=source != "db_path",
            source=source,
            tls_required=False,
            tls_enabled=False,
        )

    if _is_postgresql_url(candidate):
        tls_required, tls_enabled = _postgres_tls_status(candidate)
        return DatabaseConfig(
            backend="postgresql",
            database_url=candidate,
            sqlite_path=None,
            configured=source != "db_path",
            source=source,
            tls_required=tls_required,
            tls_enabled=tls_enabled,
        )

    if "//" in candidate and not candidate.startswith(("sqlite://", "sqlite3://", "postgres://", "postgresql://")):
        raise ValueError(f"Unsupported database scheme in DATABASE_URL: {candidate.split('://', 1)[0]}")

    if candidate.startswith("data/") or candidate.startswith("./") or candidate.endswith(".db"):
        return DatabaseConfig(
            backend="sqlite",
            database_url=candidate,
            sqlite_path=candidate,
            configured=source != "db_path",
            source=source,
            tls_required=False,
            tls_enabled=False,
        )

    raise ValueError(f"Unsupported database scheme in DATABASE_URL: {candidate.split('://', 1)[0] if '://' in candidate else 'unknown'}")
