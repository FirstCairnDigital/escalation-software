from __future__ import annotations

import os
from typing import Any, Mapping


def _is_ssl_url(value: str) -> bool:
    lowered = value.lower()
    return "sslmode=require" in lowered or "ssl=true" in lowered or "ssl=1" in lowered or "?sslmode=verify-full" in lowered


def validate_production_config(env: Mapping[str, Any] | None = None) -> dict[str, Any]:
    effective_env = dict(env or os.environ)
    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    db_url = str(effective_env.get("DATABASE_URL", "") or "").strip()
    if not db_url:
        errors.append("DATABASE_URL is required in production.")
        record("database-url", False, "DATABASE_URL missing.")
    elif not _is_ssl_url(db_url):
        errors.append("DATABASE_URL must enforce TLS/SSL (for example: sslmode=require).")
        record("database-url", False, "DATABASE_URL is not configured with TLS/SSL.")
    else:
        record("database-url", True, "DATABASE_URL is configured with TLS/SSL.")

    sbc_api_key = str(effective_env.get("SBC_API_KEY", "") or "").strip()
    if not sbc_api_key:
        errors.append("SBC_API_KEY is required in production.")
        record("sbc-api-key", False, "SBC_API_KEY missing.")
    else:
        record("sbc-api-key", True, "SBC_API_KEY is configured.")

    sbc_endpoint = str(effective_env.get("SBC_ENDPOINT", "") or "").strip()
    if not sbc_endpoint:
        errors.append("SBC_ENDPOINT is required in production.")
        record("sbc-endpoint", False, "SBC_ENDPOINT missing.")
    elif not sbc_endpoint.startswith(("http://", "https://")):
        errors.append("SBC_ENDPOINT must be a valid HTTP(S) URL.")
        record("sbc-endpoint", False, "SBC_ENDPOINT is not a valid URL.")
    else:
        record("sbc-endpoint", True, "SBC_ENDPOINT is configured.")

    signing_key = str(effective_env.get("CRYPTO_SIGNING_KEY", "") or "").strip()
    if not signing_key:
        errors.append("CRYPTO_SIGNING_KEY is required in production.")
        record("crypto-signing-key", False, "CRYPTO_SIGNING_KEY missing.")
    elif len(signing_key.encode("utf-8")) < 32:
        errors.append("CRYPTO_SIGNING_KEY must be at least 256 bits (32 bytes).")
        record("crypto-signing-key", False, "CRYPTO_SIGNING_KEY is too short.")
    else:
        record("crypto-signing-key", True, "CRYPTO_SIGNING_KEY meets minimum length.")

    data_retention_schedule = str(effective_env.get("DATA_RETENTION_CRON_SCHEDULE", "") or "").strip()
    if not data_retention_schedule:
        errors.append("DATA_RETENTION_CRON_SCHEDULE is required in production.")
        record("data-retention-cron-schedule", False, "DATA_RETENTION_CRON_SCHEDULE missing.")
    else:
        record("data-retention-cron-schedule", True, "DATA_RETENTION_CRON_SCHEDULE is configured.")

    return {
        "valid": not errors,
        "environment": "production",
        "errors": errors,
        "checks": checks,
        "database_url": db_url,
        "sbc_api_key_present": bool(sbc_api_key),
        "sbc_endpoint": sbc_endpoint,
        "crypto_signing_key_present": bool(signing_key),
        "data_retention_cron_schedule": data_retention_schedule,
    }
