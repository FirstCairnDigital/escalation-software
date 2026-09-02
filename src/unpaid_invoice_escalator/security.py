from __future__ import annotations
#
# First Cairn Digital
# P26003 separate API credentials from actor identities

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from time import monotonic


ROLE_RANK = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


@dataclass(frozen=True)
class RequestDecision:
    allowed: bool
    status_code: int | None = None
    detail: str | None = None
    identity: str = "anonymous"
    role: str = "anonymous"
    client_id: str = "DEFAULT_CLIENT"


class ApiSecurityController:
    def __init__(
        self,
        *,
        enabled: bool,
        api_keys: dict[str, str],
        api_clients: dict[str, str] | None = None,
        api_identities: dict[str, str] | None = None,
        require_explicit_client_mapping: bool = False,
        require_explicit_identity_mapping: bool = False,
        rate_limit_per_minute: int,
        auth_failure_alert_threshold: int = 10,
        rate_limit_alert_threshold: int = 10,
        server_error_alert_threshold: int = 5,
        audit_log_limit: int = 200,
    ) -> None:
        self.enabled = enabled
        self.api_keys = api_keys
        self.api_clients = api_clients or {}
        self.api_identities = {
            str(key).strip(): str(value).strip()
            for key, value in (api_identities or {}).items()
            if str(key).strip() and str(value).strip()
        }
        self.require_explicit_client_mapping = require_explicit_client_mapping
        self.require_explicit_identity_mapping = require_explicit_identity_mapping
        self.rate_limit_per_minute = rate_limit_per_minute
        self.auth_failure_alert_threshold = auth_failure_alert_threshold
        self.rate_limit_alert_threshold = rate_limit_alert_threshold
        self.server_error_alert_threshold = server_error_alert_threshold
        self._request_timestamps: dict[str, deque[float]] = {}
        self._public_request_timestamps: dict[str, deque[float]] = {}
        self._request_count = 0
        self._status_counts: dict[str, int] = {}
        self._rate_limited_count = 0
        self._auth_fail_count = 0
        self._forbidden_count = 0
        self._server_error_count = 0
        self._upload_rejected_count = 0
        self._upload_quarantined_count = 0
        self._upload_rejections_by_reason: dict[str, int] = {}
        self._audit_events: deque[dict[str, object]] = deque(maxlen=max(1, audit_log_limit))
        self._last_alert: str | None = None
        self._active_alerts: set[str] = set()

    def is_public_path(self, path: str) -> bool:
        return path in ("/health", "/ready", "/verify", "/portal", "/portal/payment-link") or path.startswith("/portal/actions/")

    def _required_role(self, *, method: str, path: str) -> str:
        if path == "/metrics" or path.startswith("/deployment/"):
            return "admin"
        if method.upper() == "GET":
            return "viewer"
        return "operator"

    def _role_allows(self, *, actual: str, required: str) -> bool:
        return ROLE_RANK.get(actual, 0) >= ROLE_RANK.get(required, 99)

    def _safe_client_host_identity(self, client_host: str | None) -> str:
        host = (client_host or "").strip()
        return host or "anonymous"

    def _public_identity(self, client_host: str | None) -> str:
        host = (client_host or "").strip() or "unknown"
        return f"public:{host}"

    def _derived_actor_identity(self, api_key: str) -> str:
        digest = sha256(api_key.encode("utf-8")).hexdigest()[:16]
        return f"credential:{digest}"

    def _authenticated_identity(self, api_key: str) -> str:
        configured_identity = self.api_identities.get(api_key, "").strip()
        if configured_identity:
            return configured_identity
        return self._derived_actor_identity(api_key)

    def _non_production_identity(self, api_key: str | None, client_host: str | None) -> str:
        if api_key:
            return self._derived_actor_identity(api_key)
        return self._safe_client_host_identity(client_host)

    def evaluate_request(
        self,
        *,
        method: str,
        path: str,
        api_key: str | None,
        client_host: str | None,
    ) -> RequestDecision:
        if self.is_public_path(path):
            return RequestDecision(allowed=True, identity=self._public_identity(client_host), role="public")
        if not self.enabled:
            return RequestDecision(
                allowed=True,
                identity=self._non_production_identity(api_key, client_host),
                role="admin",
                client_id="DEFAULT_CLIENT",
            )

        role = self.api_keys.get(api_key or "")
        if role is None:
            identity = self._safe_client_host_identity(client_host)
            self._auth_fail_count += 1
            self._record_audit_event(
                event_type="AUTH_FAILURE",
                severity="WARN",
                method=method,
                path=path,
                identity=identity,
                detail="Missing or invalid API key.",
            )
            self._trigger_threshold_alert(
                metric_name="auth_failures_total",
                count=self._auth_fail_count,
                threshold=self.auth_failure_alert_threshold,
                detail="Authentication failure threshold reached.",
            )
            return RequestDecision(
                allowed=False,
                status_code=401,
                detail="Missing or invalid API key.",
                identity=identity,
                role="anonymous",
            )

        identity = self._authenticated_identity(api_key or "")
        configured_identity = self.api_identities.get(api_key or "", "").strip()
        if self.require_explicit_identity_mapping and not configured_identity:
            self._forbidden_count += 1
            self._record_audit_event(
                event_type="IDENTITY_MAPPING_FORBIDDEN",
                severity="ERROR",
                method=method,
                path=path,
                identity=identity,
                detail="Authenticated credential has no explicit actor identity mapping.",
            )
            return RequestDecision(
                allowed=False,
                status_code=403,
                detail="Authenticated credential is not mapped to an actor identity.",
                identity=identity,
                role=role,
                client_id="",
            )

        client_id = self.api_clients.get(api_key or "", "").strip()
        if self.require_explicit_client_mapping and not client_id:
            self._forbidden_count += 1
            self._record_audit_event(
                event_type="TENANT_MAPPING_FORBIDDEN",
                severity="ERROR",
                method=method,
                path=path,
                identity=identity,
                detail="Authenticated credential has no explicit client mapping.",
            )
            return RequestDecision(
                allowed=False,
                status_code=403,
                detail="Authenticated credential is not mapped to a client.",
                identity=identity,
                role=role,
                client_id="",
            )
        if not client_id:
            client_id = "DEFAULT_CLIENT"
        required_role = self._required_role(method=method, path=path)
        if not self._role_allows(actual=role, required=required_role):
            self._forbidden_count += 1
            self._record_audit_event(
                event_type="RBAC_FORBIDDEN",
                severity="WARN",
                method=method,
                path=path,
                identity=identity,
                detail=f"Role '{role}' lacks permission for required role '{required_role}'.",
            )
            return RequestDecision(
                allowed=False,
                status_code=403,
                detail=f"Insufficient role. Required: {required_role}.",
                identity=identity,
                role=role,
                client_id=client_id,
            )
        return RequestDecision(allowed=True, identity=identity, role=role, client_id=client_id)

    def check_rate_limit(self, identity: str) -> RequestDecision:
        now = monotonic()
        window_start = now - 60.0
        entries = self._request_timestamps.setdefault(identity, deque())
        while entries and entries[0] < window_start:
            entries.popleft()
        if len(entries) >= self.rate_limit_per_minute:
            self._rate_limited_count += 1
            self._record_audit_event(
                event_type="RATE_LIMIT_EXCEEDED",
                severity="WARN",
                method=None,
                path=None,
                identity=identity,
                detail="Rate limit exceeded.",
            )
            self._trigger_threshold_alert(
                metric_name="rate_limited_total",
                count=self._rate_limited_count,
                threshold=self.rate_limit_alert_threshold,
                detail="Rate limit threshold reached.",
            )
            return RequestDecision(
                allowed=False,
                status_code=429,
                detail="Rate limit exceeded. Retry after 60 seconds.",
                identity=identity,
            )
        entries.append(now)
        return RequestDecision(allowed=True, identity=identity)

    def public_bucket_key(self, *, client_host: str | None, path: str, case_id: str | None = None) -> str:
        host = (client_host or "unknown").strip() or "unknown"
        normalized_path = (path or "/").split("?", 1)[0].strip() or "/"
        case_ref = (case_id or "").strip()
        if case_ref:
            return f"public:{host}:{normalized_path}:case={case_ref}"
        return f"public:{host}:{normalized_path}"

    def check_public_rate_limit(
        self,
        *,
        client_host: str | None,
        path: str,
        case_id: str | None = None,
    ) -> RequestDecision:
        key = self.public_bucket_key(client_host=client_host, path=path, case_id=case_id)
        now = monotonic()
        window_start = now - 60.0
        entries = self._public_request_timestamps.setdefault(key, deque())
        while entries and entries[0] < window_start:
            entries.popleft()
        if len(entries) >= self.rate_limit_per_minute:
            self._rate_limited_count += 1
            identity = f"public:{client_host or 'unknown'}:{path}"
            self._record_audit_event(
                event_type="PUBLIC_RATE_LIMIT_EXCEEDED",
                severity="WARN",
                method=None,
                path=path,
                identity=identity,
                detail=(
                    "Public portal abuse protection triggered."
                    if case_id
                    else "Public endpoint rate limit exceeded."
                ),
            )
            self._trigger_threshold_alert(
                metric_name="rate_limited_total",
                count=self._rate_limited_count,
                threshold=self.rate_limit_alert_threshold,
                detail="Rate limit threshold reached.",
            )
            return RequestDecision(
                allowed=False,
                status_code=429,
                detail="Rate limit exceeded. Retry after 60 seconds.",
                identity=identity,
            )
        entries.append(now)
        return RequestDecision(allowed=True, identity=self._public_identity(client_host))

    def record_response(self, status_code: int) -> None:
        self._request_count += 1
        key = str(status_code)
        self._status_counts[key] = self._status_counts.get(key, 0) + 1
        if status_code >= 500:
            self._server_error_count += 1
            self._record_audit_event(
                event_type="SERVER_ERROR_RESPONSE",
                severity="ERROR",
                method=None,
                path=None,
                identity="system",
                detail=f"Server responded with status {status_code}.",
            )
            self._trigger_threshold_alert(
                metric_name="server_errors_total",
                count=self._server_error_count,
                threshold=self.server_error_alert_threshold,
                detail="Server error threshold reached.",
            )

    def record_upload_rejection(self, *, reason: str, quarantined: bool) -> None:
        self._upload_rejected_count += 1
        if quarantined:
            self._upload_quarantined_count += 1
        self._upload_rejections_by_reason[reason] = self._upload_rejections_by_reason.get(reason, 0) + 1
        self._record_audit_event(
            event_type="UPLOAD_REJECTED",
            severity="WARN",
            method=None,
            path=None,
            identity="system",
            detail=f"reason={reason} quarantined={quarantined}",
        )

    def _record_audit_event(
        self,
        *,
        event_type: str,
        severity: str,
        method: str | None,
        path: str | None,
        identity: str,
        detail: str,
    ) -> None:
        self._audit_events.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "severity": severity,
                "method": method,
                "path": path,
                "identity": identity,
                "detail": detail,
            }
        )

    def _trigger_threshold_alert(self, *, metric_name: str, count: int, threshold: int, detail: str) -> None:
        if threshold <= 0 or count < threshold:
            return
        self._active_alerts.add(metric_name)
        self._last_alert = detail
        self._record_audit_event(
            event_type="ALERT_THRESHOLD_REACHED",
            severity="ERROR",
            method=None,
            path=None,
            identity="system",
            detail=f"{detail} metric={metric_name} count={count} threshold={threshold}",
        )

    def metrics_snapshot(self) -> dict[str, object]:
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "security_enabled": self.enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "requests_total": self._request_count,
            "status_counts": dict(self._status_counts),
            "auth_failures_total": self._auth_fail_count,
            "forbidden_total": self._forbidden_count,
            "rate_limited_total": self._rate_limited_count,
            "server_errors_total": self._server_error_count,
            "upload_rejected_total": self._upload_rejected_count,
            "upload_quarantined_total": self._upload_quarantined_count,
            "upload_rejections_by_reason": dict(self._upload_rejections_by_reason),
            "alert_policy": {
                "auth_failure_alert_threshold": self.auth_failure_alert_threshold,
                "rate_limit_alert_threshold": self.rate_limit_alert_threshold,
                "server_error_alert_threshold": self.server_error_alert_threshold,
            },
            "active_alerts": sorted(self._active_alerts),
            "last_alert": self._last_alert,
            "recent_audit_events": list(self._audit_events),
        }
