from __future__ import annotations

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


def _env_value(env: Mapping[str, Any], primary: str, *aliases: str, default: str = "") -> tuple[str, str | None]:
    for key in (primary, *aliases):
        raw = env.get(key)
        value = str(raw or "").strip()
        if value:
            return value, None if key == primary else key
    return default, None


def validate_production_config(env: Mapping[str, Any] | None = None) -> dict[str, Any]:
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

    app_env, _ = _env_value(effective_env, "FCD_APP_ENV", default="production")
    manifest_signing_key, signing_key_alias = _env_value(
        effective_env,
        "FCD_MANIFEST_SIGNING_KEY",
        "CRYPTO_SIGNING_KEY",
        default="dev-only-signing-key",
    )
    manifest_key_id, _ = _env_value(effective_env, "FCD_MANIFEST_KEY_ID", default="fcd-local-key")
    manifest_verify_keys, _ = _env_value(effective_env, "FCD_MANIFEST_VERIFY_KEYS")
    api_keys_raw, api_keys_alias = _env_value(effective_env, "FCD_API_KEYS", "SBC_API_KEY")
    rate_limit_raw, _ = _env_value(effective_env, "FCD_RATE_LIMIT_PER_MINUTE", default="120")
    auth_failure_raw, _ = _env_value(effective_env, "FCD_AUTH_FAILURE_ALERT_THRESHOLD", default="10")
    rate_limit_alert_raw, _ = _env_value(effective_env, "FCD_RATE_LIMIT_ALERT_THRESHOLD", default="10")
    server_error_alert_raw, _ = _env_value(effective_env, "FCD_SERVER_ERROR_ALERT_THRESHOLD", default="5")
    max_upload_raw, _ = _env_value(effective_env, "FCD_MAX_UPLOAD_BYTES", default="5242880")
    upload_types_raw, _ = _env_value(
        effective_env,
        "FCD_ALLOWED_UPLOAD_CONTENT_TYPES",
        default="application/pdf,text/plain,image/png,image/jpeg",
    )
    upload_extensions_raw, _ = _env_value(
        effective_env,
        "FCD_ALLOWED_UPLOAD_EXTENSIONS",
        default=".pdf,.txt,.png,.jpg,.jpeg",
    )
    quarantine_dir, _ = _env_value(effective_env, "FCD_QUARANTINE_DIR", default="data/quarantine")
    data_retention_days_raw, _ = _env_value(effective_env, "FCD_DATA_RETENTION_DAYS", default="2190")
    data_retention_cron_schedule, cron_alias = _env_value(
        effective_env,
        "FCD_DATA_RETENTION_CRON_SCHEDULE",
        "DATA_RETENTION_CRON_SCHEDULE",
    )
    database_url, _ = _env_value(effective_env, "DATABASE_URL")
    sbc_endpoint, _ = _env_value(effective_env, "SBC_ENDPOINT")

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
    if signing_key_alias is not None:
        record(
            "manifest-signing-key-legacy-alias",
            False,
            "warning",
            f"{signing_key_alias} was used as a legacy alias; migrate to FCD_MANIFEST_SIGNING_KEY.",
        )
    record(
        "manifest-key-id",
        bool(manifest_key_id),
        "error",
        "FCD_MANIFEST_KEY_ID is required."
        if not manifest_key_id
        else "Manifest key ID configured.",
    )
    if manifest_verify_keys:
        try:
            verification_keys = _key_map(manifest_verify_keys)
        except ValueError as exc:
            verification_keys = {}
            record("manifest-verification-keys", False, "error", f"FCD_MANIFEST_VERIFY_KEYS invalid: {exc}")
        else:
            record("manifest-verification-keys", True, "warning", "Manifest verification key ring configured.")
    else:
        verification_keys = {manifest_key_id: manifest_signing_key} if manifest_key_id and manifest_signing_key else {}
        record(
            "manifest-verification-keys",
            bool(verification_keys),
            "warning",
            "No explicit FCD_MANIFEST_VERIFY_KEYS configured; active signing key will be the only verifier."
            if verification_keys
            else "Manifest verification keys are unavailable.",
        )
    if api_keys_raw:
        if api_keys_alias is None:
            try:
                api_keys = _key_map(api_keys_raw)
            except ValueError as exc:
                api_keys = {}
                record("api-keys-configured", False, "error", f"FCD_API_KEYS invalid: {exc}")
            else:
                record("api-keys-configured", True, "error", "API keys configured for secured mode.")
        else:
            api_keys = {"legacy-credential": api_keys_raw}
            record(
                "api-keys-configured",
                True,
                "warning",
                f"{api_keys_alias} is present, but production API auth should migrate to FCD_API_KEYS.",
            )
    else:
        api_keys = {}
        record("api-keys-configured", False, "error", "FCD_API_KEYS is required for secured production operation.")

    def parse_positive_int(raw: str, *, field_name: str) -> int:
        try:
            value = int(raw)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer.") from exc
        if value <= 0:
            raise ValueError(f"{field_name} must be greater than zero.")
        return value

    parsed_values: dict[str, int] = {}
    for check_name, env_name, raw_value, severity in (
        ("rate-limit-per-minute", "FCD_RATE_LIMIT_PER_MINUTE", rate_limit_raw, "error"),
        ("auth-failure-alert-threshold", "FCD_AUTH_FAILURE_ALERT_THRESHOLD", auth_failure_raw, "warning"),
        ("rate-limit-alert-threshold", "FCD_RATE_LIMIT_ALERT_THRESHOLD", rate_limit_alert_raw, "warning"),
        ("server-error-alert-threshold", "FCD_SERVER_ERROR_ALERT_THRESHOLD", server_error_alert_raw, "warning"),
        ("max-upload-bytes", "FCD_MAX_UPLOAD_BYTES", max_upload_raw, "error"),
        ("data-retention-days", "FCD_DATA_RETENTION_DAYS", data_retention_days_raw, "error"),
    ):
        try:
            parsed_values[check_name] = parse_positive_int(raw_value, field_name=env_name)
        except ValueError as exc:
            record(check_name, False, severity, str(exc))
        else:
            record(check_name, True, severity, f"{env_name} set to {parsed_values[check_name]}.")

    upload_types = _csv_tokens(upload_types_raw)
    record(
        "allowed-upload-content-types",
        len(upload_types) > 0,
        "error",
        "FCD_ALLOWED_UPLOAD_CONTENT_TYPES must contain at least one MIME type."
        if not upload_types
        else "Allowed upload content types configured.",
    )
    upload_extensions = tuple(token.lower() for token in _csv_tokens(upload_extensions_raw))
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
        "FCD_QUARANTINE_DIR is required."
        if not quarantine_dir
        else "Quarantine directory configured.",
    )
    record(
        "data-retention-cron-schedule",
        bool(data_retention_cron_schedule),
        "error",
        "FCD_DATA_RETENTION_CRON_SCHEDULE is required."
        if not data_retention_cron_schedule
        else "Retention scheduler cron is configured.",
    )
    if cron_alias is not None:
        record(
            "data-retention-cron-schedule-legacy-alias",
            False,
            "warning",
            f"{cron_alias} was used as a legacy alias; migrate to FCD_DATA_RETENTION_CRON_SCHEDULE.",
        )

    if database_url:
        record(
            "database-url",
            _is_ssl_url(database_url),
            "warning",
            "DATABASE_URL is configured with TLS/SSL."
            if _is_ssl_url(database_url)
            else "DATABASE_URL is present but does not enforce TLS/SSL.",
        )
    if sbc_endpoint:
        record(
            "sbc-endpoint",
            sbc_endpoint.startswith(("http://", "https://")),
            "warning",
            "SBC_ENDPOINT is configured."
            if sbc_endpoint.startswith(("http://", "https://"))
            else "SBC_ENDPOINT must be a valid HTTP(S) URL.",
        )

    return {
        "valid": not errors,
        "environment": app_env,
        "errors": errors,
        "warnings": warnings,
        "checks": checks,
        "auth_enabled": True,
        "manifest_key_id": manifest_key_id,
        "verification_key_ids": sorted(verification_keys.keys()),
        "rate_limit_per_minute": parsed_values.get("rate-limit-per-minute", 0),
        "max_upload_bytes": parsed_values.get("max-upload-bytes", 0),
        "allowed_upload_content_types": list(upload_types),
        "allowed_upload_extensions": list(upload_extensions),
        "quarantine_dir": quarantine_dir,
        "data_retention_days": parsed_values.get("data-retention-days", 0),
        "data_retention_cron_schedule": data_retention_cron_schedule,
        "database_url": database_url,
        "sbc_api_key_present": bool(api_keys_raw),
        "sbc_endpoint": sbc_endpoint,
        "crypto_signing_key_present": bool(manifest_signing_key),
    }
