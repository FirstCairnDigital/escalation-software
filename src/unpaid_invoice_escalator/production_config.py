from __future__ import annotations
#
# First Cairn Digital
# P26003 production configuration consolidation

import os
from typing import Any, Mapping


def _is_ssl_url(value: str) -> bool:
    lowered = value.lower()
    return "sslmode=require" in lowered or "ssl=true" in lowered or "ssl=1" in lowered or "?sslmode=verify-full" in lowered


def _csv_tokens(value: str) -> tuple[str, ...]:
    return tuple(token.strip() for token in value.split(",") if token.strip())


def _key_map(value: str) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for token in _csv_tokens(value):
        key, separator, role = token.partition(":")
        if not separator or not role.strip():
            raise ValueError("Key mappings must use the format name:value.")
        mapping[key.strip()] = role.strip()
    return mapping


def _env_value(env: Mapping[str, Any], primary: str, *aliases: str, default: str = "") -> tuple[str, str | None, bool]:
    for key in (primary, *aliases):
        if key not in env:
            continue
        raw = env.get(key)
        if raw is None:
            continue
        value = str(raw).strip()
        if value or key == primary or len((primary, *aliases)) == 1:
            return value, None if key == primary else key, key == primary
    return default, None, False


def resolve_runtime_config(
    env: Mapping[str, Any] | None = None,
    *,
    default_app_env: str = "development",
    auth_enabled: bool | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    effective_env = dict(env or os.environ)
    if database_url is not None:
        effective_env["DATABASE_URL"] = database_url

    app_env, _, _ = _env_value(effective_env, "FCD_APP_ENV", default=default_app_env)
    app_env = (app_env or default_app_env).strip() or default_app_env
    effective_auth_enabled = auth_enabled if auth_enabled is not None else app_env.lower() == "production"

    manifest_signing_key, signing_key_alias, primary_manifest_key = _env_value(
        effective_env,
        "FCD_MANIFEST_SIGNING_KEY",
        "CRYPTO_SIGNING_KEY",
        default="dev-only-signing-key",
    )
    manifest_key_id, _, _ = _env_value(effective_env, "FCD_MANIFEST_KEY_ID", default="fcd-local-key")
    manifest_verification_keys_raw, _, _ = _env_value(effective_env, "FCD_MANIFEST_VERIFY_KEYS")
    api_keys_raw, api_keys_alias, api_keys_primary = _env_value(effective_env, "FCD_API_KEYS", "SBC_API_KEY")
    rate_limit_raw, _, _ = _env_value(effective_env, "FCD_RATE_LIMIT_PER_MINUTE", default="120")
    auth_failure_raw, _, _ = _env_value(effective_env, "FCD_AUTH_FAILURE_ALERT_THRESHOLD", default="10")
    rate_limit_alert_raw, _, _ = _env_value(effective_env, "FCD_RATE_LIMIT_ALERT_THRESHOLD", default="10")
    server_error_alert_raw, _, _ = _env_value(effective_env, "FCD_SERVER_ERROR_ALERT_THRESHOLD", default="5")
    max_upload_raw, _, _ = _env_value(effective_env, "FCD_MAX_UPLOAD_BYTES", default="5242880")
    upload_types_raw, _, _ = _env_value(
        effective_env,
        "FCD_ALLOWED_UPLOAD_CONTENT_TYPES",
        default="application/pdf,text/plain,image/png,image/jpeg",
    )
    upload_extensions_raw, _, _ = _env_value(
        effective_env,
        "FCD_ALLOWED_UPLOAD_EXTENSIONS",
        default=".pdf,.txt,.png,.jpg,.jpeg",
    )
    quarantine_dir, _, _ = _env_value(effective_env, "FCD_QUARANTINE_DIR", default="data/quarantine")
    data_retention_days_raw, _, _ = _env_value(effective_env, "FCD_DATA_RETENTION_DAYS", default="2190")
    data_retention_cron_schedule, cron_alias, cron_primary = _env_value(
        effective_env,
        "FCD_DATA_RETENTION_CRON_SCHEDULE",
        "DATA_RETENTION_CRON_SCHEDULE",
    )
    database_url_value, _, _ = _env_value(effective_env, "DATABASE_URL")
    sbc_endpoint, _, _ = _env_value(effective_env, "SBC_ENDPOINT")

    def parse_positive_int(raw: str, *, field_name: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc
        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return value

    try:
        rate_limit_per_minute = parse_positive_int(rate_limit_raw, field_name="FCD_RATE_LIMIT_PER_MINUTE")
    except ValueError:
        rate_limit_per_minute = 0
    try:
        auth_failure_threshold = parse_positive_int(auth_failure_raw, field_name="FCD_AUTH_FAILURE_ALERT_THRESHOLD")
    except ValueError:
        auth_failure_threshold = 0
    try:
        rate_limit_alert_threshold = parse_positive_int(rate_limit_alert_raw, field_name="FCD_RATE_LIMIT_ALERT_THRESHOLD")
    except ValueError:
        rate_limit_alert_threshold = 0
    try:
        server_error_threshold = parse_positive_int(server_error_alert_raw, field_name="FCD_SERVER_ERROR_ALERT_THRESHOLD")
    except ValueError:
        server_error_threshold = 0
    try:
        max_upload_bytes = parse_positive_int(max_upload_raw, field_name="FCD_MAX_UPLOAD_BYTES")
    except ValueError:
        max_upload_bytes = 0
    try:
        data_retention_days = parse_positive_int(data_retention_days_raw, field_name="FCD_DATA_RETENTION_DAYS")
    except ValueError:
        data_retention_days = 0

    upload_content_types = tuple(token.lower() for token in _csv_tokens(upload_types_raw))
    upload_extensions = tuple(token.lower() for token in _csv_tokens(upload_extensions_raw))

    if manifest_verification_keys_raw:
        verification_keys = _key_map(manifest_verification_keys_raw)
    else:
        verification_keys = {}
        if manifest_key_id and manifest_signing_key:
            verification_keys[manifest_key_id] = manifest_signing_key

    if api_keys_raw:
        if api_keys_primary:
            api_keys = _key_map(api_keys_raw)
        else:
            api_keys = {"legacy-credential": api_keys_raw}
    else:
        api_keys = {}

    legacy_aliases: dict[str, str] = {}
    if str(effective_env.get("CRYPTO_SIGNING_KEY") or "").strip():
        legacy_aliases["manifest_signing_key"] = "CRYPTO_SIGNING_KEY"
    if str(effective_env.get("SBC_API_KEY") or "").strip():
        legacy_aliases["api_keys"] = "SBC_API_KEY"
    if str(effective_env.get("DATA_RETENTION_CRON_SCHEDULE") or "").strip():
        legacy_aliases["data_retention_cron_schedule"] = "DATA_RETENTION_CRON_SCHEDULE"
    if signing_key_alias is not None and not primary_manifest_key and not legacy_aliases.get("manifest_signing_key"):
        legacy_aliases["manifest_signing_key"] = signing_key_alias
    if api_keys_alias is not None and not api_keys_primary and not legacy_aliases.get("api_keys"):
        legacy_aliases["api_keys"] = api_keys_alias
    if cron_alias is not None and not cron_primary and not legacy_aliases.get("data_retention_cron_schedule"):
        legacy_aliases["data_retention_cron_schedule"] = cron_alias

    return {
        "app_env": app_env,
        "auth_enabled": effective_auth_enabled,
        "manifest_signing_key": manifest_signing_key,
        "manifest_key_id": manifest_key_id,
        "manifest_verification_keys": verification_keys,
        "api_keys": api_keys,
        "api_clients": {},
        "rate_limit_per_minute": rate_limit_per_minute,
        "auth_failure_alert_threshold": auth_failure_threshold,
        "rate_limit_alert_threshold": rate_limit_alert_threshold,
        "server_error_alert_threshold": server_error_threshold,
        "max_upload_bytes": max_upload_bytes,
        "allowed_upload_content_types": upload_content_types,
        "allowed_upload_extensions": upload_extensions,
        "quarantine_dir": quarantine_dir,
        "data_retention_days": data_retention_days,
        "data_retention_cron_schedule": data_retention_cron_schedule,
        "database_url": database_url_value or "",
        "sbc_endpoint": sbc_endpoint,
        "legacy_aliases": legacy_aliases,
    }


def validate_production_config(env: Mapping[str, Any] | None = None, *, auth_enabled: bool | None = None) -> dict[str, Any]:
    effective_env = dict(env or os.environ)
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, severity: str, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "severity": severity, "detail": detail})
        if passed:
            return
        if severity == "error":
            errors.append(detail)
        else:
            warnings.append(detail)

    runtime = resolve_runtime_config(effective_env, default_app_env="production", auth_enabled=auth_enabled)
    app_env = runtime["app_env"]
    manifest_signing_key = runtime["manifest_signing_key"]
    manifest_key_id = runtime["manifest_key_id"]
    verification_keys = runtime["manifest_verification_keys"]
    api_keys = runtime["api_keys"]
    rate_limit_per_minute = runtime["rate_limit_per_minute"]
    auth_failure_threshold = runtime["auth_failure_alert_threshold"]
    rate_limit_alert_threshold = runtime["rate_limit_alert_threshold"]
    server_error_threshold = runtime["server_error_alert_threshold"]
    max_upload_bytes = runtime["max_upload_bytes"]
    upload_types = runtime["allowed_upload_content_types"]
    upload_extensions = runtime["allowed_upload_extensions"]
    quarantine_dir = runtime["quarantine_dir"]
    data_retention_days = runtime["data_retention_days"]
    data_retention_cron_schedule = runtime["data_retention_cron_schedule"]
    database_url = runtime["database_url"]
    sbc_endpoint = runtime["sbc_endpoint"]
    legacy_aliases = runtime["legacy_aliases"]

    record(
        "environment",
        app_env.lower() == "production",
        "warning",
        "FCD_APP_ENV is not set to production; validating using production defaults."
        if app_env.lower() != "production"
        else "Production environment declared.",
    )
    record(
        "manifest-signing-key",
        manifest_signing_key != "dev-only-signing-key",
        "error",
        "FCD_MANIFEST_SIGNING_KEY must be configured with a non-default signing key."
        if manifest_signing_key == "dev-only-signing-key"
        else "Manifest signing key configured.",
    )
    if "manifest_signing_key" in legacy_aliases:
        record(
            "manifest-signing-key-legacy-alias",
            False,
            "warning",
            f"{legacy_aliases['manifest_signing_key']} was used as a legacy alias; migrate to FCD_MANIFEST_SIGNING_KEY.",
        )
    record(
        "manifest-key-id",
        bool(manifest_key_id),
        "error",
        "FCD_MANIFEST_KEY_ID is required." if not manifest_key_id else "Manifest key ID configured.",
    )
    if verification_keys:
        record("manifest-verification-keys", True, "warning", "Manifest verification key ring configured.")
    else:
        record(
            "manifest-verification-keys",
            False,
            "warning",
            "No explicit FCD_MANIFEST_VERIFY_KEYS configured; active signing key will be the only verifier.",
        )
    record(
        "api-keys-configured",
        bool(api_keys),
        "error",
        "API keys configured for secured mode." if api_keys else "FCD_API_KEYS is required for secured production operation.",
    )
    if "api_keys" in legacy_aliases:
        record(
            "api-keys-configured-legacy-alias",
            False,
            "warning",
            f"{legacy_aliases['api_keys']} is present, but production API auth should migrate to FCD_API_KEYS.",
        )

    for check_name, env_name, raw_value, severity in (
        ("rate-limit-per-minute", "FCD_RATE_LIMIT_PER_MINUTE", rate_limit_per_minute, "error"),
        ("auth-failure-alert-threshold", "FCD_AUTH_FAILURE_ALERT_THRESHOLD", auth_failure_threshold, "warning"),
        ("rate-limit-alert-threshold", "FCD_RATE_LIMIT_ALERT_THRESHOLD", rate_limit_alert_threshold, "warning"),
        ("server-error-alert-threshold", "FCD_SERVER_ERROR_ALERT_THRESHOLD", server_error_threshold, "warning"),
        ("max-upload-bytes", "FCD_MAX_UPLOAD_BYTES", max_upload_bytes, "error"),
        ("data-retention-days", "FCD_DATA_RETENTION_DAYS", data_retention_days, "error"),
    ):
        record(check_name, raw_value > 0, severity, f"{env_name} set to {raw_value}.")

    record(
        "allowed-upload-content-types",
        len(upload_types) > 0,
        "error",
        "FCD_ALLOWED_UPLOAD_CONTENT_TYPES must contain at least one MIME type."
        if not upload_types
        else "Allowed upload content types configured.",
    )
    record(
        "allowed-upload-extensions",
        len(upload_extensions) > 0,
        "error",
        "FCD_ALLOWED_UPLOAD_EXTENSIONS must contain at least one extension."
        if not upload_extensions
        else "Allowed upload extensions configured.",
    )
    record(
        "quarantine-dir",
        bool(quarantine_dir),
        "error",
        "FCD_QUARANTINE_DIR is required." if not quarantine_dir else "Quarantine directory configured.",
    )
    record(
        "data-retention-cron-schedule",
        bool(data_retention_cron_schedule),
        "error",
        "FCD_DATA_RETENTION_CRON_SCHEDULE is required."
        if not data_retention_cron_schedule
        else "Retention scheduler cron is configured.",
    )
    if "data_retention_cron_schedule" in legacy_aliases:
        record(
            "data-retention-cron-schedule-legacy-alias",
            False,
            "warning",
            f"{legacy_aliases['data_retention_cron_schedule']} was used as a legacy alias; migrate to FCD_DATA_RETENTION_CRON_SCHEDULE.",
        )
    if database_url:
        database_tls_ok = _is_ssl_url(database_url)
        record(
            "database-url",
            database_tls_ok,
            "warning",
            "DATABASE_URL is configured with TLS/SSL." if database_tls_ok else "DATABASE_URL is present but does not enforce TLS/SSL.",
        )
    if sbc_endpoint:
        record(
            "sbc-endpoint",
            sbc_endpoint.startswith(("http://", "https://")),
            "warning",
            "SBC_ENDPOINT is configured." if sbc_endpoint.startswith(("http://", "https://")) else "SBC_ENDPOINT must be a valid HTTP(S) URL.",
        )

    return {
        "valid": not errors,
        "environment": app_env,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "auth_enabled": runtime["auth_enabled"],
        "manifest_key_id": manifest_key_id,
        "verification_key_ids": sorted(verification_keys.keys()),
        "rate_limit_per_minute": rate_limit_per_minute,
        "max_upload_bytes": max_upload_bytes,
        "allowed_upload_content_types": list(upload_types),
        "allowed_upload_extensions": list(upload_extensions),
        "quarantine_dir": quarantine_dir,
        "data_retention_days": data_retention_days,
        "data_retention_cron_schedule": data_retention_cron_schedule,
        "database_url": database_url,
        "sbc_api_key_present": bool(api_keys),
        "sbc_endpoint": sbc_endpoint,
        "crypto_signing_key_present": bool(manifest_signing_key),
    }
